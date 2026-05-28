# Deployment

## Local Python

```powershell
cd C:\MyProject\AgentX
python -m powerbanana.cli --interactive
```

Single-run JSON mode:

```powershell
python -m powerbanana.cli evals\golden_cases\conversion_rate_basic.csv "Which channel has the highest conversion rate?"
```

## Editable Install

```powershell
cd C:\MyProject\AgentX
python -m pip install -e .
powerbanana
```

## Docker

Build:

```powershell
docker build -t powerbanana .
```

Run:

```powershell
docker run --rm -it -v ${PWD}:/data powerbanana
```

Inside the container, use mounted paths such as:

```text
/data/evals/golden_cases/conversion_rate_basic.csv
```

## Verification

```powershell
python -m unittest discover -s tests
python -c "from pathlib import Path; from powerbanana.evals import GoldenCaseRunner; print(GoldenCaseRunner(Path('evals/golden_cases')).run_all())"
python -c "from pathlib import Path; from powerbanana.evals import CalibrationRunner; print(CalibrationRunner(Path('evals/calibration_cases')).run_all())"
```
