# Power Banana Scenario-Agnostic Runtime Migration Design

Status: Accepted Direction
Current authority: `docs/powerbanana-current-design.md`
Date: 2026-06-13

Detailed runtime contract supplement: `docs/superpowers/specs/2026-06-13-powerbanana-scenario-agnostic-runtime-contract-design.md`

## Goal

Define the near-term migration route for turning the current Power Banana v0.1 prototype into a scenario-agnostic enterprise agent runtime.

The product direction is a reusable governed runtime for multiple enterprise application scenarios. The first production scenario is not selected yet. The existing data-analysis path remains valuable as a reference prototype and regression fixture, but it must not define the platform's product scope.

The route covers nine ordered stages:

1. Define the scenario-independent runtime kernel.
2. Add Scenario Pack and Evaluation Contract schemas plus linting.
3. Convert the current data-analysis path into a reference scenario fixture.
4. Centralize runtime identity and references around Banana Bunch ids.
5. Add a minimal Banana Bunch Checkpoint Writer.
6. Make evaluation contract-driven.
7. Add a durable Blackboard and Event store.
8. Select the first production scenario through explicit selection gates.
9. Add Banana Trunk scheduling only after the single-Bunch runtime is stable.

This is a design refinement. It does not require immediate runtime behavior changes.

## Baseline

The current implementation already proves useful governance boundaries:

- `DeterministicDataFilePlanner` creates a candidate plan before dataset access.
- `PlanValidator` freezes only the known `data_profile_agent -> data_analysis_agent -> report_agent` prototype path.
- `TaskDagExecutor` executes only frozen plans.
- `TaskBlackboard` records planner traces, events, entries, artifacts, evaluations, gates, and vocabulary suggestions.
- `EvaluationRunner` recomputes metric outputs and aggregates gate actions.
- LLM-assisted vocabulary suggestions remain candidate-only and require deterministic validation plus human approval.

The gap is not that v0.1 is too narrow. The narrowness is useful for a reference fixture. The gap is that scenario identity, evaluation policy, runtime identity, checkpoint ownership, and durable event replay are not yet first-class implementation objects that can be reused across different enterprise scenarios.

## Non-Goals

This migration must not introduce:

- Selection of the first production scenario before the runtime kernel and scenario contract model are stable.
- Treatment of the current data-analysis path as the mandatory first product scenario.
- General natural-language analytics.
- LLM planning.
- Multi-table joins or database connections.
- External write-back.
- Parallel DAG execution inside one Banana Bunch.
- Banana Trunk scheduling before the single-Bunch lifecycle, checkpoint, and contract gates are stable.
- Memory-driven business conclusions.
- Automatic activation of LLM-suggested vocabulary, skills, scenarios, or evaluation rules.

## Approaches Considered

### Recommended: Runtime Kernel First With Reference Prototype

Define the scenario-independent runtime kernel, make Scenario Pack and Evaluation Contract schemas mandatory for enabled scenarios, and keep the current data-analysis path as a reference fixture that exercises the new contract surfaces.

This is the recommended route because it preserves working v0.1 behavior while preventing one prototype from shaping the whole enterprise-agent platform.

### Alternative: Pick The First Production Scenario Now

Choose a business scenario immediately and migrate the runtime around that scenario.

This could accelerate a demo, but it would likely overfit the runtime boundaries, evaluator vocabulary, agent roles, and report artifacts before the platform kernel is clear. It is rejected for the current design phase.

### Alternative: Trunk First

Build Banana Trunk, queues, resource locks, and multi-Bunch scheduling first.

This creates visible platform structure early, but it risks adding concurrency before the single-Bunch evidence, evaluation, and checkpoint boundaries are stable. It should wait until Stage 9.

## Migration Overview

