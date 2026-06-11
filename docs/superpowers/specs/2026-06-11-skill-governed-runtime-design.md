# Skill-Governed Runtime Design

## Goal

PowerBanana should evolve from a fixed Phase 1 data-analysis workflow into a more open governed-agent runtime. The core runtime should stay responsible for hard safety and audit boundaries, while business scenarios should be extended through versioned Skills and Scenario Packs.

The intended direction is:

- Framework = governance kernel.
- Skill = governed capability plus constraints.
- Scenario Pack = business scenario assembled from Skills, routing rules, evaluators, and golden cases.

This keeps the system adaptable to different domains without turning Skills into unbounded prompts or allowing scenario code to bypass governance.

## Current Constraint

PowerBanana currently has a fixed golden path:

```text
planner -> plan validation -> data_profile_agent -> data_analysis_agent -> report_agent
```

This is appropriate for v0.1 because it validates the AgentX v0.3 governance model on one small data-analysis path. However, the fixed path makes new scenarios expensive. Adding a contract-review, sales-ops, finance-review, or customer-service scenario would currently require code changes across planner routing, sub-agent selection, step construction, evaluation, and tests.

## Design Principle

Use Skills to make business behavior configurable, but keep non-negotiable governance inside the framework.

Skills may declare:

- What capability they provide.
- What input and output schemas they require.
- Which tools they may call.
- What context they are allowed to read.
- What risk level they carry.
- Which evaluators must pass.
- Which Human Gates are required.
- What golden cases protect their behavior.

Skills must not decide:

- Whether they can bypass ToolGateway.
- Whether they can skip PlanValidator.
- Whether their own output is accepted as final without evaluation.
- Whether high-risk writes can avoid Human Gate.
- Whether they can read full Blackboard or Memory directly.

## Runtime Architecture

```mermaid
flowchart TD
    U["User Request"] --> R["Scenario Router"]
    R --> SP["Scenario Pack"]
    SP --> P["Planner"]
    P --> CP["Candidate Plan / Workflow / StepPlan"]
    CP --> SV["SkillPolicyValidator"]
    SV --> PV["PlanValidator"]
    PV --> SCH["MainAgent Scheduler"]
    SCH --> EX["Executor"]
    EX --> SK["Skill Runtime / Sub-agent Runtime"]
    SK --> TG["ToolGateway"]
    SK --> BB["TaskBlackboard"]
    BB --> EV["EvaluationRunner"]
    EV --> HG["Human Gate"]
    EV --> RP["Report"]
```

The framework owns routing, validation, execution, blackboard writes, tool mediation, evaluation aggregation, human gates, and final reporting. Scenario Packs and Skills provide declarative capabilities and constraints.

## Main Agent Scheduler

The Main Agent should be a deterministic scheduler, not a free-running executor. It may use a Planner to produce candidate DAGs and Skill chains, but only the scheduler advances frozen work.

Scheduler responsibilities:

- Maintain task, DAG node, workflow node, and Skill step state.
- Compute ready nodes from the frozen Task DAG.
- Dispatch only nodes whose dependencies, context permissions, tool policy, budget, and Human Gate state allow execution.
- Enforce Scenario Pack concurrency limits.
- Track running work, retries, timeouts, skips, and failures.
- Write dispatch decisions and node transitions to TaskBlackboard.
- Trigger EvaluationRunner after node or fan-in completion.
- Route blocked or risky nodes to Human Gate.
- Hand only evaluated artifacts to report generation.

The scheduler must not:

- Invent new Skills after validation.
- Execute a Skill that was not present in the frozen plan.
- Let sub-agents call each other directly.
- Let a node read unevaluated upstream artifacts unless the Scenario Pack explicitly allows candidate-only reads.
- Treat Skill output as trusted before Blackboard recording and evaluation.

This makes the Main Agent powerful enough to coordinate many agents while keeping it predictable and auditable.

## Parallel Execution Model

Parallelism should be DAG-driven. The scheduler can run multiple nodes from the same ready layer when all of these are true:

1. The nodes have no unmet dependencies.
2. Their required input refs are available in TaskBlackboard.
3. Their Scenario Pack allows parallel execution.
4. Their Skill manifests allow concurrent execution.
5. ToolGateway rate limits and risk policy allow the tool calls.
6. Human Gate is not pending for a required upstream decision.
7. The target artifacts do not conflict, or a merge policy is declared.

Example parallel shape:

```text
profile_document
  -> extract_payment_terms
  -> detect_compliance_risk
  -> detect_confidentiality_risk
  -> aggregate_risk_report
```

After `profile_document` succeeds, the three risk Skills can run in parallel if the scenario policy allows it. `aggregate_risk_report` is a fan-in node and can run only after the required upstream nodes finish and their outputs pass evaluation or are explicitly marked as candidate artifacts.

