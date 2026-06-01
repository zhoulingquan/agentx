# Planner

PowerBanana now has an explicit Planner boundary before DAG execution.

The current implementation is deterministic and does not call an LLM. It classifies the question with the governed planner lexicon from `config/planner_lexicon.csv`, parses supported metric terms from `config/analysis_terms.csv`, creates the same Phase 1 data-file analysis plan every run, records a Planner trace on the Task Blackboard, evaluates that trace, routes non-executable scenarios to clarification, then hands only executable passing candidates to `PlanValidator`.

## Runtime Flow

| Stage | Owner | Output | Notes |
|---|---|---|---|
| User request | `PowerBananaAgent` | File path and question | The request is still treated as untrusted input. |
| Candidate planning | `DeterministicDataFilePlanner` | `PlannerResult` | Produces a candidate `TaskPlan` plus `PlannerTrace` and optional `AnalysisRequest`. |
| Planner evaluation | `PlannerIntentEvaluator` | `planner_evaluation` | Checks intent consistency, confidence, and required warnings. |
| Planner gate | `PowerBananaAgent` | `blocked` report or continued execution | Blocks before validation and DAG execution when planner evaluation returns `block`. |
| Planner routing | `PowerBananaAgent` | `planner_routing_gate` | Routes ambiguous, unsupported, or unknown scenarios to `needs_clarification` before dataset loading. |
| Validation | `PlanValidator` | Frozen `TaskPlan` | Rejects malformed plans before execution. |
| Scheduling | `TaskDagExecutor.from_plan` | DAG trace | Builds executors only from frozen plans. |
| Reporting | `ReportAgent` | `PowerBananaReport` | Includes both `task_plan` and `planner_trace`. |

## Current Planner

`DeterministicDataFilePlanner` is intentionally small:

- It sets `planner_mode` to `deterministic_no_llm`.
- It loads `config/planner_lexicon.csv` at startup and classifies questions into known scenarios through `PlannerClassifier`.
- It loads `config/analysis_terms.csv` and parses `AnalysisRequest` for executable `metric_analysis` questions.
- It emits a candidate plan for `data_profile_agent -> data_analysis_agent -> report_agent`.
- It does not execute tools, read data, mutate files, or decide final answers.
- It writes an auditable `planner_trace` Blackboard entry with `intent`, `confidence`, matched signals, warnings, and lexicon version before validation.
- Its trace is evaluated before the candidate plan is frozen.
- If planner evaluation blocks, PowerBanana returns a structured blocked report without loading the dataset or running DAG nodes.
- If the intent is not executable, PowerBanana records a `planner_routing_gate`, creates a clarification gate, and returns without loading the dataset or running DAG nodes.

This gives PowerBanana the same architectural slot that a future LLM planner will use, without introducing model nondeterminism yet.

## Extension Direction

The next planner improvements should keep the same contract:

1. Produce a candidate `TaskPlan`.
2. Produce a `PlannerTrace` explaining the decision.
3. Let `PlannerIntentEvaluator` gate the candidate.
4. Route non-executable scenarios before data access.
5. Let `PlanValidator` freeze or reject only executable passing plans.
6. Let `TaskDagExecutor` execute only frozen plans.

Future planner variants can select scenarios, add plan warnings, or call an LLM. They should still avoid direct tool execution and should keep all planner decisions visible through the Blackboard and final report.

See [Planner Lexicon](planner-lexicon.md) for the governed vocabulary and expansion flow.

## Plan Validation

`PlanValidator` rejects candidate plans when:

- The plan is empty.
- Node ids are duplicated.
- A node references an unknown agent.
- A node runtime mode does not match the registered agent profile.
- A dependency points to an unknown node.
- A node repeats the same dependency.
- The dependency graph contains a cycle.
- The graph has zero or multiple root nodes.
- A `data_file_analysis` plan does not match the expected profile -> analysis -> report pattern.

`TaskDagExecutor.from_plan` adds a final defense by refusing any plan whose status is not `frozen`.
