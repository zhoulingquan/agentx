# Power Banana Scenario-Agnostic Runtime Contract Design

Status: Accepted Supplement
Current authority: `docs/powerbanana-current-design.md`
Date: 2026-06-13

## Goal

Fill the remaining design gaps before implementation work begins on the scenario-agnostic enterprise agent runtime.

This supplement makes the platform contracts explicit enough that a later implementation plan can build the runtime in one coherent pass instead of discovering object shapes, states, and governance rules while coding.

The design completes six areas:

1. Runtime kernel records and refs.
2. Scenario Pack normative schema.
3. Evaluation Contract normative schema.
4. Data-analysis reference prototype boundaries.
5. First production scenario selection gates.
6. Registry, permission, error, recovery, and observability contracts.

## Positioning

Power Banana is a multi-application enterprise agent runtime. It is not currently selecting a first production scenario.

The existing data-analysis path is a reference prototype. It validates the runtime skeleton, but it does not define the platform's product scope.

This document is design-only. It does not require immediate changes to `powerbanana/`, tests, or runtime behavior.

## Design Approach

### Recommended: Contract Completion Before Implementation

Complete the runtime contracts, schema rules, registry model, and scenario selection gates before writing the next implementation pass.

This is the accepted approach because the implementation now needs stable boundaries more than additional prototype behavior.

### Rejected: Pick A Scenario And Implement Around It

Choosing contract review, ticket triage, finance review, or data analysis now would make the runtime look complete while hiding scenario-specific assumptions in the kernel.

### Rejected: Build Trunk Scheduling First

Multi-Bunch scheduling is useful later, but it depends on stable Bunch identity, checkpoints, events, permissions, and replay.

## Contract Families

The runtime should treat these as first-class contract families:

| Contract Family | Purpose | Initial Owner |
|---|---|---|
| Runtime Kernel Contract | Defines records, refs, lifecycle, event, context, checkpoint, and audit surfaces. | Platform runtime governance |
| Scenario Pack | Declares one bounded business workflow without executable code. | Scenario governance |
| Evaluation Contract | Declares checks, evaluators, baseline coverage, and gate actions. | Evaluation governance |
| Component Registry | Declares Sub-Agents, Skills, Tools, Evaluators, artifact schemas, and vocabularies. | Platform runtime governance |
| Reference Fixture Contract | Preserves prototype behavior as regression coverage without making it product scope. | Platform runtime governance |
| Scenario Selection Record | Captures why a candidate scenario can become the first enabled production scenario. | Product and scenario governance |

Each contract should include:

- `schema_version`
- stable id
- semantic version where applicable
- owner
- status
- created timestamp
- updated timestamp
- compatibility notes
- validation or lint result refs

## Ref Grammar

Runtime records should use stable refs rather than raw object embedding.

| Ref Kind | Format | Meaning |
|---|---|---|
| Banana Bunch | `bunch://<banana_bunch_id>` | Runtime identity for one business task run. |
| Trunk Blackboard | `trunk-blackboard://<record_kind>/<record_id>` | Global coordination metadata. |
| Bunch Blackboard | `bunch-blackboard://<banana_bunch_id>/<record_kind>/<record_id>` | Bunch-scoped evidence, events, artifacts, gates, and evaluations. |
| Artifact | `artifact://<banana_bunch_id>/<artifact_id>/<version>` | Versioned material output. |
| Evaluation | `evaluation://<banana_bunch_id>/<evaluation_id>` | Evaluation result record. |
| Human Gate | `human-gate://<banana_bunch_id>/<gate_id>` | User or reviewer decision point. |
| Checkpoint | `checkpoint://<banana_bunch_id>/<checkpoint_id>` | Continuity record written by the Checkpoint Writer. |
| Scenario Pack | `scenario://<scenario_id>@<scenario_version>` | Scenario declaration. |
| Evaluation Contract | `evaluation-contract://<contract_id>@<contract_version>` | Evaluation policy declaration. |
| Skill | `skill://<skill_id>@<skill_version>` | Registered skill implementation. |
| Tool | `tool://<tool_id>@<policy_version>` | Registered tool policy. |
| Actor | `actor://<tenant_id>/<actor_id>` | User, system component, or service actor. |
| Tenant | `tenant://<tenant_id>` | Enterprise boundary. |

