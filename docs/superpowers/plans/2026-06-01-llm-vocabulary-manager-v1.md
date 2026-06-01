# LLM Vocabulary Manager v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pluggable LLM-style vocabulary advisor that proposes missing analysis CSV terms and asks for user approval before any vocabulary expansion.

**Architecture:** Planner records incomplete metric-analysis requests as needing vocabulary help. DataAnalysisAgent profiles the dataset, asks a pluggable advisor for a `VocabularySuggestion`, validates it, writes it to the Blackboard, and creates a human gate. The default advisor is no-op to preserve deterministic runtime.

**Tech Stack:** Python dataclasses/protocols, CSV-backed vocabulary, `unittest`, existing Blackboard and human gate records.

---

### Task 1: Vocabulary Suggestion Model

**Files:**
- Modify: `powerbanana/models.py`
- Modify: `powerbanana/blackboard.py`
- Test: `tests/test_vocabulary_manager.py`

- [x] Write failing tests for recording `VocabularySuggestion` entries.
- [x] Add `VocabularySuggestion` model and Blackboard recording helper.
- [x] Verify targeted tests pass.

### Task 2: Advisor And Validator

**Files:**
- Create: `powerbanana/vocabulary.py`
- Test: `tests/test_vocabulary_manager.py`

- [x] Write failing tests for valid group-by suggestions and rejected hallucinated fields.
- [x] Implement `LLMVocabularyAdvisor`, `NullVocabularyAdvisor`, `VocabularySuggestionValidator`, and CSV append helper for approved suggestions.
- [x] Verify targeted tests pass.

### Task 3: Planner Incomplete Request Path

**Files:**
- Modify: `powerbanana/analysis_request.py`
- Modify: `powerbanana/planner.py`
- Modify: `powerbanana/evaluation.py`
- Test: `tests/test_analysis_request.py`

- [x] Write failing tests that unknown group-by terms leave `analysis_request` unset with `needs_vocabulary_suggestion`.
- [x] Let Planner evaluation pass this controlled incomplete state.
- [x] Verify targeted tests pass.

### Task 4: Agent Human Gate Integration

**Files:**
- Modify: `powerbanana/agent.py`
- Modify: `powerbanana/subagents.py`
- Modify: `powerbanana/models.py`
- Test: `tests/test_powerbanana.py`

- [x] Write failing end-to-end test using fake advisor for `哪个地区收入最高？`.
- [x] Call the advisor after dataset profiling when the Planner lacks a full request.
- [x] Record suggestion, evaluation gate, and human clarification gate.
- [x] Verify full test suite, golden cases, and calibration.

### Task 5: Docs And Sync

**Files:**
- Modify: `README.md`
- Modify: `docs/planner.md`
- Modify: `docs/planner-lexicon.md`
- Modify: `docs/evaluation-layer.md`

- [x] Document that LLM is candidate-only and cannot auto-write CSV.
- [x] Document how approved suggestions map to `config/analysis_terms.csv`.
- [ ] Commit and push to GitHub.
