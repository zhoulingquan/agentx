# Power Banana Scenario Contract Migration Design

Status: Accepted Direction
Current authority: `docs/powerbanana-current-design.md`
Date: 2026-06-13

## Goal

Define the near-term migration route for turning the current Power Banana v0.1 runtime into a scenario-contract governed runtime without broadening the first business capability.

The route covers seven ordered stages:

1. Wrap the current fixed path as the first Scenario Pack.
2. Add an Evaluation Contract schema and linter.
3. Centralize runtime identity and references around Banana Bunch ids.
4. Add a minimal Banana Bunch Checkpoint Writer.
5. Make evaluation contract-driven.
6. Add a durable Blackboard and Event store.
7. Add Banana Trunk scheduling only after the single-Bunch runtime is stable.

This is a design refinement. It does not require immediate runtime behavior changes.

## Baseline

The current implementation already proves useful governance boundaries:

- `DeterministicDataFilePlanner` creates a candidate plan before dataset access.
- `PlanValidator` freezes only the known `data_profile_agent -> data_analysis_agent -> report_agent` path.
- `TaskDagExecutor` executes only frozen plans.
- `TaskBlackboard` records planner traces, events, entries, artifacts, evaluations, gates, and vocabulary suggestions.
- `EvaluationRunner` recomputes metric outputs and aggregates gate actions.
- LLM-assisted vocabulary suggestions remain candidate-only and require deterministic validation plus human approval.

The gap is not that v0.1 is too narrow. The gap is that scenario identity, evaluation policy, runtime identity, checkpoint ownership, and durable event replay are not yet first-class implementation objects.

## Non-Goals

This migration must not introduce:

- A second business scenario before the first Scenario Pack and Evaluation Contract are stable.
- General natural-language analytics.
- LLM planning.
- Multi-table joins or database connections.
- External write-back.
- Parallel DAG execution inside one Banana Bunch.
- Banana Trunk scheduling before the single-Bunch lifecycle, checkpoint, and contract gates are stable.
- Memory-driven business conclusions.
- Automatic activation of LLM-suggested vocabulary, skills, scenarios, or evaluation rules.

## Approaches Considered

### Recommended: Scenario-Contract First

Wrap the current path as `sales_channel_analysis`, make the Evaluation Contract mandatory, centralize ids and refs, then add checkpointing, contract-driven evaluation, durable storage, and Trunk scheduling.

This is the recommended route because it preserves the working v0.1 behavior while converting implicit governance into explicit, testable objects.

### Alternative: Trunk First

Build Banana Trunk, queues, resource locks, and multi-Bunch scheduling first.

This creates visible platform structure early, but it risks adding concurrency before the single-Bunch evidence, evaluation, and checkpoint boundaries are stable. It should wait until Stage 7.

### Alternative: Implementation Cleanup Only

Rename `task_001`, remove hard-coded refs, and refactor internals without adding Scenario Pack or Evaluation Contract files.

This improves code shape but misses the core design goal: business behavior must be declared and linted outside the runtime kernel.

## Migration Overview

| Stage | Name | Primary Outcome | May Proceed When |
|---|---|---|---|
| 1 | Wrap first Scenario Pack | Existing path is represented as `sales_channel_analysis` without expanded behavior. | Scenario declaration matches current tests and non-goals. |
| 2 | Contract schema and linter | Enabled scenarios require valid paired Evaluation Contracts. | Invalid or unpaired enabled scenarios fail lint. |
| 3 | Runtime identity and refs | `banana_bunch_<id>` refs are generated through one identity/ref layer. | No new code creates raw `task_001` refs directly. |
| 4 | Minimal Checkpoint Writer | Lifecycle continuity is writer-owned and separate from business evidence. | Checkpoints record phase and refs only, not raw evidence. |
| 5 | Contract-driven evaluation | Evaluators are selected from the pinned Evaluation Contract. | Baseline checks cannot be disabled by scenario config. |
| 6 | Durable Blackboard/Event store | Entries and events are append-only, replayable, and auditable. | Replay reproduces final report state from persisted records. |
| 7 | Banana Trunk scheduling | Multi-Bunch coordination runs through queues, locks, and events. | Single-Bunch lifecycle, contracts, checkpoints, and replay are stable. |

## Stage 1: Wrap The Current Path As A Scenario Pack

