# Repository Hygiene

PowerBanana keeps tests and synthetic evaluation assets in Git so every machine and every GitHub checkout can reproduce the same behavior.

## What Stays In Git

| Path | Keep | Reason |
|---|---|---|
| `powerbanana/` | Yes | Runtime source code. |
| `config/planner_lexicon.csv` | Yes | User-editable preset Planner vocabulary. |
| `tests/` | Yes | Automated regression tests. |
| `evals/golden_cases/` | Yes | Synthetic user-question golden cases. |
| `evals/calibration_cases/` | Yes | Synthetic evaluation calibration cases. |
| `evals/fixtures/` | Yes | Shared synthetic fixtures. |
| `docs/` | Yes | GitHub Pages documentation. |

## What Stays Local

| Pattern | Reason |
|---|---|
| `runs/` | Local evaluation snapshots, replay output, and vocabulary suggestion review logs. |
| `local_data/`, `private_data/`, `user_uploads/` | Real or private datasets should not be committed. |
| `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` | Tool caches. |
| `.coverage`, `coverage.xml`, `htmlcov/` | Coverage reports generated locally or in CI. |
| `*.log` | Local runtime logs. |

## Practical Rule

Commit files that define expected behavior. Ignore files that are produced by running tools, contain private data, or only matter on one computer.

Before pushing larger changes, run:

```powershell
git status --short
python -m unittest discover -s tests
```