| Stage | Name | Primary Outcome | May Proceed When |
|---|---|---|---|
| 1 | Runtime kernel | Scenario-independent lifecycle, ownership, evidence, tool, gate, registry, permission, error, observability, and artifact boundaries are explicit. | Kernel contracts can describe the current prototype without scenario-specific assumptions. |
| 2 | Contract schema and linter | Enabled scenarios require valid Scenario Packs and paired Evaluation Contracts. | Invalid, unpaired, reference-only, or prototype-only scenarios fail lint. |
| 3 | Reference fixture | Existing data-analysis behavior is preserved as a reference scenario fixture, not product scope. | Current golden, planner, calibration, and vocabulary tests still pass through the fixture. |
| 4 | Runtime identity and refs | `banana_bunch_<id>` refs are generated through one identity/ref layer. | No new code creates raw `task_001` refs directly. |
| 5 | Minimal Checkpoint Writer | Lifecycle continuity is writer-owned and separate from business evidence. | Checkpoints record phase and refs only, not raw evidence. |
| 6 | Contract-driven evaluation | Evaluators are selected from the pinned Evaluation Contract. | Baseline checks cannot be disabled by scenario config. |
| 7 | Durable Blackboard/Event store | Entries and events are append-only, replayable, and auditable. | Replay reproduces final report state from persisted records. |
| 8 | First production scenario selection | The first enabled business scenario is chosen through explicit gates. | Scenario candidates have owner, value, evidence, deterministic evals, and regression assets. |
| 9 | Banana Trunk scheduling | Multi-Bunch coordination runs through queues, locks, and events. | Single-Bunch lifecycle, contracts, checkpoints, replay, and one enabled scenario are stable. |

## Stage 1: Define The Scenario-Independent Runtime Kernel

The first stage names the platform kernel before naming a production scenario.

The runtime kernel owns:

- Banana Bunch lifecycle state.
- Scenario binding and version pinning.
- Plan validation and freeze boundaries.
- Blackboard writes and artifact versioning.
- ToolGateway mediation.
- Evaluation execution.
- Human Gate creation and resolution.
- Checkpoint write requests.
- Final or partial report assembly.
- Component registry loading.
- Permission, tenant, error, and observability contracts.

The runtime kernel must not own:

- Scenario-specific task taxonomy.
- Scenario-specific business vocabulary.
- Scenario-specific evaluator choices beyond mandatory baselines.
- Scenario-specific report content.
- Scenario-specific tool permissions beyond the ToolGateway contract.

### Stage 1 Acceptance

- The kernel contracts can describe the current data-analysis prototype and at least two hypothetical enterprise scenarios without changing kernel object names.
- Runtime lifecycle objects do not contain a hard-coded `sales_channel_analysis`, `data_file_analysis`, or channel-metric assumption.
- The current prototype can still expose planner trace, frozen plan, DAG trace, Blackboard entries, evaluation, and Human Gates.
- Runtime record shapes and gate actions are defined by the runtime contract supplement rather than invented during implementation.

## Stage 2: Add Scenario Pack And Evaluation Contract Schema

Every enabled business scenario must have:

- A Scenario Pack that declares identity, status, task taxonomy, sub-agent roles, skills, vocabulary, tool permissions, artifact schemas, resource locks, human gates, and regression suites.
- A paired Evaluation Contract that declares stage checks, evaluator ids, required inputs, pass conditions, fail actions, final-report requirements, and baseline coverage.

Example candidate shape:

```yaml
scenario_pack:
  scenario_id: example_business_scenario
  scenario_version: 0.1.0
  status: candidate
  purpose: Describe one bounded business workflow without changing the runtime kernel.
  task_classification:
    supported_intents:
      - governed_business_task
    unsupported_intents:
      - external_write_without_gate
  sub_agents:
    - intake_agent
    - work_agent
    - report_agent
  skills:
    - scenario_input_profile
    - scenario_task_execute
    - scenario_report_assemble
```

Example paired contract:

```yaml
evaluation_contract:
  contract_id: example_business_scenario_eval
  contract_version: 0.1.0
  status: candidate
  applies_to:
    scenario_id: example_business_scenario
    scenario_version_range: ">=0.1.0 <0.2.0"
  stages:
    planner:
      checks:
        - planner_intent_consistency
    artifact:
      checks:
        - artifact_reference_coverage
    final_report:
      checks:
        - final_report_support
```

### Required Baseline Checks

Each enabled contract must include blocking or explicit gate coverage for:

- Planner intent consistency.
- Input snapshot presence and version.
- Required field or evidence availability.
- Evidence reference coverage.
- Artifact correctness or recomputation where the scenario produces derived results.
- Context security findings.
- Final report artifact support.

### Enabled Lint Rules

The linter must block activation when:

