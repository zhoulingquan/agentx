# LLM Vocabulary Manager v1 Design

## Goal

PowerBanana should use an LLM-style advisor as a candidate generator for missing vocabulary, especially dynamic `group_by` terms, while keeping CSV mutation behind validation and user approval.

## Scope

In scope:

- Add a pluggable `LLMVocabularyAdvisor` protocol.
- Add `VocabularySuggestion` records for proposed CSV terms.
- Use the advisor only when `metric_analysis` is detected but `AnalysisRequest` cannot be fully parsed.
- Validate suggestions against the uploaded dataset columns and existing analysis terms.
- Create a `HumanGateRecord` asking the user to approve the suggested vocabulary.
- Keep default runtime deterministic by using a no-op advisor unless one is injected.

Out of scope:

- Direct OpenAI API calls.
- Automatic CSV writes without user approval.
- Multi-turn approval handling in the CLI.
- Multi-table joins or forecasting.

## Runtime Flow

1. Planner classifies the question with `config/planner_lexicon.csv`.
2. Planner tries to parse `AnalysisRequest` with `config/analysis_terms.csv`.
3. If a metric is recognized but `group_by` is not, Planner records a warning instead of blocking.
4. DAG runs only far enough to profile the dataset.
5. `DataAnalysisAgent` asks `LLMVocabularyAdvisor` for a candidate vocabulary term using the question, dataset columns, and active terms.
6. `VocabularySuggestionValidator` rejects hallucinated fields, duplicate terms, or unsupported suggestion kinds.
7. If valid, PowerBanana records a `vocabulary_suggestion` Blackboard entry and opens a human clarification gate.

## Safety Rules

- LLM suggestions are never executed as final analysis requests in the same run.
- LLM suggestions are never written to CSV automatically.
- Suggested `value` must exist in the dataset columns.
- Suggested `terms` must not already be active in `config/analysis_terms.csv`.
- The final report must expose the suggestion through Blackboard entries and human gates.

## Example

Question:

```text
哪个地区收入最高？
```

Dataset columns:

```text
region,revenue
```

Suggestion:

```json
{
  "target_csv": "config/analysis_terms.csv",
  "kind": "group_by",
  "value": "region",
  "terms": ["地区", "区域"],
  "status": "pending_user_approval"
}
```

PowerBanana returns `needs_clarification` and asks whether this term should be added.
