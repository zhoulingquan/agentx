# PowerBanana Memory System Design

## Goal

PowerBanana needs a Memory System that supports enterprise business workflows without turning memory into an uncontrolled business knowledge store.

The current boundary is:

- Memory stores runtime continuity, process experience, and repeated exception candidates.
- Knowledge Base will later store industry knowledge, enterprise policies, domain references, and authoritative business facts.
- Memory is layered into Short-Term Runtime Memory, Mid-Term Episodic Memory, Long-Term Governed Memory, and an Evolution Memory Loop.

This design is inspired by MiMo-Code's checkpoint, task progress, and memory maintenance patterns, but narrows them for PowerBanana's governed, scenario-based runtime.

## Non-Goal: Industry Knowledge Storage

PowerBanana Memory must not store:

- Industry regulations or professional knowledge.
- Contract clause interpretations.
- Enterprise policy documents.
- Authoritative metric definitions.
- Data dictionary ownership or long-term data semantics.
- Domain facts that should be cited from a Knowledge Base.

When future Knowledge Base support is added, Context Manager will combine:

- Memory: how the agent should continue work and improve the workflow.
- Knowledge Base: what business knowledge supports the answer.

Memory may store references to Knowledge Base results or tool evidence, but it must not become the source of truth for that knowledge.

## Design Principle

Memory has three jobs:

1. Task continuity: preserve where the current task, DAG, sub-agents, Human Gates, and EvaluationResults are.
2. Context recovery: rebuild useful context across compaction, long-running tasks, and resumed sessions.
3. Process improvement: detect repeated exceptions in fixed business workflows and ask whether they should become Skill, evaluator, golden case, or calibration case changes.

Memory must never override:

- Current tool evidence.
- TaskBlackboard artifacts.
- User confirmations.
- EvaluationResults.
- Human Gate decisions.
- Future Knowledge Base retrieval results.

## Current Implementation Baseline

The current code has only a minimal working-memory seed:

- `MemoryManager.write_task_summary()` writes one task summary record after report generation.
- The record lives inside the current `TaskBlackboard.memory_records`.
- It is not persisted to disk.
- It is not loaded at the beginning of a later task.
- It is not bounded, curated, searched, approved, or injected through Context Manager as a frozen memory snapshot.

Therefore the current implementation should be treated as a seed for the future Memory boundary, not as the final layered memory system.

The first design milestone should establish Short-Term Runtime Memory and a small scenario-local Process Memory snapshot. Mid-Term Episode Search, Long-Term Governed Memory, and Evolution Loop behavior should then be enabled progressively.

## External Lessons Adopted

From MiMo-Code, PowerBanana should adopt:

- Dedicated checkpoint writing instead of ad hoc main-agent memory writes.
- Task progress files for long-running or resumed work.
- Path guards that enforce ownership of memory and checkpoint files.
- Draft-only learning passes that propose reusable assets from repeated work.

From Hermes Agent, PowerBanana should adopt:

- Small, bounded memory that stays high-signal.
- Session search adapted as structured Episode search.
- SQLite + FTS5 as a local, rebuildable Episode Search backend for lightweight deployments.
- Skills as procedural memory, where repeatable procedures become Skill drafts rather than prose memory.
- Write approval for memory and Skill changes.
- Security scanning before memory is injected into prompts.

From QwenPaw, PowerBanana should adopt:

- Tool-result offloading plus compact summaries so large tool outputs are stored as refs instead of flooding prompts.
- A structured context compaction flow that preserves tool-use/tool-result pairs, Human Gates, approvals, and evaluation repair turns.
- Hybrid retrieval as a future backend option: BM25/FTS for exact process terms, optional vector retrieval for semantically similar Episodes.
- Heartbeat-style maintenance as a Main Agent governance digest for stale approvals, candidate TTLs, repeated failures, and checkpoint lag.
- Memory evolution as draft-only suggestions. Repeated facts or exceptions may become Skill, evaluator, golden case, calibration case, or process-memory candidates only after user confirmation and validation.
- Workspace-copy discipline for procedural memory: active Skills should be read from scenario activation snapshots, not directly from mutable shared Skill pools.

PowerBanana should not adopt:

- Free-form personal memory as a business decision input.
- Raw transcript search exposed directly to agents.
- A single global SQLite database that bypasses scenario isolation or path guards.
- Agent-managed Skill writes that become active automatically.
- External memory providers in the first implementation phase.
- Industry knowledge storage inside Memory.
- Proactive memory updates that bypass the Main Agent, Scenario Pack validation, or Human Gate.

## Architecture

```mermaid
flowchart TD
    U["User Task"] --> BB["TaskBlackboard"]
    BB --> CW["ScenarioCheckpointWriter"]
    CW --> CP["Checkpoint / Progress / Notes"]
    BB --> ES["Episode Store"]
    ES --> EL["Exception Learning Assistant"]
    EL --> MC["Memory Candidate Pipeline"]
    MC --> MP["Memory Policy Gate"]
    MP --> PM["Process Memory"]
    MP --> DC["Skill / Evaluator / Golden Case Drafts"]
    CP --> CTX["Scenario Context Manager"]
    ES --> CTX
    PM --> CTX
    CTX --> AG["Main Agent / Sub-agents"]
    KB["Future Knowledge Base"] -. "retrieved knowledge with citations" .-> CTX
```

TaskBlackboard remains the current-task fact source. Memory stores summaries, state, and improvement candidates around that fact source.

## Scenario Context Manager

The Scenario Context Manager is the runtime compiler for memory. It does not own long-term storage and it does not execute business actions. Its job is to build a bounded, labeled, scenario-safe `Scenario Context Bundle` before planning, routing, DAG node execution, sub-agent dispatch, evaluation repair, governance review, or task resume.

It should borrow MiMo-Code's rebuild-context discipline:

- Inject a clear statement that the included memory blocks are already loaded.
- Tell the agent not to re-read whole memory files that are already present.
- Preserve the newest task tail so the agent resumes without asking what to do next.
- Use section-aware budgets instead of cutting arbitrary text.
- Convert large, regeneratable tool results into artifact references and summaries.
- Keep a memory keys index so the agent can request targeted retrieval without pulling every file.

