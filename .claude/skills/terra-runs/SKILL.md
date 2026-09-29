---
name: terra-runs
description: Launch, monitor, and verify harmonized Segmentator (MOOSE + TotalSegmentator) runs on Terra — manifest → data table → submission → triage. Use for "run a batch", "resubmit", "check the runs", "why did this workflow fail".
---

# Running harmonized Segmentator workflows on Terra

Read [`workflows/harmonized/Docs/operations.md`](../../../workflows/harmonized/Docs/operations.md)
first — it holds the commands, sizing, and the known-failure table. This skill is
the procedure.

## Configuration

The `util/terraOps` scripts need a workspace, method config, image registry and
(optionally) a delivery bucket, from flags or `TERRA_WORKSPACE`,
`TERRA_METHOD_CONFIG`, `SEGMENTATOR_REGISTRY`, `SEGMENTATOR_DELIVERY_BUCKET`.
**If one is unset, ask the user — never guess or reuse values from old output.**
Submissions spend money in someone's billing project.

## Procedure

1. **Preflight** (operations.md → *Before any submission*): the branch the config
   fetches from is pushed, Dockstore has the WDL change, changed images are
   rebuilt and pushed. Stop and tell the user if any of these isn't true.
2. **Confirm the plan with the user** before submitting: series count, engines,
   workspace, and a cost estimate (`cost-analysis` skill, or ~$0.02–0.045 per
   series for both engines at 20 series per entity).
3. For a risky change, submit **one small entity** first and wait for it.
4. Build the manifest, upload it, submit (operations.md → *Submitting a batch*).
   Record the printed submission IDs.
5. Run `watch_wave.py` in the background. If a workflow runs for hours with no
   new checkpoint objects, read its live stderr before deciding it's stuck
   (operations.md → *Monitoring*). Ask before aborting anything.
6. When terminal, run `check_outputs.py <submissionId>` for each submission and
   classify every error against the *Triage* table. Report new signatures
   separately from known ones.
