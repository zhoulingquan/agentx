# Vocabulary Advisor Evals v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a governed evaluation suite and manual dry-run command for LLM vocabulary suggestions.

**Architecture:** Keep LLM vocabulary generation behind `LLMVocabularyAdvisor` and validate every candidate through `VocabularyManager`. Add `evals/vocabulary_cases/` for deterministic fake-LLM responses and a `VocabularyAdvisorGoldenCaseRunner` that verifies accepted/rejected suggestions without calling a real network service. Add `powerbanana vocab suggest` so users can inspect a configured advisor result before recording or approving anything.

**Tech Stack:** Python standard library, `unittest`, existing PowerBanana CLI, existing `JsonLLMVocabularyAdvisor`, `VocabularyManager`, and CSV analysis term loader.

---

### Task 1: Vocabulary Advisor Golden Cases

**Files:**
- Create: `tests/test_vocabulary_advisor_golden_cases.py`
- Create: `evals/vocabulary_cases/*.json`
- Modify: `powerbanana/evals.py`

- [ ] **Step 1: Write failing tests**

Add tests that expect `VocabularyAdvisorGoldenCaseRunner(Path("evals/vocabulary_cases")).run_all()` to pass all built-in cases and to fail a temporary case when the expected suggestion value is wrong.

- [ ] **Step 2: Add deterministic cases**

Create cases for valid `region`, hallucinated `country`, duplicate `channel`, unsupported `metric`, model decline, and incomplete JSON response.

- [ ] **Step 3: Implement runner**

Create `VocabularyAdvisorGoldenCaseResult`, `VocabularyAdvisorGoldenCaseSummary`, a fake JSON client, and a runner that feeds each case through `JsonLLMVocabularyAdvisor` and `VocabularyManager`.

- [ ] **Step 4: Verify**

Run: `python -m unittest tests.test_vocabulary_advisor_golden_cases`

Expected: pass.

### Task 2: CLI Suggest Dry Run

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `powerbanana/cli.py`

- [ ] **Step 1: Write failing tests**

Add CLI tests for `python -m powerbanana.cli vocab suggest --question ... --columns region,revenue --dry-run` and for `--dataset` column discovery. Patch `vocabulary_advisor_from_env` with a deterministic fake advisor.

- [ ] **Step 2: Implement command**

Add `vocab suggest` with `--question`, `--columns`, `--dataset`, `--analysis-terms`, `--store`, and `--dry-run`. Dry-run prints validation output and never records to the JSONL store. Non-dry-run records a valid pending suggestion through `VocabularySuggestionRepository`.

- [ ] **Step 3: Verify**

Run: `python -m unittest tests.test_cli`

Expected: pass.

### Task 3: Documentation And Regression

**Files:**
- Modify: `README.md`
- Modify: `docs/planner-lexicon.md`
- Modify: `docs/regression-and-calibration.md`
- Modify: `docs/index.md`

- [ ] **Step 1: Document usage**

Document the vocabulary advisor golden suite and `vocab suggest --dry-run` workflow.

- [ ] **Step 2: Run full verification**

Run:

```powershell
python -m unittest discover -s tests
python -c "from pathlib import Path; from powerbanana.evals import PlannerGoldenCaseRunner; result = PlannerGoldenCaseRunner(Path('evals/planner_cases')).run_all(); print(result); raise SystemExit(0 if result.failed == 0 else 1)"
python -c "from pathlib import Path; from powerbanana.evals import VocabularyAdvisorGoldenCaseRunner; result = VocabularyAdvisorGoldenCaseRunner(Path('evals/vocabulary_cases')).run_all(); print(result); raise SystemExit(0 if result.failed == 0 else 1)"
python -c "from pathlib import Path; from powerbanana.evals import GoldenCaseRunner; result = GoldenCaseRunner(Path('evals/golden_cases')).run_all(); print(result); raise SystemExit(0 if result.failed == 0 else 1)"
python -c "from pathlib import Path; from powerbanana.evals import CalibrationRunner; result = CalibrationRunner(Path('evals/calibration_cases')).run_all(); print(result); raise SystemExit(0 if result.failed == 0 else 1)"
```

Expected: all commands exit 0.