PowerBanana adapts these ideas with stricter enterprise boundaries:

- The bundle is always pinned to one `scenario_id`, `scenario_version`, `evaluation_contract_version`, and `task_id`.
- Every included item must have a layer, source ref, allowed use, confidence or freshness marker, and redaction level.
- The bundle must not include raw uploaded documents, raw transcripts, unrestricted SQL results, or another scenario's files.
- The bundle must not weaken ScenarioPathGuard, MemoryPathGuard, Evaluation gates, Human Gates, or Knowledge Base authority.

### Scenario Context Bundle

Suggested bundle shape:

```yaml
scenario_context_bundle:
  identity:
    scenario_id: contract_payment_review
    scenario_version: 0.3.0
    evaluation_contract_version: 0.2.0
    task_id: task_001
    scenario_root: scenario_packs/contract_payment_review
  active_recall_protocol:
    already_loaded:
      - memory/CHECKPOINT.md
      - memory/MEMORY.md
    whole_file_reread_policy: disallow_unless_missing_tail
    targeted_lookup_policy: use_context_manager_or_grep_by_keyword
  short_term_runtime:
    taskblackboard_summary_ref: blackboard://task_001/current
    checkpoint_ref: memory/CHECKPOINT.md
    dag_state_ref: blackboard://task_001/dag
    subagent_progress_refs:
      - memory/tasks/task_001/progress.md
  blocking_controls:
    evaluation_results:
      - eval_result_003
    human_gates:
      - human_gate_002
  long_term_governed:
    process_memory_snapshot_ref: memory/MEMORY.md
  mid_term_episodic:
    retrieved_episodes:
      - episode_2026_06_11_001
  evolution_loop:
    candidates_for_user_decision:
      - exception_001
  future_knowledge_base:
    retrieved_refs: []
```

Bundle sections should be ordered by runtime authority:

1. Scenario identity and pinned versions.
2. User intent and current task objective.
3. Blocking EvaluationResults and Human Gates.
4. Current TaskBlackboard and DAG state.
5. Checkpoint next action and sub-agent progress ledger.
6. Active Long-Term Governed Memory snapshot.
7. Retrieved Mid-Term Episodes.
8. Evolution candidates, only in governance or user-decision flows.
9. Future Knowledge Base citations, when enabled.

### Agent-Facing Context Protocol

Every main-agent or sub-agent prompt should include a compact protocol derived from the bundle:

```text
You are operating inside scenario <scenario_id>@<scenario_version>.
The context blocks below are already loaded. Do not read whole memory files again.
Use targeted lookup only when a specific missing detail is needed.
Request Episode Search through Context Manager; do not query SQLite directly.
Do not write checkpoint, MEMORY.md, Episode, or candidate files.
Treat memory as hints. Current tool evidence, TaskBlackboard, EvaluationResults,
Human Gates, and Knowledge Base citations override memory.
```

Sub-agents should receive the smallest bundle that satisfies their node:

- Scenario identity.
- Assigned DAG node or task.
- Relevant TaskBlackboard refs.
- Required Skill and evaluator constraints.
- Any needed checkpoint or progress refs.
- No unrelated Episodes, no unrelated process memory, and no evolution candidates unless the sub-agent is a governance reviewer.

### Context Compilation Flow

```text
runtime requests context for a purpose
-> ScenarioPathGuard pins scenario root
-> MemoryPathGuard pins memory scope
-> Context Manager gathers required sources by purpose
-> section-aware budgeter clips each source
-> Episode Search runs only if the purpose requests it
-> safety scanner rejects unsafe memory or retrieved summaries
-> conflict resolver applies authority order
-> Context Bundle is labeled and emitted
```

Allowed purposes:

- `plan_task`
- `resume_task`
- `execute_dag_node`
- `dispatch_subagent`
- `evaluate_output`
- `repair_after_evaluation`
- `ask_user_about_exception`
- `governance_review`

Context Manager must reject a request whose purpose is missing or incompatible with the requested memory item's `allowed_use`.

## Four-Layer Memory Model

PowerBanana should treat memory as four governed layers. The layers differ by lifespan, writer, retrieval mode, and whether they are allowed to influence runtime behavior.

```mermaid
flowchart TD
    STM["Layer 1: Short-Term Runtime Memory"] --> MTE["Layer 2: Mid-Term Episodic Memory"]
    MTE --> LTM["Layer 3: Long-Term Governed Memory"]
    MTE --> EVO["Layer 4: Evolution Memory Loop"]
    LTM --> CTX["Context Manager"]
    STM --> CTX
    EVO --> DRAFTS["Draft Skills / Evaluators / Golden Cases"]
    DRAFTS --> GOV["Lint / Replay / Approval"]
    GOV --> LTM
```

### Layer 1: Short-Term Runtime Memory

Goal:

- Keep the current task coherent while the main agent, sub-agents, tools, DAG nodes, evaluations, and Human Gates are running.
- Recover from context compaction, crashes, or long-running task pauses.
- Coordinate parallel sub-agents without letting every agent write durable memory directly.

Stores:

- Current TaskBlackboard state.
- `CHECKPOINT.md`.
- `tasks/<task_id>/progress.md`.
- `notes.md`.
- DAG node state, sub-agent progress, pending gates, and next action.

Lifecycle:

- Created when a scenario task starts.
- Updated during execution by TaskBlackboard and `ScenarioCheckpointWriter`.
- Closed when the task is finalized.
- Summarized into an Episode candidate after task closure.

Rules:

- It is the highest-priority memory layer during task execution.
- It must not be used as long-term evidence after the task is closed.
- Ordinary agents may write task artifacts through TaskBlackboard, but they cannot write checkpoint-owned files.
- If Short-Term Runtime Memory conflicts with any older memory, the current short-term state wins.

### Layer 2: Mid-Term Episodic Memory

Goal:

- Remember recent completed tasks, failures, fixes, user corrections, evaluation outcomes, and repeated exception signals.
- Support similar-task recovery and controlled exception detection.
- Provide a searchable history without exposing raw transcripts or source documents to agents.

