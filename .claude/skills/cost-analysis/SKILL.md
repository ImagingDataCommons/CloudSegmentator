---
name: cost-analysis
description: Measure what a Terra submission actually cost and predict runs before launching them (submission_cost → cost_model fit/predict/batch/evaluate). Use for "what did that run cost", "predict the full run", "is this batch size right".
---

# Cost measurement and prediction

Read [`util/executionAnalytics/README.md`](../../../util/executionAnalytics/README.md)
first — the approach, runbook, file formats, *Findings so far*, and caveats are
there. This skill is the procedure.

## Measuring a finished submission

1. Check when it finished. Billing settles **24–48 h** after the run; before
   that the numbers are a lower bound — say so, and offer to re-measure later.
2. `python submission_cost.py <submission URL or id> [--workspace <namespace>/<name>]`
   from `util/executionAnalytics`. If the workspace isn't in the URL or
   `--workspace`, ask the user. If the billing export isn't readable, use
   `--no-bq` and label the result as an estimate.
3. Report $/series and the preemption overhead (`runtimeMin` vs
   `doneRuntimeMin`, `attempts`) — never Terra's `cost` field alone.

The `submission_*.csv` outputs are gitignored; don't commit run data.

## Predicting a run

1. Use a model fitted on the **same configuration** (image digests, tasks,
   radiomics engine, region). If the config changed since the fit, say the
   prediction is unreliable and suggest a small pilot to refit.
2. `cost_model.py predict` for the manifest; `cost_model.py batch` if the
   question is batch size.
3. Present preemption as calm vs churn scenarios, not a single number.
