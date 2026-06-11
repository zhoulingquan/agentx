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
    SP --> PG["ScenarioPathGuard"]
    SP --> EC["Evaluation Contract"]
    EC --> P["Planner"]
    P --> CP["Candidate Plan / Workflow / StepPlan"]
    CP --> SV["SkillPolicyValidator"]
    SV --> PV["PlanValidator"]
    PV --> SCH["MainAgent Scheduler"]
    SCH --> EX["Executor"]
    EX --> SK["Skill Runtime / Sub-agent Runtime"]
    SCH --> CW["ScenarioCheckpointWriter"]
    CW --> SM["Scenario Memory / Checkpoint"]
    SK --> TG["ToolGateway"]
    SK --> BB["TaskBlackboard"]
    BB --> EV["EvaluationRunner"]
    EV --> GJ["GoalJudgeEvaluator"]
    EV --> HG["Human Gate"]
    EV --> RP["Report"]
```

The framework owns routing, path guarding, validation, execution, checkpointing, blackboard writes, tool mediation, evaluation aggregation, goal judgment, human gates, and final reporting. Scenario Packs and Skills provide declarative capabilities and constraints.

## Main Agent Scheduler

The Main Agent should be a deterministic scheduler, not a free-running executor. It may use a Planner to produce candidate DAGs and Skill chains, but only the scheduler advances frozen work.

Scheduler responsibilities:

- Maintain task, DAG node, workflow node, and Skill step state.
- Compute ready nodes from the frozen Task DAG.
- Dispatch only nodes whose dependencies, context permissions, tool policy, budget, and Human Gate state allow execution.
- Enforce Scenario Pack concurrency limits.
- Track running work, retries, timeouts, skips, and failures.
- Write dispatch decisions and node transitions to TaskBlackboard.
- Notify ScenarioCheckpointWriter of task state, fan-in state, and long-running progress.
- Trigger EvaluationRunner after node or fan-in completion.
- Require GoalJudgeEvaluator before declaring an autonomous task complete.
- Route blocked or risky nodes to Human Gate.
- Hand only evaluated artifacts to report generation.

The scheduler must not:

- Invent new Skills after validation.
- Execute a Skill that was not present in the frozen plan.
- Let sub-agents call each other directly.
- Let a node read unevaluated upstream artifacts unless the Scenario Pack explicitly allows candidate-only reads.
- Treat Skill output as trusted before Blackboard recording and evaluation.
- Write directly to scenario checkpoint, durable memory, or enabled scenario files.

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

## Skill Folder Isolation

Skills should be split into global Skills and scenario-local Skills.

Global Skills live in a shared registry and may be reused across scenarios:

```text
skills/
  global/
    profile_dataset/
      SKILL.md
      handler.py
      tests/
    summarize_report/
      SKILL.md
      handler.py
      tests/
```

Scenario-local Skills live inside one scenario directory and are not reusable by default:

```text
scenario_packs/
  contract_payment_review/
    skills/
      extract_contract_terms/
        SKILL.md
        handler.py
        tests/
      detect_payment_risk/
        SKILL.md
        handler.py
        tests/
```

Global Skill rules:

- Must be reviewed as reusable platform capabilities.
- Must have stable input and output schemas.
- Must have versioned manifests.
- Must avoid domain-specific hidden assumptions.
- May be referenced by multiple Scenario Packs through exact versions.

Scenario-local Skill rules:

- Belongs to exactly one Scenario Pack.
- Resolves only under that scenario directory.
- Cannot be referenced by another scenario unless promoted through an explicit review into `skills/global/`.
- Can use domain terminology and domain evaluators from its owning scenario.
- Must still use ToolGateway, TaskBlackboard, ContextManager, and EvaluationRunner boundaries.

Example Skill references:

```yaml
allowed_skills:
  - global:profile_dataset@0.1.0
  - global:summarize_report@0.1.0
  - local:extract_contract_terms@0.1.0
  - local:detect_payment_risk@0.1.0