Stores:

- `episodes/<episode_id>.json` as the auditable source of truth.
- A rebuildable local search index under `index/`.
- Optional replay snapshots and EvaluationResult summaries by reference.

Lifecycle:

- Created from a closed TaskBlackboard summary.
- Indexed after redaction and policy checks.
- Retained for a scenario-defined window such as 30, 60, or 90 days.
- Compressed or expired when it no longer contributes to recovery, exception detection, or audit.

Rules:

- Episode Search is on-demand; it is not injected by default.
- Search results enter prompts only through Context Manager.
- Search results are evidence pointers and recovery hints, not business truth.
- Cross-scenario Episode Search is disabled by default.

### Layer 3: Long-Term Governed Memory

Goal:

- Keep stable, approved process knowledge for one scenario.
- Preserve workflow preferences, reporting preferences, durable recovery hints, and repeated exception summaries.
- Feed runtime as bounded hints, not as authoritative facts.

Stores:

- Structured records under `records/<memory_id>.json`.
- A human-readable `MEMORY.md` snapshot derived from approved records.
- Approved Skill, evaluator, golden case, or calibration case versions when repeated process lessons should become procedural assets.

Lifecycle:

- Starts as a candidate generated from Episodes, evaluations, or user confirmations.
- Passes schema validation, safety checks, source-reference checks, and policy gates.
- Becomes active only after approval or an allowed governance rule.
- Can become stale, superseded, expired, or rolled back.

Rules:

- It must not store industry knowledge, domain facts, policy text, or metric definitions.
- It is scenario-local unless explicitly promoted through a separate global review.
- It can be injected only within strict token budgets and only when `allowed_use` matches the current node.
- It loses to TaskBlackboard, EvaluationResults, Human Gates, and Knowledge Base retrievals.

### Layer 4: Evolution Memory Loop

Goal:

- Turn repeated special cases in fixed enterprise workflows into user-reviewed improvements.
- Help the system learn where workflows need a new Skill, a Skill change, an evaluator, a Human Gate, or a golden/calibration case.
- Keep self-improvement explicit, inspectable, reversible, and scenario-local by default.

Stores:

- Exception candidates.
- Distill candidates.
- Proposed Skill, evaluator, golden case, calibration case, and process memory drafts.
- User decisions and suppression records.

Sub-agent candidate proposals start as task-local TaskBlackboard records. They enter the Evolution Memory Loop only when the Main Agent triages them, decides to present them through the unified user interaction gateway, or a governance flow accepts them as durable candidates.

Lifecycle:

```text
episode signals
-> repeated pattern detected
-> candidate created
-> main-agent triage
-> user asked in business language
-> draft generated
-> lint and replay
-> approval
-> versioned activation
-> monitoring
-> rollback or supersession if quality drops
```

Rules:

- One odd case can create an observation, but it cannot trigger self-modification.
- User confirmation creates only a draft.
- Drafts do not influence normal runtime until validation and approval finish.
- Evolution outputs remain scenario-local unless promoted through multi-scenario evidence and review.
- Unpresented task-local candidate proposals expire or archive according to scenario policy.
- Suppressed, merged, expired, or rejected candidates keep their reason and evidence refs for audit.

## Directory Shape

Memory is scenario-local by default:

```text
scenario_packs/
  <scenario_id>/
    memory/
      CHECKPOINT.md
      MEMORY.md
      notes.md
      records/
        <memory_id>.json
      tasks/
        <task_id>/
          progress.md
      episodes/
        <episode_id>.json
      index/
        episode_index.sqlite
        rebuild_manifest.json
      candidates/
        <candidate_id>.json
      distill/
        skill_candidates/
        evaluator_candidates/
        golden_case_candidates/
        calibration_case_candidates/
```

`MEMORY.md` is a human-readable scenario process memory summary, not a domain knowledge file.

`index/episode_index.sqlite` is a derived search index. It can be deleted and rebuilt from `episodes/*.json` and `records/*.json`; it is not the source of truth.

## Memory Types

| Layer | Type | Stores | Lifetime | Runtime Use |
|---|---|---|---|---|
| Short-Term Runtime | TaskBlackboard | Current task artifacts, tool results, traces, EvaluationResults | Task | Current-task fact source |
| Short-Term Runtime | Checkpoint | Intent, next action, DAG state, sub-agent state, gates | Task/session | Recovery |
| Short-Term Runtime | Task Progress | Per-task and per-sub-agent progress | Task/session | Recovery and audit |
| Short-Term Runtime | Notes | Temporary scratch notes | Task/session | Writer-owned scratch |
| Mid-Term Episodic | Episode | Closed task summary, failure/fix summary, evaluation outcome summary | Short to medium | Similar task recovery and exception detection |
| Mid-Term Episodic | Episode Search Index | Redacted searchable fields derived from Episodes | Rebuildable | On-demand search through Context Manager |
| Long-Term Governed | Process Memory | Stable workflow preference or process lesson | Medium to long | Context hint only |
| Long-Term Governed | Structured Memory Record | Approved process memory source record with lifecycle metadata | Medium to long | Source for `MEMORY.md` snapshot |
| Evolution Loop | Exception Candidate | Repeated special case in a fixed workflow | Until accepted/discarded | User confirmation |
| Evolution Loop | Distill Candidate | Draft Skill/evaluator/golden/calibration change | Until approved/discarded | Governance workflow only |

## Small-Capacity Process Memory

PowerBanana should start with a small-capacity, scenario-local process memory snapshot. This is the closest equivalent to Hermes-style bounded memory, but it is narrower and enterprise-governed.

This snapshot belongs to Layer 3: Long-Term Governed Memory. It is generated from approved structured records and injected only as bounded process hints.

File:

```text
scenario_packs/<scenario_id>/memory/MEMORY.md
```

Purpose:

- Keep the highest-signal workflow lessons for one scenario.
- Help the agent continue work consistently.
- Help the agent ask better exception-learning questions.
- Avoid repeatedly making the same process mistake.

It must not contain domain knowledge or business facts.

Suggested budget:

