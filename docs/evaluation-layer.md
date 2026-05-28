# Evaluation Layer

PowerBanana uses a deterministic, extensible Evaluation Layer. Evaluators inspect structured context and return an `EvaluatorOutcome`; the `EvaluationRunner` aggregates all outcomes into one `EvaluationResult`.

## Default Evaluators

| Evaluator | Purpose | Typical Gate |
|---|---|---|
| `schema_evaluator` | Ensures required evaluation inputs exist | `block` |
| `dataset_reference_evaluator` | Checks dataset version consistency | `block` |
| `field_reference_evaluator` | Checks result fields reference dataset columns | `return_partial` |
| `evidence_coverage_evaluator` | Checks evidence refs and step trace coverage | `block` |
| `metric_recompute_evaluator` | Recomputes conversion rate from rows | `block` |
| `context_security_evaluator` | Checks prompt-injection findings were handled as data | `human_review` |

## Gate Actions

| Gate Action | Meaning |
|---|---|
| `pass` | Return normally |
| `pass_with_warning` | Return normally with warnings |
| `return_partial` | Return a partial answer with limitations |
| `needs_clarification` | Ask the user for clarification |
| `human_review` | Require human review |
| `block` | Do not return the candidate as a final answer |

## Custom Evaluator

```python
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
    "evals/golden_cases/conversion_rate_basic.csv",
    "Which channel has the highest conversion rate?",
)
```

## Persistence and Replay

Persistence is opt-in:

```python
from pathlib import Path

from powerbanana.agent import PowerBananaAgent
from powerbanana.evaluation import EvaluationRunner, LocalEvaluationStore, ReplayRunner


runner = EvaluationRunner(store=LocalEvaluationStore(Path("runs")))
report = PowerBananaAgent(evaluation_runner=runner).answer(
    Path("evals/golden_cases/conversion_rate_basic.csv"),
    "Which channel has the highest conversion rate?",
)

replay = ReplayRunner().run_snapshot(report.evaluation.snapshot_ref)
print(replay)
```

This writes:

- `runs/evaluations.jsonl`
- `runs/replay_snapshots/*.json`