Refs must not encode raw business data. If a consumer needs the data, it must resolve the ref through the owning API and permission policy.

## Shared Record Metadata

Every durable runtime record should include:

```yaml
record_metadata:
  schema_version: 0.1.0
  record_id: record_001
  record_type: bunch_artifact
  tenant_id: tenant_default
  banana_bunch_id: banana_bunch_001
  actor_id: actor://tenant_default/system/runtime
  correlation_id: corr_001
  causation_id: event_001
  visibility: bunch_private
  created_at: 2026-06-13T00:00:00Z
  updated_at: 2026-06-13T00:00:00Z
```

Required metadata rules:

- `schema_version` is required for all durable records.
- `tenant_id` is required even in single-tenant local mode.
- `banana_bunch_id` is required for Bunch-owned records and omitted only for pure Trunk records.
- `actor_id` identifies the component or user that created the record.
- `correlation_id` groups records from one user request or resumed action.
- `causation_id` points to the event, gate, or task that caused the write when available.
- `visibility` is one of `trunk_status`, `bunch_private`, `cross_bunch_summary`, `audit_only`, or `public_report`.

## Banana Bunch Identity Contract

A Banana Bunch is the stable runtime identity for one business task run.

```yaml
banana_bunch_identity:
  schema_version: 0.1.0
  banana_bunch_id: banana_bunch_001
  tenant_id: tenant_default
  created_by: actor://tenant_default/user_001
  created_from:
    user_request_ref: bunch-blackboard://banana_bunch_001/requests/request_001
    parent_bunch_ref: null
  scenario_binding:
    state: unbound
    scenario_ref: null
    evaluation_contract_ref: null
    bound_at: null
    bound_by: null
  lifecycle_state: created
  priority: normal
  resource_locks: []
  legacy_refs:
    task_id: task_001
```

Binding rules:

- New Bunches start with `scenario_binding.state: unbound`.
- A Bunch may bind to a `reference` Scenario Pack only in test, calibration, replay, or explicit developer mode.
- A production Bunch may bind only to an `enabled` Scenario Pack.
- Once execution starts, scenario binding is immutable. Changing scenario requires a new Bunch or a new attempt record.

## Lifecycle Contract

Allowed lifecycle states:

| State | Meaning | Writable Business Artifacts |
|---|---|---|
| `created` | Bunch identity exists, no scenario binding yet. | No |
| `planning` | Scenario routing and candidate plan are in progress. | Planner traces only |
| `planner_blocked` | Planner or scenario lint blocked execution. | No |
| `ready` | Plan is frozen and waiting for scheduler permission. | No |
| `running` | One or more plan nodes are executing. | Yes |
| `waiting_for_human` | A Human Gate must be answered. | No new business artifacts except gate records |
| `paused` | Runtime checkpointed and stopped at a safe boundary. | No |
| `partial` | A partial report was returned with limitations. | Read-only except audit metadata |
| `completed` | Final evaluated report exists. | Read-only except audit metadata |
| `blocked` | Execution stopped by evaluation or policy. | Read-only except audit metadata |
| `failed` | Runtime/system failure stopped execution. | Read-only except audit metadata |
| `cancelled` | User or Trunk cancelled execution. | Read-only except audit metadata |

Transition rules:

- `created -> planning -> ready -> running` is the normal path.
- `planning -> planner_blocked` is terminal for that attempt.
- `running -> waiting_for_human -> running` is allowed when a gate resolves.
- `running -> paused -> ready` is allowed only from checkpoint-safe boundaries.
- Terminal states cannot transition back to active execution.
- Retrying from a terminal state creates a new attempt record or a new Bunch derived from the original.