```

The `local:` prefix always resolves inside the selected scenario directory. The `global:` prefix resolves only from the approved global Skill registry. A Scenario Pack cannot reference another scenario's local Skills.

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
- Evaluation Pack or Evaluation Contract reference.
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

## Scenario File Isolation

Every scenario should be isolated at the filesystem level. A scenario owns its own configuration, generated drafts, plans, DAG templates, policies, tests, and compiled contracts inside one scenario directory.

Recommended shape:

```text
scenario_packs/
  sales_channel_analysis/
    SCENARIO.md
    EVALUATION.md
    README.md
    CHECKPOINT.md
    planner/
      routing_terms.csv
      planner_rules.yaml
    plans/
      task_plan_template.yaml
      workflow_dag.yaml
    policies/
      tool_policy.yaml
      context_policy.yaml
      concurrency_policy.yaml
      merge_policy.yaml
      human_gate_policy.yaml
    contracts/
      evaluation_contract.yaml
    skills/
      compute_grouped_metric/
        SKILL.md
        handler.py
        tests/
    golden_cases/
      conversion_rate_basic.json
    calibration_cases/
      metric_mismatch_should_block.json
    memory/
      MEMORY.md
      notes.md
      tasks/
        T1/
          progress.md
    drafts/
      2026-06-11-initial/
        SCENARIO.md
        EVALUATION.md
        notes.md
    changes/
      change_0001/
        request.md
        diff.md
        validation_result.json
```

Another scenario must have a separate directory:

```text
scenario_packs/
  contract_payment_review/
    SCENARIO.md
    EVALUATION.md
    planner/
    plans/
    policies/
    contracts/
    skills/
    golden_cases/
    calibration_cases/
    drafts/
    changes/
```

The runtime must treat the scenario directory as the configuration boundary. Data-analysis files, contract-review files, finance-review files, and ticket-triage files should not be mixed in shared folders except for explicitly shared registries such as global Skill definitions or baseline evaluators.

Rules:

- Each scenario directory has exactly one active `SCENARIO.md` and one active `EVALUATION.md`.
- Generated plans and DAG templates live under the same scenario directory.
- Scenario-specific policies live under the same scenario directory.
- Golden and calibration cases are scenario-local.
- Drafts and change requests are scenario-local.
- Compiled Evaluation Contracts are scenario-local and versioned.
- Scenario-local Skills live under the scenario directory and cannot be referenced by other scenarios.
- Scenario memory, checkpoints, task progress, notes, and rule-change logs are scenario-local.
- Shared Skills and shared baseline evaluators may live outside scenario directories, but the Scenario Pack must reference exact versions from approved registries.
- A runtime task resolves files only through its pinned `scenario_id` and `scenario_version`.
- Cross-scenario file references are denied unless the target is from an approved shared registry.

This prevents the data-analysis runtime from accidentally loading contract-review DAGs, evaluators, policies, or examples, and vice versa.

## Scenario Runtime State And Path Guard

The runtime should add a scenario-scoped state layer inspired by long-horizon coding agents that keep structured checkpoints and memory across sessions. The important lesson is not the coding-agent behavior itself; it is the separation between working state, durable memory, and write permissions.

Each active task should be bound to:

- `scenario_id`.
- `scenario_version`.
- `evaluation_contract_version`.
- `scenario_root`.
- `task_id`.
- `allowed_global_registries`.

All scenario file reads and writes must pass through a `ScenarioPathGuard`. The guard rejects:

- Paths outside the pinned `scenario_root`.
- Another scenario's `SCENARIO.md`, `EVALUATION.md`, plans, DAGs, policies, Skills, examples, memory, checkpoints, or change requests.
- Scenario-local Skill references that are not under the pinned scenario directory.
- Writes to enabled Scenario Pack files outside an approved draft or change request flow.
- Direct writes by general agents to checkpoint-writer-owned files.

The guard allows:

- Reads from the pinned scenario directory.
- Reads from approved global Skill and baseline evaluator registries by exact version.
- Writes to task-local artifacts through TaskBlackboard.
- Writes to draft and change folders during initialization or rule maintenance.
- Writes to scenario checkpoint and memory files only by the dedicated writer role.

This guard is a framework hard constraint. A Skill manifest, Planner output, or Scenario Pack cannot weaken it.

## Scenario Checkpoint Writer

Long-running multi-agent workflows need a dedicated writer that maintains scenario state without letting the main agent rewrite history opportunistically. AgentX should introduce a hidden `ScenarioCheckpointWriter` sub-agent per running scenario task.

The writer owns these files under the selected scenario directory:

```text
scenario_packs/<scenario_id>/
  CHECKPOINT.md
  memory/
    MEMORY.md
    notes.md
    tasks/<task_id>/progress.md
  changes/<change_id>/validation_result.json
