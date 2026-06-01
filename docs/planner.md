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
| Vocabulary suggestion | `DataAnalysisAgent` | `vocabulary_suggestion_gate` | Uses an injected advisor only when metric analysis needs a missing vocabulary term. |
| Validation | `PlanValidator` | Frozen `TaskPlan` | Rejects malformed plans before execution. |
| Scheduling | `TaskDagExecutor.from_plan` | DAG trace | Builds executors only from frozen plans. |
| Reporting | `ReportAgent` | `PowerBananaReport` | Includes both `task_plan` and `planner_trace`. |

## Current Planner

`DeterministicDataFilePlanner` is intentionally small:

- It sets `planner_mode` to `deterministic_no_llm`.
- It loads `config/planner_lexicon.csv` at startup and classifies questions into known scenarios through `PlannerClassifier`.
- It loads `config/analysis_terms.csv` and parses `AnalysisRequest` for executable `metric_analysis` questions.
- If a metric is recognized but the grouping field is missing from the active vocabulary, it records `needs_vocabulary_suggestion` for the analysis stage.
- It emits a candidate plan for `data_profile_agent -> data_analysis_agent -> report_agent`.
- It does not execute tools, read data, mutate files, or decide final answers.
- It writes an auditable `planner_trace` Blackboard entry with `intent`, `confidence`, matched signals, warnings, and lexicon version before validation.
- Its trace is evaluated before the candidate plan is frozen.
- If planner evaluation blocks, PowerBanana returns a structured blocked report without loading the dataset or running DAG nodes.
- If the intent is not executable, PowerBanana records a `planner_routing_gate`, creates a clarification gate, and returns without loading the dataset or running DAG nodes.

This gives PowerBanana the same architectural slot that a future LLM planner will use, without introducing model nondeterminism yet.

## LLM-Assisted Vocabulary

PowerBanana can accept an injected `LLMVocabularyAdvisor`. The advisor is a candidate generator only: it receives the user question, uploaded dataset columns, and active analysis terms, then may propose a `VocabularySuggestion`.

The suggestion must pass deterministic validation before it is shown to the user:

- The target must be `config/analysis_terms.csv`.
- The suggestion kind must be supported.
- The suggested value must exist in the dataset columns.
- The suggested terms must not already be active.

Accepted suggestions are recorded on the Blackboard, persisted to `runs/vocabulary_suggestions.jsonl`, and returned through a human approval gate. They are not written to CSV automatically and are not executed as an analysis request in the same run.

Review suggestions from the CLI:

```powershell
python -m powerbanana.cli vocab list
python -m powerbanana.cli vocab approve vocab_000001 --dry-run
python -m powerbanana.cli vocab approve vocab_000001
python -m powerbanana.cli vocab promote-golden vocab_000001 --question "哪个地区收入最高？" --matched-signal "收入" --expected-metric revenue
python -m powerbanana.cli vocab promote-e2e-golden vocab_000001 --dataset samples\region_revenue.csv --question "哪个地区收入最高？" --expected-metric revenue
python -m powerbanana.cli vocab reject vocab_000001 --note "Not needed"
```

`--dry-run` prints the exact CSV row without mutating files. Approval appends the reviewed term to `config/analysis_terms.csv`, reloads that CSV, records `validation_status` and `validation_output` in the JSONL suggestion record, and writes a local golden case draft under `runs/golden_case_drafts/`. Rejection updates only the local JSONL review log.

`promote-golden` turns a reviewed draft into a formal Planner golden case under `evals/planner_cases/`. Planner golden cases can now check selected `AnalysisRequest` fields with `expected_analysis_request`, so a promoted group-by term can assert `group_by = region`, not only the high-level scenario.

`promote-e2e-golden` turns a reviewed draft plus a synthetic CSV into a formal end-to-end golden case under `evals/golden_cases/`. It runs PowerBanana first, captures the completed answer and analysis result, copies the CSV fixture, then validates the generated golden case before keeping it.

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
