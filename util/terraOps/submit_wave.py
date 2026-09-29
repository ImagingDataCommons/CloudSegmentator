"""Submit a MOOSE + TotalSegmentator pair of harmonized-workflow runs on Terra.

For each engine: PUT the shared method config with that engine's inputs (docker,
nb2 path, SNOMED mapping, model list), point it at the requested root entity
type, then POST a submission. The config is a shared mutable slot -- Terra
snapshots it per submission, so reconfigure-then-submit per engine is safe.

Usage:
    python submit_wave.py <rootEntityType> <entityName> [entityType] [expression]
                          [--workspace ns/name] [--config ns/name]
                          [--registry R] [--bucket gs://...] [--models moose,totalseg]

    # one entity:            submit_wave.py twoVM_pilot 4
    # an entity set:         submit_wave.py twoVM_batch23 batch23_all \\
    #                                       twoVM_batch23_set this.twoVM_batch23s

Configuration (flag, else environment variable):
    --workspace  TERRA_WORKSPACE              <namespace>/<name> of the workspace
    --config     TERRA_METHOD_CONFIG          <namespace>/<name> of the method config
                                              (default: <workspace namespace>/SegmentatorTwoVmWorkflowOnTerra)
    --registry   SEGMENTATOR_REGISTRY         Docker Hub namespace of the inference images
                                              (<registry>/cloudsegmentator-inference-<engine>:main;
                                              default: imagingdatacommons)
    --bucket     SEGMENTATOR_DELIVERY_BUCKET  dicomSegBucketUri; unset = leave the config's value

dicomSegBucketUri deliveries overwrite per-file (same <uid>/<model>_<idx>[_sr].dcm
names -> latest run wins).
"""
import argparse
import os

from terra_common import add_workspace_arg, api, split_ref, token, workspace

DEFAULT_CONFIG_NAME = "SegmentatorTwoVmWorkflowOnTerra"

# inferenceRAM per engine (GB). TotalSegmentator lung_vessels peaks ~14 GiB on a
# 320-Mvox series and LIVELOCKS a swapless 16 GB VM, so TotalSeg gets 26. Asking
# for 32 silently buys a 6-vCPU shape (+~14 % $/series) for no speed-up.
MODELS = {
    "moose": {
        "ram": "16",
        "inputs": {
            "Segmentator.inferenceNotebookPath": '"workflows/models/moose/Notebooks/inference.ipynb"',
            "Segmentator.snomedMappingPath": '""',   # moosez bundles its own mapping
            "Segmentator.inferenceParamsYaml": '"moose_models: clin_ct_body,clin_ct_body_composition,clin_ct_cardiac,clin_ct_digestive,clin_ct_lungs,clin_ct_muscles,clin_ct_organs,clin_ct_peripheral_bones,clin_ct_ribs,clin_ct_vertebrae"',
            "Segmentator.modelName": '"moose"',
        },
    },
    "totalseg": {
        "ram": "26",
        "inputs": {
            "Segmentator.inferenceNotebookPath": '"workflows/models/totalseg/Notebooks/inference.ipynb"',
            "Segmentator.snomedMappingPath": '"workflows/models/totalseg/resources/snomed_mapping.csv"',
            "Segmentator.inferenceParamsYaml": '"task: total,lung_vessels"',
            "Segmentator.modelName": '"totalseg"',
        },
    },
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("root_type", help="root entity type of the data table")
    ap.add_argument("entity_name", help="entity (or entity set) to run on")
    ap.add_argument("entity_type", nargs="?", help="entity type if not root_type (e.g. a set)")
    ap.add_argument("expression", nargs="?", help="expression expanding a set, e.g. this.twoVM_xs")
    add_workspace_arg(ap)
    ap.add_argument("--config", default=os.environ.get("TERRA_METHOD_CONFIG"),
                    help="method config <namespace>/<name> (default: $TERRA_METHOD_CONFIG)")
    ap.add_argument("--registry", default=os.environ.get("SEGMENTATOR_REGISTRY", "imagingdatacommons"),
                    help="Docker Hub namespace of the inference images "
                         "(default: $SEGMENTATOR_REGISTRY, else imagingdatacommons)")
    ap.add_argument("--bucket", default=os.environ.get("SEGMENTATOR_DELIVERY_BUCKET"),
                    help="dicomSegBucketUri for SEG/SR delivery (default: leave config value)")
    ap.add_argument("--models", default=",".join(MODELS),
                    help="comma-separated engines to submit (default: all)")
    ap.add_argument("--inference-ram", help="override inferenceRAM (GB) for every engine")
    args = ap.parse_args()

    ns, name = workspace(args)
    cns, cname = split_ref(args.config or f"{ns}/{DEFAULT_CONFIG_NAME}",
                           "Method config", "--config", "TERRA_METHOD_CONFIG")
    cfg_path = f"/workspaces/{ns}/{name}/method_configs/{cns}/{cname}"
    tok = token()

    for model in args.models.split(","):
        spec = MODELS[model]
        cfg = api(cfg_path, tok)
        cfg["inputs"].update(spec["inputs"])
        cfg["inputs"]["Segmentator.inferenceDocker"] = f'"{args.registry}/cloudsegmentator-inference-{model}:main"'
        cfg["inputs"]["Segmentator.inferenceRAM"] = args.inference_ram or spec["ram"]
        if args.bucket:
            cfg["inputs"]["Segmentator.dicomSegBucketUri"] = f'"{args.bucket}"'
        cfg["inputs"]["Segmentator.dicomStoreImportUri"] = '""'
        cfg["rootEntityType"] = args.root_type
        api(cfg_path, tok, "PUT", cfg)
        body = {
            "methodConfigurationNamespace": cns,
            "methodConfigurationName": cname,
            "entityType": args.entity_type or args.root_type,
            "entityName": args.entity_name,
            "useCallCache": False,
            "deleteIntermediateOutputFiles": False,
        }
        if args.expression:
            body["expression"] = args.expression
        sub = api(f"/workspaces/{ns}/{name}/submissions", tok, "POST", body)
        print(f"{model}: submissionId={sub['submissionId']}")


if __name__ == "__main__":
    main()