## Event Contract

Events are control-plane records. They carry refs and small metadata, not raw evidence.

```yaml
runtime_event:
  schema_version: 0.1.0
  event_id: event_001
  event_type: bunch.plan_frozen
  tenant_id: tenant_default
  source_ref: bunch://banana_bunch_001
  target_ref: trunk-blackboard://schedule/scheduler
  banana_bunch_id: banana_bunch_001
  correlation_id: corr_001
  causation_id: event_000
  idempotency_key: banana_bunch_001:plan_frozen:plan_001
  payload:
    plan_ref: bunch-blackboard://banana_bunch_001/plans/plan_001
    scenario_ref: scenario://example_business_scenario@0.1.0
  created_at: 2026-06-13T00:00:00Z
```

Rules:

- Event ids are globally unique within a tenant.
- Handlers must be idempotent by `idempotency_key`.
- Event ordering is guaranteed only within one Banana Bunch.
- Rejected events produce `runtime_event_rejection` records with reason and current lifecycle state.

## Blackboard Record Contract

Banana Bunch Blackboard is the source of truth for Bunch-scoped evidence.

```yaml
blackboard_record:
  schema_version: 0.1.0
  record_id: bb_entry_001
  banana_bunch_id: banana_bunch_001
  record_kind: structured_entry
  actor_id: actor://tenant_default/system/data_profile_agent
  target_ref: bunch-blackboard://banana_bunch_001/entries/data_profile_001
  payload_schema: data_profile.v0.1
  payload_ref: artifact://banana_bunch_001/data_profile/1
  visibility: bunch_private
  created_at: 2026-06-13T00:00:00Z
```

Allowed record kinds:

- `request`
- `planner_trace`
- `candidate_plan`
- `frozen_plan`
- `event`
- `structured_entry`
- `artifact`
- `evaluation`
- `human_gate`
- `tool_call`
- `vocabulary_suggestion`
- `checkpoint_ref`
- `final_report`

Rules:

- Records are append-only.
- Material business claims must be represented as artifacts or structured entries.
- Final reports must cite evaluated artifact refs.
- A Blackboard record may point to payload content, but it must not hide business evidence inside opaque logs.

## Artifact Contract

Artifacts are versioned material outputs written by runtime components, Sub-Agents, Skills, or report assembly.

```yaml
artifact_record:
  schema_version: 0.1.0
  artifact_id: artifact_001
  artifact_type: scenario_result
  artifact_version: 1
  banana_bunch_id: banana_bunch_001
  producer_ref: skill://scenario_task_execute@0.1.0
  source_refs:
    - bunch-blackboard://banana_bunch_001/entries/input_snapshot_001
  content_ref: bunch-blackboard://banana_bunch_001/artifact_payloads/artifact_001_v1
  content_schema: scenario_result.v0.1
  evaluation_refs: []
  status: draft
  created_at: 2026-06-13T00:00:00Z
```

Artifact statuses:

- `draft`
- `evaluating`
- `accepted`
- `accepted_with_warning`
- `rejected`
- `superseded`

Rules:

- Artifact versions are immutable.
- A rejected artifact cannot be cited by a final report as supporting evidence.
- Superseding creates a new version and preserves the old one.
- Evaluation may attach refs to an artifact but must not mutate the artifact payload.

## Human Gate Contract

Human Gates are decision records, not free-form chats.

```yaml
human_gate:
  schema_version: 0.1.0
  gate_id: gate_001
  banana_bunch_id: banana_bunch_001
  gate_type: needs_clarification
  reason: missing_required_input
  prompt: "Please choose which input source should be used."
  required_actor_role: end_user
  related_refs:
    - bunch-blackboard://banana_bunch_001/planner_traces/planner_trace_001
  allowed_responses:
    - provide_missing_input
    - cancel_bunch
  status: open
  opened_at: 2026-06-13T00:00:00Z
  resolved_at: null
  resolution_ref: null
```

