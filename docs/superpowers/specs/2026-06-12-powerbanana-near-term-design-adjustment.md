# PowerBanana Near-Term Design Adjustment (Superseded)

Status: Superseded Reference
Current authority: `docs/powerbanana-current-design.md`
Superseded by: `docs/superpowers/specs/2026-06-13-powerbanana-scenario-contract-migration-design.md`

This document assumed the data-analysis prototype would become the first governed Scenario Pack. That assumption is no longer current. The accepted direction is scenario-agnostic runtime-kernel first, with the data-analysis path retained as a reference prototype and regression fixture.

## Goal

Clarify the next PowerBanana design step without starting implementation work.

This document adjusts the design direction after reviewing the current v0.1 runtime. It keeps PowerBanana's narrow data-analysis path intact and defines how the design should evolve toward the skill-governed runtime described in the broader architecture documents.

## Current Reading

PowerBanana v0.1 is a governed reference path, not a general analytics agent. The current runtime already has several strong governance boundaries:

- A deterministic Planner produces a candidate plan before any data access.
- Planner evaluation and routing can block or clarify before dataset loading.
- `PlanValidator` freezes only the known `data_profile_agent -> data_analysis_agent -> report_agent` path.
- The autonomous analysis step is constrained by registered skills and an autonomy policy.
- `TaskBlackboard` records events, structured entries, artifact versions, evaluations, gates, tool calls, and vocabulary suggestions.
- Evaluation recomputes the metric result before the report is accepted.
- Memory is currently only a local working-memory seed written after report generation.

The design issue is not that v0.1 is too narrow. The narrowness is useful. The issue is that the current fixed path does not yet name the scenario, skill policy, evaluation contract, and checkpoint boundaries as first-class design objects.

## Design Decision

The next design direction should be:

1. Treat the existing channel metric workflow as the first governed Scenario Pack.
2. Pair that Scenario Pack with an explicit Evaluation Contract.
3. Keep the runtime kernel responsible for validation, scheduling, blackboard writes, tool mediation, evaluation, human gates, and report assembly.
4. Keep business behavior in versioned scenario and skill policy definitions.
5. Add checkpoint and memory design as writer-owned runtime state, not as free-form agent memory.

This is a design-only adjustment. It does not require immediate changes to `powerbanana/`, tests, or runtime behavior.

## Recommended First Scenario Pack

The existing fixed workflow should be described as:

```yaml
scenario_pack:
  scenario_id: sales_channel_analysis
  scenario_version: 0.1.0
  status: enabled
  purpose: Rank a single-table channel metric from an uploaded CSV or simple XLSX file.
  supported_inputs:
    file_types:
      - csv
      - xlsx
    table_shape: single_table
  planner_scenarios:
    - metric_analysis
    - conversion_rate_analysis
  allowed_subagents:
    - data_profile_agent
    - data_analysis_agent
    - report_agent
  allowed_skills:
    - compute_grouped_metric@0.1.0
    - rank_metric_values@0.1.0
  allowed_metrics:
    - conversion_rate
    - revenue
    - orders
    - visits
  default_group_by: channel
  concurrency_policy:
    mode: serial
    max_parallel_nodes: 1
  human_gates:
    - clarification
    - vocabulary_suggestion
```

This Scenario Pack should not broaden capability. It should document and later validate the behavior PowerBanana already has.

## Evaluation Contract

Every enabled Scenario Pack should have a paired Evaluation Contract. For `sales_channel_analysis`, the contract should bind the existing evaluator set to scenario outputs:

```yaml
evaluation_contract:
  contract_id: sales_channel_analysis_eval
  contract_version: 0.1.0
  scenario_id: sales_channel_analysis
  required_evaluators:
    planner_trace:
      - planner_intent_evaluator@0.1.0
    analysis_result:
      - schema_evaluator@0.1.0
      - dataset_reference_evaluator@0.1.0
      - field_reference_evaluator@0.1.0
      - evidence_coverage_evaluator@0.1.0
      - metric_recompute_evaluator@0.1.0
      - context_security_evaluator@0.1.0
  gate_rules:
    block:
      - missing_planner_trace
      - planner_scenario_mismatch
      - missing_analysis_request
      - dataset_version_mismatch
      - missing_evidence_ref
      - top_value_mismatch
      - metric_value_mismatch
    return_partial:
      - missing_required_fields
      - no_valid_denominator
      - no_valid_metric_values
    needs_clarification:
      - ambiguous_metric
      - unsupported_question
      - vocabulary_suggestion_requires_approval
  regression_assets:
    planner_cases: evals/planner_cases
    golden_cases: evals/golden_cases
    calibration_cases: evals/calibration_cases
    vocabulary_cases: evals/vocabulary_cases
```

