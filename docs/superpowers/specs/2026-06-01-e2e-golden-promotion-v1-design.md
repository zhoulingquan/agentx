# End-to-End Golden Promotion v1 Design

Status: Reference  
Current authority: `docs/powerbanana-current-design.md`

Planner golden promotion proves that the Planner can classify and parse an approved vocabulary term. End-to-end golden promotion proves the full PowerBanana path can answer a real question against a real synthetic CSV fixture.

## Goals

- Promote a reviewed vocabulary draft into `evals/golden_cases/`.
- Require a real user question and a CSV dataset fixture.
- Run PowerBanana before writing the formal golden case.
- Copy the dataset into the golden case directory and write a matching JSON expectation file.
- Validate the generated case with `GoldenCaseRunner` before keeping it.

## Non-Goals

- No automatic creation of business datasets.
- No promotion of private or production data. Users should pass a synthetic CSV.
- No support for partial or clarification cases in this first version.

## CLI

```powershell
python -m powerbanana.cli vocab promote-e2e-golden vocab_000001 --dataset samples\region_revenue.csv --question "哪个地区收入最高？"
```

The command resolves the suggestion id through `runs/vocabulary_suggestions.jsonl`, runs PowerBanana with the provided dataset and question, copies the dataset into `evals/golden_cases/`, writes a formal golden case JSON, and validates it.

## Generated Case

The generated JSON captures the observed completed behavior:

- `expected_status`
- `expected_answer`
- `expected_top_value`
- `expected_evaluation_verdict`
- `expected_gate_action`
- `expected_failure_reasons`
- `expected_blocking_issues`
- `expected_security_findings_count`
- `expected_human_gates_count`
- `expected_step_skills`
- `expected_row_count`
- `expected_columns`
- `expected_analysis_result`

`GoldenCaseRunner` checks `expected_analysis_result` fields only when present, keeping older cases compatible.

## Error Handling

- Placeholder questions are rejected.
- Missing datasets are rejected.
- Non-completed PowerBanana reports are rejected.
- Existing target files are rejected unless `--overwrite` is supplied.
- Failed validation removes the generated files.

## Testing

Tests cover service promotion, placeholder rejection, generated JSON fields, runner validation, and CLI promotion through a suggestion id.
