# Evaluation Layer

PowerBanana uses a deterministic, extensible Evaluation Layer. Evaluators inspect structured context and return an `EvaluatorOutcome`; the `EvaluationRunner` aggregates all outcomes into one `EvaluationResult`.

The layer now evaluates four targets:

| Target | Entry Point | Report Field |
|---|---|---|
| Planner trace | `EvaluationRunner.evaluate_planner_trace` | `planner_evaluation` |
| Planner routing gate | `EvaluationRunner.evaluate_gate` | `evaluation` |
| Vocabulary suggestion gate | `EvaluationRunner.evaluate_gate` | `evaluation` |
| Analysis result | `EvaluationRunner.evaluate_analysis` | `evaluation` |

## Default Evaluators

| Evaluator | Purpose | Typical Gate |
|---|---|---|
| `planner_intent_evaluator` | Checks Planner intent, confidence, scenario consistency, and required warnings | `block` |
| `schema_evaluator` | Ensures required evaluation inputs exist | `block` |
| `dataset_reference_evaluator` | Checks dataset version consistency | `block` |
| `field_reference_evaluator` | Checks result fields reference dataset columns | `return_partial` |
| `evidence_coverage_evaluator` | Checks evidence refs and step trace coverage | `block` |
| `metric_recompute_evaluator` | Recomputes requested metric values from rows | `block` |
| `context_security_evaluator` | Checks prompt-injection findings were handled as data | `human_review` |

## Planner Evaluation

`PlannerIntentEvaluator` checks Planner output before the Task Plan is frozen and executed. It blocks when:

- `PlannerTrace` is missing.
- `PlannerTrace.intent` is missing.
- `PlannerTrace.scenario_id` and `PlannerIntent.scenario_id` disagree.
- A known non-`unknown` scenario has confidence below `0.5`.
- `unsupported_*` scenarios do not carry `unsupported_capability`.
- `ambiguous_metric` does not carry `missing_metric`.
- `metric_analysis` scenarios do not include an `AnalysisRequest`, unless the Planner explicitly marks `needs_vocabulary_suggestion`.

Planner evaluation is recorded separately as `planner_evaluation`, so final answer evaluation remains focused on the analysis result. If planner evaluation returns `block`, PowerBanana returns a blocked report immediately and does not validate the candidate plan, load the dataset, or run DAG nodes.

After planner evaluation passes, `PowerBananaAgent` treats `metric_analysis` as the executable v0.1 scenario. `ambiguous_metric`, `unsupported_*`, and `unknown` scenarios record a `planner_routing_gate` evaluation with `needs_clarification`, create a human clarification gate, and return before dataset loading or DAG execution.

If the Planner marks `needs_vocabulary_suggestion`, PowerBanana profiles the dataset, asks the injected vocabulary advisor for a candidate, validates it, then records a `vocabulary_suggestion_gate` with `needs_clarification`. The analysis is not executed until the vocabulary has been approved and added.

## Gate Actions

| Gate Action | Meaning |
|---|---|
| `pass` | Return normally |
| `pass_with_warning` | Return normally with warnings |
| `return_partial` | Return a partial answer with limitations |
| `needs_clarification` | Ask the user for clarification |
| `human_review` | Require human review |
| `block` | Do not return the candidate as a final answer |

## User-Friendly Evaluation

Evaluation should be usable by non-technical domain owners. Users should be able to describe what a good result means, what must be checked, and when a person should review the output, without writing evaluator code.

The user-friendly layer has three parts:

| Part | Purpose |
|---|---|
| Evaluation Assistant | Uses guided LLM conversation to collect quality rules from the user |
| Evaluation Policy / Contract | Stores the structured, linted rules that the runtime can execute |
| Human-Friendly Evaluation Report | Explains evaluation results in business language while preserving technical audit fields |

The LLM is only a drafting and explanation assistant. It does not decide whether a result is trusted, cannot disable baseline evaluators, and cannot enable a scenario by itself.

## Evaluation Assistant

The Evaluation Assistant should ask targeted questions while a Scenario Pack is being initialized or explicitly revised:

1. What should a good final answer contain?
2. Which mistakes are unacceptable?
3. Which claims must cite evidence, source rows, or source text?
4. Which conditions should return a partial result?
5. Which conditions should ask the user for clarification?
6. Which conditions require human review?
7. What risk thresholds or business rules matter?
8. Can the user provide one good example and one bad example?

The assistant may generate:

- `EVALUATION.md` draft.
- Structured Evaluation Contract draft.
- Golden case drafts.
- Calibration case drafts.
- Plain-language explanations of linter failures.

The assistant must not:

- Disable baseline evaluators such as schema, evidence, context security, or source-version checks.
- Mark high-risk rules as automatically passing.
- Enable unregistered evaluators.
- Bypass calibration cases.
- Approve or enable its own draft.
- Treat natural-language prose as executable policy.

## Initialization And Rule Updates

Evaluation setup should run during Agent initialization, not during every task.

The Evaluation Assistant should run when:

- The Agent starts for the first time and no enabled Scenario Pack exists.
- A domain owner creates a new Scenario Pack.
- A user with permission asks to add or modify a quality rule.
- An imported Scenario Pack has no valid Evaluation Contract in the current environment.

Normal task execution should not regenerate `EVALUATION.md` or the Evaluation Contract. Runtime tasks load the active, enabled Scenario Pack and paired Evaluation Contract, then run deterministic evaluators.

Rule updates are versioned:

```text
user requests evaluation rule change
-> assistant asks follow-up questions
-> create change request
-> generate new EVALUATION.md draft version
-> show human-readable diff
-> run Evaluation Policy lint
-> compile new Evaluation Contract
-> run affected golden and calibration cases
-> request domain-owner or administrator approval
-> activate new version or keep existing version
```

Enabled Evaluation Packs are immutable. Running tasks remain pinned to the Evaluation Contract version they started with. New tasks use a changed Evaluation Contract only after linting, calibration, and approval.

## Evaluation Contract

Every enabled Scenario Pack must have a paired Evaluation Contract. The contract binds the scenario, Skills, expected artifacts, required evaluators, and gate rules.

Example:

```yaml
evaluation_contract:
  scenario_id: contract_payment_review
  version: 0.1.0
  required_baseline_evaluators:
    - schema_evaluator@0.1.0
    - evidence_coverage_evaluator@0.1.0
    - context_security_evaluator@0.1.0
  skill_output_checks:
    extract_contract_terms@0.1.0:
      output_schema: ContractTerms
      required_evaluators:
        - schema_evaluator@0.1.0
        - evidence_coverage_evaluator@0.1.0
    detect_payment_risk@0.1.0:
      output_schema: PaymentRiskFinding
      required_evaluators:
        - contract_payment_rule_evaluator@0.1.0
  gate_rules:
    - id: missing_payment_terms
      condition: payment_terms.not_found
      gate_action: human_review
    - id: claim_without_evidence
      condition: report.claims_without_evidence > 0
      gate_action: block
```

`SCENARIO.md` explains how the scenario runs. `EVALUATION.md` explains how the scenario is judged. The runtime compiles both into the contract and executes only the structured fields that pass linting.

## Evaluation Layers

Evaluation should run in layers:

| Layer | Purpose | User configurable |
|---|---|---|
| Baseline | Schema, evidence, context safety, source version, ToolGateway boundary | No |
| Skill | Checks each Skill output against its schema and evidence requirements | Limited by Skill manifest |
| Scenario | Domain-specific business rules and thresholds | Yes, through builder and approval |
| Fan-in | Checks whether parallel outputs can be merged safely | Yes, through merge policy |
| Report | Checks final answer completeness, support, and safety | Yes, with baseline checks required |

The scheduler uses the strongest resulting gate action when deciding whether to continue, retry, ask for clarification, route to human review, return a partial result, or block.

## Human-Friendly Reports

Runtime reports should expose both machine fields and user-facing explanations.

Technical form:

```json
{
  "gate_action": "block",
  "failure_reasons": ["evidence_ref_not_in_step_trace"],
  "blocking_issues": ["missing evidence for report claim"]
}
```

User-facing form:

```text
Result not approved.

Why:
- One report claim is missing a source reference.

What to do:
- Add a source quote, source row, or route this result to human review.
```

The plain-language explanation may be generated with LLM assistance, but it must be grounded in the structured `EvaluationResult`. It cannot soften or override the gate action.

## Scenario Enablement

A Scenario Pack cannot move to `enabled` unless evaluation is complete enough to protect the workflow:

- `EVALUATION.md` exists.
- Evaluation Policy linting passes.
- Baseline evaluators are present.
- Every Skill output has an evaluator or explicit human review path.
- Every high-risk rule maps to Human Gate.
- Fan-in nodes have fan-in evaluator coverage.
- At least one positive golden case exists.
- At least one negative or escalation calibration case exists.
- A domain owner or administrator approves the pack.
- The active Scenario Pack version and active Evaluation Contract version are pinned for runtime tasks.

See [Skill-Governed Runtime Design](superpowers/specs/2026-06-11-skill-governed-runtime-design.md) for the paired Scenario Pack and Evaluation Contract design.

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
