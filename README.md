# PowerBanana

PowerBanana is the v0.1 reference agent built from the AgentX v0.3 design.

It implements a narrow, auditable data-analysis workflow:

1. Load one CSV or simple XLSX dataset.
2. Create a dataset snapshot.
3. Profile basic schema and missing values.
4. Scan uploaded cells as untrusted data for prompt-injection patterns.
5. Execute controlled analysis steps through registered skill-like functions.
6. Recompute and evaluate the result before returning a report.

The v0.1 runtime includes explicit sub-agents:

| Sub-agent | Runtime | Responsibility |
|---|---|---|
| `data_profile_agent` | `workflow` | Load the file, create the dataset snapshot, profile columns, and scan untrusted cells. |
| `data_analysis_agent` | `autonomous` L2 | Execute the controlled Step Plan through skill-like functions. |
| `report_agent` | `workflow` | Run final consistency checks and produce the structured report. |

The runtime now includes the first governance pieces from the v0.3 design:

- `DeterministicDataFilePlanner` creates a candidate Task Plan before any DAG execution.
- `PlannerClassifier` maps user questions to known scenarios with the user-editable `config/planner_lexicon.csv`.
- `AnalysisRequestParser` maps supported metric terms from `config/analysis_terms.csv` into structured analysis requests.
- `LLMVocabularyAdvisor` can propose missing vocabulary terms, but suggestions require validation and user approval before CSV changes.
- `PlannerIntentEvaluator` checks Planner intent consistency and blocks DAG execution when planning is unsafe.
- Planner routing returns clarification for ambiguous, unsupported, or unknown scenarios before loading the dataset.
- `PlanValidator` rejects malformed plans, including empty plans, cycles, duplicate dependencies, disconnected roots, and scenario pattern mismatches.
- `TaskDagExecutor` schedules `data_profile_agent -> data_analysis_agent -> report_agent` only from frozen plans.
- `TaskBlackboard` records event log entries and structured Blackboard entries for artifacts, security findings, and evaluations.
- `TaskBlackboard` tracks artifact versions for first-write consistency checks.
- `SkillRegistry` exposes versioned skills such as `compute_grouped_metric@0.1.0` and `rank_metric_values@0.1.0`.
- `AutonomyPolicy` enforces the L2 analysis agent's allowed skills and maximum step count.
- `StepPlan` records skill steps with attempt and idempotency metadata before execution.
- `ToolGateway` owns read-only dataset loading through `dataset.read_snapshot`.
- `ContextManager` builds a trust-labeled context bundle for the autonomous analysis agent.
- `MemoryManager` writes a local working-memory task summary after report generation.
- `LLMSettings` records deterministic no-LLM mode for v0.1 while preserving a future model configuration boundary.
- `HumanGateRecord` captures clarification gates for ambiguous questions.

PowerBanana v0.1 intentionally supports a small first path: ranking channels by `conversion_rate`, `revenue`, `orders`, or `visits` from one table.

## Run

Interactive mode:

```powershell
python -m powerbanana.cli --interactive
```

PowerBanana starts with a yellow ASCII `POWER BANANA` logo, then asks for a dataset path and analysis question.

Single-run JSON mode:

```powershell
python -m powerbanana.cli path\to\data.csv "Which channel has the highest conversion rate?"
```

The single-run command prints a structured JSON report containing the answer, dataset snapshot, planner evaluation, security findings, step trace, final evaluation result, and limitations.

Docker:

```powershell
docker build -t powerbanana .
docker run --rm -it -v ${PWD}:/data powerbanana
```

Inside the container, type the mounted dataset path such as `/data/examples/sales.csv`. The image starts with `CMD ["powerbanana"]`, which opens the interactive CLI by default.

## Test

```powershell
python -m unittest discover -s tests
```

Run golden cases:

```powershell
python -c "from pathlib import Path; from powerbanana.evals import GoldenCaseRunner; print(GoldenCaseRunner(Path('evals/golden_cases')).run_all())"
```

Run planner golden cases:

```powershell
python -c "from pathlib import Path; from powerbanana.evals import PlannerGoldenCaseRunner; print(PlannerGoldenCaseRunner(Path('evals/planner_cases')).run_all())"
```

Edit Planner vocabulary:

```text
config/planner_lexicon.csv
config/analysis_terms.csv
```

Add scenario terms or metric terms by editing the CSV files and restarting PowerBanana.