## Concurrency Policy

Concurrency policy belongs to the Scenario Pack and is enforced by the scheduler. A low-risk read-only analysis scenario can allow more parallelism than a high-risk write or external-action scenario.

Example:

```yaml
concurrency_policy:
  max_parallel_sub_agents: 4
  max_parallel_skill_steps: 4
  max_parallel_tool_calls: 2
  max_parallel_high_risk_nodes: 0
  allow_parallel_candidate_reads: false
  on_tool_rate_limit: retry_with_backoff
```

The default policy should be conservative:

- One task chain runs linearly unless the Scenario Pack opts into parallel layers.
- Read-only, low-risk Skills may be parallelized.
- LLM-backed Skills default to sequential execution unless deterministic aggregation is defined.
- Write actions and external side effects are never parallelized in Phase 1.
- A Human Gate blocks dependent nodes but does not need to block unrelated independent nodes unless scenario policy requires a full pause.

## Blackboard Merge And Fan-in

Parallel execution only works if Blackboard writes and fan-in are explicit.

Each parallel node should write unique artifact refs by default:

```text
blackboard://task_001/artifacts/payment_terms_v1
blackboard://task_001/artifacts/compliance_risk_v1
blackboard://task_001/artifacts/confidentiality_risk_v1
```

If multiple nodes may write related claims or the same logical artifact, the Scenario Pack must declare a merge policy:

```yaml
merge_policy:
  artifact_conflict: require_human_review
  claim_conflict: create_conflict_entry
  duplicate_claim: keep_highest_confidence_with_trace
  fan_in_requires:
    - all_required_nodes_completed
    - no_blocking_evaluations
    - no_unresolved_conflicts
```

Fan-in nodes read only from Blackboard refs, not from direct sub-agent messages. They must check:

- Required upstream nodes completed, skipped with allowed degradation, or failed with allowed fallback.
- Required upstream evaluations passed or returned an allowed partial result.
- No blocking security finding exists.
- Conflicts are resolved or explicitly surfaced to Human Gate.
- Artifact versions match the expected refs.

This makes parallelism safe enough for multi-agent workflows instead of turning it into uncontrolled message passing.

## Skill Manifest

Each Skill should be represented by a manifest plus an implementation handler.

Example shape:

```yaml
skill_id: compute_grouped_metric
version: 0.2.0
capability_tags:
  - data_analysis
  - metric_computation
risk_level: low
input_schema: Rows,AnalysisRequest
output_schema: MetricResult
allowed_tools:
  - dataset.read_snapshot
context_policy:
  allowed_refs:
    - dataset://current
    - blackboard://current/artifacts/data_profile
  trust_rules:
    dataset://current: data_only
required_evaluators:
  - schema_evaluator
  - metric_recompute_evaluator
  - evidence_coverage_evaluator
human_gate:
  required: false
idempotency:
  key_fields:
    - task_id
    - dataset_version
    - skill_id
    - input_hash
golden_cases:
  - evals/golden_cases/conversion_rate_basic.json
```

The manifest is not an execution permission by itself. It is an input to validation. The runtime still decides whether a requested Skill can run in the current scenario, autonomy level, tool policy, and risk context.

## Scenario Pack

A Scenario Pack should assemble a business scenario without changing the core runtime.

It should contain:

- Scenario identity and routing terms.
- Allowed Skills and Skill versions.
- Optional default Task DAG or Workflow DAG template.
- Concurrency policy.
- Merge and fan-in policy.
- Planner rules or planner adapter.
- Context policy.
- Evaluation policy.
- Human Gate policy.
- Tool policy.
- Golden cases and calibration cases.

Example:

```yaml
scenario_id: sales_channel_analysis
route_terms:
  - channel
  - conversion rate
  - revenue
allowed_skills:
  - profile_dataset@0.1.0
  - compute_grouped_metric@0.2.0
  - rank_metric_values@0.1.0
  - summarize_metric_report@0.1.0
default_flow:
  - profile_dataset
  - compute_grouped_metric
  - rank_metric_values
  - summarize_metric_report
concurrency_policy:
  max_parallel_sub_agents: 1
  max_parallel_skill_steps: 1
  max_parallel_tool_calls: 1
merge_policy:
  artifact_conflict: block
  fan_in_requires:
    - all_required_nodes_completed
    - no_blocking_evaluations
evaluation_policy:
  required:
    - planner_intent_evaluator
    - metric_recompute_evaluator
    - context_security_evaluator
```

## Validation Flow

The Planner may choose Skills, but it only creates candidates. Before execution, the framework must validate:

