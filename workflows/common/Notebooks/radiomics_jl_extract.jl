#!/usr/bin/env julia
# ============================================================================
# radiomics_jl_extract.jl — Radiomics.jl driver for the harmonized workflow's
# output-conversion step (nb3, outputConversionNotebook.ipynb).
#
# This is the SINGLE place that owns the Radiomics.jl-specific API, so the Julia
# engine can be updated/retuned without touching the notebook. Selected at
# runtime via the WDL `radiomicsMethod = "radiomicsjl"` input; the Julia runtime
# and the Radiomics.jl package live in the output_conversion Docker image.
#
# Engine: pzaffino/Radiomics.jl (registered package name `Radiomics`, IBSI-1
# compliant). API: Radiomics.extract_radiomic_features(img, mask, spacing; ...).
#
# Two modes:
#
#   1) one-shot (original CLI):
#        julia radiomics_jl_extract.jl <ref_nifti> <seg_nifti> <label_id[,label_id...]> [features]
#      prints a JSON array of per-label feature objects to stdout. `features` is an
#      optional comma-separated list of feature classes (default first_order,shape3d).
#
#   2) worker (what nb3 uses): ONE Julia process per output-conversion run, so the
#      ~8-10 s of Julia startup + package load + JIT is paid once per workflow
#      instead of once per (series x sub-model) -- MOOSE has 10 seg files per series.
#        julia -t auto radiomics_jl_extract.jl --worker
#      Reads one JSON request per line on stdin:
#        {"id": 7, "ref": "<ref_nifti>", "seg": "<seg_nifti>", "labels": [1,2,3],
#         "features": ["first_order", "shape3d"]}          # optional; see DEFAULT_FEATURES
#      and answers with exactly one line on stdout, prefixed by a sentinel so any
#      chatter the library prints to stdout cannot corrupt the protocol:
#        @@RESULT {"id": 7, "result": [ {"label_id": 1, ...}, ... ]}
#        @@RESULT {"id": 7, "error": "<message>"}
#      Errors are per request; the worker keeps serving. EOF on stdin exits 0.
#
# Contract of a result (consumed by nb3's _features_radiomicsjl): a JSON array of
# per-label feature objects, each carrying an integer "label_id":
#   [{"label_id": 1, "first_order_mean": 12.3, ...}, {"label_id": 2, ...}]
# Only numeric feature values are emitted (non-scalar/diagnostic values dropped).
# ============================================================================

using NIfTI
using JSON
using Radiomics

# Radiomics.jl feature classes. The caller (nb3, via the WDL `radiomicsFeatureClasses`
# input) selects the scope per request with "features": [...]; DEFAULT_FEATURES is
# used when a request / the CLI does not specify one. Empty list = all classes.
# Options (3D data): first_order, shape3d, glcm, glrlm, glszm, ngtdm, gldm
const KNOWN_FEATURES = Symbol[:first_order, :shape3d, :glcm, :glrlm, :glszm, :ngtdm, :gldm]
const DEFAULT_FEATURES = Symbol[:first_order, :shape3d]

"""Normalize a feature-class spec (JSON array of strings, comma-separated string,
or `nothing`) to a Vector{Symbol}. Unknown names raise so the request errors
visibly instead of silently computing a different scope."""
function _parse_features(x)
    x === nothing && return DEFAULT_FEATURES
    names = x isa AbstractString ? split(x, ",") : x
    out = Symbol[]
    for n in names
        s = lowercase(strip(String(n)))
        isempty(s) && continue
        s == "all" && return Symbol[]          # empty vector = all classes
        s == "firstorder" && (s = "first_order")
        s == "shape" && (s = "shape3d")
        sym = Symbol(s)
        sym in KNOWN_FEATURES || error("unknown Radiomics.jl feature class '$s' (valid: $(KNOWN_FEATURES))")
        sym in out || push!(out, sym)
    end
    return isempty(out) ? DEFAULT_FEATURES : out
end

