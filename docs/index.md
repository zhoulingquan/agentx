# PowerBanana Documentation

PowerBanana is a v0.1 reference agent built from the AgentX v0.3 governed-agent design. It currently focuses on one deterministic Phase 1 path: answering conversion-rate questions from a CSV or simple XLSX dataset.

## Quick Start

Run locally:

```powershell
cd C:\MyProject\AgentX
python -m powerbanana.cli --interactive
```

Run with Docker:

```powershell
cd C:\MyProject\AgentX
docker build -t powerbanana .
docker run --rm -it -v ${PWD}:/data powerbanana
```

Use a CSV with these columns:

```csv
channel,visits,orders
email,100,20
ads,200,30
organic,80,8
```

Typical question:

```text
Which channel has the highest conversion rate?
```

## Project Areas

| Area | Page |
|---|---|
| Running and deployment | [Deployment](deployment.md) |
| Planner boundary | [Planner](planner.md) |
| Planner lexicon | [Planner Lexicon](planner-lexicon.md) |
| Task Blackboard | [Task Blackboard](blackboard.md) |
| Golden cases and calibration | [Regression and Calibration](regression-and-calibration.md) |
| Evaluation governance | [Evaluation Layer](evaluation-layer.md) |
| GitHub workflow | [Repository Workflow](repository-workflow.md) |
| Architecture source design | [AgentX v0.3 Design](enterprise_agent_design_v0.3.md) |

## Current Scope

Supported:

- CSV files.
- Simple XLSX files when `openpyxl` is installed.
- Single-table conversion-rate analysis.
- Deterministic no-LLM execution.
- Deterministic candidate planning before DAG execution.
- Governed planner lexicon for scenario classification.
- Task DAG trace, Blackboard events, Step trace, Evaluation result.
- Golden cases, calibration cases, and replay snapshots.

Not supported yet:

- General natural-language analytics.
- Multi-table joins.
- Database connections.
- Write-back, exports, or external actions.
- LLM planning.