```yaml
process_memory_budget:
  max_chars: 2400
  max_items: 12
  max_item_chars: 240
  injection_mode: frozen_at_task_start
  refresh_policy: after_approved_memory_candidate
```

Suggested `MEMORY.md` sections:

```markdown
# Scenario Process Memory

## Workflow Hints
- Keep ranking reports concise and include metric value plus group label.

## Repeated Exceptions
- Users often clarify ambiguous "best channel" questions by choosing revenue or conversion rate.

## Reporting Preferences
- Prefer plain business wording over implementation details.

## Suppressed Patterns
- Do not ask about single-occurrence formatting preferences.
```

The snapshot is derived from structured records. It is not the source of truth. If the Markdown conflicts with structured records, TaskBlackboard, or EvaluationResults, the structured source wins.

## Structured Memory Records

The runtime should store structured records separately from the human-readable snapshot.

Example:

```json
{
  "memory_id": "mem_proc_001",
  "scenario_id": "sales_channel_analysis",
  "scope": "scenario",
  "layer": "long_term_governed",
  "memory_type": "process_lesson",
  "allowed_use": "report_format_hint",
  "content": {
    "summary": "Reports are clearer when metric ranking includes both value and row count."
  },
  "source_refs": ["episode_2026_06_11_001", "eval_result_003"],
  "promotion_reason": "Repeated user correction appeared in 3 recent episodes.",
  "confidence": 0.82,
  "status": "active",
  "owner": "scenario_owner",
  "created_at": "2026-06-11T10:00:00+08:00",
  "last_verified_at": "2026-06-11T10:00:00+08:00",
  "review_after": "2026-09-11T10:00:00+08:00",
  "expires_at": "2026-09-11T10:00:00+08:00",
  "supersedes": [],
  "version": "0.1.0"
}
```

Required fields:

- `memory_id`
- `scenario_id`
- `scope`
- `layer`
- `memory_type`
- `allowed_use`
- `content.summary`
- `source_refs`
- `confidence`
- `status`
- `owner`
- `created_at`
- `review_after`
- `version`

Allowed `memory_type` values in the first phase:

- `process_lesson`
- `reporting_preference`
- `workflow_recovery_hint`
- `repeated_exception_summary`
- `suppressed_pattern`

Rejected `memory_type` values:

- `industry_rule`
- `domain_fact`
- `policy_document`
- `contract_interpretation`
- `metric_definition`

Allowed `allowed_use` values:

- `resume_task`
- `workflow_hint`
- `report_format_hint`
- `exception_learning_prompt`
- `debugging_hint`

The Context Manager must reject records whose `allowed_use` does not match the current node purpose.

Allowed `layer` values:

- `short_term_runtime`
- `mid_term_episodic`
- `long_term_governed`
- `evolution_loop`

Only `long_term_governed` records can generate the active `MEMORY.md` snapshot. `mid_term_episodic` records are retrieved through Episode Search. `evolution_loop` records are surfaced only in user decision or governance flows.

## ScenarioCheckpointWriter

`ScenarioCheckpointWriter` is the only writer for checkpoint-owned files:

- `memory/CHECKPOINT.md`
- `memory/notes.md`
- `memory/tasks/<task_id>/progress.md`

It records:

- Active user intent.
- Pinned Scenario Pack and Evaluation Contract versions.
- Current DAG node states.
- Running sub-agents and their progress.
- Pending Human Gates.
- Blocking EvaluationResults.
- Next concrete action.
- References to TaskBlackboard artifacts and replay snapshots.

It must not:

- Modify enabled `SCENARIO.md`, `EVALUATION.md`, or Skill files.
- Store industry knowledge.
- Create enabled rules, evaluators, or Skills.
- Treat memory as evidence for final business claims.

### Sub-Agent Progress Reconciliation

PowerBanana should borrow MiMo-Code's progress reconciliation pattern for parallel work, but keep stricter write ownership. Sub-agents report task-local progress through TaskBlackboard or a task-local progress event. The progress event shape is defined by the Sub-Agent Runtime Contract; this section defines how those events are materialized into memory-owned files. `ScenarioCheckpointWriter` is the component that materializes those reports into `memory/tasks/<task_id>/progress.md` and reconciles them into the scenario checkpoint.

Each writer-created progress file should include machine-readable freshness metadata:

```markdown
---
task_id: task_001.extract_appendix
subagent_id: extract_appendix_worker_01
written_at: 2026-06-11T10:20:00+08:00
scenario_id: contract_payment_review
---

## Current Status
in_progress

## Evidence And Outputs
- artifact://task_001/appendix_terms.json

## Exact Values To Preserve
- evaluator_id: payment_terms_presence@0.2.0

## Findings Worth Promoting
- Appendix checks resolved the missing payment terms fallback.
```

The writer should track reconciliation markers in `CHECKPOINT.md`:

```text
(progress: memory/tasks/task_001.extract_appendix/progress.md, last_reconciled_written_at: 2026-06-11T10:20:00+08:00)
```

Reconciliation rules:

- Read only sub-agent progress files whose `written_at` is newer than the checkpoint marker.
- Integrate status, blockers, artifact refs, and exact-form values into checkpoint sections.
- Preserve exact-form values byte-for-byte when they are needed for replay or evaluator matching.
- Do not let sub-agent progress write directly into `MEMORY.md` or Long-Term Governed Memory.
- If a sub-agent progress item suggests a durable lesson, record it first as a task-local candidate proposal; the Main Agent decides whether it should become an Episode or process memory candidate.
- If progress is missing or malformed, mark the node as requiring recovery rather than inventing state.

## MemoryPathGuard

All memory access goes through `MemoryPathGuard`.

It enforces:

- Every read and write is bound to a pinned `scenario_id`.
- A scenario cannot read another scenario's checkpoint, progress, episode, candidate, or process memory.
- Ordinary agents cannot write checkpoint-owned files.
- Memory candidates cannot write directly into active process memory.
- Draft Skill or evaluator changes are written only under scenario-local `distill/` or `changes/`.

This guard complements `ScenarioPathGuard`. `ScenarioPathGuard` protects scenario files generally; `MemoryPathGuard` protects memory-specific ownership and lifecycle rules.

