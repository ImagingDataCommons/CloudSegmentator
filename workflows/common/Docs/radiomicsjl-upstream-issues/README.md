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

Until it is fixed upstream, interpret or guard single-slice labels with care under
`radiomicsMethod=radiomicsjl`.
