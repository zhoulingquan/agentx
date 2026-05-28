# Planner

PowerBanana now has an explicit Planner boundary before DAG execution.

The current implementation is deterministic and does not call an LLM. It classifies the question with the governed planner lexicon, creates the same Phase 1 data-file analysis plan every run, records a Planner trace on the Task Blackboard, then hands the candidate plan to `PlanValidator`.

## Runtime Flow

| Stage | Owner | Output | Notes |
|---|---|---|---|
| User request | `PowerBananaAgent` | File path and question | The request is still treated as untrusted input. |
| Candidate planning | `DeterministicDataFilePlanner` | `PlannerResult` | Produces a candidate `TaskPlan` plus `PlannerTrace`. |
| Planner evaluation | `PlannerIntentEvaluator` | `planner_evaluation` | Checks intent consistency, confidence, and required warnings. |
| Validation | `PlanValidator` | Frozen `TaskPlan` | Checks known agents, runtime modes, duplicate node ids, and dependencies. |
| Scheduling | `TaskDagExecutor` | DAG trace | Executes only the frozen plan. |
| Reporting | `ReportAgent` | `PowerBananaReport` | Includes both `task_plan` and `planner_trace`. |

## Current Planner

`DeterministicDataFilePlanner` is intentionally small:

- It sets `planner_mode` to `deterministic_no_llm`.
- It classifies questions into known scenarios through `PlannerClassifier`.
- It emits a candidate plan for `data_profile_agent -> data_analysis_agent -> report_agent`.
- It does not execute tools, read data, mutate files, or decide final answers.
- It writes an auditable `planner_trace` Blackboard entry with `intent`, `confidence`, matched signals, warnings, and lexicon version before validation.
- Its trace is evaluated before the candidate plan is frozen.

This gives PowerBanana the same architectural slot that a future LLM planner will use, without introducing model nondeterminism yet.

## Extension Direction

The next planner improvements should keep the same contract:

1. Produce a candidate `TaskPlan`.
2. Produce a `PlannerTrace` explaining the decision.
3. Let `PlanValidator` freeze or reject the plan.
4. Let `TaskDagExecutor` execute only frozen plans.

Future planner variants can select scenarios, add plan warnings, or call an LLM. They should still avoid direct tool execution and should keep all planner decisions visible through the Blackboard and final report.

See [Planner Lexicon](planner-lexicon.md) for the governed vocabulary and expansion flow.
