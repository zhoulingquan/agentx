# Repository Workflow

This workspace currently contains local project files. To synchronize with GitHub, initialize Git and add a GitHub remote.

## First-Time Setup

```powershell
cd C:\MyProject\AgentX
git init
git branch -M main
git remote add origin https://github.com/zhoulingquan/agentx.git
```

Then commit and push:

```powershell
git add .
git commit -m "Initial PowerBanana project"
git push -u origin main
```

## Expected Change Workflow

For each future change:

1. Update source code and tests.
2. Update documentation under `docs/` when behavior changes.
3. Run unit tests, golden cases, and calibration cases.
4. Commit the change.
5. Push to GitHub.

Suggested verification commands:

```powershell
python -m unittest discover -s tests
python -c "from pathlib import Path; from powerbanana.evals import GoldenCaseRunner; print(GoldenCaseRunner(Path('evals/golden_cases')).run_all())"
python -c "from pathlib import Path; from powerbanana.evals import CalibrationRunner; print(CalibrationRunner(Path('evals/calibration_cases')).run_all())"
```

## GitHub Pages

The documentation is prepared for GitHub Pages from the `docs/` directory. In GitHub:

1. Open repository settings.
2. Go to Pages.
3. Set source to `Deploy from a branch`.
4. Select branch `main`.
5. Select folder `/docs`.

After the next push, GitHub Pages will publish the documentation site.