The first stage introduces a machine-readable Scenario Pack for the current fixed workflow:

```yaml
scenario_pack:
  scenario_id: sales_channel_analysis
  scenario_version: 0.1.0
  status: enabled
  purpose: Rank a single-table channel metric from an uploaded CSV or simple XLSX file.
```

The Scenario Pack must describe only behavior that already exists or is already in scope:

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

### Stage 1 Deliverables

- `scenarios/sales_channel_analysis/scenario.yaml`.
- Scenario registry loader with one enabled scenario.
- Compatibility mapping from the old `data_file_analysis` plan name to `sales_channel_analysis`.
- Tests proving current golden cases still pass with the Scenario Pack loaded.

### Stage 1 Acceptance

- The current fixed workflow can be described by the Scenario Pack without changing its answer behavior.
- The Planner can bind the selected scenario id to the Banana Bunch context.
- Existing v0.1 reports still expose planner trace, frozen plan, DAG trace, Blackboard entries, evaluation, and Human Gates.

## Stage 2: Add Evaluation Contract Schema And Linter

Every enabled Scenario Pack must have a paired Evaluation Contract.

The first contract is:

```yaml
evaluation_contract:
  contract_id: sales_channel_analysis_eval
  contract_version: 0.1.0
  status: enabled
  applies_to:
    scenario_id: sales_channel_analysis
    scenario_version_range: ">=0.1.0 <0.2.0"
```

The contract owns evaluation policy. It binds stages, evaluators, required inputs, pass conditions, fail actions, and final report requirements.

### Required Baseline Checks

The first enabled contract must include blocking or explicit gate coverage for:

- Planner intent consistency.
- Dataset snapshot presence and version.
- Required field availability.
- Evidence reference coverage.
- Metric recomputation.
- Context security findings.
- Final report artifact support.

### Enabled Lint Rules

The linter must block activation when:

- `scenario_id` and `applies_to.scenario_id` differ.
- The contract is missing or not enabled.
- A referenced evaluator, skill, sub-agent, tool, vocabulary, artifact schema, or test suite is unknown.
- A check uses a `fail_action` outside the contract's allowed gate actions.
- A check that routes to clarification or human review lacks a human gate reason.
- No blocking check exists for planner, artifact, or final-report stages.
- The scenario tries to enable parallel execution in the first implementation pass.

### Stage 2 Acceptance

- `status: enabled` fails when the paired Evaluation Contract is missing or invalid.
- Lint output is written as governance metadata.
- The Planner can only select scenarios whose lint result passes.

## Stage 3: Centralize Runtime Identity And References

The current code uses `task_001` and `data_file_analysis` in many refs. Stage 3 introduces a compatibility layer before broad renaming.

### Identity Objects

The runtime should create one identity record per business task:

```yaml
banana_bunch_identity:
  banana_bunch_id: banana_bunch_001
  legacy_task_id: task_001
  scenario_id: sales_channel_analysis
  scenario_version: 0.1.0
  evaluation_contract_id: sales_channel_analysis_eval
  evaluation_contract_version: 0.1.0
```

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
| `data_file_analysis` | `sales_channel_analysis`. |
| `task_001` refs | Generated Banana Bunch refs through the ref builder. |

### Stage 3 Acceptance

- New artifacts, evaluations, gates, and tool calls receive refs from the identity/ref layer.
- Existing tests can still assert legacy refs where compatibility is intentionally preserved.
- A new test prevents direct introduction of additional raw `task_001` refs outside the compatibility layer.

## Stage 4: Add Minimal Banana Bunch Checkpoint Writer

Checkpointing serves continuity, not business truth.

The Banana Bunch Checkpoint Writer is the only component that writes checkpoint-owned files. Agents, Skills, Planner output, Memory, and evaluators may request checkpoint updates through runtime APIs, but they do not write checkpoint state directly.

### Minimal Checkpoint Shape

