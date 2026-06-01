# Vocabulary Approval Validation v1 Design

Vocabulary approval should not stop at writing one CSV row. This design makes approval safer by adding preview, post-write validation, and a generated golden case draft.

## Goals

- Let users preview the exact CSV row before approval.
- Validate `config/analysis_terms.csv` after approval.
- Record validation status and output in the local suggestion JSONL record.
- Generate a local golden case draft that explains which regression case should be added.
- Keep generated drafts local under `runs/` until a user decides to promote them into `evals/`.

## Non-Goals

- No automatic mutation of committed golden case files.
- No automatic rollback after a failed validation.
- No real LLM provider is added.

## Flow

1. User runs `powerbanana vocab approve vocab_000001 --dry-run`.
2. CLI prints the exact CSV line that would be appended.
3. User runs `powerbanana vocab approve vocab_000001`.
4. Approval appends the row to `config/analysis_terms.csv`.
5. PowerBanana reloads the CSV and checks that the approved term is active.
6. PowerBanana writes a local golden case draft to `runs/golden_case_drafts/`.
7. The suggestion record stores `validation_status`, `validation_output`, and `golden_case_draft_path`.

If validation fails, the record status becomes `approved_validation_failed`. This is intentionally visible so the user does not treat the new term as stable.

## Data Additions

`VocabularySuggestionRecord` adds:

- `validation_status`: `passed`, `failed`, or empty.
- `validation_output`: human-readable validation messages.
- `golden_case_draft_path`: local path to the generated draft JSON.

## Testing

Tests cover dry-run no mutation, successful validation, failed validation status, golden case draft creation, and CLI output.