Gate statuses:

- `open`
- `answered`
- `approved`
- `rejected`
- `expired`
- `cancelled`

Rules:

- Gate answers create decision refs.
- Gate answers do not directly mutate artifacts, scenarios, contracts, or checkpoints.
- `human_review` gates require an accountable reviewer role, not just the requesting user.

## Checkpoint Contract

Checkpoints store continuity state only.

```yaml
banana_bunch_checkpoint:
  schema_version: 0.1.0
  checkpoint_id: checkpoint_001
  banana_bunch_id: banana_bunch_001
  lifecycle_state: waiting_for_human
  current_phase: human_gate
  scenario_ref: scenario://example_business_scenario@0.1.0
  evaluation_contract_ref: evaluation-contract://example_business_scenario_eval@0.1.0
  latest_event_ref: bunch-blackboard://banana_bunch_001/events/event_010
  latest_plan_ref: bunch-blackboard://banana_bunch_001/plans/plan_001
  latest_report_ref: null
  pending_human_gate_refs:
    - human-gate://banana_bunch_001/gate_001
  evaluation_refs:
    - evaluation://banana_bunch_001/eval_001
  next_action: wait_for_human
  created_at: 2026-06-13T00:00:00Z
```

Rules:

- Only the Checkpoint Writer writes checkpoint records.
- Checkpoints contain refs and lifecycle metadata only.
- Checkpoints must not contain raw input rows, tool output, hidden model reasoning, or unreviewed business claims.
- Resume uses the latest valid checkpoint and then resolves cited refs through normal APIs.

## Context Bundle Contract

Context Bundles are trust-labeled read bundles assembled for Planner, Sub-Agent, Skill, Evaluator, or report assembly calls.

```yaml
context_bundle:
  schema_version: 0.1.0
  context_id: context_001
  banana_bunch_id: banana_bunch_001
  target_component_ref: skill://scenario_task_execute@0.1.0
  purpose: execute_scenario_task
  trust_labels:
    user_instruction: untrusted_instruction
    uploaded_input: untrusted_data
    scenario_pack: trusted_policy
    evaluation_contract: trusted_policy
    memory: continuity_hint
  included_refs:
    - scenario://example_business_scenario@0.1.0
    - evaluation-contract://example_business_scenario_eval@0.1.0
    - bunch-blackboard://banana_bunch_001/entries/input_snapshot_001
  excluded_refs:
    - bunch-blackboard://banana_bunch_001/private/hidden_reasoning
  created_at: 2026-06-13T00:00:00Z
```

Rules:

- User instructions, uploaded files, and LLM outputs are never trusted policy.
- Scenario Packs and Evaluation Contracts are trusted only after schema validation and lint.
- Memory is a continuity hint and cannot override Blackboard evidence, Evaluation results, Human Gates, or Checkpoints.

## Scenario Pack Normative Schema

Scenario Packs declare business boundaries. They do not contain arbitrary executable code.

Required top-level fields:

| Field | Requirement |
|---|---|
| `schema_version` | Scenario Pack schema version. |
| `scenario_id` | Stable `snake_case` id. |
| `scenario_version` | Semantic version. |
| `status` | One of the allowed statuses below. |
| `display_name` | Human-readable name. |
| `purpose` | One bounded business workflow. |
| `ownership` | Business owner, technical owner, reviewer roles. |
| `task_classification` | Supported task types, planner intents, rejection intents. |
| `input_contract` | Input types, shapes, required evidence, max files, size limits. |
| `output_contract` | Artifact types and final report shape. |
| `evaluation_contract_ref` | Required for `candidate`, `reference`, `enabled`, and `deprecated`. |
| `allowed_components` | Sub-Agents, Skills, Tools, Evaluators, artifact schemas, vocabularies. |
| `execution_policy` | Concurrency, retry, timeout, checkpoint, partial-result rules. |
| `security_policy` | Data sensitivity, network, write, tenant, and cross-Bunch restrictions. |
| `human_gate_policy` | Required gate reasons and accountable actor roles. |
| `test_policy` | Golden, negative, calibration, replay, and lint test refs. |
| `observability_policy` | Required traces, audit records, metrics, and retention class. |

