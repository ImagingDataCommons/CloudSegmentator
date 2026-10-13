# Radiomics.jl single-slice ROI bug

[pzaffino/Radiomics.jl](https://github.com/pzaffino/Radiomics.jl) computes labels
confined to a single slice as 2D: no `shape3d` features, and `total_energy` loses the
z spacing. It is a regression in v1.3.3 (commit 53dfc84 / PR #26) that is still present
in 2.0.0; v1.3.2 gives correct values except `flatness=NaN`. It was found while
cross-validating the harmonized workflow's radiomics engines (see
`util/executionAnalytics/radiomics_compare.py`).

`radiomicsjl_single_slice_mre.jl` is a minimal reproducible example. Run it in the
`output_conversion` image (Julia 1.10 + Radiomics.jl 2.0.0):

```bash
docker run --rm -v "$PWD:/work" <registry>/cloudsegmentator-output-conversion \
  julia /work/radiomicsjl_single_slice_mre.jl
```

Until it is fixed upstream, the `output_conversion` image applies
[`radiomicsjl-single-slice.patch`](../../Dockerfiles/output_conversion/radiomicsjl-single-slice.patch)
to its Radiomics.jl 2.0.0: the unit-dimension squeeze runs only when the full image has
a unit dimension (genuinely 2D input), and elongation/flatness are 0 rather than NaN for
a zero minor/least axis. With it, the MRE's single-slice label (and a one-voxel-thick
sagittal sheet) get all 15 shape3d features and the exact total_energy, matching
pyradiomics; labels spanning more than one slice are bit-identical to unpatched 2.0.0.
The fix is the natural upstream PR.