# keep_largest_only=false so no mask voxels are silently dropped (closer to the
# pyradiomics behaviour, which does not prune disconnected components).
const KEEP_LARGEST_ONLY = false

const SENTINEL = "@@RESULT "

function _emit(out, lid, feats)
    d = Dict{String,Any}()
    for (k, v) in feats
        if v isa Real          # keep numeric scalars only; JSON-clean + matches nb3 filter
            d[String(k)] = v
        end
    end
    d["label_id"] = Int(lid)
    push!(out, d)
end

"""Extract features for `labels` of `seg_path` against `ref_path`.
Returns a Vector of per-label Dicts (see contract above). Throws on error."""
function extract(ref_path::AbstractString, seg_path::AbstractString, labels::Vector{Int},
                 features::Vector{Symbol}=DEFAULT_FEATURES)
    out = Vector{Dict{String,Any}}()
    isempty(labels) && return out

    ref = niread(ref_path)
    seg = niread(seg_path)
    img = ref.raw            # documented Radiomics.jl usage (raw stored intensities)
    mask = seg.raw

    if size(img) != size(mask)
        error("reference $(size(img)) and segmentation $(size(mask)) grids differ")
    end

    # Voxel spacing (mm): NIfTI pixdim[2:4] are the x/y/z sizes (pixdim[1] is qfac).
    pd = seg.header.pixdim
    spacing = Float64[pd[2], pd[3], pd[4]]

    # One call for all labels — Radiomics.jl handles multi-label internally (and
    # in parallel when JULIA_NUM_THREADS>1; nb3 starts the worker with -t auto).
    result = Radiomics.extract_radiomic_features(img, mask, spacing;
                                                 features=features,
                                                 labels=labels,
                                                 keep_largest_only=KEEP_LARGEST_ONLY)

    if keytype(result) <: Integer
        # Multiple labels: Dict{Int, Dict{String,Any}} keyed by label value.
        for (lid, feats) in result
            _emit(out, lid, feats)
        end
    else
        # Single-label fallback: Dict{String,Any} (library stamps "label_id").
        lid = haskey(result, "label_id") ? result["label_id"] : labels[1]
        _emit(out, lid, result)
    end
    return out
end

function _parse_labels(x)
    if x isa AbstractString
        return Int[parse(Int, strip(s)) for s in split(x, ",") if !isempty(strip(s))]
    end
    return Int[Int(v) for v in x]
end

function worker()
    println(stderr, "radiomics_jl_extract.jl worker ready (threads=$(Threads.nthreads()), default features=$(DEFAULT_FEATURES))")
    for line in eachline(stdin)
        line = strip(line)
        isempty(line) && continue
        id = nothing
        try
            req = JSON.parse(line)
            id = get(req, "id", nothing)
            labels = _parse_labels(get(req, "labels", Int[]))
            features = _parse_features(get(req, "features", nothing))
            res = extract(String(req["ref"]), String(req["seg"]), labels, features)
            println(stdout, SENTINEL, JSON.json(Dict("id" => id, "result" => res)))
        catch err
            msg = sprint(showerror, err)
            println(stdout, SENTINEL, JSON.json(Dict("id" => id, "error" => msg)))
        end
        flush(stdout)
    end
end

function main()
    if length(ARGS) >= 1 && ARGS[1] == "--worker"
        worker()
        return
    end
    if length(ARGS) < 3
        println(stderr, "usage: julia radiomics_jl_extract.jl <ref_nifti> <seg_nifti> <label_id[,label_id...]> [feature[,feature...]]")
        println(stderr, "       julia -t auto radiomics_jl_extract.jl --worker")
        exit(2)
    end
    ref_path, seg_path, label_arg = ARGS[1], ARGS[2], ARGS[3]
    labels = _parse_labels(label_arg)
    try
        features = _parse_features(length(ARGS) >= 4 ? ARGS[4] : nothing)
        println(JSON.json(extract(ref_path, seg_path, labels, features)))
    catch err
        println(stderr, "ERROR: ", sprint(showerror, err))
        exit(3)
    end
end

main()