LLM-assisted vocabulary management is candidate-only. When injected, an advisor can suggest a missing term such as `group_by=region`, but PowerBanana only records a `vocabulary_suggestion` and opens a human gate. It never writes the CSV or executes the suggested analysis in the same run.

Review pending vocabulary suggestions:

```powershell
python -m powerbanana.cli vocab list
python -m powerbanana.cli vocab approve vocab_000001 --dry-run
python -m powerbanana.cli vocab approve vocab_000001
python -m powerbanana.cli vocab promote-golden vocab_000001 --question "哪个地区收入最高？" --matched-signal "收入" --expected-metric revenue
python -m powerbanana.cli vocab reject vocab_000001 --note "Not a stable business term"
```

Suggestions are stored locally in `runs/vocabulary_suggestions.jsonl`. `--dry-run` previews the exact CSV row without changing files. Approving a suggestion appends it to `config/analysis_terms.csv`, reloads the CSV to verify the term is active, stores `validation_status` on the suggestion record, and writes a local golden case draft under `runs/golden_case_drafts/`. Rejecting a suggestion keeps the audit record but does not change active vocabulary.

After approval, review the generated golden case draft and promote it into `evals/planner_cases/` when it represents stable expected behavior. The promotion command validates the new Planner golden case before writing it. End-to-end golden cases still need a synthetic CSV fixture and expected answer before they can be added to `evals/golden_cases/`.

## Extending Evaluation

PowerBanana runs analysis results through an `EvaluationRunner`. You can register your own evaluator without changing the core agent:

```python
from pathlib import Path

from powerbanana.agent import PowerBananaAgent
from powerbanana.evaluation import EvaluationRunner, EvaluatorOutcome, default_evaluator_registry


class RowCountWarningEvaluator:
    evaluator_id = "row_count_warning_evaluator"
    version = "0.1.0"

    def evaluate(self, context):
        if context.dataset_snapshot and context.dataset_snapshot.row_count < 5:
            return EvaluatorOutcome(
                evaluator_id=self.evaluator_id,
                version=self.version,
                passed=True,
                warnings=["small_dataset"],
                scores={"row_count_policy": 0.5},
                gate_action="pass_with_warning",
            )
        return EvaluatorOutcome(self.evaluator_id, self.version, True)


registry = default_evaluator_registry()
registry.register(RowCountWarningEvaluator())
runner = EvaluationRunner(registry)

report = PowerBananaAgent(evaluation_runner=runner).answer(
    Path("evals/golden_cases/conversion_rate_basic.csv"),
    "Which channel has the highest conversion rate?",
)
```

Persist evaluation records and replay snapshots locally:

```python
from pathlib import Path

from powerbanana.agent import PowerBananaAgent
from powerbanana.evaluation import EvaluationRunner, LocalEvaluationStore, ReplayRunner


store = LocalEvaluationStore(Path("runs"))
runner = EvaluationRunner(store=store)

report = PowerBananaAgent(evaluation_runner=runner).answer(
    Path("evals/golden_cases/conversion_rate_basic.csv"),
    "Which channel has the highest conversion rate?",
)

replay = ReplayRunner().run_snapshot(report.evaluation.snapshot_ref)
print(replay)
```

Run calibration cases:

```powershell
python -c "from pathlib import Path; from powerbanana.evals import CalibrationRunner; print(CalibrationRunner(Path('evals/calibration_cases')).run_all())"
```

## Repository Layout

Keep these project assets in Git:

| Path | Purpose |
|---|---|
| `powerbanana/` | Runtime source code. |
| `config/` | User-editable Planner lexicon CSV. |
| `tests/` | Automated tests for the CLI, Planner, Blackboard, DAG, and governance behavior. |
| `evals/` | Synthetic planner cases, golden cases, calibration cases, and fixtures. |
| `docs/` | GitHub Pages documentation. |

Keep real user datasets and local run outputs out of Git. Use local-only directories such as `local_data/`, `private_data/`, `user_uploads/`, or `runs/`.

## Scope

Supported in v0.1:

- CSV files.
- Simple XLSX files when `openpyxl` is installed.
- Single-table analysis.
- Channel ranking for conversion rate, revenue, orders, and visits.
- LLM-style vocabulary suggestions with human approval gates.
- Step trace and deterministic evaluation.

Not supported yet:

- Multi-table joins.
- Database connections.
- Write-back, export, or external actions.
- Complex forecasting or BI dashboards.