Allowed statuses:

| Status | Meaning | Planner Selectable |
|---|---|---|
| `draft` | Editable, incomplete, not runnable. | No |
| `candidate` | Runnable only in tests, calibration, replay, or explicit developer mode. | No |
| `reference` | Stable fixture used to validate runtime behavior, not product scope. | No |
| `enabled` | May be selected for new production Banana Bunches. | Yes |
| `deprecated` | Existing Bunches may continue; new Bunches should not select it. | No |
| `disabled` | Not runnable. | No |

Allowed transitions:

```text
draft -> candidate
candidate -> reference
candidate -> enabled
reference -> candidate
enabled -> deprecated
enabled -> disabled
deprecated -> disabled
disabled -> candidate
```

Transition rules:

- `reference -> enabled` is not allowed directly. A reference fixture must return to `candidate` and pass production promotion gates first.
- `disabled -> candidate` requires a new scenario version or explicit governance approval.
- Existing Bunches keep the scenario version pinned at creation time.

## Scenario Pack Lint Rules

Lint must fail when:

- `scenario_id` is not `snake_case`.
- `scenario_version` is not semantic version.
- `status` is not one of the allowed statuses.
- `ownership.business_owner` is missing for `enabled`.
- `evaluation_contract_ref` is missing for any runnable status.
- Referenced Evaluation Contract does not apply to the Scenario Pack version.
- A referenced Sub-Agent, Skill, Tool, Evaluator, artifact schema, vocabulary, or test suite is unknown.
- A version range is invalid or cannot be satisfied.
- `final_report_policy.require_artifact_refs` is not `true`.
- `human_gate_policy` lacks reasons for clarification, human review, or policy-changing flows.
- `security_policy` allows external write-back without an explicit Human Gate and tool policy.
- `execution_policy.concurrency` is not `serial` in the initial runtime implementation.
- `reference` status has `planner_selectable: true`.
- `enabled` status relies only on reference fixture tests and lacks production ownership and scenario selection records.

Canonical lint error ids:

| Error Id | Meaning |
|---|---|
| `SCENARIO_INVALID_ID` | Scenario id is not stable `snake_case`. |
| `SCENARIO_INVALID_STATUS` | Status is not allowed. |
| `SCENARIO_MISSING_OWNER` | Enabled scenario lacks accountable owner. |
| `SCENARIO_MISSING_CONTRACT` | Runnable scenario lacks Evaluation Contract. |
| `SCENARIO_CONTRACT_MISMATCH` | Evaluation Contract does not apply to Scenario Pack. |
| `SCENARIO_UNKNOWN_COMPONENT` | Referenced component is not registered. |
| `SCENARIO_UNSAFE_TOOL_POLICY` | Tool policy exceeds allowed risk without gate. |
| `SCENARIO_REFERENCE_SELECTABLE` | Reference fixture is exposed to production Planner. |
| `SCENARIO_MISSING_TESTS` | Required test suites are missing. |

## Evaluation Contract Normative Schema

Evaluation Contracts declare trust boundaries.

Required top-level fields:

