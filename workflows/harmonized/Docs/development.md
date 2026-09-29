# Developing the harmonized workflow

Rules for changing the notebooks and WDL safely, and how to reproduce a Terra
failure locally. For the architecture and contracts, see [README.md](README.md);
for running batches, see [operations.md](operations.md).

## Where things are

| Piece | Path | Runs on |
|---|---|---|
| nb1 DICOM → NIfTI | `workflows/common/Notebooks/convertNotebook.ipynb` | GPU VM (model image) |
| nb2 inference | `workflows/models/<model>/Notebooks/inference.ipynb` | GPU VM (model image) |
| nb3 SEG / radiomics / SR / upload | `workflows/common/Notebooks/outputConversionNotebook.ipynb` | CPU VM (`output_conversion`) |
| Checkpoint/resume, attempt ledger, RAM sampler | `workflows/common/Notebooks/segmentator_checkpoint.py` | all three |
| Radiomics.jl driver | `workflows/common/Notebooks/radiomics_jl_extract.jl` | nb3 |
| WDL | `workflows/harmonized/Terra/twoVM.wdl` | — |

The legacy `workflows/MOOSE/` and `workflows/TotalSegmentator/` pipelines are
separate; don't port harmonized changes into them.

## Editing the notebooks

- **Cell `source` storage is mixed**: some cells are JSON lists of lines, some
  single strings. Don't normalize it — that rewrites the whole file. The files
  round-trip through `json.dumps(nb, indent=1, ensure_ascii=False)` (keep each
  file's newline style and trailing newline). Edit a cell by exact-substring
  replacement on its joined source, re-split with `splitlines(keepends=True)`
  only if the cell was already a list, and assert each old string occurs once.
- After an edit, `compile()` every code cell and check `git diff --stat`: a
  notebook change should be tens of lines, not hundreds.
- Don't commit notebook outputs.

## Notebook ↔ WDL coupling

- Output filenames, papermill `-p` names, and fetched sidecar files (the
  checkpoint module, SNOMED CSVs, `radiomicsFeaturesMaps.csv`,
  `radiomics_jl_extract.jl`) must change together in **one push** — Terra fetches
  them from GitHub raw at run time, and a mismatch fails every workflow after the
  compute is spent.
- WDL Booleans reach papermill as the strings `true` / `false`, which are
  both truthy. nb3 normalizes its flags with `_as_bool`; any new boolean
  parameter, in any notebook, needs the same treatment.
- A new notebook parameter with a default needs **no WDL change** (papermill
  only overrides what `-p` passes). Model-specific knobs go through
  `inferenceParamsYaml`.
- Undeclared task outputs are **not delocalized** — anything that must outlive
  the VM needs a WDL `output`, or has to ride in an existing archive or CSV.
  Metrics CSVs are append-only: add columns, don't rename or reorder, so
  `util/executionAnalytics` keeps parsing them.

## Reproducing locally

Smoke-test nb2/nb3 with papermill inside the images before spending a Terra
submission on a code change (commands in
[README.md](README.md#verifying-the-contracts-locally)); that has been the
validation path for every engine upgrade.

- **Images**: `<registry>/cloudsegmentator-inference-{moose,totalseg}:main` and
  `<registry>/cloudsegmentator-output-conversion:main`, or build them (see
  [Docker build order](README.md#docker-build-order)).
- nnU-Net passes tensors via `/dev/shm`: run containers with `--shm-size=8g`
  (Terra sizes shm from VM RAM).
- Docker Desktop's VM caps container RAM (about half the host), which is useful
  for reproducing a VM memory ceiling; sample `docker stats` to measure a
  model's peak RAM.
- **Windows**: if `docker info` hangs, Docker Desktop's backend is wedged —
  quit and relaunch it (and quit it when done: its WSL VM holds gigabytes).
  In Git Bash, prefix docker commands with `MSYS_NO_PATHCONV=1`, or `/data`
  arguments get rewritten to Windows paths.

### Recovering a failed run's data from its checkpoint

Failed or aborted runs leave their checkpoint behind (successful runs delete
it), so you can reproduce without re-downloading or re-converting:

```
<checkpointGcsPath>/<submissionId>_<workflowId>/
  nifti/all.tar.lz4            # nb1's converted NIfTIs (Boundary A contents)
  seg/<uid>/<model>.tar.lz4    # each finished nb2 (series, model) output
```

Without an `lz4` CLI (typical on Windows), `pip install lz4` and stream with
`tarfile.open(fileobj=lz4.frame.open(path), mode="r|")`.

The live log of a running task is in the workspace bucket under
`submissions/<sid>/Segmentator/<wid>/call-<task>/stderr` (retries under
`attempt-N/`, synced lazily); checkpoint object timestamps are the more
reliable liveness signal.
