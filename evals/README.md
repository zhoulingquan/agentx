# Evaluation Assets

This directory contains synthetic evaluation data used to protect PowerBanana behavior as the agent evolves.

| Directory | Purpose |
|---|---|
| `planner_cases/` | Planner scenario-classification golden cases. |
| `golden_cases/` | User-question regression cases with expected status, answer fragments, and governance signals. |
| `calibration_cases/` | Evaluation-layer calibration cases for pass, warning, human-review, and block decisions. |
| `fixtures/` | Shared synthetic datasets for tests and examples. |

These files should stay in the repository because they are part of the test contract. Do not place real user uploads, private business data, or ad hoc local experiment files here.

Run planner golden cases:

```powershell
python -c "from pathlib import Path; from powerbanana.evals import PlannerGoldenCaseRunner; print(PlannerGoldenCaseRunner(Path('evals/planner_cases')).run_all())"
```

Run golden cases:

```powershell
python -c "from pathlib import Path; from powerbanana.evals import GoldenCaseRunner; print(GoldenCaseRunner(Path('evals/golden_cases')).run_all())"
```

Run calibration cases:

```powershell
python -c "from pathlib import Path; from powerbanana.evals import CalibrationRunner; print(CalibrationRunner(Path('evals/calibration_cases')).run_all())"
```
