# Golden Case Promotion v1 Design

Status: Reference  
Current authority: `docs/powerbanana-current-design.md`

Vocabulary approval now creates local golden case drafts, but those drafts do not yet enter the regression suite. This design adds a promotion step for turning reviewed drafts into formal Planner golden cases.

## Goals

- Promote a local draft from `runs/golden_case_drafts/` into `evals/planner_cases/`.
- Let users provide the real question and matched signal when the draft still contains placeholders.
- Add optional Planner golden checks for `analysis_request` fields such as `group_by`.
- Validate the promoted case before writing it into the formal suite.
- Keep end-to-end golden cases as manual follow-up until a synthetic dataset and expected answer are supplied.

## Non-Goals

- No automatic end-to-end golden case promotion.
- No automatic CSV fixture generation.
- No change to existing golden case formats unless they opt into `expected_analysis_request`.

## CLI

```powershell
python -m powerbanana.cli vocab promote-golden vocab_000001 --question "哪个地区收入最高？" --matched-signal "收入"
```

The command resolves the suggestion id through `runs/vocabulary_suggestions.jsonl`, reads its `golden_case_draft_path`, writes a candidate Planner golden case, validates it with `PlannerGoldenCaseRunner`, and only commits the new JSON file if validation passes.

## Planner Golden Extension

Planner golden JSON may include:

```json
{
  "expected_analysis_request": {
    "group_by": "region",
    "metric": "revenue"
  }
}
```

The runner checks only the fields provided. Existing cases without this field are unchanged.

## Error Handling

- Missing suggestion id or draft path fails with a clear error.
- Placeholder questions are rejected unless `--question` is supplied.
- Existing target files are rejected unless `--overwrite` is supplied.
- Failed validation leaves no formal golden case file behind.

## Testing

Tests cover successful promotion, placeholder rejection, analysis request checking in Planner golden cases, and CLI promotion through a suggestion id.