## Episode Store

An episode is a structured closed-task summary.

It may include:

- Task goal.
- Scenario and version.
- DAG path executed.
- Skills used.
- Tool evidence refs.
- EvaluationResult summaries.
- Human Gate decisions.
- User corrections.
- Special cases encountered.
- Final outcome.

It must not include:

- Raw uploaded files.
- Full transcripts.
- Industry knowledge text copied from source documents.
- Sensitive values unless allowed by retention policy and redaction.

Example:

```json
{
  "episode_id": "episode_2026_06_11_001",
  "scenario_id": "contract_payment_review",
  "task_id": "task_001",
  "workflow_path": ["profile_document", "extract_contract_terms", "detect_payment_risk"],
  "special_cases": [
    {
      "case_type": "appendix_needed",
      "summary": "Main document lacked payment terms, but user pointed to appendix."
    }
  ],
  "evaluation_summary": {
    "gate_action": "human_review",
    "blocking_issues": ["missing_payment_terms"]
  },
  "user_corrections": [
    "Check appendix before marking payment terms missing."
  ]
}
```

## Episode Search Index

PowerBanana should borrow Hermes Agent's lightweight local search idea, but adapt it as a scenario-local Episode Search index.

Default local backend:

```text
scenario_packs/<scenario_id>/memory/index/episode_index.sqlite
```

The default lightweight implementation should use SQLite + FTS5 when available. The index is suitable for local development, single-scenario deployments, desktop usage, and early enterprise pilots. It should remain replaceable by PostgreSQL FTS, pgvector, OpenSearch, or a managed search service in later platform deployments.

The SQLite file is derived state:

- It is rebuilt from `episodes/*.json` and approved `records/*.json`.
- It must not be edited by agents.
- It must not be the only copy of any memory.
- It must be scoped to one scenario directory.
- It must be protected by `MemoryPathGuard`.

The indexer should use a lazy reconcile model:

- Before search, compare indexed fingerprints against source file size and modification time.
- Index new or changed Episode summaries.
- Prune index rows whose source files no longer exist.
- Keep source JSON and structured records as the source of truth.
- Treat the SQLite file as disposable cache.

Suggested indexed fields:

```sql
episode_id
scenario_id
scenario_version
task_goal_summary
workflow_path
skill_ids
failure_summary
fix_summary
evaluation_summary
human_gate_summary
user_correction_summary
special_case_summary
created_at
retention_until
redaction_level
```

FTS5 should index only redacted text fields:

- `task_goal_summary`
- `failure_summary`
- `fix_summary`
- `evaluation_summary`
- `human_gate_summary`
- `user_correction_summary`
- `special_case_summary`

It must not index:

- Raw transcripts.
- Raw uploaded documents.
- Full tool outputs.
- Sensitive values outside retention policy.
- Knowledge Base passages copied as text.
- Hidden instructions found in source data.

Search flow:

```text
Context Manager requests similar-task context
-> MemoryPathGuard pins scenario_id and scenario_root
-> Episode index reconciles changed source files
-> EpisodeSearch queries SQLite FTS5
-> results are filtered by retention, redaction, and allowed_use
-> results are ranked and clipped to token budget
-> Context Manager injects summaries with source refs only
```

FTS query rules:

- Tokenize user or system queries into Unicode letter, number, and underscore runs.
- Phrase-quote each token before passing it to FTS5, so punctuation and special characters cannot crash the MATCH parser.
- Join tokens with OR to preserve recall.
- Use BM25 ranking to prefer records matching more and rarer tokens.
- Apply a relative score floor, for example `0.15` of the top result, to remove common-token noise without losing all results in a small corpus.

Suggested search policy:

```yaml
episode_search_policy:
  backend: sqlite_fts5
  lazy_reconcile: true
  query_tokenization: unicode_word_runs
  query_join: OR
  ranking: bm25
  relative_score_floor: 0.15
  max_results: 8
  max_tokens: 800
  require_scope_filter: true
  require_redaction_filter: true
  require_allowed_use: true
```

Search results should include:

- `episode_id`
- matched summary field
- short excerpt or generated summary
- score
- created time
- scenario version
- relevant Skills and evaluators
- source refs for audit

The agent never receives arbitrary SQL access. It can only ask Context Manager for an approved retrieval purpose such as `resume_task`, `debugging_hint`, or `exception_learning_prompt`.

### Hybrid Retrieval Upgrade Path

QwenPaw's hybrid search model is useful later, but PowerBanana should treat it as an Episode Search backend upgrade rather than a domain knowledge store. The default local backend remains SQLite + FTS5 because it is transparent, rebuildable, and easy to scope per scenario. A later enterprise backend may add vector retrieval when exact keyword search misses semantically similar repeated exceptions.

Upgrade rules:

- Hybrid retrieval is allowed only over redacted Episode summaries, approved process-memory records, and governance candidates.
- It must not index raw contracts, spreadsheets, source documents, full tool outputs, or future Knowledge Base passages copied as memory.
- BM25/FTS should remain the precision anchor for exact terms such as clause names, evaluator IDs, threshold names, error codes, and Skill IDs.
- Vector retrieval may provide recall for similar failure patterns, user corrections, or repeated exceptions.
- Ranking fusion must be deterministic, logged, and clipped by Context Manager budgets.
- Each result must keep source refs, scenario scope, allowed use, confidence, and redaction labels.

Example future policy:

```yaml
episode_search_policy:
  backend: hybrid
  lexical_backend: sqlite_fts5
  vector_backend: managed_vector_index
  lexical_weight: 0.65
  vector_weight: 0.35
  require_scope_filter: true
  require_allowed_use: true
  require_source_refs: true
```

## Exception Learning Assistant

PowerBanana business flows are relatively fixed. Therefore the learning loop should focus on repeated special cases inside those fixed flows, not on open-ended self-improvement.

Internally, this replaces the broad meaning of `ScenarioDream` and `ScenarioDistill`:

- `ScenarioDream` summarizes repeated exceptions and process signals from episodes.
- `ScenarioDistill` turns high-confidence repeated exceptions into user-facing improvement proposals.

