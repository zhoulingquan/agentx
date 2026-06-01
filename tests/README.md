# Tests

This directory contains automated tests that should stay in the repository.

| File | Purpose |
|---|---|
| `test_powerbanana.py` | Core PowerBanana behavior and report generation. |
| `test_cli.py` | CLI entry-point behavior. |
| `test_governance.py` | DAG, Blackboard, Evaluation, Planner, and governance trace checks. |
| `test_analysis_request.py` | CSV-backed AnalysisRequest extraction checks. |
| `test_vocabulary_manager.py` | LLM-style vocabulary suggestion validation and persistence checks. |
| `test_planner_evaluation.py` | Planner intent evaluation gate checks. |
| `test_planner_golden_cases.py` | Planner scenario golden case suite. |
| `test_planner_lexicon.py` | Rule-based Planner lexicon classification and extension checks. |

Run all tests from the repository root:

```powershell
python -m unittest discover -s tests
```

Do not commit generated caches such as `__pycache__`, `.pytest_cache`, coverage output, or local run artifacts.

Planner vocabulary lives in `config/planner_lexicon.csv`; metric extraction vocabulary lives in `config/analysis_terms.csv`. After editing either CSV, run the Planner lexicon and golden case tests.
