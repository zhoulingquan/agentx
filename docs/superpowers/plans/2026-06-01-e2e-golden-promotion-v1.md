# End-to-End Golden Promotion v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote reviewed vocabulary drafts into formal end-to-end golden cases validated by the full PowerBanana workflow.

**Architecture:** Extend `GoldenCasePromoter` with `promote_e2e_case`, let `GoldenCaseRunner` accept an injected agent and optional `expected_analysis_result`, and expose `powerbanana vocab promote-e2e-golden`.

**Tech Stack:** Python JSON/CSV files, existing PowerBananaAgent, existing GoldenCaseRunner, argparse, `unittest`.

---

### Task 1: GoldenCaseRunner Injection And Analysis Checks

**Files:**
- Modify: `powerbanana/evals.py`
- Test: `tests/test_golden_promotion.py`

- [x] **Step 1: Write failing test**

Create a temp golden case with `expected_analysis_result` and validate it with a `PowerBananaAgent` using temp analysis terms.

- [x] **Step 2: Implement runner support**

Add optional `agent` to `GoldenCaseRunner` and check provided `expected_analysis_result` fields.

### Task 2: E2E Promotion Service

**Files:**
- Modify: `powerbanana/golden_promotion.py`
- Test: `tests/test_golden_promotion.py`

- [x] **Step 1: Write failing test**

Promote a draft and synthetic CSV into temp `golden_cases`, assert JSON and copied CSV exist, and assert validation passes.

- [x] **Step 2: Implement service**

Run PowerBanana, require `completed`, write case JSON and copied CSV, validate, and clean up on failure.

### Task 3: CLI Command

**Files:**
- Modify: `powerbanana/cli.py`
- Test: `tests/test_cli.py`

- [x] **Step 1: Write failing CLI test**

Call `vocab promote-e2e-golden vocab_000001 --dataset ... --question ...` with temp store, temp terms, and temp cases dir.

- [x] **Step 2: Implement CLI command**

Resolve the draft path, build a planner from `--analysis-terms`, call `promote_e2e_case`, and print generated paths.

### Task 4: Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/planner.md`
- Modify: `docs/planner-lexicon.md`
- Modify: `tests/README.md`

- [x] **Step 1: Document e2e promotion workflow**

Explain that the dataset should be synthetic and that generated cases enter `evals/golden_cases/`.

- [x] **Step 2: Run full verification**

Run unit tests, Planner golden cases, end-to-end golden cases, and calibration cases.
