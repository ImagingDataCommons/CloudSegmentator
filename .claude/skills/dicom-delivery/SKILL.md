---
name: dicom-delivery
description: Delivering DICOM-SEG/SR outputs to GCS and (eventually) a Healthcare DICOM store — bucket layout, overwrite semantics, provenance-metadata verification with pydicom, store-import prerequisites. Use for "upload results", "check the metadata", "import into the DICOM store".
---

# DICOM delivery: bucket upload, metadata, store import

Read [`workflows/harmonized/Docs/operations.md`](../../../workflows/harmonized/Docs/operations.md)
→ *Delivered outputs* first, and the *Contracts* section of
[`workflows/harmonized/Docs/README.md`](../../../workflows/harmonized/Docs/README.md)
for the metadata nb3 stamps on each SEG and SR.

## Procedure

- **Which bucket / store**: ask the user; don't reuse a destination from earlier
  runs or examples. Uploading publishes data to wherever it points.
- **Checking a delivery**: list with `gcloud storage ls -l` and judge freshness
  by object timestamp — re-runs overwrite but never delete, so stale files from
  an older run can sit next to new ones.
- **Checking metadata with pydicom**: always skip SegmentNumber 0 (the labelmap
  background segment). Concluding "metadata missing / MANUAL" from
  `SegmentSequence[0]` is the classic mistake. Read with
  `stop_before_pixels=True`.
- **DICOM store import** has never been validated end-to-end. Before enabling
  `dicomStoreImportUri`, walk the user through each prerequisite in
  operations.md and confirm it, then verify the result in the store itself —
  nb3 only warns on failure.
