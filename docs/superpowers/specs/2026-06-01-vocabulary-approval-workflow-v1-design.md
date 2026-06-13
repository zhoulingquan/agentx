# Vocabulary Approval Workflow v1 Design

Status: Reference  
Current authority: `docs/powerbanana-current-design.md`

PowerBanana can already ask a pluggable vocabulary advisor for missing analysis terms, but those suggestions currently live only inside the run report. This design adds a small local approval workflow so users can review candidate terms before they become active CSV vocabulary.

## Goals

- Persist valid `VocabularySuggestion` records as pending local review items.
- Let users list, approve, and reject suggestions from the CLI.
- Write approved suggestions into `config/analysis_terms.csv` through the existing CSV append path.
- Keep rejected suggestions in the audit log without changing active vocabulary.
- Keep the default runtime deterministic and human-gated.

## Non-Goals

- No real LLM provider is added in this version.
- No web admin UI is added in this version.
- No automatic scenario creation is added in this version.
- No automatic CSV mutation happens during the same analysis run that creates a suggestion.

## Architecture

`VocabularySuggestionRepository` owns a local JSONL file, `runs/vocabulary_suggestions.jsonl`. Each record has a stable suggestion id, the serialized suggestion, timestamps, optional reviewer note, and status. The repository never interprets LLM output; it only persists already validated suggestions.

`VocabularyManager` keeps generating and validating suggestions. When a valid suggestion is accepted by `DataAnalysisAgent`, the manager records it in the pending repository before the Blackboard human gate is created. If no repository is configured, it uses the default local file under `runs/`.

The CLI gets a `vocab` subcommand with three actions:

- `powerbanana vocab list`
- `powerbanana vocab approve <suggestion_id>`
- `powerbanana vocab reject <suggestion_id>`

Approving a suggestion marks the local record approved and appends it to `config/analysis_terms.csv`. Rejecting marks the local record rejected and does not touch the CSV. Both operations are idempotency-aware: approving or rejecting an already final record returns a clear error instead of silently mutating state.

## Data Model

JSONL records use this shape:

```json
{
  "suggestion_id": "vocab_000001",
  "status": "pending_user_approval",
  "created_at": "2026-06-01T00:00:00Z",
  "updated_at": "2026-06-01T00:00:00Z",
  "reviewer_note": "",
  "suggestion": {
    "target_csv": "config/analysis_terms.csv",
    "kind": "group_by",
    "value": "region",
    "terms": ["地区", "区域"],
    "reason": "missing_group_by_term",
    "source": "fake_llm",
    "confidence": 0.8,
    "status": "pending_user_approval"
  }
}
```

## Error Handling

- Missing suggestion store returns an empty list.
- Unknown suggestion id returns a CLI error code.
- Re-approving or re-rejecting a final suggestion returns a CLI error code.
- Approving a suggestion with `status != pending_user_approval` is blocked.
- CSV append remains restricted to approved suggestions.

## Testing

Unit tests cover repository persistence, list ordering, approval CSV append, rejection without CSV mutation, and CLI command behavior. Existing planner, evaluation, and golden cases continue to protect runtime behavior.