```yaml
banana_bunch_checkpoint:
  banana_bunch_id: banana_bunch_001
  scenario_id: sales_channel_analysis
  scenario_version: 0.1.0
  evaluation_contract_id: sales_channel_analysis_eval
  evaluation_contract_version: 0.1.0
  lifecycle_state: completed
  current_phase: report
  latest_report_ref: bunch-blackboard://banana_bunch_001/artifacts/final_report_v1
  pending_human_gate_refs: []
  evaluation_refs:
    - bunch-blackboard://banana_bunch_001/evaluations/eval_banana_bunch_001_analysis_v1
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

### Stage 4 Acceptance

- Checkpoint records can resume or explain task state without becoming evidence.
- Memory cannot override checkpoint state.
- Checkpoint refs appear in lifecycle transition records.

## Stage 5: Make Evaluation Contract-Driven

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
- Dataset or source-version evaluator.
- Context security evaluator.
- Final report support evaluator.

Scenario-specific contracts may add checks or make gate behavior stricter. They may not remove baseline coverage.

### Stage 5 Acceptance

- Evaluation results record the active contract id and version.
- Tests prove an invalid contract cannot omit baseline checks.
- Tests prove a passing Goal or final report cannot override a blocking deterministic evaluator.

## Stage 6: Add Durable Blackboard And Event Store

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

### Stage 6 Acceptance

- A completed first-scenario run can be replayed from persisted governance records.
- Duplicate event ids are deduplicated.
- Artifact version conflicts are rejected.
- Visibility scopes are preserved.

## Stage 7: Add Banana Trunk Scheduling

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

### Stage 7 Acceptance

- One running Banana Bunch and queued additional Bunches can be represented without mixing Blackboard state.
- Resource lock decisions are recorded as Trunk metadata.
- Cross-Bunch reads require an explicit access record and return refs or summaries, not raw private evidence by default.

## Owner Model

| Object | Owner | May Write | May Read |
|---|---|---|---|
| Scenario Pack | Scenario governance | Approved scenario maintenance flow | Runtime loader, Planner, Bunch Main Agent |
| Evaluation Contract | Evaluation governance | Approved evaluation maintenance flow | Evaluation Runner, Planner gate, Bunch Main Agent |
| Banana Bunch Blackboard | Active Bunch runtime | Runtime, agents, evaluators through Blackboard APIs | Owning Bunch; Trunk by explicit read level |
| Checkpoint | Checkpoint Writer | Checkpoint Writer only | Runtime, Trunk, Bunch Main Agent |
| Memory | Memory System | Memory maintenance flow | Context Manager as continuity hints |
| Banana Trunk Blackboard | Trunk runtime | Trunk and scheduler | Trunk Agent, authorized status views |

## Testing Strategy

Each stage should add tests before it is considered complete:

- Scenario schema tests for required fields and status values.
- Evaluation Contract lint tests for missing, invalid, or unpaired contracts.
- Planner tests proving only enabled lint-passing scenarios are selectable.
- Ref builder tests preventing new direct `task_001` refs.
- Checkpoint tests proving checkpoint files contain refs, not raw rows or raw artifacts.
- Evaluation tests proving contract-pinned checks run by stage.
- Replay tests proving durable Blackboard records reconstruct completed and partial reports.
- Trunk tests proving Bunch isolation, resource locks, queue lanes, and cross-Bunch access records.

Existing planner cases, golden cases, calibration cases, and vocabulary advisor cases remain part of the scenario governance suite.

## Risk Controls

| Risk | Control |
|---|---|
| Scenario files become too large. | Keep scenario identity/policy separate from Evaluation Contract, vocabulary, artifact schemas, and tests. |
| Evaluation drift. | Block `enabled` status unless the paired contract is valid and lint-passing. |
| Naming churn breaks existing tests. | Add identity/ref builder and legacy aliases before replacing refs. |
| Checkpoint becomes hidden evidence. | Checkpoint stores refs and phase metadata only. Blackboard artifacts remain the source of truth. |
| Durable store work delays governance migration. | Add durable store after Scenario Pack, contract, identity, and checkpoint boundaries are stable. |
| Trunk complexity arrives too early. | Require single-Bunch lifecycle, contract-driven evaluation, checkpointing, and replay before Stage 7. |

## Final Acceptance Criteria

This migration route is fully implemented when:

- The current first scenario is represented by an explicit `sales_channel_analysis` Scenario Pack.
- The scenario cannot become enabled without a valid paired Evaluation Contract.
- Runtime identity and refs are generated through a Banana Bunch-aware layer.
- Checkpoints are writer-owned continuity records, not business evidence.
- Evaluation results cite the pinned Evaluation Contract id and version.
- Blackboard events and entries can be persisted and replayed.
- Banana Trunk scheduling is deferred until the single-Bunch runtime is governed, checkpointed, and replayable.
