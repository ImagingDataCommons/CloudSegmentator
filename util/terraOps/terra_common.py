"""Shared helpers for the Terra ops scripts: workspace resolution, auth, REST calls.

The workspace is taken from --workspace <namespace>/<name> or, failing that, the
TERRA_WORKSPACE environment variable. Auth is `gcloud auth print-access-token`
(run `gcloud auth login` once).
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

FIRECLOUD = "https://api.firecloud.org/api"


def add_workspace_arg(parser):
    parser.add_argument(
        "--workspace", default=os.environ.get("TERRA_WORKSPACE"),
        help="Terra workspace as <namespace>/<name> (default: $TERRA_WORKSPACE)")


def split_ref(ref, what, flag, env):
    """Split '<namespace>/<name>' or exit with a hint about where to set it."""
    if not ref or "/" not in ref:
        sys.exit(f"{what} not set: pass {flag} <namespace>/<name> or set ${env}")
    return tuple(ref.split("/", 1))


def workspace(args):
    return split_ref(args.workspace, "Terra workspace", "--workspace", "TERRA_WORKSPACE")


def token():
    return subprocess.run("gcloud auth print-access-token", shell=True,
                          capture_output=True, text=True).stdout.strip()


def api(path, tok, method="GET", body=None, timeout=120, exit_on_http_error=True):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(FIRECLOUD + path, data=data, method=method,
                                 headers={"Authorization": f"Bearer {tok}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if not exit_on_http_error:
            raise
        print(f"{method} {path} -> HTTP {e.code}: {e.read().decode()[:800]}")
        sys.exit(1)
