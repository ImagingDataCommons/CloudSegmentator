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
# Usage:
#   julia radiomics_jl_extract.jl <ref_nifti> <seg_nifti> <label_id[,label_id...]>
#
# Contract (consumed by nb3's _features_radiomicsjl): prints to stdout a JSON
# array of per-label feature objects, each carrying an integer "label_id":
#   [{"label_id": 1, "first_order_mean": 12.3, ...}, {"label_id": 2, ...}]
# Only numeric feature values are emitted (non-scalar/diagnostic values dropped).
# ============================================================================

using NIfTI
using JSON
using Radiomics

# Which Radiomics.jl feature classes to compute (feature scope is intentionally
# editable here — see plan "decide later"). Empty vector = all classes.
# Options (3D data): :first_order, :glcm, :shape3d, :glszm, :ngtdm, :glrlm, :gldm
const FEATURES = Symbol[:first_order, :shape3d]

# keep_largest_only=false so no mask voxels are silently dropped (closer to the
# pyradiomics behaviour, which does not prune disconnected components).
const KEEP_LARGEST_ONLY = false

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

function main()
    if length(ARGS) < 3
        println(stderr, "usage: julia radiomics_jl_extract.jl <ref_nifti> <seg_nifti> <label_id[,label_id...]>")
        exit(2)
    end
    ref_path, seg_path, label_arg = ARGS[1], ARGS[2], ARGS[3]
    labels = Int[parse(Int, strip(s)) for s in split(label_arg, ",") if !isempty(strip(s))]
    if isempty(labels)
        println("[]")
        return
    end

    ref = niread(ref_path)
    seg = niread(seg_path)
    img = ref.raw            # documented Radiomics.jl usage (raw stored intensities)
    mask = seg.raw

    if size(img) != size(mask)
        println(stderr, "ERROR: reference $(size(img)) and segmentation $(size(mask)) grids differ")
        exit(3)
    end

    # Voxel spacing (mm): NIfTI pixdim[2:4] are the x/y/z sizes (pixdim[1] is qfac).
    pd = seg.header.pixdim
    spacing = Float64[pd[2], pd[3], pd[4]]

    # One call for all labels — Radiomics.jl handles multi-label internally (and
    # in parallel when JULIA_NUM_THREADS>1), which is why nb3 batches per seg file.
    result = Radiomics.extract_radiomic_features(img, mask, spacing;
                                                 features=FEATURES,
                                                 labels=labels,
                                                 keep_largest_only=KEEP_LARGEST_ONLY)

    out = Vector{Dict{String,Any}}()
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

    println(JSON.json(out))
end

main()
