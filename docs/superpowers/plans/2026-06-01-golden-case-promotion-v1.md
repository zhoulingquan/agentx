# Golden Case Promotion v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote reviewed vocabulary golden case drafts into formal Planner golden cases and validate them before they enter the regression suite.

**Architecture:** Add a small `GoldenCasePromoter` service, extend `PlannerGoldenCaseRunner` to optionally check `expected_analysis_request`, and expose `powerbanana vocab promote-golden`.

**Tech Stack:** Python dataclasses, JSON files, existing Planner golden runner, argparse, `unittest`.

---

### Task 1: Planner Golden AnalysisRequest Checks

**Files:**
- Modify: `powerbanana/evals.py`
- Test: `tests/test_planner_golden_cases.py`

- [x] **Step 1: Write failing test**

```python
case = {
    "case_id": "region_revenue",
    "question": "哪个地区收入最高？",
    "expected_scenario": "metric_analysis",
    "expected_analysis_request": {"group_by": "region"}
}
```

- [x] **Step 2: Implement optional checks**

Check only provided fields on `trace.analysis_request`; keep older cases unchanged.

### Task 2: GoldenCasePromoter

**Files:**
- Create: `powerbanana/golden_promotion.py`
- Test: `tests/test_golden_promotion.py`

- [x] **Step 1: Write failing tests for promotion**

Promote a draft with a real question into a temp `planner_cases` directory and assert validation passes.

- [x] **Step 2: Implement promotion service**

Read draft JSON, build case JSON, validate in a temp candidate directory, then write to final directory only when validation passes.

### Task 3: CLI Command

**Files:**
- Modify: `powerbanana/cli.py`
- Test: `tests/test_cli.py`

- [x] **Step 1: Write failing CLI test**

Call `vocab promote-golden vocab_000001 --question ... --matched-signal ...` with temp store, temp analysis terms, and temp cases dir.

- [x] **Step 2: Implement CLI command**

Resolve suggestion id to draft path, call `GoldenCasePromoter`, and print the promoted file path.

### Task 4: Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/planner-lexicon.md`
- Modify: `docs/planner.md`
- Modify: `tests/README.md`

- [x] **Step 1: Document promotion workflow**

Explain when to use `promote-golden` and why end-to-end golden cases still need synthetic data.

- [x] **Step 2: Run full verification**

Run unit tests, Planner golden cases, end-to-end golden cases, and calibration cases.
