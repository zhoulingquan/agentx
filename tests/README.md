# Tests

This directory contains automated tests that should stay in the repository.

| File | Purpose |
|---|---|
| `test_powerbanana.py` | Core PowerBanana behavior and report generation. |
| `test_cli.py` | CLI entry-point behavior. |
| `test_governance.py` | DAG, Blackboard, Evaluation, Planner, and governance trace checks. |
| `test_planner_lexicon.py` | Rule-based Planner lexicon classification and extension checks. |

Run all tests from the repository root:

```powershell
python -m unittest discover -s tests
```

Do not commit generated caches such as `__pycache__`, `.pytest_cache`, coverage output, or local run artifacts.