User-facing names should be:

- Exception Learning Assistant.
- Skill Improvement Suggestions.
- Process Exception Suggestions.

## Repeated Exception Triggers

The system should not ask the user after every odd case. It should wait for repeated, meaningful signals.

Example policy:

```yaml
exception_learning_policy:
  min_occurrences: 3
  time_window_days: 30
  min_impact_level: medium
  require_human_confirmation_signal: true
  require_evaluation_signal: true
  auto_create_skill: false
  auto_modify_skill: false
```

Trigger signals include:

- The same Human Gate reason appears repeatedly.
- The same evaluator failure appears repeatedly.
- The user makes the same correction multiple times.
- The same Skill produces the same kind of incomplete output.
- The same DAG node repeatedly enters fallback.
- The same input shape repeatedly needs an extra step.

## User Confirmation Flow

When a repeated exception is detected, PowerBanana should ask in business language:

```text
In the last 30 days, this scenario saw 3 tasks where payment terms were
missing from the main document but later found in an appendix.

Should PowerBanana handle this as part of the workflow?

Options:
1. Add this behavior to the existing Skill.
2. Create a new local Skill for appendix checks.
3. Add a Human Gate rule only.
4. Add golden/calibration cases only.
5. Ignore this pattern for now.
```

The user response creates a draft. It does not change runtime behavior directly.

## Memory Maintenance Heartbeat

PowerBanana should use heartbeat-style checks as a read-only governance digest over memory and learning state. This is not a proactive autonomous assistant. It is a scheduled review that tells the Main Agent where attention may be needed.

Heartbeat memory checks:

- Episode index is out of sync with source Episode files.
- Candidate proposals are near TTL expiry.
- Repeated exceptions passed threshold but have not been triaged.
- Process memory records are stale or past review date.
- A Skill/evaluator draft was created from exception learning but still lacks lint, tests, or approval.
- Checkpoint summaries have not reconciled recent TaskBlackboard events.
- Approval or Human Gate decisions referenced by memory candidates are missing or unresolved.

Example digest:

```yaml
memory_heartbeat_digest:
  digest_id: mhb_001
  scenario_id: contract_payment_review
  generated_at: 2026-06-12T10:00:00+08:00
  findings:
    - type: candidate_near_expiry
      severity: medium
      ref: memory://contract_payment_review/candidates/exception_001
      suggested_main_agent_action: ask_user_or_defer
    - type: episode_index_lag
      severity: low
      ref: memory://contract_payment_review/index/episode_index.sqlite
      suggested_main_agent_action: schedule_reconcile
```

Rules:

- The heartbeat creates a digest and runtime event only.
- The Main Agent decides whether the digest becomes a user-facing message.
- The heartbeat cannot activate memory, approve candidates, modify Skills, or change Scenario Packs.
- Digest findings must reference structured memory records, not raw transcripts.

## Exception Candidate Record

```json
{
  "candidate_id": "exception_001",
  "scenario_id": "contract_payment_review",
  "type": "repeated_exception",
  "summary": "Payment terms were missing in the main document but found in an appendix in 3 recent tasks.",
  "occurrence_count": 3,
  "time_window_days": 30,
  "evidence_refs": [
    "episode_001",
    "episode_004",
    "episode_007"
  ],
  "impacted_skill": "local:extract_contract_terms@0.1.0",
  "suggested_actions": [
    "modify_existing_skill",
    "add_calibration_case"
  ],
  "status": "pending_user_decision"
}
```

## Candidate State Machines

Exception candidates have a separate lifecycle from active memory and active Skills.

```text
observed
-> candidate_created
-> threshold_met
-> pending_user_decision
-> user_selected_action
-> draft_created
-> lint_passed
-> tests_passed
-> approved
-> activated
-> monitored
-> retained_or_rolled_back
```

Terminal states:

- `ignored`
- `rejected`
- `suppressed`
- `expired`
- `superseded`
- `rolled_back`

Rules:

- `observed` can be created from one event, but it cannot prompt the user.
- `threshold_met` requires the exception learning policy to pass.
- `pending_user_decision` is the first user-facing state.
- `draft_created` still has no runtime effect.
- `activated` requires approval and version publication.
- `monitored` tracks whether the change improves evaluator results, reduces Human Gate frequency, or reduces repeated user corrections.
- `retained_or_rolled_back` must record the decision, evidence, and rollback target when relevant.
- Suppressed patterns must record who suppressed them and when to ask again, if ever.

Process memory records have a simpler lifecycle:

```text
candidate
-> validated
-> active
-> stale
-> expired
```

Only `active` process memory can be considered by Context Manager, and even then only as a hint.

## Layer Promotion And Demotion

Memory does not move between layers automatically just because it exists. Each promotion requires evidence, policy checks, and the right approval boundary.

Default promotion path:

```text
Short-Term Runtime Memory
-> closed TaskBlackboard summary
-> Mid-Term Episode
-> repeated pattern or explicit user preference
-> Memory Candidate
-> policy and safety validation
-> user or administrator approval
-> Long-Term Governed Memory or scenario-local Skill/Evaluator/Golden Case draft
```

Promotion rules:

- Short-Term Runtime Memory can create an Episode only after task closure.
- One Episode can create a candidate, but cannot create Long-Term Governed Memory by itself unless the user explicitly marks it as a stable preference.
- Repeated Episode signals can create an Exception Candidate when the threshold policy passes.
- Long-Term Governed Memory requires source refs, confidence, allowed use, expiry or review date, and an owner.
- Skill, evaluator, golden case, and calibration case changes require linting, replay, and approval before activation.

Demotion and cleanup rules:

- Old Episodes can be compressed into aggregate summaries when they exceed retention windows.
- Stale Long-Term Governed Memory should move to `stale` before expiry.
- Superseded records must keep a pointer to the replacing record.
- Failed evolved Skills or evaluator changes should be rolled back and linked to the candidate that caused the change.
- Suppressed patterns stay visible in governance records but should not keep prompting the user.

Long-term memory should be reviewed on a schedule:

