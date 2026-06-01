# AnalysisRequest v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured deterministic analysis requests and execute grouped metric ranking for conversion rate, revenue, orders, and visits.

**Architecture:** `DeterministicDataFilePlanner` will parse an `AnalysisRequest` from CSV-backed vocabulary and store it in `PlannerTrace`. `DataAnalysisAgent` will execute that request through generalized metric skills, and `MetricRecomputeEvaluator` will recompute the requested metric from rows.

**Tech Stack:** Python dataclasses, CSV configuration, `unittest`, existing PowerBanana DAG/evaluation framework.

---

### Task 1: Analysis Request Model And Vocabulary

**Files:**
- Modify: `powerbanana/models.py`
- Create: `config/analysis_terms.csv`
- Create: `powerbanana/analysis_request.py`
- Test: `tests/test_analysis_request.py`

- [x] Write failing tests for extracting `metric`, `group_by`, and `rank_direction`.
- [x] Implement `AnalysisRequest` and CSV-backed `AnalysisRequestParser`.
- [x] Verify tests pass.

### Task 2: Planner Trace Integration

**Files:**
- Modify: `powerbanana/models.py`
- Modify: `powerbanana/planner.py`
- Modify: `powerbanana/evaluation.py`
- Test: `tests/test_planner_evaluation.py`

- [x] Write failing tests that Planner trace includes `analysis_request` for revenue/orders/visits questions.
- [x] Populate `PlannerTrace.analysis_request`.
- [x] Ensure Planner evaluation blocks executable scenarios with missing request.
- [x] Verify targeted tests pass.

### Task 3: Generalized Metric Execution

**Files:**
- Modify: `powerbanana/skills.py`
- Modify: `powerbanana/subagents.py`
- Modify: `powerbanana/evaluation.py`
- Test: `tests/test_powerbanana.py`

- [x] Write failing end-to-end tests for revenue highest, orders lowest, and visits lowest.
- [x] Generalize grouped metric computation and ranking skills.
- [x] Execute `blackboard.planner_trace.analysis_request` instead of raw question heuristics.
- [x] Update evaluator recomputation for all supported metrics.
- [x] Verify targeted tests pass.

### Task 4: Golden Cases And Docs

**Files:**
- Add: `evals/golden_cases/*`
- Modify: `README.md`
- Modify: `docs/planner.md`
- Modify: `docs/planner-lexicon.md`
- Modify: `docs/evaluation-layer.md`

- [x] Add golden cases for revenue, orders, visits, and lowest ranking.
- [x] Document AnalysisRequest and CSV vocabulary.
- [x] Run `python -m unittest discover -s tests`.
- [x] Run Planner golden, end-to-end golden, and calibration suites.
- [ ] Commit and push to GitHub.