```

Responsibilities:

- Maintain the current task intent, active Scenario Pack version, Evaluation Contract version, and next concrete action.
- Record scheduler node states, running sub-agents, pending Human Gates, and blocked dependencies.
- Reconcile sub-agent progress into scenario task progress.
- Promote only durable, verified scenario knowledge into scenario `MEMORY.md`.
- Keep exact-form values such as thresholds, rule IDs, evaluator IDs, dataset versions, and file paths byte-for-byte when they are needed for replay.
- Keep checkpoint sections bounded so context reconstruction can inject high-signal state instead of raw history.

Restrictions:

- The main agent and ordinary sub-agents may append task artifacts through TaskBlackboard but cannot directly write writer-owned checkpoint files.
- The writer cannot modify source scenario files that are currently enabled.
- The writer cannot create or enable new Skills, rules, evaluators, or golden cases.
- The writer can summarize a possible rule or Skill candidate, but activation still goes through rule maintenance.

This turns checkpointing into a governed runtime service instead of an informal memory habit.

## Scenario Dream And Distill

The framework should support controlled self-improvement, but only as draft generation. Two maintenance passes can be added:

`ScenarioDream`:

- Reads recent scenario checkpoints, task progress, evaluation reports, Human Gate decisions, and replay snapshots.
- Consolidates durable scenario knowledge into `memory/MEMORY.md`.
- Removes stale or contradicted scenario notes.
- Flags repeated failures, recurring ambiguity, and missing domain vocabulary.

`ScenarioDistill`:

- Looks for repeated manual workflows, repeated correction patterns, recurring evaluator failures, and common human review reasons.
- Produces candidate local Skills, evaluator rules, golden cases, calibration cases, or promotion candidates for global Skills.
- Creates drafts under `drafts/` or `changes/`, never enabled artifacts.
- Requires evidence from at least two tasks, a stable input/output shape, and a clear stopping condition before proposing a reusable asset.

Distillation output must enter the same lifecycle as user-requested changes:

```text
candidate discovered
-> create draft under scenario directory
-> lint Scenario Pack and Evaluation Pack
-> compile Evaluation Contract
-> run affected golden and calibration cases
-> request approval
-> activate or discard
```

This lets the agent learn from repeated work while preserving scenario isolation, auditability, and human approval.

## Scenario And Evaluation Pack Pairing

A Scenario Pack must be paired with an Evaluation Pack before it can be enabled. The Scenario Pack defines how the business workflow may run. The Evaluation Pack defines how the workflow is judged as correct, safe, partial, blocked, or requiring human review.

Recommended directory shape:

```text
scenario_packs/
  contract_payment_review/
    SCENARIO.md
    EVALUATION.md
    golden_cases/
      valid_payment_review.json
      missing_payment_terms.json
    calibration_cases/
      long_payment_period_should_human_review.json
      claim_without_evidence_should_block.json
```

`SCENARIO.md` owns:

- Scenario identity and purpose.
- Input types.
- Routing terms.
- Allowed Skills and versions.
- Default Task DAG or Workflow DAG.
- Tool policy.
- Concurrency policy.
- Merge and fan-in policy.
- Human Gate categories.

`EVALUATION.md` owns:

- Baseline evaluators that cannot be disabled.
- Skill-level evaluator requirements.
- Scenario-level business rules.
- Fan-in evaluator requirements.
- Report-level evaluator requirements.
- Gate mapping for `pass`, `pass_with_warning`, `return_partial`, `needs_clarification`, `human_review`, and `block`.
- Golden case and calibration case requirements.

The runtime should compile both files into an Evaluation Contract. The contract is the machine-checked binding between a scenario, its Skills, its expected artifacts, its evaluators, and its gate rules.

Example:

```yaml
evaluation_contract:
  scenario_id: contract_payment_review
  version: 0.1.0
  required_baseline_evaluators:
    - schema_evaluator@0.1.0
    - evidence_coverage_evaluator@0.1.0
    - context_security_evaluator@0.1.0
  required_domain_evaluators:
    - contract_payment_rule_evaluator@0.1.0
  skill_output_checks:
    extract_contract_terms@0.1.0:
      output_schema: ContractTerms
      required_evaluators:
        - schema_evaluator@0.1.0
        - evidence_coverage_evaluator@0.1.0
    detect_payment_risk@0.1.0:
      output_schema: PaymentRiskFinding
      required_evaluators:
        - contract_payment_rule_evaluator@0.1.0
        - risk_severity_evaluator@0.1.0
  gate_rules:
    - id: missing_payment_terms
      condition: payment_terms.not_found
      gate_action: human_review
    - id: claim_without_evidence
      condition: report.claims_without_evidence > 0
      gate_action: block
    - id: payment_days_over_60
      condition: payment_days > 60
      gate_action: human_review
