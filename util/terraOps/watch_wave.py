"""Poll Terra submissions; print a line on every status change; exit when all done.

Usage: watch_wave.py <label:submissionId> [<label:submissionId> ...] [--workspace ns/name]

Each printed line is an event (drive it from a Monitor or a background shell and
treat exit as "all terminal"). Warns hourly after 3 h so preemption churn or a
livelocked task gets noticed. Poll errors (Terra 502s) are printed and retried.
"""
import argparse
import json
import time

from terra_common import add_workspace_arg, api, token, workspace


def main():
    ap = argparse.ArgumentParser(description="Watch submissions until all are terminal.")
    ap.add_argument("targets", nargs="+", metavar="label:submissionId")
    add_workspace_arg(ap)
    args = ap.parse_args()
    ns, name = workspace(args)
    targets = [a.split(":", 1) for a in args.targets]
    prev = {}
    start = time.time()
    warned_hours = set()
    while True:
        tok = token()
        all_done = True
        for label, sid in targets:
            try:
                det = api(f"/workspaces/{ns}/{name}/submissions/{sid}", tok,
                          timeout=60, exit_on_http_error=False)
            except Exception as exc:  # noqa: BLE001 - transient API errors
                print(f"{label}: poll error ({exc}); retrying", flush=True)
                all_done = False
                continue
            sub_status = det.get("status")
            wf = {}
            for w in det.get("workflows", []):
                wf[w.get("status", "?")] = wf.get(w.get("status", "?"), 0) + 1
            state = f"{sub_status} {json.dumps(wf, sort_keys=True)}"
            if prev.get(sid) != state:
                print(f"{label} [{sid[:8]}]: {state} (T+{(time.time() - start) / 60:.0f}m)",
                      flush=True)
                prev[sid] = state
            if sub_status not in ("Done", "Aborted"):
                all_done = False
        hours = int((time.time() - start) / 3600)
        if hours >= 3 and hours not in warned_hours:
            warned_hours.add(hours)
            print(f"WARNING: wave still running after {hours}h — "
                  f"check for preemption churn / cost", flush=True)
        if all_done:
            print("ALL SUBMISSIONS TERMINAL", flush=True)
            break
        time.sleep(90)


if __name__ == "__main__":
    main()