- `scenario_id` and `applies_to.scenario_id` differ.
- The paired contract is missing or not enabled.
- A referenced evaluator, skill, sub-agent, tool, vocabulary, artifact schema, or test suite is unknown.
- A check uses a `fail_action` outside the contract's allowed gate actions.
- A check that routes to clarification or human review lacks a human gate reason.
- No blocking check exists for planner, artifact, or final-report stages.
- A prototype or regression fixture attempts to become enabled only because it has existing tests.
- A `reference` Scenario Pack is exposed to the production Planner.
- A scenario tries to enable parallel execution in the initial runtime implementation pass.

### Stage 2 Acceptance

- `status: enabled` fails when the paired Evaluation Contract is missing or invalid.
- Lint output is written as governance metadata.
- The Planner can only select scenarios whose lint result passes.

## Stage 3: Convert The Data-Analysis Path Into A Reference Fixture

The current fixed workflow should be represented as a reference or candidate Scenario Pack, not as the chosen first production scenario.

The fixture may declare:

```yaml
scenario_pack:
  scenario_id: sales_channel_analysis
  scenario_version: 0.1.0
  status: reference
  purpose: Exercise the runtime kernel with a deterministic single-table metric-ranking prototype.
```

The fixture should preserve only behavior that already exists or is already in scope:

- CSV input.
- Simple XLSX input when `openpyxl` is installed.
- One uploaded table.
- Supported metrics: `conversion_rate`, `revenue`, `orders`, and `visits`.
- Supported grouping fields from governed vocabulary.
- Serial execution.
- Candidate-only vocabulary suggestions.
- Planner, golden, calibration, and vocabulary advisor regression assets.

It must not add:

- New metrics.
- Multi-file analysis.
- Multi-table joins.
- Database access.
- LLM planning.
- External writes.
- Parallel execution.

### Stage 3 Acceptance

- Current golden cases still pass with the reference fixture loaded.
- The fixture can be used to test Scenario Pack loading, contract linting, evaluation wiring, identity refs, checkpoints, and replay.
- The fixture cannot be selected as a production scenario unless its status and ownership are explicitly promoted through the same gates as any other scenario.

## Stage 4: Centralize Runtime Identity And References

The current code uses `task_001` and `data_file_analysis` in many refs. Stage 4 introduces a compatibility layer before broad renaming.

### Identity Objects

The runtime should create one identity record per business task:

```yaml
banana_bunch_identity:
  banana_bunch_id: banana_bunch_001
  legacy_task_id: task_001
  scenario_id: pending_scenario_binding
  scenario_version: none
  evaluation_contract_id: pending_contract_binding
  evaluation_contract_version: none
```

After scenario binding, the same record is updated with pinned scenario and contract refs. Prototype runs may bind to a reference fixture; production runs bind only to enabled scenarios.

### Ref Builder

All new refs should be created through a single builder:

```text
blackboard_ref(kind, name) -> bunch-blackboard://banana_bunch_001/<kind>/<name>
dataset_ref(name) -> dataset://banana_bunch_001/<name>
checkpoint_ref() -> bunch-checkpoint-writer://banana_bunch_001
```

Existing `blackboard://task_001/...` refs may remain in compatibility reports until callers are migrated. New code must not create raw hard-coded `task_001` refs.

### Mapping Rules

| Legacy Concept | Current Design Concept |
|---|---|
| `task_id` | `banana_bunch_id` for runtime identity; `legacy_task_id` only for compatibility. |
| `TaskBlackboard` | Banana Bunch Blackboard. |
| `data_file_analysis` | Prototype scenario binding for the current reference fixture. |
| `task_001` refs | Generated Banana Bunch refs through the ref builder. |

### Stage 4 Acceptance

- New artifacts, evaluations, gates, and tool calls receive refs from the identity/ref layer.
- Existing tests can still assert legacy refs where compatibility is intentionally preserved.
- A new test prevents direct introduction of additional raw `task_001` refs outside the compatibility layer.

## Stage 5: Add Minimal Banana Bunch Checkpoint Writer

Checkpointing serves continuity, not business truth.

The Banana Bunch Checkpoint Writer is the only component that writes checkpoint-owned files. Agents, Skills, Planner output, Memory, and evaluators may request checkpoint updates through runtime APIs, but they do not write checkpoint state directly.

### Minimal Checkpoint Shape