```yaml
memory_review_policy:
  process_memory_review_days: 90
  episode_retention_days: 60
  stale_grace_days: 30
  require_owner_for_long_term: true
  require_source_refs: true
  allow_auto_expiry: true
```

## Candidate Actions

PowerBanana can propose:

- Modify an existing scenario-local Skill.
- Create a new scenario-local Skill.
- Add a Human Gate rule.
- Add or adjust an evaluator.
- Add golden cases.
- Add calibration cases.
- Ignore or suppress the pattern.

It must not:

- Automatically modify a Skill.
- Automatically create an enabled Skill.
- Promote a local Skill to global.
- Store the exception as industry knowledge.
- Treat repeated user corrections as authoritative domain policy without approval.

## Skill Change Lifecycle

When the user chooses to modify or create a Skill:

```text
user confirms exception candidate
-> create Skill change draft
-> generate paired evaluator or golden/calibration case drafts when needed
-> lint Skill manifest and Scenario Pack
-> run affected golden and calibration cases
-> request domain-owner or administrator approval
-> publish new local Skill version or discard draft
```

Existing Skill example:

```text
local:extract_contract_terms@0.1.0
-> draft change
-> local:extract_contract_terms@0.2.0
```

New Skill example:

```text
local:check_contract_appendix@0.1.0
```

New Skills are scenario-local by default. Promotion to global requires separate multi-scenario evidence, review, tests, versioning, and approval.

## Context Manager Rules

Memory enters prompts only through Context Manager.

Context Manager may inject:

- Short-Term Runtime Memory needed for continuation, recovery, or coordination.
- Mid-Term Episodic Memory returned by approved Episode Search.
- Long-Term Governed Memory relevant to report format or workflow behavior.
- Evolution Loop candidates when asking the user for confirmation or running governance review.

Context Manager must not inject:

- Raw episode transcripts.
- Unapproved exception candidates as instructions.
- Distill drafts as active rules.
- Memory items with `allowed_use` incompatible with the current node.
- Any memory item that conflicts with current TaskBlackboard evidence or EvaluationResults.

## Context Injection Policy

Memory injection should be bounded and purpose-specific.

Suggested budgets:

```yaml
context_memory_budget:
  short_term_runtime_tokens: 1200
  checkpoint_tokens: 700
  task_progress_tokens: 500
  mid_term_episode_tokens: 800
  process_memory_tokens: 500
  long_term_governed_tokens: 500
  evolution_prompt_tokens: 500
```

Injection rules:

- Short-Term Runtime Memory is injected when needed for active execution, continuation, recovery, or coordination.
- Checkpoint and task progress may be injected when resuming or continuing a long task.
- Mid-Term Episodes are retrieved on demand; they are not injected by default.
- Long-Term Governed Memory may be injected at task start as a frozen scenario snapshot.
- Evolution candidates may be injected only when the system is asking the user for a decision or running governance review.
- Distill drafts are never injected as instructions for normal task execution.

If token budget is exceeded, the priority order is:

1. Current TaskBlackboard state.
2. Blocking EvaluationResults and Human Gates.
3. Checkpoint next action.
4. Task progress summary.
5. Active Long-Term Governed Process Memory.
6. Mid-Term Episode search results.
7. Evolution candidates for user confirmation.

Context Manager must label every injected memory item with its layer, source ref, allowed use, and confidence. Unlabeled memory cannot enter prompts.

## Context Budgeting And Rebuild

PowerBanana should use section-aware context budgeting rather than arbitrary text truncation. The goal is to keep the context bundle useful after long tasks, compaction, retries, or multi-agent execution without flooding the model with raw history.

Suggested bundle section budgets:

```yaml
scenario_context_bundle_budget:
  scenario_identity_tokens: 300
  active_user_intent_tokens: 500
  blocking_controls_tokens: 800
  taskblackboard_summary_tokens: 1200
  checkpoint_tokens: 900
  subagent_progress_tokens: 700
  long_term_governed_memory_tokens: 500
  retrieved_episode_tokens: 800
  evolution_candidate_tokens: 500
  memory_keys_index_tokens: 400
  future_knowledge_refs_tokens: 800
```

Section-aware rules:

- Preserve section headers and source refs even when bodies are clipped.
- Prefer the current node, blocking controls, and next action over older narrative.
- When a section exceeds its budget, keep a concise head plus a pointer to the full source.
- Do not split exact-form values such as thresholds, rule IDs, evaluator IDs, dataset versions, or file paths.
- Do not split tool-call and tool-result pairs needed to understand current state.
- Do not compact Human Gate decisions, approval records, or write-action previews.

Tail preservation should keep the most recent execution context:

```yaml
tail_preservation_policy:
  min_recent_tokens: 10000
  max_recent_tokens_soft: 20000
  min_recent_text_messages: 5
  preserve_tool_call_pairs: true
  preserve_human_gate_turns: true
  preserve_evaluation_repair_turns: true
```

Rebuild flow:

```text
context boundary chosen
-> ScenarioCheckpointWriter settles or times out visibly
-> Context Manager compiles Scenario Context Bundle
-> synthetic continuation message is inserted or equivalent prompt section is emitted
-> recent tail is preserved
-> compactable tool result bodies are replaced with artifact refs and short summaries
-> agent resumes directly from the latest state
```

Compactable content:

- Read-only file previews that can be reopened by artifact ref.
- Large data snapshots already stored in TaskBlackboard artifacts.
- Search result bodies already summarized and source-linked.
- Tool success confirmations that add no decision state.

Non-compactable content:

- User confirmations.
- Human Gate decisions.
- Evaluation failures and repair instructions.
- Approval previews for write actions.
- Exact-form values required for replay.
- Current task objective and next action.

The continuation prompt should explicitly say that the bundle is loaded, recent messages are real history, and the agent should resume directly rather than recapping or asking what to do next.

## Memory Safety

Because memory can enter prompts, every memory item must be treated as potentially unsafe until validated.

Validation should check:

