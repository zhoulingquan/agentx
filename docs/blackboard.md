# Task Blackboard

PowerBanana uses `TaskBlackboard` as the single-task collaboration state. Earlier versions exposed runtime fields and event logs; the current implementation also writes structured `BlackboardEntry` records.

## Entry Schema

Each entry includes:

| Field | Purpose |
|---|---|
| `entry_id` | Stable per-task entry id such as `entry_0001` |
| `entry_type` | Entry category, such as `artifact`, `security_finding`, or `evaluation` |
| `owner_agent_id` | Agent or layer that owns the entry |
| `source_ref` | Source of the entry, such as a row/column reference or evaluator id |
| `target_ref` | Blackboard URI for the written fact |
| `visibility_scope` | Intended visibility boundary |
| `confidence` | Confidence attached to the entry |
| `version` | Entry or artifact version |
| `payload` | Structured payload |
| `audit_ref` | Event id that records the write |

## Current Entry Types

| Entry Type | Written By | Example Target |
|---|---|---|
| `artifact` | `data_profile_agent`, `data_analysis_agent` | `blackboard://task_001/artifacts/analysis_result_v1` |
| `security_finding` | `data_profile_agent` | `blackboard://task_001/security_findings/security_finding_001` |
| `evaluation` | `evaluation_layer` | `blackboard://task_001/artifacts/analysis_result_v1` |

## Relationship To Events

Events answer "what happened and when." Entries answer "what structured fact now exists." Every entry has an `audit_ref` pointing to an `entry_written` event.

## Why This Matters

Structured entries are the foundation for:

- Blackboard persistence.
- Evidence and claim references.
- Evaluation replay.
- Visibility and permission policies.
- Conflict detection.

The current implementation is still in-memory, but the entry shape is designed so it can later move to a durable event/state store.