The contract should make one rule explicit: no scenario can be `enabled` unless its Evaluation Contract is valid.

## Runtime Boundary

The runtime kernel should remain non-negotiable. Scenario Packs may declare allowed behavior, but they must not bypass:

- Planner trace recording.
- Planner evaluation.
- Plan validation.
- ToolGateway mediation.
- TaskBlackboard artifact writes.
- EvaluationRunner aggregation.
- Human Gate creation.
- Final report assembly from evaluated artifacts.

The Planner may later select a Scenario Pack, but it should still produce candidates only. It should not execute tools, write files, or decide final answers.

## Memory And Checkpoint Boundary

The current `MemoryManager.write_task_summary()` is only a seed. The design should distinguish three separate responsibilities:

| Boundary | Purpose | Authority |
|---|---|---|
| TaskBlackboard | Current task facts, artifacts, events, evaluations, gates | Source of truth during the task |
| ScenarioCheckpointWriter | Durable short-term runtime checkpoint and progress files | Sole writer for checkpoint-owned files |
| Memory System | Continuity, episode candidates, process improvement candidates | Never overrides current evidence or gates |

The near-term checkpoint target should be minimal:

```yaml
checkpoint:
  task_id: task_001
  scenario_id: sales_channel_analysis
  scenario_version: 0.1.0
  evaluation_contract_version: 0.1.0
  status: completed | partial | blocked | needs_clarification
  current_phase: planner | profile | analysis | report | closed
  latest_answer_ref: blackboard://task_001/artifacts/final_report_v1
  pending_human_gates:
    - gate_001
  evaluation_refs:
    - blackboard://task_001/artifacts/analysis_result_v1
  next_action: none | wait_for_user | rerun_after_vocabulary_approval
```

This checkpoint is runtime continuity state. It is not business knowledge and should not become a hidden source of analytic truth.

## Migration Path

The design should migrate in small phases:

1. **Design clarification only.** Document the Scenario Pack, Evaluation Contract, runtime boundary, and checkpoint ownership. No runtime behavior changes.
2. **Schema and linter.** Add machine-readable Scenario Pack and Evaluation Contract schemas, plus lint tests.
3. **Wrap the current path.** Bind the existing fixed workflow to `sales_channel_analysis` without changing supported questions or outputs.
4. **Policy validation.** Validate allowed sub-agents, skills, metrics, evaluator bindings, and serial concurrency before plan freeze.
5. **Checkpoint writer.** Introduce a minimal writer-owned short-term checkpoint for task status and pending gates.
6. **Config loading.** Move from built-in definitions to versioned scenario/evaluation files after the schema is stable.
7. **Scheduler extension.** Add ready-node scheduling and concurrency only after serial scenario validation is stable.
8. **Second scenario.** Add a meaningfully different low-risk scenario to test whether the runtime abstraction is reusable.

## Non-Goals

This design adjustment does not propose:

- A general natural-language analytics agent.
- LLM planning in the next implementation step.
- Multi-table joins or database connections.
- Parallel DAG execution in the first migration step.
- External write-back, exports, or connector actions.
- Free-form memory that affects business conclusions.
- Automatic activation of LLM-suggested vocabulary or scenario changes.
- A second business scenario before the existing path is wrapped and validated.

## Risks

**Scenario Pack complexity.** Scenario files can become large if routing, tools, evaluators, golden cases, and memory policies are mixed together.

Mitigation: keep Scenario Pack identity and policy separate from the Evaluation Contract.

**Evaluation drift.** A Scenario Pack without a paired contract can look enabled while its outputs are not actually governed.

Mitigation: make the paired Evaluation Contract mandatory for enabled status.

**Memory overreach.** Checkpoints and memory can accidentally become hidden decision inputs.

Mitigation: TaskBlackboard and current tool evidence always outrank memory. Checkpoints preserve progress; they do not justify answers.

**Premature generalization.** Adding multiple scenarios too early can force abstractions before the first pack is stable.

Mitigation: wrap `sales_channel_analysis` first, then add one different low-risk scenario as a validation milestone.

## Success Criteria

The adjusted design is successful when:

- The current PowerBanana workflow can be described as an enabled Scenario Pack without changing its behavior.
- Every enabled Scenario Pack has a valid paired Evaluation Contract.
- The runtime boundary clearly states what scenario definitions cannot bypass.
- The memory/checkpoint boundary clearly separates current-task facts from continuity state.
- The migration path allows implementation in small, testable phases.
- No design section implies that code must be changed in the current documentation-only step.