| Field | Requirement |
|---|---|
| `schema_version` | Evaluation Contract schema version. |
| `contract_id` | Stable `snake_case` id. |
| `contract_version` | Semantic version. |
| `status` | `draft`, `candidate`, `reference`, `enabled`, `deprecated`, or `disabled`. |
| `applies_to` | Scenario id and compatible version range. |
| `baseline_coverage` | Required baseline check ids. |
| `allowed_gate_actions` | Gate actions this contract may emit. |
| `default_gate_action` | Used when a check fails without a specific action. |
| `checks` | Ordered stage checks. |
| `aggregation_policy` | How check outcomes combine into one gate action. |
| `final_report_requirements` | Required citations, limitations, warnings, and source summaries. |
| `evaluator_refs` | Registered evaluators and compatible versions. |

Allowed gate actions:

| Gate Action | Meaning |
|---|---|
| `pass` | Continue normally. |
| `pass_with_warning` | Continue and preserve warning in artifacts and report. |
| `needs_more_evidence` | Pause execution until additional evidence is produced or supplied. |
| `needs_clarification` | Pause for user clarification. |
| `human_review` | Pause for accountable reviewer decision. |
| `return_partial` | Return partial report with limitations. |
| `block` | Stop execution and report blocking reasons. |

Gate action precedence:

```text
block
> human_review
> needs_clarification
> needs_more_evidence
> return_partial
> pass_with_warning
> pass
```

Required stages:

- `planner`
- `input`
- `artifact`
- `final_report`

Optional stages:

- `tool_call`
- `security`
- `human_gate`
- `replay`

Baseline checks:

| Check | Required Stage | Required For |
|---|---|---|
| `planner_intent_consistency` | `planner` | All enabled scenarios |
| `scenario_contract_match` | `planner` | All enabled scenarios |
| `input_snapshot_presence` | `input` | All enabled scenarios |
| `required_evidence_availability` | `input` | All enabled scenarios |
| `artifact_reference_coverage` | `artifact` | All enabled scenarios |
| `artifact_correctness` | `artifact` | Scenarios that produce derived outputs |
| `context_security` | `security` or `artifact` | All scenarios using untrusted input |
| `final_report_support` | `final_report` | All enabled scenarios |
| `limitation_disclosure` | `final_report` | All enabled scenarios |

## Evaluation Contract Lint Rules

Lint must fail when:

- `contract_id` is not `snake_case`.
- `contract_version` is not semantic version.
- `applies_to.scenario_id` does not match the Scenario Pack.
- Required baseline checks are missing.
- A check has no registered evaluator.
- A check references inputs that cannot be produced by the Scenario Pack, runtime kernel, or registry.
- `fail_action` is not in `allowed_gate_actions`.
- `needs_clarification` or `human_review` lacks `human_gate_reason`.
- `aggregation_policy` can downgrade a blocking baseline check.
- `final_report_requirements.must_cite_evaluated_artifacts` is not `true`.
- An enabled contract references draft evaluators or artifact schemas.

Canonical lint error ids:

| Error Id | Meaning |
|---|---|
| `EVAL_INVALID_ID` | Contract id is not stable `snake_case`. |
| `EVAL_CONTRACT_SCENARIO_MISMATCH` | Contract does not apply to Scenario Pack. |
| `EVAL_MISSING_BASELINE` | Required baseline check is absent. |
| `EVAL_UNKNOWN_EVALUATOR` | Referenced evaluator is not registered. |
| `EVAL_INVALID_GATE_ACTION` | Fail action is not allowed. |
| `EVAL_MISSING_HUMAN_GATE_REASON` | Human decision action lacks reason. |
| `EVAL_UNSAFE_AGGREGATION` | Aggregation can hide blocking failure. |
| `EVAL_UNSUPPORTED_INPUT_REF` | Required input cannot be produced. |

## Component Registry Contract

The runtime should load component manifests before loading Scenario Packs.

Each registered component should declare:

```yaml
component_manifest:
  component_id: scenario_task_execute
  component_type: skill
  version: 0.1.0
  owner: platform_runtime
  status: enabled
  input_schema_ref: artifact-schema://scenario_task_input@0.1.0
  output_schema_ref: artifact-schema://scenario_task_result@0.1.0
  allowed_tool_refs: []
  required_permissions:
    - read_bunch_blackboard
    - write_bunch_artifact
  risk_level: low
```