```yaml
banana_bunch_checkpoint:
  banana_bunch_id: banana_bunch_001
  scenario_id: pending_scenario_binding
  scenario_version: none
  evaluation_contract_id: pending_contract_binding
  evaluation_contract_version: none
  lifecycle_state: completed
  current_phase: report
  latest_report_ref: bunch-blackboard://banana_bunch_001/artifacts/final_report_v1
  pending_human_gate_refs: []
  evaluation_refs:
    - bunch-blackboard://banana_bunch_001/evaluations/eval_banana_bunch_001_v1
  next_action: none
  updated_at: 2026-06-13T00:00:00Z
```

The checkpoint must contain refs and lifecycle metadata only. It must not embed raw rows, raw tool output, hidden model reasoning, or unreviewed business claims.

### Write Boundaries

Checkpoint writes should occur:

- After scenario binding.
- After plan freeze.
- After each terminal or pausable phase transition.
- When a Human Gate opens or resolves.
- When a final or partial report is assembled.

Checkpoint writes should not occur in the middle of a tool call or while an artifact version is being written.

### Stage 5 Acceptance

- Checkpoint records can resume or explain task state without becoming evidence.
- Memory cannot override checkpoint state.
- Checkpoint refs appear in lifecycle transition records.

## Stage 6: Make Evaluation Contract-Driven

The Evaluation Runner should execute checks from the pinned Evaluation Contract for the active Banana Bunch.

The runner may keep default evaluators for compatibility, but scenario execution must resolve:

```text
active Banana Bunch
-> pinned Scenario Pack
-> pinned Evaluation Contract
-> stage checks
-> registered evaluators
-> aggregated gate action
```

### Baseline Evaluator Rule

Baseline evaluators cannot be disabled by a Scenario Pack:

- Schema or required-input evaluator.
- Evidence reference evaluator.
- Input source-version evaluator.
- Context security evaluator.
- Final report support evaluator.

Scenario-specific contracts may add checks or make gate behavior stricter. They may not remove baseline coverage.

### Stage 6 Acceptance

- Evaluation results record the active contract id and version.
- Tests prove an invalid contract cannot omit baseline checks.
- Tests prove a passing Goal or final report cannot override a blocking deterministic evaluator.

## Stage 7: Add Durable Blackboard And Event Store

The in-memory Banana Bunch Blackboard should migrate toward durable append-only records.

### Store Requirements

The store should support:

- Append-only events.
- Structured entries.
- Artifact version records.
- Evaluation records.
- Human Gate records.
- Vocabulary suggestion records.
- Checkpoint refs.
- Replay snapshots.

Every record should include:

- Stable id.
- Banana Bunch id.
- Actor id.
- Target ref.
- Correlation or causation id when available.
- Created timestamp.
- Schema version.

### Replay Rule

Replay should reconstruct the report state from persisted entries, artifacts, evaluations, gates, and checkpoint records. Replay does not need to reconstruct hidden model context or raw prompt text.

### Stage 7 Acceptance

- A completed prototype or scenario run can be replayed from persisted governance records.
- Duplicate event ids are deduplicated.
- Artifact version conflicts are rejected.
- Visibility scopes are preserved.

## Stage 8: Select The First Production Scenario

Only after the runtime kernel, schemas, linting, reference fixture, identity, checkpoints, contract-driven evaluation, and replay are stable should the project select the first production scenario.

Candidate scenario families include:

- Governed data analysis.
- Contract or policy review.
- Ticket triage.
- Finance or invoice review.
- Sales operation assistance.
- Knowledge retrieval with cited evidence.
- Approval-flow assistance.

Selection should use explicit gates:

- Business owner exists and accepts responsibility for scenario behavior.
- Scenario has clear value and bounded workflow.
- Required inputs and outputs can be represented as governed artifacts.
- Deterministic or strongly checkable evaluation coverage exists.
- Tool permissions are narrow and auditable.
- Human Gate reasons are clear.
- Golden cases, negative cases, calibration cases, and replay fixtures can be built.

### Stage 8 Acceptance

- The first production Scenario Pack is promoted through `candidate -> enabled`.
- Its Evaluation Contract is paired, enabled, lint-passing, and baseline-complete.
- The data-analysis reference fixture remains available for regression even if another scenario is selected first.

## Stage 9: Add Banana Trunk Scheduling

Banana Trunk should be implemented after the single-Bunch runtime is stable.

Trunk owns:

