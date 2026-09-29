"""Verify a finished harmonized-workflow submission: per-workflow status, run
summaries, and the content of every error file.

Usage: check_outputs.py <submissionId> [--full-errors] [--workspace ns/name]

Default prints each error file's first lines; --full-errors prints everything.
Triage the errors against the KNOWN failure modes before treating anything as
new (see .claude/skills/terra-runs/SKILL.md):
  - itkimage2segimage "Invalid Value"      -> known series class (~2 %), both engines
  - radiomics_jl NaN "not allowed in JSON" -> known Radiomics.jl bug, drops one
                                              (series, model) radiomics + SR
  - "moose produced no output" (body_composition) -> anatomical (no L3 in FOV), benign
  - "Radiomics.jl worker crashed"          -> nb3 RAM pressure (giant series on 16 GB VM)
"""
import argparse
import json
import subprocess

from terra_common import add_workspace_arg, api, token, workspace


def gcs_cat(url):
    # One command string: with shell=True, a list runs only its first item on POSIX.
    # shell=True itself is kept so Windows resolves gcloud.cmd.
    return subprocess.run(f'gcloud storage cat "{url}"',
                          capture_output=True, text=True, shell=True).stdout


def main():
    ap = argparse.ArgumentParser(description="Verify a finished submission's outputs.")
    ap.add_argument("submission_id")
    ap.add_argument("--full-errors", action="store_true",
                    help="print every line of each error file")
    add_workspace_arg(ap)
    args = ap.parse_args()
    NS, NAME = workspace(args)
    sid, full = args.submission_id, args.full_errors
    tok = token()
    det = api(f"/workspaces/{NS}/{NAME}/submissions/{sid}", tok)
    print(f"submission {sid[:8]}: status={det.get('status')} "
          f"est=${det.get('cost', 0):.2f}  (billing settles ~24-48 h later)")
    for w in det.get("workflows", []):
        wid = w.get("workflowId")
        if not wid:
            continue
        md = api(f"/workspaces/{NS}/{NAME}/submissions/{sid}/workflows/{wid}"
                 "?includeKey=outputs&includeKey=status", tok)
        ent = w.get("workflowEntity", {}).get("entityName")
        print(f"\n===== entity {ent} [{wid[:8]}] {md.get('status')} =====")
        outs = md.get("outputs", {})
        for k in sorted(outs):
            v = outs[k]
            if not isinstance(v, str):
                continue
            if k.endswith("runSummary"):
                s = json.loads(gcs_cat(v))
                print(f"  summary: seg_err={s.get('dicom_seg_errors')} "
                      f"rad_err={s.get('radiomics_errors')} sr_err={s.get('sr_errors')} "
                      f"srs={s.get('structured_reports_written')} "
                      f"skipped_large={s.get('radiomics_labels_skipped_large')} "
                      f"engine={s.get('engine', '?')} v{s.get('engine_version', '?')} "
                      f"elapsed={s.get('total_elapsed_s', 0) / 60:.0f}m")
                # nb3 records GCS upload / DICOM-store import outcomes here; a failed
                # delivery does not fail the workflow, so this is the only signal.
                for step, d in (s.get("delivery") or {}).items():
                    if d.get("requested"):
                        print(f"  delivery {step}: {d.get('status')}"
                              + (f" ({d.get('dicom_seg_files', 0)} SEG, {d.get('sr_files', 0)} SR)"
                                 if step == "gcs_upload" else "")
                              + (f" -- {d['error']}" if d.get("error") else ""))
            elif "error" in k.lower():
                txt = gcs_cat(v).strip()
                lines = txt.splitlines()
                print(f"  --- {k.split('.')[-1]} ({len(lines)} lines) ---")
                print("\n".join(lines) if full else "\n".join(lines[:8]))


if __name__ == "__main__":
    main()