```

No Scenario Pack may move from `draft` to `enabled` without a valid Evaluation Contract.

## Agent Initialization Flow

Scenario and Evaluation Pack generation should run during Agent initialization, not during every task. The runtime should distinguish setup-time configuration from task-time execution.

Initialization should run when:

- The Agent starts for the first time and has no enabled Scenario Pack.
- An administrator creates a new business scenario.
- A domain owner explicitly asks to add a new scenario.
- A deployment imports a Scenario Pack that has not been linted or approved in this environment.

Initialization flow:

```text
agent starts
-> load enabled Scenario Packs
-> if none exist, start Scenario Builder
-> collect scenario requirements through guided questions
-> collect evaluation requirements through guided questions
-> create scenario directory under scenario_packs/<scenario_id>/
-> generate SCENARIO.md draft inside that scenario directory
-> generate EVALUATION.md draft inside that scenario directory
-> initialize scenario CHECKPOINT.md and memory/ templates
-> lint Scenario Pack
-> lint Evaluation Pack
-> compile Evaluation Contract
-> write Evaluation Contract under that scenario directory
-> generate golden and calibration drafts under that scenario directory
-> request domain-owner or administrator approval
-> enable approved pack and pin active version
```

After initialization, normal user tasks do not regenerate Scenario Packs or Evaluation Contracts. They load the active, enabled versions and run through routing, planning, validation, scheduling, Blackboard, EvaluationRunner, and Human Gate.

Initialization may run `ScenarioDream` only to import verified durable knowledge from a known prior scenario source. It must not run `ScenarioDistill` to auto-create enabled Skills or rules during first setup. Distillation can create drafts only after the scenario has enough real task history.

## Rule Maintenance Flow

Users should be able to add or modify rules after initialization, but changes must be versioned and governed. An enabled Scenario Pack should not be edited in place.

Rule changes should start from user-friendly requests such as:

- Add a new high-risk condition.
- Change a threshold.
- Require an extra evidence field.
- Add a new output section.
- Add a new human review trigger.
- Add a new golden or calibration example.

Rule maintenance flow:

```text
user requests rule change
-> builder asks follow-up questions
-> create change request
-> create change folder under the scenario directory
-> generate new draft version of SCENARIO.md and/or EVALUATION.md in that change folder
-> show human-readable diff
-> run Scenario Pack lint
-> run Evaluation Policy lint
-> compile new Evaluation Contract
-> run affected golden and calibration cases
-> request approval
-> activate new version or keep existing version
```

The same flow applies when `ScenarioDistill` proposes a candidate rule, Skill, evaluator, golden case, or calibration case. Distilled candidates are treated as suggestions from historical evidence, not as trusted runtime policy.

Versioning rules:

- Enabled packs are immutable.
- Rule changes create a new draft version, such as `contract_payment_review@0.2.0`.
- Running tasks stay pinned to the Scenario Pack and Evaluation Contract version they started with.
- New tasks use the newly active version only after approval.
- Rollback switches the active pointer back to a previous approved version.
- Every rule change writes an audit record with the requester, reviewer, diff, test results, and activation time.

The LLM may help collect the change, explain the diff, and suggest affected tests. It must not directly activate the change or bypass linting, calibration, approval, or version pinning.

## Runtime Task Flow

Once a Scenario Pack is enabled, normal task execution should follow this governed loop:

```text
user request
-> Scenario Router selects enabled scenario
-> bind scenario_id, scenario_version, evaluation_contract_version
-> ScenarioPathGuard opens pinned scenario root
-> Planner creates candidate plan or DAG
-> SkillPolicyValidator and PlanValidator freeze executable plan
-> MainAgent Scheduler dispatches ready nodes
-> sub-agents execute Skills through ToolGateway
-> Skill outputs write artifacts to TaskBlackboard
-> ScenarioCheckpointWriter records progress and state
-> EvaluationRunner evaluates node outputs and fan-in
-> GoalJudgeEvaluator checks task-level stop condition
-> Human Gate handles blocking or high-risk outcomes
-> Report is assembled from evaluated artifacts only
```

The runtime does not regenerate `SCENARIO.md`, `EVALUATION.md`, Skill manifests, or Evaluation Contracts during this flow. It may append runtime state and artifacts under writer-owned memory, TaskBlackboard, run snapshots, or explicitly approved task output folders.

## Goal Judge

The system should add an independent `GoalJudgeEvaluator` to prevent the main agent from declaring work complete without evidence. The judge reads the task transcript, scheduler trace, TaskBlackboard artifacts, and EvaluationResults, then returns a structured verdict:

```yaml
goal_judge:
  ok: false
  impossible: false
  reason: "The report has no evaluated payment-risk artifact."
  missing:
    - artifact: blackboard://task_001/artifacts/payment_risk_v1
    - evaluation: contract_payment_rule_evaluator@0.1.0