Component types:

- `sub_agent`
- `skill`
- `tool`
- `evaluator`
- `artifact_schema`
- `vocabulary`
- `report_template`

Rules:

- Scenario Packs reference components by id and version range.
- Enabled scenarios cannot reference draft components.
- Tools require explicit policies for read, compute, network, and write behavior.
- Evaluators must declare the stage and input refs they can evaluate.
- Artifact schemas must be versioned and immutable after use by accepted artifacts.

## Tool Policy Contract

Each ToolGateway tool policy should declare:

- tool id and version
- access mode: `read_only`, `compute_only`, `write_with_gate`, or `external_network_with_gate`
- tenant scope
- allowed input refs
- allowed output refs
- data sensitivity allowed
- resource lock requirements
- audit fields
- timeout and retry rules

Initial runtime rule:

- `write_with_gate` and `external_network_with_gate` are defined for future compatibility but not enabled in the initial implementation.

## Permission And Tenant Contract

Enterprise operation requires tenant and actor metadata even in local mode.

Required actor roles:

| Role | Meaning |
|---|---|
| `end_user` | Requests work and answers user clarification gates. |
| `scenario_owner` | Owns scenario business behavior and promotion decisions. |
| `reviewer` | Resolves human review gates. |
| `platform_admin` | Manages runtime, registry, and tenant configuration. |
| `auditor` | Reads audit records without mutating runtime state. |
| `system_component` | Runtime, agent, skill, evaluator, or tool actor. |

Access levels:

| Access Level | Allows |
|---|---|
| `status` | Lifecycle, priority, checkpoint summary, pending gates. |
| `summary` | Evaluated report summaries and limitations. |
| `evidence_ref` | Explicit artifact/evaluation refs. |
| `raw_evidence` | Raw input or tool output through owning Bunch APIs. |
| `audit` | Audit metadata and governance records. |

Rules:

- Default cross-Bunch access is `status`.
- `raw_evidence` requires explicit policy and Human Gate or administrative audit reason.
- Trunk scheduling must not require `raw_evidence`.
- Audit records are append-only.

## Error And Recovery Contract

Errors should be typed so runtime behavior is consistent.

| Error Class | Examples | Default Action |
|---|---|---|
| `user_input_error` | Missing input, ambiguous request, unsupported intent. | `needs_clarification` |
| `scenario_contract_error` | Lint failed, unknown component, invalid version range. | `block` |
| `permission_error` | Unauthorized ref, forbidden tool, tenant mismatch. | `human_review` or `block` |
| `tool_error` | Timeout, parse failure, unavailable external dependency. | retry then `needs_more_evidence` |
| `evaluation_error` | Evaluator cannot run, required refs missing. | `block` |
| `security_error` | Prompt injection, unsafe write request, policy violation. | `human_review` or `block` |
| `runtime_error` | Storage failure, duplicate immutable record, event handler crash. | retry then `failed` |

Recovery rules:

- Retry is allowed only for idempotent steps.
- Retry attempts must be recorded.
- Partial results require an Evaluation Contract action of `return_partial`.
- Terminal-state retry creates a new attempt record or derived Bunch.

## Observability And Audit Contract

The runtime should produce enough records to answer:

- What did the user ask?
- Which Scenario Pack and Evaluation Contract were pinned?
- Which plan was frozen?
- Which tools, Skills, Sub-Agents, and Evaluators ran?
- Which artifacts support each material claim?
- Which checks passed, warned, blocked, or requested human action?
- Which Human Gates were opened and resolved?
- Which checkpoint can resume the run?
- Which tenant and actor performed each write?

Required observability fields:

- `trace_id`
- `correlation_id`
- `causation_id`
- `tenant_id`
- `actor_id`
- `component_ref`
- `scenario_ref`
- `evaluation_contract_ref`
- `banana_bunch_id`
- `event_id`
- `record_ref`
- `gate_action`
- `created_at`