- Creating Banana Bunches.
- Maintaining the Bunch Registry.
- Routing user messages.
- Queue lanes.
- Priority.
- Resource locks.
- Checkpoint-only pause and resume.
- Cross-Bunch access decisions.

Trunk must not:

- Execute scenario-specific business steps.
- Read raw Bunch evidence by default.
- Merge Bunch Blackboards.
- Override Human Gates or Evaluation results.
- Deliver direct Bunch-to-Bunch messages.

### Stage 9 Acceptance

- One running Banana Bunch and queued additional Bunches can be represented without mixing Blackboard state.
- Resource lock decisions are recorded as Trunk metadata.
- Cross-Bunch reads require an explicit access record and return refs or summaries, not raw private evidence by default.

## Owner Model

| Object | Owner | May Write | May Read |
|---|---|---|---|
| Runtime kernel contract | Platform runtime governance | Approved runtime maintenance flow | Runtime loader, Planner, Bunch Main Agent, evaluators |
| Scenario Pack | Scenario governance | Approved scenario maintenance flow | Runtime loader, Planner, Bunch Main Agent |
| Evaluation Contract | Evaluation governance | Approved evaluation maintenance flow | Evaluation Runner, Planner gate, Bunch Main Agent |
| Banana Bunch Blackboard | Active Bunch runtime | Runtime, agents, evaluators through Blackboard APIs | Owning Bunch; Trunk by explicit read level |
| Checkpoint | Checkpoint Writer | Checkpoint Writer only | Runtime, Trunk, Bunch Main Agent |
| Memory | Memory System | Memory maintenance flow | Context Manager as continuity hints |
| Banana Trunk Blackboard | Trunk runtime | Trunk and scheduler | Trunk Agent, authorized status views |

## Testing Strategy

Each stage should add tests before it is considered complete:

- Runtime kernel contract tests proving no scenario-specific names are required.
- Scenario schema tests for required fields and status values.
- Evaluation Contract lint tests for missing, invalid, or unpaired contracts.
- Planner tests proving only enabled lint-passing scenarios are selectable.
- Reference fixture tests proving the current data-analysis prototype still passes golden, planner, calibration, and vocabulary cases.
- Ref builder tests preventing new direct `task_001` refs.
- Checkpoint tests proving checkpoint files contain refs, not raw rows or raw artifacts.
- Evaluation tests proving contract-pinned checks run by stage.
- Replay tests proving durable Blackboard records reconstruct completed and partial reports.
- Trunk tests proving Bunch isolation, resource locks, queue lanes, and cross-Bunch access records.

Existing planner cases, golden cases, calibration cases, and vocabulary advisor cases remain part of the reference fixture governance suite.

## Risk Controls

| Risk | Control |
|---|---|
| Prototype overfits the platform. | Keep data analysis as reference fixture until a production scenario is explicitly selected. |
| Scenario files become too large. | Keep scenario identity/policy separate from Evaluation Contract, vocabulary, artifact schemas, and tests. |
| Evaluation drift. | Block `enabled` status unless the paired contract is valid and lint-passing. |
| Naming churn breaks existing tests. | Add identity/ref builder and legacy aliases before replacing refs. |
| Checkpoint becomes hidden evidence. | Checkpoint stores refs and phase metadata only. Blackboard artifacts remain the source of truth. |
| Durable store work delays governance migration. | Add durable store after Scenario Pack, contract, identity, and checkpoint boundaries are stable. |
| Trunk complexity arrives too early. | Require single-Bunch lifecycle, contract-driven evaluation, checkpointing, and replay before Stage 9. |

## Final Acceptance Criteria

This migration route is fully implemented when:

- The runtime kernel is scenario-independent and can host multiple enterprise Scenario Packs.
- No production scenario is selected implicitly by existing prototype code.
- The current data-analysis path is preserved as a reference fixture or explicitly promoted through normal scenario gates.
- Enabled scenarios cannot run without a valid paired Evaluation Contract.
- Runtime identity and refs are generated through a Banana Bunch-aware layer.
- Checkpoints are writer-owned continuity records, not business evidence.
- Evaluation results cite the pinned Evaluation Contract id and version.
- Blackboard events and entries can be persisted and replayed.
- Banana Trunk scheduling is deferred until the single-Bunch runtime is governed, checkpointed, and replayable.
