# Power Banana Design Documentation

Power Banana is currently in the design-convergence stage. The repository keeps historical and topic-specific design documents, but future implementation work should use one current authority.

## Current Authority

Use [Power Banana Current Design](powerbanana-current-design.md) as the source of truth for future implementation.

Older documents are retained as reference or historical material. When any document conflicts with the current design, the current design wins.

## Project Areas

| Area | Page |
|---|---|
| Current implementation authority | [Power Banana Current Design](powerbanana-current-design.md) |
| Running and deployment | [Deployment](deployment.md) |
| Planner boundary | [Planner](planner.md) |
| Planner lexicon | [Planner Lexicon](planner-lexicon.md) |
| Task Blackboard | [Task Blackboard](blackboard.md) |
| Golden cases and calibration | [Regression and Calibration](regression-and-calibration.md) |
| Evaluation governance | [Evaluation Layer](evaluation-layer.md) |
| Near-term design adjustment | [Power Banana Near-Term Design Adjustment](superpowers/specs/2026-06-12-powerbanana-near-term-design-adjustment.md) |
| Scenario-contract migration route | [Power Banana Scenario Contract Migration Design](superpowers/specs/2026-06-13-powerbanana-scenario-contract-migration-design.md) |
| Skill-governed runtime direction | [Skill-Governed Runtime Design](superpowers/specs/2026-06-11-skill-governed-runtime-design.md) |
| Runtime memory system | [Power Banana Memory System Design](superpowers/specs/2026-06-11-powerbanana-memory-system-design.md) |
| GitHub workflow | [Repository Workflow](repository-workflow.md) |
| Repository hygiene | [Repository Hygiene](repository-hygiene.md) |
| Historical architecture source | [AgentX v0.3 Design](enterprise_agent_design_v0.3.md) |

## Consolidated Design Scope

The current design keeps the first scenario intentionally narrow:

- CSV files.
- Simple XLSX files when `openpyxl` is installed.
- Single-table metric ranking for conversion rate, revenue, orders, and visits.
- Deterministic no-LLM execution by default.
- Deterministic candidate planning before DAG execution.
- Strict plan validation before DAG execution.
- Governed planner lexicon for scenario classification.
- Optional real LLM vocabulary advisor for candidate-only missing-term suggestions.
- Local vocabulary suggestion approval flow with dry-run, validation, golden case drafts, Planner promotion, and end-to-end golden promotion.
- Vocabulary advisor golden cases for testing LLM-style suggestion safety without real API calls.
- Task DAG trace, Blackboard events, Step trace, Evaluation result.
- Golden cases, calibration cases, and replay snapshots.

Out of scope for the first implementation pass:

- General natural-language analytics.
- Multi-table joins.
- Database connections.
- Write-back, exports, or external actions.
- LLM planning.
