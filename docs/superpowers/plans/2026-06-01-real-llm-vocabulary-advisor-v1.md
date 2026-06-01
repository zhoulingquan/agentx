# Real LLM Vocabulary Advisor v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional real LLM vocabulary advisor that can suggest missing analysis terms without directly mutating CSV vocabulary.

**Architecture:** Keep the deterministic planner and existing approval workflow as the source of truth. Add a JSON-only LLM adapter behind the existing `LLMVocabularyAdvisor` protocol, validate its output into `VocabularySuggestion`, and let `VocabularyManager` keep enforcing dataset-column and active-term checks.

**Tech Stack:** Python standard library, `unittest`, OpenAI Responses-compatible HTTP JSON schema calls through `urllib.request`.

---

### Task 1: Advisor Contract Tests

**Files:**
- Create: `tests/test_llm_vocabulary.py`
- Create: `powerbanana/llm_vocabulary.py`

- [ ] **Step 1: Write failing tests**

Add tests proving that a fake JSON client can produce a pending `VocabularySuggestion`, that `should_suggest = false` returns `None`, and that client failures are safely ignored.

- [ ] **Step 2: Run the tests**

Run: `python -m unittest tests.test_llm_vocabulary`

Expected: fail because `powerbanana.llm_vocabulary` does not exist yet.

- [ ] **Step 3: Implement minimal advisor**

Create `JsonLLMVocabularyAdvisor`, `LLMJsonClient`, and helper schema/payload builders. The advisor must coerce only valid JSON payloads into `VocabularySuggestion` and return `None` on unsafe or incomplete outputs.

- [ ] **Step 4: Verify**

Run: `python -m unittest tests.test_llm_vocabulary`

Expected: pass.

### Task 2: OpenAI-Compatible Client And Env Wiring

**Files:**
- Modify: `powerbanana/llm.py`
- Modify: `powerbanana/cli.py`
- Modify: `tests/test_llm_vocabulary.py`

- [ ] **Step 1: Write failing tests**

Add tests for `vocabulary_advisor_from_env`: disabled by default, OpenAI provider requires an API key, and OpenAI provider returns a JSON advisor when configured.

- [ ] **Step 2: Implement env factory**

Add `vocabulary_advisor_from_env(environ=None)` to `powerbanana.llm`. Supported values:

```text
POWERBANANA_VOCAB_ADVISOR=none|off|disabled|openai
OPENAI_API_KEY=<secret>
POWERBANANA_VOCAB_MODEL=<model>
POWERBANANA_VOCAB_BASE_URL=<base URL>
```

- [ ] **Step 3: Wire CLI only**

Use the env factory in CLI-created `PowerBananaAgent` instances. Leave `PowerBananaAgent()` deterministic unless an advisor is explicitly passed.

- [ ] **Step 4: Verify**

Run: `python -m unittest tests.test_llm_vocabulary tests.test_cli`

Expected: pass.

### Task 3: Documentation And Regression

**Files:**
- Modify: `README.md`
- Modify: `docs/planner-lexicon.md`
- Modify: `docs/index.md`

- [ ] **Step 1: Document the safety boundary**

State that the real LLM advisor is off by default, only generates pending candidates, and never writes CSV by itself.

- [ ] **Step 2: Run full verification**

Run:

```powershell
python -m unittest discover -s tests
python -c "from pathlib import Path; from powerbanana.evals import PlannerGoldenCaseRunner; result = PlannerGoldenCaseRunner(Path('evals/planner_cases')).run_all(); print(result); raise SystemExit(0 if result.failed == 0 else 1)"
python -c "from pathlib import Path; from powerbanana.evals import GoldenCaseRunner; result = GoldenCaseRunner(Path('evals/golden_cases')).run_all(); print(result); raise SystemExit(0 if result.failed == 0 else 1)"
python -c "from pathlib import Path; from powerbanana.evals import CalibrationRunner; result = CalibrationRunner(Path('evals/calibration_cases')).run_all(); print(result); raise SystemExit(0 if result.failed == 0 else 1)"
```

Expected: all commands exit 0.