- Prompt-injection phrases.
- Credential exfiltration requests.
- Hidden or bidirectional Unicode characters.
- Unsupported `memory_type`.
- Unsupported `allowed_use`.
- Missing source refs.
- Sensitive values that violate retention policy.
- Business knowledge content that belongs in Knowledge Base.
- Search-index poisoning, including malicious text hidden in user corrections, source file cells, filenames, or tool outputs.

Unsafe items are rejected or quarantined as candidates. They are not injected into Context Manager output.

Episode Search has two safety gates:

- Index-time gate: only redacted summaries can enter SQLite FTS5.
- Retrieval-time gate: matched summaries are scanned again before Context Manager injection.

Memory conflict rules:

- Current TaskBlackboard evidence beats memory.
- Current EvaluationResults beat memory.
- Human Gate decisions beat memory.
- Future Knowledge Base retrievals beat memory for domain facts.
- Newer approved process memory beats older process memory only when it supersedes the old record explicitly.

## Phased Rollout

Phase 0: current baseline

- `MemoryManager.write_task_summary()` writes a minimal task summary to the in-memory TaskBlackboard.
- No persistent small-capacity memory.
- No checkpoint files.
- No Episode Store.
- No MemoryPathGuard.

Phase 1:

- Short-Term Runtime Memory.
- Scenario Context Manager baseline.
- Scenario Context Bundle for task start and resume.
- Scenario-local checkpoints.
- Task progress.
- Notes.
- Episode summaries.
- MemoryPathGuard.
- No long-term automatic writes.
- Small-capacity scenario `MEMORY.md` generated from approved process memory.

Phase 2:

- Mid-Term Episodic Memory.
- Scenario-local SQLite + FTS5 Episode Search index.
- Lazy reconcile for Episode Search index.
- Unicode tokenization, phrase-quoted FTS5 queries, BM25 ranking, and relative score floor.
- Retention, redaction, and rebuild policies for Episodes.
- Search only through Context Manager.
- Memory heartbeat digest for stale candidates, index lag, unresolved approvals, and checkpoint reconciliation lag.

Phase 3:

- Long-Term Governed Memory records.
- Process Memory with strict `allowed_use`.
- Memory promotion, demotion, expiry, supersession, and rollback metadata.
- Frozen `MEMORY.md` snapshots generated from approved records.
- Section-aware context budgeting.
- Tail preservation and compactable tool-result summaries.
- Optional hybrid Episode Search policy design, still restricted to redacted process and Episode summaries.

Phase 4:

- Evolution Memory Loop.
- Exception Learning Assistant.
- Exception Candidate records.
- Draft-only Skill, evaluator, golden case, and calibration case suggestions.
- Replay and monitoring for evolved changes.

Phase 5:

- Knowledge Base integration.
- Context Manager combines Memory and retrieved knowledge.
- Memory remains process-oriented; Knowledge Base becomes the source for domain knowledge.

## Testing

Tests should cover:

- Rejection of cross-scenario memory reads.
- Rejection of ordinary-agent writes to checkpoint-owned files.
- Short-Term Runtime Memory closure creating an Episode candidate only after task finalization.
- Concurrent sub-agent progress reconciliation without corrupting checkpoint-owned files.
- Sub-agent progress reports materialized only by `ScenarioCheckpointWriter`.
- Progress reconciliation based on `written_at` and `last_reconciled_written_at`.
- Checkpoint reconstruction from `CHECKPOINT.md` and task progress.
- Scenario Context Bundle includes pinned scenario identity and active recall protocol.
- Context Manager refuses whole-file re-read instructions for memory already loaded unless a missing tail is explicitly requested.
- Section-aware context budgeting preserves headers, source refs, and exact-form values.
- Tail preservation keeps recent message and tool-call continuity.
- Microcompact replaces only compactable tool result bodies and preserves Human Gates, Evaluation repair turns, and approvals.
- Episode creation without raw source document leakage.
- SQLite + FTS5 Episode Search indexing only redacted summary fields.
- SQLite + FTS5 query builder handles punctuation, CJK tokens, and empty queries safely.
- Episode Search uses scope filters, BM25 ranking, relative score floor, and result limits.
- Episode Search results filtered by scenario, retention, redaction level, and allowed use.
- Rebuilding `index/episode_index.sqlite` from Episodes and structured records.
- Small-capacity `MEMORY.md` budget enforcement.
- Process Memory schema validation.
- Layer field validation for `short_term_runtime`, `mid_term_episodic`, `long_term_governed`, and `evolution_loop`.
- Memory promotion from Episode to Candidate to Long-Term Governed Memory only through policy gates.
- Stale, expired, superseded, and rolled-back memory records are not injected as active hints.
- Rejection of unsupported `memory_type` and `allowed_use`.
- Rejection or quarantine of prompt-injection-like memory content.
- Exception candidate creation only after threshold triggers.
- No suggestion when repeated signal is below threshold.
- Suppression state preventing repeated prompts for ignored patterns.
- User confirmation creates a draft, not an enabled Skill.
- Existing Skill modification creates a versioned draft.
- New Skill proposal stays scenario-local.
- Distill drafts cannot affect runtime until linting, tests, and approval pass.
- Evolved Skill or evaluator changes move into monitoring and can be rolled back.
- Context Manager refuses to inject unapproved candidates as instructions.
- Context Manager respects memory token budgets and priority order.
- Context Manager labels injected memory with layer, source ref, allowed use, and confidence.
- Memory does not override TaskBlackboard, EvaluationResult, Human Gate, or Knowledge Base evidence.
- Hybrid retrieval tests proving vector results are scoped, redacted, source-linked, budget-clipped, and limited to Episode/process memory summaries.
- Memory heartbeat tests proving stale candidates, index lag, unresolved approvals, and checkpoint lag create digests without activating memory or changing Skills.

## Success Criteria

The Memory System is successful when PowerBanana can resume long-running scenario tasks, explain task progress, search recent similar Episodes, preserve approved process memory, and detect repeated special cases in fixed business workflows without storing industry knowledge or changing Skills automatically.

The agent may ask the user whether a repeated exception should become a Skill or evaluator improvement, but runtime behavior changes only after draft generation, linting, regression checks, approval, and post-activation monitoring.
