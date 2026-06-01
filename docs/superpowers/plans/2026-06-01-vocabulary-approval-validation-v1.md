# Vocabulary Approval Validation v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade vocabulary approval with dry-run preview, post-approval validation, and local golden case draft generation.

**Architecture:** Extend `VocabularyApprovalService` with preview and validation helpers, extend `VocabularySuggestionRecord` with validation metadata, and expose new CLI flags on `vocab approve`. Generated golden case drafts remain local under `runs/`.

**Tech Stack:** Python dataclasses, JSONL persistence, CSV parsing, argparse, `unittest`.

---

### Task 1: Approval Preview And Metadata

**Files:**
- Modify: `powerbanana/vocabulary.py`
- Test: `tests/test_vocabulary_manager.py`

- [x] **Step 1: Write failing tests for dry-run preview**

```python
preview = VocabularyApprovalService(repo).preview("vocab_000001")
self.assertEqual(preview.csv_line, "group_by,region,地区|区域,,")
self.assertEqual(repo.get_record("vocab_000001").status, "pending_user_approval")
```

- [x] **Step 2: Implement preview**

Add `VocabularyApprovalPreview` and a CSV-line helper on `VocabularySuggestionStore`.

### Task 2: Validation And Golden Drafts

**Files:**
- Modify: `powerbanana/vocabulary.py`
- Test: `tests/test_vocabulary_manager.py`

- [x] **Step 1: Write failing tests for validation metadata and draft file**

```python
record = service.approve("vocab_000001", terms_path, golden_case_drafts_dir=draft_dir)
self.assertEqual(record.validation_status, "passed")
self.assertTrue(Path(record.golden_case_draft_path).exists())
```

- [x] **Step 2: Implement approval validation**

Reload `analysis_terms.csv`, confirm the approved value and terms are active, and write a local draft JSON.

### Task 3: CLI Flags

**Files:**
- Modify: `powerbanana/cli.py`
- Test: `tests/test_cli.py`

- [x] **Step 1: Write failing CLI tests**

```python
exit_code = cli.main(["vocab", "approve", "vocab_000001", "--dry-run", "--store", str(store_path)])
self.assertEqual(exit_code, 0)
self.assertIn("would append", stdout.getvalue())
```

- [x] **Step 2: Implement CLI flags**

Add `--dry-run` and `--golden-drafts` to `vocab approve`, and print validation and draft paths after approval.

### Task 4: Documentation And Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/planner.md`
- Modify: `docs/planner-lexicon.md`
- Modify: `tests/README.md`

- [x] **Step 1: Document approval validation workflow**

Document dry-run, validation status, and local golden case drafts.

- [x] **Step 2: Run complete verification**

Run unit tests, planner golden cases, end-to-end golden cases, and calibration cases.
