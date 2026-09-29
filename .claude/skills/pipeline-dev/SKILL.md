---
name: pipeline-dev
description: Editing the harmonized workflow notebooks/WDL safely and debugging the pipeline locally (docker repro, checkpoint data recovery, papermill quirks). Use before modifying nb1/nb2/nb3, the WDL, or reproducing a Terra failure locally.
---

# Pipeline development and local debugging

Read [`workflows/harmonized/Docs/development.md`](../../../workflows/harmonized/Docs/development.md)
first — the notebook editing rules and the notebook ↔ WDL coupling rules there
are mandatory. Architecture and contracts:
[`workflows/harmonized/Docs/README.md`](../../../workflows/harmonized/Docs/README.md).

## Editing a notebook

1. Load it as JSON; change cells by exact-substring replacement, asserting each
   old string occurs exactly once. Keep each cell's storage form (list of lines
   vs single string), the file's newline style, and `indent=1`.
2. `compile()` every code cell.
3. `git diff --stat` — tens of lines, not hundreds. If it's hundreds, you
   normalized something; start over.
4. If you touched an output filename, a papermill parameter, or a fetched
   sidecar, make the matching WDL change in the same commit.

## Reproducing a Terra failure

1. Get the failing call's stderr from the workspace bucket (development.md →
   last section).
2. Pull its inputs from the run's checkpoint instead of re-downloading
   (development.md → *Recovering a failed run's data*).
3. Run the notebook with papermill inside the same image the run used (image
   digest is in the Cromwell metadata), with `--shm-size=8g`.
4. Fix, re-run locally, and only then suggest a small Terra run (`terra-runs`
   skill) to confirm.
