# Planner Lexicon

PowerBanana can classify common question scenarios without an LLM by using a governed planner lexicon.

The lexicon is not just a keyword list. It combines scenario rules, phrase groups, negative terms, confidence scoring, and pending suggestions that require user review before they become active behavior.

## Components

| Component | Purpose |
|---|---|
| `PlannerLexicon` | Versioned set of scenario rules. |
| `ScenarioRule` | Defines required phrase groups, optional signals, negative terms, base confidence, and warnings. |
| `PlannerClassifier` | Matches a user question against the lexicon and returns `PlannerIntent`. |
| `LexiconStore` | Loads `config/planner_lexicon.csv` and builds scenario rules. |
| `LexiconSuggestionBuilder` | Records proposed terms from misclassified questions as `pending_review`. |
| `LLMVocabularyAdvisor` | Optional candidate source for missing analysis terms. |
| `VocabularySuggestionValidator` | Checks suggested terms before user approval. |

## Built-In Scenarios

| Scenario | Example Signals | Notes |
|---|---|---|
| `metric_analysis` | `conversion + rate`, `revenue`, `orders`, `visits`, `转化率`, `营收` | Supported first-path analysis. |
| `ambiguous_metric` | `best`, `perform`, `表现最好` without a specific metric | Produces a missing-metric warning. |
| `unsupported_forecast` | `forecast`, `predict`, `预测`, `预估` | Recognized but not supported yet. |
| `unknown` | No rule matched | Keeps confidence low and marks `unknown_scenario`. |

## Planner Golden Cases

Planner classification is protected by `evals/planner_cases/`. Each case is a JSON file with a user question and the expected planner intent:

```json
{
  "case_id": "conversion_rate_basic",
  "question": "Which channel has the highest conversion rate?",
  "expected_scenario": "metric_analysis",
  "expected_min_confidence": 0.8,
  "expected_matched_signals_contains": ["conversion", "rate"]
}
```

Run the suite:

```powershell
python -c "from pathlib import Path; from powerbanana.evals import PlannerGoldenCaseRunner; print(PlannerGoldenCaseRunner(Path('evals/planner_cases')).run_all())"
```

Add a planner golden case whenever a new user phrasing, synonym, unsupported capability, or ambiguity pattern is introduced.

## User-Editable CSV

Scenario vocabulary is stored in `config/planner_lexicon.csv`. Metric extraction vocabulary is stored in `config/analysis_terms.csv`. PowerBanana reads both CSV files when `DeterministicDataFilePlanner` starts.

```csv
scenario_id,match_type,terms,confidence_base
metric_analysis,required_any,conversion+rate|conversion_rate|revenue|orders|visits,0.8
metric_analysis,optional,highest|best|lowest|fewest|channel,
metric_analysis,negative,forecast|predict|join|merge,
```

CSV columns:

| Column | Meaning |
|---|---|
| `scenario_id` | Target scenario such as `metric_analysis`. |
| `match_type` | One of `required_any`, `optional`, `negative`, or `warnings`. |
| `terms` | Terms separated by `|`. Use `+` when all terms in a phrase group must appear. |
| `confidence_base` | Optional base confidence for the scenario. |

Examples:

```csv
metric_analysis,required_any,net sales,0.8
```

```csv
kind,value,terms,aggregation,required_columns
metric,revenue,revenue|sales|gmv,sum,channel|revenue
rank_direction,lowest,lowest|fewest|least,,
```

After editing either CSV, restart PowerBanana and run the planner golden cases plus end-to-end golden cases.

## LLM-Assisted Suggestions

When `AnalysisRequestParser` recognizes a metric but cannot identify the grouping field from `config/analysis_terms.csv`, PowerBanana can ask an injected `LLMVocabularyAdvisor` for a candidate term. This is designed for cases like:

```text
哪个地区收入最高？
```

If the uploaded dataset has a `region` column, the advisor might suggest:

```json
{
  "target_csv": "config/analysis_terms.csv",
  "kind": "group_by",
  "value": "region",
  "terms": ["地区", "区域"],
  "status": "pending_user_approval"
}
```

The suggestion is recorded as a `vocabulary_suggestion` Blackboard entry, persisted to `runs/vocabulary_suggestions.jsonl`, and shown through a human gate. It is not written to CSV until a user approves it and regression tests are run.

Review commands:

```powershell
python -m powerbanana.cli vocab list
python -m powerbanana.cli vocab approve vocab_000001 --dry-run
python -m powerbanana.cli vocab approve vocab_000001
python -m powerbanana.cli vocab promote-golden vocab_000001 --question "哪个地区收入最高？" --matched-signal "收入" --expected-metric revenue
python -m powerbanana.cli vocab promote-e2e-golden vocab_000001 --dataset samples\region_revenue.csv --question "哪个地区收入最高？" --expected-metric revenue
python -m powerbanana.cli vocab reject vocab_000001 --note "Rejected after review"
```

Approval validation stores three extra fields on the local suggestion record:

| Field | Meaning |
|---|---|
| `validation_status` | `passed` or `failed` after approval validation. |
| `validation_output` | Messages from reloading and checking `config/analysis_terms.csv`. |
| `golden_case_draft_path` | Local JSON draft under `runs/golden_case_drafts/`. |

Promoted Planner golden cases may include an `expected_analysis_request` block:

```json
{
  "expected_analysis_request": {
    "metric": "revenue",
    "group_by": "region"
  }
}
```

This lets a vocabulary expansion prove that the Planner can parse the approved field, not only classify the broad scenario.

End-to-end promotion needs a synthetic CSV fixture:

```powershell
python -m powerbanana.cli vocab promote-e2e-golden vocab_000001 --dataset samples\region_revenue.csv --question "哪个地区收入最高？" --expected-metric revenue
```

This command runs the full agent, captures the completed answer, copies the dataset into `evals/golden_cases/`, writes the matching JSON expectation file, and validates the generated case before keeping it.

## Expansion Governance

The safe expansion loop is:

1. Classifier returns an actual scenario.
2. Golden case, evaluator, or user feedback identifies the expected scenario.
3. `LexiconSuggestionBuilder` or an injected advisor records suggested terms with `status = pending_user_approval`.
4. A user reviews the pending suggestion with `powerbanana vocab list`.
5. The user previews the exact row with `powerbanana vocab approve <suggestion_id> --dry-run`.
6. Approved terms are written into `config/analysis_terms.csv` with `powerbanana vocab approve <suggestion_id>`.
7. The approval command validates the CSV and writes a local golden case draft.
8. Rejected suggestions remain in the local JSONL audit log and do not change CSV vocabulary.
9. A reviewed Planner golden case is promoted with `powerbanana vocab promote-golden <suggestion_id>`.
10. A reviewed end-to-end golden case is promoted with `powerbanana vocab promote-e2e-golden <suggestion_id> --dataset <synthetic.csv>`.
11. Regression tests must pass before the new vocabulary is treated as stable.

This prevents one accidental input from silently changing Planner behavior for everyone.

## Current Limit

The classifier only recognizes scenarios represented in rules. It should be treated as deterministic routing, not language understanding. Future LLM planners should still emit the same `PlannerIntent` shape so validators and evaluators can compare model output against lexicon-based expectations.
