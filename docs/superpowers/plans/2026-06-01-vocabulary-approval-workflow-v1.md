# Vocabulary Approval Workflow v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local approval workflow for LLM-style vocabulary suggestions so users can list, approve, reject, and persist reviewed terms safely.

**Architecture:** Add a JSONL-backed repository for pending vocabulary suggestions, wire it into `VocabularyManager` and `DataAnalysisAgent`, and expose `powerbanana vocab` CLI commands. Approval appends to `config/analysis_terms.csv`; rejection updates only the review log.

**Tech Stack:** Python dataclasses, JSONL persistence, argparse subcommands, CSV vocabulary append, `unittest`.

---

### Task 1: Repository Persistence

**Files:**
- Modify: `powerbanana/vocabulary.py`
- Test: `tests/test_vocabulary_manager.py`

- [x] **Step 1: Write failing tests**

```python
def test_repository_saves_pending_suggestion_with_stable_id(self):
    path = Path(tempfile.NamedTemporaryFile(delete=False).name)
    repo = VocabularySuggestionRepository(path)
    record = repo.save_pending(self.region_suggestion())
    self.assertEqual(record.suggestion_id, "vocab_000001")
    self.assertEqual(record.status, "pending_user_approval")
    self.assertEqual(repo.list_records()[0].suggestion.value, "region")
```

- [x] **Step 2: Verify red**

Run: `python -m unittest tests.test_vocabulary_manager.VocabularyManagerTests.test_repository_saves_pending_suggestion_with_stable_id`

Expected: FAIL because `VocabularySuggestionRepository` is not defined.

- [x] **Step 3: Implement repository**

Add `VocabularySuggestionRecord`, `VocabularySuggestionRepository.save_pending`, `list_records`, `approve`, and `reject`.

- [x] **Step 4: Verify green**

Run: `python -m unittest tests.test_vocabulary_manager`

Expected: PASS.

### Task 2: CLI Approval Commands

**Files:**
- Modify: `powerbanana/cli.py`
- Test: `tests/test_cli.py`

- [x] **Step 1: Write failing tests**

```python
def test_vocab_list_prints_pending_suggestions(self):
    store_path = self.write_pending_suggestion()
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = cli.main(["vocab", "list", "--store", str(store_path)])
    self.assertEqual(exit_code, 0)
    self.assertIn("vocab_000001", stdout.getvalue())
```

- [x] **Step 2: Verify red**

Run: `python -m unittest tests.test_cli.PowerBananaCliTests.test_vocab_list_prints_pending_suggestions`

Expected: FAIL because `vocab` subcommands are not implemented.

- [x] **Step 3: Implement CLI**

Add `vocab list`, `vocab approve`, and `vocab reject` subcommands with `--store` and `--analysis-terms` options.

- [x] **Step 4: Verify green**

Run: `python -m unittest tests.test_cli`

Expected: PASS.

### Task 3: Runtime Persistence

**Files:**
- Modify: `powerbanana/vocabulary.py`
- Modify: `powerbanana/subagents.py`
- Test: `tests/test_powerbanana.py`

- [x] **Step 1: Write failing test**

```python
def test_vocabulary_suggestion_is_persisted_for_review(self):
    store = VocabularySuggestionRepository(path)
    manager = VocabularyManager(FakeVocabularyAdvisor(), default_analysis_terms(), suggestion_repository=store)
    analysis_agent = DataAnalysisAgent(vocabulary_manager=manager)
    report = PowerBananaAgent(data_analysis_agent=analysis_agent).answer(path, "哪个地区收入最高？")
    self.assertEqual(report.status, "needs_clarification")
    self.assertEqual(store.list_records()[0].suggestion.value, "region")
```

- [x] **Step 2: Verify red**

Run: `python -m unittest tests.test_powerbanana.PowerBananaAgentTests.test_vocabulary_suggestion_is_persisted_for_review`

Expected: FAIL because valid suggestions are not persisted.

- [x] **Step 3: Implement runtime persistence**

Let `VocabularyManager` accept a repository and expose `record_pending`; call it after validation and before human gate creation.

- [x] **Step 4: Verify green**

Run: `python -m unittest tests.test_powerbanana`

Expected: PASS.

### Task 4: Documentation And Regression

**Files:**
- Modify: `README.md`
- Modify: `docs/planner-lexicon.md`
- Modify: `docs/planner.md`
- Modify: `tests/README.md`

- [x] **Step 1: Document CLI workflow**

Add the `powerbanana vocab list`, `approve`, and `reject` commands.

- [x] **Step 2: Run complete verification**

Run:

```powershell
python -m unittest discover -s tests
python -c "from pathlib import Path; from powerbanana.evals import PlannerGoldenCaseRunner; print(PlannerGoldenCaseRunner(Path('evals/planner_cases')).run_all())"
python -c "from pathlib import Path; from powerbanana.evals import GoldenCaseRunner; print(GoldenCaseRunner(Path('evals/golden_cases')).run_all())"
python -c "from pathlib import Path; from powerbanana.evals import CalibrationRunner; print(CalibrationRunner(Path('evals/calibration_cases')).run_all())"
```

Expected: all tests and golden suites pass.
