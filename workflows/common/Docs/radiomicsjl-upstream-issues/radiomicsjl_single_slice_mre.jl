# Minimal reproducible example: Radiomics.jl silently degrades single-slice ROIs
# in a 3D volume to 2D.
#
# When a label's ROI occupies exactly one z-slice (its cropped bounding box has a
# unit z dimension), extract_radiomic_features:
#   1. returns NO shape3d features for that label, and
#   2. computes firstorder_total_energy with the z spacing dropped -- the voxel
#      volume collapses to the in-plane pixel area (here 2x3=6 instead of 2x3x5=30),
# while a control ROI spanning two slices in the same volume behaves correctly.
# The trigger is the ROI-crop squeeze in src/utils/utils.jl ("Detected a unit
# dimension (size 1) along axis 3 ... Squeezing to 2D") -- but the *image* is 3D;
# only this label's bounding box is one slice thick, which is normal for small
# structures at the edge of a scan's field of view.
#
# REGRESSION: introduced in v1.3.3 by PR #26 / commit 53dfc84
# (squeeze_unit_dimension). v1.3.2 returns the exact total_energy and 14 of 15
# valid shape3d values for the same label (only shape3d_flatness is NaN, from
# the zero-extent least axis — apparently what #26 set out to fix).
#
# Tested with Radiomics.jl v1.3.3 and v2.0.0 (bug) and v1.3.2 (clean), Julia 1.10.5:
#   julia radiomicsjl_single_slice_mre.jl

using Radiomics
using Printf

# --- synthetic volume: 20 x 20 x 10, anisotropic spacing ---------------------
spacing = [2.0, 3.0, 5.0]                       # mm; voxel volume = 30 mm^3
img = zeros(Float32, 20, 20, 10)
for k in 1:10, j in 1:20, i in 1:20
    img[i, j, k] = 100 + 10i + j + 3k           # deterministic, non-constant
end

mask = zeros(UInt8, 20, 20, 10)
mask[6:10, 6:10, 5:6] .= 1                      # label 1: 50 voxels on TWO slices (control)
mask[6:10, 6:10, 8]   .= 2                      # label 2: 25 voxels on ONE slice

result = Radiomics.extract_radiomic_features(img, mask, spacing;
                                             features=[:first_order, :shape3d],
                                             labels=[1, 2],
                                             keep_largest_only=false)

# --- report ------------------------------------------------------------------
for lid in (1, 2)
    feats = result[lid]
    nslices = length(unique(getindex.(findall(==(lid), mask), 3)))
    vals = Float64.(img[mask .== lid])

    shape_keys = [k for k in keys(feats) if startswith(String(k), "shape")]
    energy = sum(vals .^ 2)                                # matches firstorder_energy
    expected_te = energy * prod(spacing)                   # energy * voxel volume
    got_te = Float64(get(feats, "firstorder_total_energy", NaN))

    println("\nlabel $lid  ($(length(vals)) voxels on $nslices slice(s))")
    println("  diagnosis_Dimensionality_of_image : ",
            get(feats, "diagnosis_Dimensionality_of_image", "?"))
    println("  shape3d features returned         : $(length(shape_keys))",
            isempty(shape_keys) ? "   <-- BUG: expected > 0" : "")
    @printf("  firstorder_energy                 : %.6g  (manual sum(v^2): %.6g)\n",
            get(feats, "firstorder_energy", NaN), energy)
    @printf("  firstorder_total_energy           : %.6g\n", got_te)
    @printf("  expected energy * voxelvol (%g)   : %.6g\n", prod(spacing), expected_te)
    if isfinite(got_te) && !isapprox(got_te, expected_te; rtol=1e-6)
        @printf("  <-- BUG: off by factor %.4f = the z spacing (%.1f); applied voxel volume was the in-plane area %.1f\n",
                expected_te / got_te, spacing[3], spacing[1] * spacing[2])
    end
end