```

Rules:

- The judge is independent of the working sub-agent that produced the result.
- The judge can require continuation, clarification, human review, or blocking.
- The judge cannot weaken a blocking EvaluationResult.
- The judge cannot mark a scenario enabled.
- The judge fails open only for low-risk convenience tasks; high-risk scenarios should fail to human review if the judge is unavailable.
- A maximum re-entry count prevents infinite autonomous loops.

This is a task-level stop-condition gate. It complements deterministic evaluators rather than replacing them.

## User-Friendly Evaluation Builder

Non-technical users should not write evaluator code or gate rules directly. A Scenario Pack Builder can use an LLM conversation to collect evaluation requirements and generate an Evaluation Pack draft.

The builder should ask questions such as:

1. What does a good final answer need to contain?
2. Which mistakes are unacceptable?
3. Which conclusions require evidence or source references?
4. Which cases should return a partial result instead of a full answer?
5. Which cases must ask for clarification?
6. Which cases must go to human review?
7. Can you provide one good example and one bad example?
8. What risk levels or business thresholds matter?

The LLM may generate:

- `EVALUATION.md` draft.
- Structured Evaluation Contract draft.
- Golden case drafts.
- Calibration case drafts.
- Plain-language explanations of linter failures.

The LLM must not:

- Disable baseline evaluators.
- Mark a high-risk rule as automatically passing.
- Enable an unregistered evaluator.
- Approve its own Evaluation Pack.
- Bypass calibration cases.
- Treat natural-language evaluation prose as executable policy.

Execution uses only structured frontmatter and YAML blocks that pass linting. Natural-language sections explain intent but do not become runtime rules.

## Evaluation Layering

Evaluation should be layered so every Scenario Pack gets common safety checks and domain-specific checks.

| Layer | Purpose | User configurable |
|---|---|---|
| Baseline Evaluation | Schema, evidence, context safety, dataset or source version, ToolGateway boundary | No |
| Skill Evaluation | Whether each Skill output matches its schema and evidence requirements | Limited by Skill manifest |
| Scenario Evaluation | Domain-specific business rules and thresholds | Yes, through builder and approval |
| Fan-in Evaluation | Whether parallel outputs can be safely merged | Yes, through merge policy |
| Report Evaluation | Whether the final user-facing answer is complete, supported, and safe | Yes, with required baseline checks |

Each layer writes an EvaluationResult to TaskBlackboard. The scheduler uses the strongest gate action when deciding whether to continue, retry, ask for clarification, route to human review, return partial output, or block.

## Scenario Enablement Lifecycle

Scenario Pack status should follow this lifecycle:

```text
draft
-> scenario_lint_passed
-> evaluation_lint_passed
-> calibration_ready
-> approved
-> enabled
```

Enablement requirements:

- `SCENARIO.md` exists and passes Scenario Pack linting.
- `EVALUATION.md` exists and passes Evaluation Policy linting.
- Every Skill output has an evaluator or an explicit human review path.
- Every high-risk rule has a Human Gate.
- Every fan-in node has merge and fan-in evaluation rules.
- At least one positive golden case exists.
- At least one negative or escalation calibration case exists.
- An administrator or domain owner approves the pack.

## Validation Flow

The Planner may choose Skills, but it only creates candidates. Before execution, the framework must validate:

1. The selected Scenario Pack exists and is enabled.
2. The selected Scenario Pack has a valid paired Evaluation Contract.
3. The task is bound to a pinned `scenario_id`, `scenario_version`, `evaluation_contract_version`, and `scenario_root`.
4. ScenarioPathGuard is active for all scenario file reads and writes.
5. All scenario-local files resolve under the selected scenario directory.
6. Cross-scenario file references are rejected unless they point to an approved shared registry.
7. Global Skill references resolve only from the approved global Skill registry.
8. Local Skill references resolve only under the selected scenario directory.
9. Cross-scenario local Skill references are rejected.
10. Every Skill exists, is versioned, and is allowed by the Scenario Pack.
11. Each Skill input can be satisfied by prior outputs, user input, or allowed ToolGateway results.
12. Tool permissions match the Skill manifest and scenario policy.
13. Context references are limited to authorized Blackboard, scenario Memory, and dataset views.
14. Required baseline, Skill-level, scenario-level, fan-in, report, and goal-judge evaluators are present and versioned.
15. Human Gate requirements are attached for risky operations.
16. DAG and Step Plan topology is acyclic and bounded.
17. Autonomy Policy allows the proposed number of steps, alternatives, retries, and parallelism.
18. Concurrency Policy allows every parallel-ready layer.
19. Merge Policy covers any fan-in node or shared logical artifact.
20. ScenarioCheckpointWriter permissions are available for long-running or autonomous tasks.
21. Golden and calibration case requirements are satisfied for enabled scenarios.

Only a passing candidate becomes a frozen executable plan.

## Constraint Model

Constraints should be split into two layers.

Framework hard constraints:

- All tools go through ToolGateway.
- All executable plans go through PlanValidator.
- All Skill calls are scheduled by the MainAgent Scheduler and Executor.
- All outputs that matter are written to TaskBlackboard.
- Final answers require EvaluationRunner aggregation.
- Autonomous task completion requires GoalJudgeEvaluator or an explicit low-risk bypass policy.
- Enabled scenarios require a valid paired Evaluation Contract.
- Scenario file access goes through ScenarioPathGuard.
- Scenario-local files must resolve under the pinned scenario directory.
- Scenario-local Skills must resolve under the pinned scenario directory.
- Scenario checkpoints, memory, notes, and task progress are scenario-local.
- Checkpoint-writer-owned files are writable only by ScenarioCheckpointWriter.
- Cross-scenario local Skill reuse is denied by default.
- Writes and high-risk actions require Human Gate.
- Raw user content remains untrusted unless transformed by verified tools.
- Parallel nodes cannot read each other's private state or direct messages.
- Fan-in nodes can read only authorized Blackboard refs and evaluation results.
- ScenarioDream and ScenarioDistill can create draft candidates only; they cannot enable runtime policy.

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
- Evaluation policy references.
- Golden and calibration requirements.

This split keeps the platform open to new scenarios while preserving safety boundaries.

## Multi-Industry Fit Assessment

This architecture is a reasonable foundation for a multi-industry business-agent platform because it separates stable governance from scenario-specific behavior.

The reusable platform layer is:

- Scenario routing.
- Deterministic scheduling.
- Plan and Skill policy validation.
- ToolGateway mediation.
- TaskBlackboard state, evidence, and audit records.
- Evaluation aggregation.
- Human Gate handling.
- Report assembly from evaluated artifacts.

The industry-specific layer is:

- Scenario Pack.
- Domain vocabulary and routing rules.
- Domain Skills.
- Domain tool bindings.
- Domain evaluators.
- Domain Human Gate policy.
- Golden cases and calibration cases.

This separation lets the same runtime support sales analysis, contract review, finance review, customer-service triage, compliance checks, and internal knowledge workflows without rewriting the scheduler or governance core.

## Suitable Scenario Types

The architecture is best suited to scenarios where the work can be represented as a governed DAG of evidence-producing steps.

Good early candidates:

- Sales and operations analysis.
- CSV, spreadsheet, and report analysis.
- Contract review and clause-risk extraction.
- Finance document review and rule checking.
- Customer-service ticket classification and response drafting.
- Internal knowledge retrieval followed by structured reporting.
- Compliance and quality review workflows.

These scenarios share useful traits: inputs can be snapshotted, intermediate artifacts can be written to Blackboard, outputs can be evaluated, and high-risk actions can be routed to Human Gate.

## Less Suitable Initial Scenarios

The architecture should not start with scenarios where the primary value depends on unrestricted autonomy, high-frequency side effects, or hard real-time decisions.

Poor initial candidates:

- Fully autonomous production-system operators.
- High-frequency trading or real-time fraud blocking.
- Irreversible write actions without human approval.
- Open-ended internet agents with broad tool access.
- High-liability legal, medical, or financial final decisions without expert review.
- Long chains of cross-system writes where rollback and idempotency are not mature.

These scenarios may become possible later, but only after ToolGateway permissions, Human Gate workflows, replay, compensation, and tenant-level access control are production-grade.

## Key Design Risks

The architecture is sound, but its multi-industry usefulness depends on controlling a few risks.

Scenario Pack complexity:

- Scenario Packs can become too large if routing, workflow, tool policy, evaluator policy, and tests are not schema-validated.
- Mitigation: define a strict Scenario Pack schema and linter before adding many scenarios.

Skill granularity:

- Skills that are too broad become opaque scenario-specific mini-agents.
- Skills that are too small create brittle plans and excessive scheduler overhead.
- Mitigation: define Skills around independently testable business capabilities with clear input and output schemas.

Evaluator coverage:

- Multi-industry agents fail when they can execute but cannot verify domain correctness.
- Mitigation: every production Skill needs at least schema checks, evidence checks, and one domain-specific evaluator or human review path.

Permission and data isolation:

- Multi-industry use will introduce departments, tenants, data classes, and tool credentials.
- Mitigation: keep credentials out of Skills, enforce all tool access through ToolGateway, and add tenant and role policy before production multi-tenant deployment.

Parallel fan-in:

- Parallel agents may produce conflicting claims or partially evaluated artifacts.
- Mitigation: require merge policy, conflict entries, artifact versions, and fan-in evaluators before enabling broad parallelism.

Self-improvement drift:

- Memory consolidation and workflow distillation may overfit to recent tasks or promote accidental behavior into policy.
- Mitigation: keep ScenarioDream and ScenarioDistill read-only over raw history, draft-only for generated assets, and subject to linting, calibration, approval, and version pinning.

Checkpoint authority drift:

- A long-running agent may overwrite or misplace state if every sub-agent can write memory files directly.
- Mitigation: reserve checkpoint, memory, notes, and task progress ownership to ScenarioCheckpointWriter and enforce write allowlists through ScenarioPathGuard.

## Production Readiness Requirements

Before treating this as a production multi-industry platform, the following components should exist:

1. Scenario Pack schema and linter.
2. Skill manifest schema and SkillPolicyValidator.
3. MainAgent Scheduler with ready-node dispatch, state transitions, retries, timeouts, and Human Gate blocking.
4. Blackboard persistence with artifact versioning, conflict entries, and replay snapshots.
5. Evaluation registry with domain-specific evaluator contracts.
6. Golden and calibration case runners per Scenario Pack.
7. ToolGateway policy with deny-by-default authorization.
8. ScenarioPathGuard with per-scenario read/write allowlists.
9. ScenarioCheckpointWriter with checkpoint, memory, notes, and task progress ownership.
10. GoalJudgeEvaluator for task-level stop conditions.
11. ScenarioDream and ScenarioDistill maintenance flows with draft-only output.
12. Tenant, role, data-classification, and credential-isolation model.
13. Observability for scheduler transitions, tool calls, checkpoint updates, evaluation outcomes, goal-judge verdicts, and human gates.
14. Release and rollback process for Scenario Packs and Skill versions.

For near-term implementation, the first platform investments should be Scenario Pack schema/linting, Skill manifests with policy validation, deterministic MainAgent Scheduler, ScenarioPathGuard, and a minimal ScenarioCheckpointWriter.

## Migration Plan

PowerBanana should migrate incrementally.

1. Introduce a Skill manifest model next to the existing `SkillDefinition`.
2. Bind existing `compute_grouped_metric` and `rank_metric_values` Skills to manifests.
3. Add `SkillPolicyValidator` and run it before Step Plan execution.
4. Move hardcoded metric requirements into Skill and analysis vocabulary metadata.
5. Introduce a minimal `sales_channel_analysis` Scenario Pack for the existing path.
6. Add a Scenario Pack schema and linter before creating additional industry packs.
7. Add an Evaluation Pack schema, Evaluation Contract compiler, and EvaluationPolicyLinter.
8. Create an `EVALUATION.md` for `sales_channel_analysis` and pair it with the first Scenario Pack.
9. Let the Planner select the Scenario Pack and Skill chain, while preserving the current fixed fallback.
10. Introduce a scheduler state model for `pending`, `ready`, `running`, `succeeded`, `failed`, `skipped`, `blocked`, and `needs_human_gate`.
11. Replace the linear TaskDagExecutor loop with ready-node scheduling while keeping default concurrency at 1.
12. Add Scenario Pack `concurrency_policy` and enforce it before dispatch.
13. Add merge and fan-in validation for aggregate nodes.
14. Enable parallel execution first for low-risk read-only Skills.
15. Add one non-data-analysis Scenario Pack, such as contract review or ticket triage, to validate cross-industry reuse.
16. Add first-run Agent initialization that launches the Scenario and Evaluation builders when no enabled Scenario Pack exists.
17. Add rule maintenance change requests that create new draft pack versions instead of editing enabled packs in place.
18. Add one user-friendly builder path that collects both scenario requirements and evaluation requirements through guided questions.
19. Add scenario directory isolation checks for file resolution and cross-scenario references.
20. Add global and scenario-local Skill registries with explicit `global:` and `local:` resolution.
21. Add a promotion path for turning a scenario-local Skill into a reviewed global Skill.
22. Add ScenarioPathGuard for scenario file reads and writes.
23. Add ScenarioCheckpointWriter with scenario-local checkpoint and memory templates.
24. Add GoalJudgeEvaluator as a task-level stop-condition gate.
25. Add ScenarioDream for scenario memory consolidation.
26. Add ScenarioDistill for draft-only Skill, evaluator, golden case, and calibration case candidates.
27. Expand golden cases to assert selected Skills, required evaluators, scheduler transitions, path-guard decisions, checkpoint updates, goal-judge verdicts, and policy gates.

This path avoids a large rewrite. The existing fixed workflow becomes the first Scenario Pack.

## Testing

Tests should cover:

- Skill manifest parsing and validation.
- Scenario Pack schema and lint validation.
- Evaluation Pack schema and lint validation.
- Evaluation Contract compilation from `SCENARIO.md` and `EVALUATION.md`.
- Rejection of enabled Scenario Packs without a paired Evaluation Contract.
- Rejection of scenario-local files outside the pinned scenario directory.
- Rejection of unapproved cross-scenario references.
- Rejection of `local:` Skill references outside the pinned scenario directory.
- Rejection of another scenario's local Skill.
- Rejection of cross-scenario memory, checkpoint, notes, task progress, draft, or change file references.
- Rejection of direct writes to ScenarioCheckpointWriter-owned files by ordinary agents.
- Acceptance of approved `global:` Skill references by exact version.
- Skill promotion tests proving local Skills cannot become global without review, versioning, tests, and approval.
- Rejection of unknown or disabled Skills.
- Rejection of Skills that request unauthorized tools.
- Rejection of missing required evaluators.
- Rejection of high-risk Skills without Human Gate.
- Rejection of parallel nodes when Scenario Pack concurrency does not allow them.
- Rejection of fan-in nodes without an explicit merge policy.
- Rejection of fan-in nodes without fan-in evaluator coverage.
- Scheduler tests for ready-node selection, dependency blocking, retry limits, timeout handling, and Human Gate blocking.
- GoalJudgeEvaluator tests for satisfied, missing-evidence, impossible, judge-unavailable, and max-reentry cases.
- Blackboard tests for parallel artifact version conflicts and conflict entry creation.
- ScenarioCheckpointWriter tests for progress reconciliation, exact-form preservation, bounded checkpoint sections, and writer allowlists.
- ScenarioDream tests for memory consolidation without creating enabled rules.
- ScenarioDistill tests for draft-only candidates with enough repeated evidence and no auto-activation.
- Successful execution of the current metric-analysis flow through the new manifest path.
- Successful execution of at least one non-data-analysis Scenario Pack through the same runtime interfaces.
- Builder tests that turn user-friendly quality criteria into draft evaluation rules without enabling them automatically.
- First-run initialization tests for the no-enabled-pack state.
- Runtime tests that skip builders and load only active enabled versions.
- Rule maintenance tests that create new draft versions, show diffs, rerun affected golden and calibration cases, and require approval before activation.
- Version pinning tests proving running tasks keep their original Scenario Pack and Evaluation Contract versions.
- Scenario isolation tests proving data-analysis tasks cannot load contract-review plans, policies, evaluators, or test cases.
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

The multi-industry abstraction should be considered validated only after at least two meaningfully different Scenario Packs run through the same scheduler, Blackboard, ToolGateway, EvaluationRunner, and Human Gate interfaces without changing the core orchestration loop.

Every enabled Scenario Pack must have a paired Evaluation Contract that covers baseline checks, Skill outputs, scenario rules, fan-in behavior, report quality, golden cases, and calibration cases. A Scenario Pack without this pairing remains `draft` or `scenario_lint_passed`, never `enabled`.

Scenario and Evaluation builders should run during initialization or explicit rule-maintenance flows only. Normal task execution should use pinned, enabled Scenario Pack and Evaluation Contract versions without regenerating configuration.

Each scenario must own its generated files under its own scenario directory. Runtime file resolution must use the pinned scenario directory and deny accidental mixing of plans, DAGs, policies, evaluators, golden cases, calibration cases, drafts, or change requests from another scenario.

Global Skills may be reused across scenarios only through the approved global Skill registry. Scenario-local Skills remain isolated inside their owning scenario directory and cannot be used by other scenarios unless promoted to global through review, tests, versioning, and approval.

The framework should become more open, but the acceptance rule remains strict: no Skill result becomes trusted merely because a Skill produced it. It becomes trusted only after the framework records, evaluates, and gates it.
