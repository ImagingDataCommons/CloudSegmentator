"""Upload a make_terra_manifest data table to Terra and create its _all set.

Usage: upload_table.py <name> [manifests_dir] [--workspace ns/name]

Reads <dir>/<name>_terra_data_table.tsv (root entity type twoVM_<name>), uploads
it via flexibleImportEntities, then uploads a membership TSV creating the entity
set twoVM_<name>_set / <name>_all over every row. Submit against it with:

    submit_wave.py twoVM_<name> <name>_all twoVM_<name>_set this.twoVM_<name>s
"""
import argparse
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from terra_common import FIRECLOUD, add_workspace_arg, token, workspace


def post_tsv(tsv_text, tok, ns, name):
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="entities"; filename="upload.tsv"\r\n'
            f"Content-Type: text/tab-separated-values\r\n\r\n"
            f"{tsv_text}\r\n--{boundary}--\r\n").encode()
    req = urllib.request.Request(
        f"{FIRECLOUD}/workspaces/{ns}/{name}/flexibleImportEntities",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {tok}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.read().decode()[:200]
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()[:500]}")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="Upload a manifest data table and its _all set.")
    ap.add_argument("name", help="manifest name (reads <name>_terra_data_table.tsv)")
    ap.add_argument("manifests_dir", nargs="?", type=Path,
                    default=Path(__file__).resolve().parent.parent / "executionAnalytics" / "manifests")
    add_workspace_arg(ap)
    args = ap.parse_args()
    ns, ws_name = workspace(args)
    name = args.name
    tsv = (args.manifests_dir / f"{name}_terra_data_table.tsv").read_text(encoding="utf-8")
    tok = token()
    print("entities:", post_tsv(tsv, tok, ns, ws_name))
    ids = [row.split("\t", 1)[0] for row in tsv.splitlines()[1:] if row.strip()]
    membership = f"membership:twoVM_{name}_set_id\ttwoVM_{name}\n" + \
        "".join(f"{name}_all\t{i}\n" for i in ids)
    print("set:", post_tsv(membership, tok, ns, ws_name))
    print(f"created set {name}_all with {len(ids)} entities: {ids}")


if __name__ == "__main__":
    main()