Audit retention classes:

| Class | Use |
|---|---|
| `short_lived_debug` | Development traces that do not carry business evidence. |
| `runtime_audit` | Lifecycle, scenario binding, gate, evaluation, and checkpoint records. |
| `business_evidence` | Inputs, artifacts, reports, and source snapshots. |
| `security_audit` | Permission failures, policy violations, and cross-Bunch access. |

## Reference Prototype Boundary

The data-analysis prototype should be represented as:

```yaml
scenario_pack:
  scenario_id: sales_channel_analysis
  scenario_version: 0.1.0
  status: reference
  planner_selectable: false
```

It validates:

- Candidate planning before data access.
- Plan validation and freeze.
- ToolGateway-mediated local file read.
- Blackboard entries and artifact refs.
- Metric recomputation as one example of artifact correctness.
- Human Gates for ambiguous input and vocabulary approval.
- Evaluation snapshots and replay.

It does not validate:

- Production scenario selection.
- Multi-scenario Planner routing.
- Enterprise tenant permissions beyond local default.
- General natural-language analytics.
- External write actions.
- Multi-Bunch scheduling.

Promotion rule:

- If data analysis is later proposed as the first production scenario, it must be copied or promoted through `reference -> candidate -> enabled`, with production ownership, selection record, enabled Evaluation Contract, and production test assets.

## First Production Scenario Selection Contract

Scenario selection should produce a durable record before any scenario becomes the first production `enabled` scenario.

```yaml
scenario_selection_record:
  schema_version: 0.1.0
  selection_id: scenario_selection_001
  candidate_scenario_ref: scenario://example_business_scenario@0.1.0
  decision: selected_for_first_production
  business_owner: actor://tenant_default/user_business_owner
  technical_owner: actor://tenant_default/user_tech_owner
  rationale:
    value: bounded_high_frequency_workflow
    evidence_checkability: deterministic_or_strongly_checkable
    tool_risk: low
    input_availability: representative_fixtures_available
  required_assets:
    - enabled_scenario_pack
    - enabled_evaluation_contract
    - golden_cases
    - negative_cases
    - calibration_cases
    - replay_fixtures
    - human_gate_examples
  approved_at: 2026-06-13T00:00:00Z
```

Selection gates:

- Business owner exists.
- Workflow is bounded and repeatable.
- Inputs and outputs can be represented as governed artifacts.
- Evaluation can check material claims.
- Tool permissions are narrow.
- Human Gate reasons are known.
- Test fixtures exist.
- Scenario does not require Trunk scheduling, external writes, or long-term memory to be useful.

Candidate families remain examples, not commitments:

- Governed data analysis.
- Contract or policy review.
- Ticket triage.
- Finance or invoice review.
- Sales operation assistance.
- Knowledge retrieval with cited evidence.
- Approval-flow assistance.

## Implementation Readiness Checklist

The design is ready for implementation planning when:

- Runtime refs and shared metadata are stable.
- Scenario Pack statuses include `reference`.
- Evaluation gate actions include `needs_more_evidence`.
- Scenario Pack and Evaluation Contract lint rules have canonical error ids.
- Component registry fields are defined.
- Tenant, actor, role, and access levels are defined.
- Error classes map to default recovery actions.
- Observability fields and audit retention classes are defined.
- Data-analysis prototype boundary is explicit.
- First production scenario selection requires a durable selection record.

## Final Acceptance Criteria

This supplement is complete when future implementation plans can cite it to build:

- runtime identity and ref builders
- scenario and evaluation schema loaders
- lint rules
- component registries
- checkpoint writer
- contract-driven evaluator selection
- reference fixture wrapping
- scenario selection records
- audit and observability records

No implementation plan should need to invent new core record shapes or gate actions while coding the first scenario-agnostic runtime pass.
