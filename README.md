# PowerBanana

PowerBanana is the v0.1 reference agent built from the AgentX v0.3 design.

It implements a narrow, auditable data-analysis workflow:

1. Load one CSV or simple XLSX dataset.
2. Create a dataset snapshot.
3. Profile basic schema and missing values.
4. Scan uploaded cells as untrusted data for prompt-injection patterns.
5. Execute controlled analysis steps through registered skill-like functions.
6. Recompute and evaluate the result before returning a report.

The v0.1 runtime includes explicit sub-agents:

| Sub-agent | Runtime | Responsibility |
|---|---|---|
| `data_profile_agent` | `workflow` | Load the file, create the dataset snapshot, profile columns, and scan untrusted cells. |
| `data_analysis_agent` | `autonomous` L2 | Execute the controlled Step Plan through skill-like functions. |
| `report_agent` | `workflow` | Run final consistency checks and produce the structured report. |

The runtime now includes the first governance pieces from the v0.3 design:

- `TaskDagExecutor` schedules `data_profile_agent -> data_analysis_agent -> report_agent`.
- `TaskBlackboard` records event log entries for blackboard creation, DAG transitions, artifact writes, agent completion, and skill execution.
- `SkillRegistry` exposes versioned skills such as `compute_grouped_metric@0.1.0` and `rank_metric_values@0.1.0`.
- `AutonomyPolicy` enforces the L2 analysis agent's allowed skills and maximum step count.

PowerBanana v0.1 intentionally supports a small first path: answering which channel has the highest conversion rate from `channel`, `visits`, and `orders` columns.

## Run

```powershell
python -m powerbanana.cli path\to\data.csv "Which channel has the highest conversion rate?"
```

The command prints a structured JSON report containing the answer, dataset snapshot, security findings, step trace, evaluation result, and limitations.

## Test

```powershell
python -m unittest discover -s tests
```

## Scope

Supported in v0.1:

- CSV files.
- Simple XLSX files when `openpyxl` is installed.
- Single-table analysis.
- Conversion-rate question answering.
- Step trace and deterministic evaluation.

Not supported yet:

- Multi-table joins.
- Database connections.
- Write-back, export, or external actions.
- Complex forecasting or BI dashboards.
