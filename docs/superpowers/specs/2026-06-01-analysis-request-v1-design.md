# AnalysisRequest v1 Design

Status: Reference  
Current authority: `docs/powerbanana-current-design.md`

## Goal

PowerBanana should turn supported user questions into a structured `AnalysisRequest` before the DAG runs, then execute simple grouped metric analysis for conversion rate, revenue, orders, and visits without using an LLM.

## Scope

In scope:

- Add an `AnalysisRequest` model with `metric`, `group_by`, `aggregation`, `rank_direction`, and `required_columns`.
- Let `DeterministicDataFilePlanner` populate `AnalysisRequest` from CSV-backed terms.
- Keep `metric_analysis` as the executable Planner scenario for supported metrics.
- Let `DataAnalysisAgent` execute the request instead of re-parsing the raw question.
- Support highest and lowest ranking for `conversion_rate`, `revenue`, `orders`, and `visits`.
- Keep unsupported, ambiguous, and unknown Planner routing unchanged.

Out of scope:

- LLM planning.
- Multi-table joins.
- User-defined formulas.
- Dashboard or UI changes.

## Architecture

Planner classification remains scenario-based through `config/planner_lexicon.csv`. A new CSV-backed analysis vocabulary maps question terms to metric and rank fields. The Planner writes the parsed request into `PlannerTrace`; the analysis agent reads that request from the Blackboard and executes deterministic skills.

The analysis agent remains the only component that reads dataset rows. It validates required columns after `data_profile_agent` creates a dataset snapshot, then uses registered skills to compute grouped values and rank them. Evaluation recomputes the same metric from rows to verify correctness.

## Behavior

| Question | Expected Request | Expected Answer |
|---|---|---|
| Which channel has the highest conversion rate? | `metric=conversion_rate`, `group_by=channel`, `rank_direction=highest` | Highest conversion rate |
| Which channel has the highest revenue? | `metric=revenue`, `group_by=channel`, `rank_direction=highest` | Highest revenue |
| Which channel has the fewest orders? | `metric=orders`, `group_by=channel`, `rank_direction=lowest` | Lowest orders |
| Which channel has the lowest visits? | `metric=visits`, `group_by=channel`, `rank_direction=lowest` | Lowest visits |

## Testing

Add focused unit tests for request extraction and skill computation. Add end-to-end golden cases for revenue, orders, visits, and lowest ranking. Existing Planner golden, end-to-end golden, and calibration suites must continue to pass.
