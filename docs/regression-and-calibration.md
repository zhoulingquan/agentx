# Regression and Calibration

PowerBanana uses three test suites with different purposes.

## Planner Golden Cases

Planner golden cases test deterministic scenario classification before the DAG runs. They protect the governed lexicon from accidental drift as synonyms and unsupported capability patterns are added.

Run:

```powershell
python -c "from pathlib import Path; from powerbanana.evals import PlannerGoldenCaseRunner; print(PlannerGoldenCaseRunner(Path('evals/planner_cases')).run_all())"
```

Current coverage:

| Case Type | Purpose |
|---|---|
| Conversion-rate phrasing | English and Chinese synonyms route to `conversion_rate_analysis` |
| Ambiguous performance phrasing | Missing metric routes to `ambiguous_metric` |
| Unsupported revenue phrasing | Revenue-like requests route to `unsupported_revenue` |
| Unsupported forecast phrasing | Forecast and prediction requests route to `unsupported_forecast` |
| Unknown phrasing | Unmatched questions route to `unknown` |

## Golden Cases

Golden cases test end-to-end product behavior: dataset input, user question, answer, status, traces, security findings, and evaluation result.

Run:

```powershell
python -c "from pathlib import Path; from powerbanana.evals import GoldenCaseRunner; print(GoldenCaseRunner(Path('evals/golden_cases')).run_all())"
```

Current coverage:

| Case | Purpose |
|---|---|
| `conversion_rate_basic` | Normal success path |
| `conversion_rate_tie_first_seen` | Tie behavior |
| `missing_orders_column` | Missing required field |
| `missing_visits_column` | Missing required field |
| `zero_visits_no_valid_denominator` | No valid denominator |
| `nonnumeric_rows_skipped` | Bad rows skipped with limitation |
| `prompt_injection_cell` | Cell-level prompt injection finding |
| `ambiguous_performance_question` | Clarification gate |
| `unsupported_revenue_question` | Unsupported question |
| `empty_csv` | Empty dataset boundary |

## Calibration Cases

Calibration cases test whether evaluators judge correctly. They do not need to run the full agent; instead, they feed structured `EvaluationContext` fixtures directly into the Evaluation Layer.

Run:

```powershell
python -c "from pathlib import Path; from powerbanana.evals import CalibrationRunner; print(CalibrationRunner(Path('evals/calibration_cases')).run_all())"
```

Current coverage:

| Case | Expected Behavior |
|---|---|
| `valid_analysis_should_pass` | Correct result passes |
| `wrong_top_value_should_block` | Wrong top value blocks |
| `missing_evidence_should_block` | Missing evidence blocks |
| `unsafe_security_action_should_human_review` | Unsafe security handling escalates |
| `safe_prompt_injection_should_warn` | Safe handling passes with warning |
| `dataset_version_mismatch_should_block` | Dataset version mismatch blocks |

Calibration summary tracks:

- `false_pass`
- `false_fail`
- `escalation_miss`
- `over_escalation`
