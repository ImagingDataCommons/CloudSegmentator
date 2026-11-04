# Notes for coding agents

CloudSegmentator runs segmentation models (MOOSE, TotalSegmentator) on IDC imaging
data in the cloud and converts the results to DICOM-SEG, radiomics and DICOM SR.

## Layout

- `workflows/harmonized/` — the model-agnostic workflow (one WDL, three notebooks).
  Start at [`workflows/harmonized/Docs/README.md`](workflows/harmonized/Docs/README.md).
- `workflows/common/`, `workflows/models/<model>/` — its shared and per-model
  notebooks, Dockerfiles and resources.
- `workflows/MOOSE/`, `workflows/TotalSegmentator/` — the older per-model
  workflows; keep changes to them separate.
- `util/terraOps/` — command-line tools to submit and monitor Terra runs.
- `util/executionAnalytics/` — cost measurement and prediction.
- `paper/` — the scripts and data behind the 2026 paper's figures, a record of
  fixed runs. Start at [`paper/README.md`](paper/README.md).

## Docs to read before acting

| Task | Read |
|---|---|
| Changing notebooks or the WDL, reproducing a failure | [`workflows/harmonized/Docs/development.md`](workflows/harmonized/Docs/development.md) |
| Submitting, monitoring or triaging Terra runs; checking delivered DICOM | [`workflows/harmonized/Docs/operations.md`](workflows/harmonized/Docs/operations.md) |
| Measuring or predicting cost | [`util/executionAnalytics/README.md`](util/executionAnalytics/README.md) |

Claude Code users get these as project skills in `.claude/skills/`
(`pipeline-dev`, `terra-runs`, `dicom-delivery`, `cost-analysis`).

## Rules

- **Never guess cloud targets.** Terra workspace, method config, image registry,
  and delivery bucket come from flags or `TERRA_WORKSPACE`,
  `TERRA_METHOD_CONFIG`, `SEGMENTATOR_REGISTRY`, `SEGMENTATOR_DELIVERY_BUCKET`.
  If one is unset, ask.
- **Confirm before spending or publishing**: submitting Terra jobs, aborting
  them, pushing Docker images, and uploading to buckets or DICOM stores all
  need the user's go-ahead.
- **Notebooks**: edit cell sources surgically, never re-serialize a whole
  notebook, never commit outputs (see development.md).
- **No run data in git**: per-submission CSVs, billing exports, manifests and
  figures from individual runs stay local (`.gitignore` covers the common ones).
- **`paper/` is exempt from "never guess cloud targets" and "no run data in git".**
  It records the paper's runs, so its scripts name their submissions, workspaces
  and buckets, and `paper/data/` holds the tables derived from them. Change it
  only to correct the paper's analysis, and name a figure's files and function by
  its keyword, as `paper/README.md` describes.
