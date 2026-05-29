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

## Built-In Scenarios

| Scenario | Example Signals | Notes |
|---|---|---|
| `conversion_rate_analysis` | `conversion + rate`, `转化率`, `成交率` | Supported first-path analysis. |
| `ambiguous_metric` | `best`, `perform`, `表现最好` without a specific metric | Produces a missing-metric warning. |
| `unsupported_revenue` | `revenue`, `sales`, `收入`, `营收`, `GMV` | Recognized but not supported yet. |
| `unsupported_forecast` | `forecast`, `predict`, `预测`, `预估` | Recognized but not supported yet. |
| `unknown` | No rule matched | Keeps confidence low and marks `unknown_scenario`. |

## Planner Golden Cases

Planner classification is protected by `evals/planner_cases/`. Each case is a JSON file with a user question and the expected planner intent:

```json
{
  "case_id": "conversion_rate_basic",
  "question": "Which channel has the highest conversion rate?",
  "expected_scenario": "conversion_rate_analysis",
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

All preset vocabulary is stored in `config/planner_lexicon.csv`. PowerBanana reads this CSV when `DeterministicDataFilePlanner` starts.

```csv
scenario_id,match_type,terms,confidence_base
conversion_rate_analysis,required_any,conversion+rate|conversion_rate|转化率|成交率,0.8
conversion_rate_analysis,optional,highest|best|channel|渠道|最高,
conversion_rate_analysis,negative,forecast|predict|预测|预估|join|merge,
```

CSV columns:

| Column | Meaning |
|---|---|
| `scenario_id` | Target scenario such as `conversion_rate_analysis`. |
| `match_type` | One of `required_any`, `optional`, `negative`, or `warnings`. |
| `terms` | Terms separated by `|`. Use `+` when all terms in a phrase group must appear. |
| `confidence_base` | Optional base confidence for the scenario. |

Examples:

```csv
conversion_rate_analysis,required_any,转单率,0.8
unsupported_revenue,required_any,GMV,
unsupported_revenue,warnings,unsupported_capability,
```

After editing the CSV, restart PowerBanana and run the planner golden cases.

## Expansion Governance

The safe expansion loop is:

1. Classifier returns an actual scenario.
2. Golden case, evaluator, or user feedback identifies the expected scenario.
3. `LexiconSuggestionBuilder` records suggested terms with `status = pending_review`.
4. A user reviews the suggestion.
5. Approved terms are written into `config/planner_lexicon.csv`.
6. A golden case is added for the question.
7. Regression tests must pass before the new vocabulary is treated as stable.

This prevents one accidental input from silently changing Planner behavior for everyone.

## Current Limit

The classifier only recognizes scenarios represented in rules. It should be treated as deterministic routing, not language understanding. Future LLM planners should still emit the same `PlannerIntent` shape so validators and evaluators can compare model output against lexicon-based expectations.
