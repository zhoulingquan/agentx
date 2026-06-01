# Tests

This directory contains automated tests that should stay in the repository.

| File | Purpose |
|---|---|
| `test_powerbanana.py` | Core PowerBanana behavior and report generation. |
| `test_cli.py` | CLI entry-point behavior. |
| `test_governance.py` | DAG, Blackboard, Evaluation, Planner, and governance trace checks. |
| `test_analysis_request.py` | CSV-backed AnalysisRequest extraction checks. |
| `test_golden_promotion.py` | Golden case draft promotion checks. |
| `test_vocabulary_manager.py` | LLM-style vocabulary suggestion validation, approval, and persistence checks. |
| `test_vocabulary_advisor_golden_cases.py` | Vocabulary advisor golden cases for accepted and rejected LLM-style suggestions. |
| `test_llm_vocabulary.py` | JSON LLM vocabulary adapter, environment wiring, and audit metadata checks. |
| `test_planner_evaluation.py` | Planner intent evaluation gate checks. |
| `test_planner_golden_cases.py` | Planner scenario golden case suite. |
| `test_planner_lexicon.py` | Rule-based Planner lexicon classification and extension checks. |

Run all tests from the repository root:

```powershell
python -m unittest discover -s tests
```

Do not commit generated caches such as `__pycache__`, `.pytest_cache`, coverage output, or local run artifacts.

Planner vocabulary lives in `config/planner_lexicon.csv`; metric extraction vocabulary lives in `config/analysis_terms.csv`. Pending LLM-style vocabulary suggestions live locally in `runs/vocabulary_suggestions.jsonl` and can be reviewed with `python -m powerbanana.cli vocab list`. Preview fresh suggestions with `python -m powerbanana.cli vocab suggest --question "..." --columns region,revenue --dry-run`. Preview approvals with `python -m powerbanana.cli vocab approve vocab_000001 --dry-run`; approved suggestions write local draft files under `runs/golden_case_drafts/`. Promote reviewed Planner drafts with `python -m powerbanana.cli vocab promote-golden vocab_000001 --question "..." --matched-signal "..."`; promote full synthetic CSV cases with `python -m powerbanana.cli vocab promote-e2e-golden vocab_000001 --dataset sample.csv --question "..."`. After approving a suggestion or editing either CSV, run the Planner lexicon, vocabulary advisor, and golden case tests.