1. The selected Scenario Pack exists and is enabled.
2. Every Skill exists, is versioned, and is allowed by the Scenario Pack.
3. Each Skill input can be satisfied by prior outputs, user input, or allowed ToolGateway results.
4. Tool permissions match the Skill manifest and scenario policy.
5. Context references are limited to authorized Blackboard, Memory, and dataset views.
6. Required evaluators are present and versioned.
7. Human Gate requirements are attached for risky operations.
8. DAG and Step Plan topology is acyclic and bounded.
9. Autonomy Policy allows the proposed number of steps, alternatives, retries, and parallelism.
10. Concurrency Policy allows every parallel-ready layer.
11. Merge Policy covers any fan-in node or shared logical artifact.

Only a passing candidate becomes a frozen executable plan.

## Constraint Model

Constraints should be split into two layers.

Framework hard constraints:

- All tools go through ToolGateway.
- All executable plans go through PlanValidator.
- All Skill calls are scheduled by the MainAgent Scheduler and Executor.
- All outputs that matter are written to TaskBlackboard.
- Final answers require EvaluationRunner aggregation.
- Writes and high-risk actions require Human Gate.
- Raw user content remains untrusted unless transformed by verified tools.
- Parallel nodes cannot read each other's private state or direct messages.
- Fan-in nodes can read only authorized Blackboard refs and evaluation results.

Skill-declared constraints:

- Required input fields.
- Output schema.
- Allowed low-level tools.
- Context visibility and trust labels.
- Risk level.
- Evaluator requirements.
- Human Gate triggers.
- Concurrency constraints.
- Merge and fan-in requirements.
- Golden case coverage.

This split keeps the platform open to new scenarios while preserving safety boundaries.

## Migration Plan

PowerBanana should migrate incrementally.

1. Introduce a Skill manifest model next to the existing `SkillDefinition`.
2. Bind existing `compute_grouped_metric` and `rank_metric_values` Skills to manifests.
3. Add `SkillPolicyValidator` and run it before Step Plan execution.
4. Move hardcoded metric requirements into Skill and analysis vocabulary metadata.
5. Introduce a minimal `sales_channel_analysis` Scenario Pack for the existing path.
6. Let the Planner select the Scenario Pack and Skill chain, while preserving the current fixed fallback.
7. Introduce a scheduler state model for `pending`, `ready`, `running`, `succeeded`, `failed`, `skipped`, `blocked`, and `needs_human_gate`.
8. Replace the linear TaskDagExecutor loop with ready-node scheduling while keeping default concurrency at 1.
9. Add Scenario Pack `concurrency_policy` and enforce it before dispatch.
10. Add merge and fan-in validation for aggregate nodes.
11. Enable parallel execution first for low-risk read-only Skills.
12. Expand golden cases to assert selected Skills, required evaluators, scheduler transitions, and policy gates.

This path avoids a large rewrite. The existing fixed workflow becomes the first Scenario Pack.

## Testing

Tests should cover:

- Skill manifest parsing and validation.
- Rejection of unknown or disabled Skills.
- Rejection of Skills that request unauthorized tools.
- Rejection of missing required evaluators.
- Rejection of high-risk Skills without Human Gate.
- Rejection of parallel nodes when Scenario Pack concurrency does not allow them.
- Rejection of fan-in nodes without an explicit merge policy.
- Scheduler tests for ready-node selection, dependency blocking, retry limits, timeout handling, and Human Gate blocking.
- Blackboard tests for parallel artifact version conflicts and conflict entry creation.
- Successful execution of the current metric-analysis flow through the new manifest path.
- Golden cases that verify selected Scenario Pack, Skill chain, scheduler trace, evaluation gates, and final answer.

## Non-Goals

This design does not introduce:

- Free-form LLM planning.
- Arbitrary plugin execution.
- Direct Skill access to credentials, raw full Blackboard, or full Memory.
- Write-back tools in Phase 1.
- Multi-tenant permission enforcement.
- Distributed worker infrastructure.
- Unbounded autonomous loops.

Those can be added later only through the same ToolGateway, Policy, Evaluation, and Human Gate boundaries.

## Success Criteria

The design is successful when a new low-risk scenario can be added mostly by introducing a Scenario Pack, Skill manifests, focused handlers, concurrency and merge policies, and tests, without changing the core runtime orchestration loop.

The scheduler should be able to execute a frozen DAG with at least one parallel ready layer, record deterministic node transitions, block unsafe fan-in, and preserve the current single-chain PowerBanana behavior when concurrency limits are set to 1.

The framework should become more open, but the acceptance rule remains strict: no Skill result becomes trusted merely because a Skill produced it. It becomes trusted only after the framework records, evaluates, and gates it.
