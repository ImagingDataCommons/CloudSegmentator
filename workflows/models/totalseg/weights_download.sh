#!/bin/bash
# Downloads TotalSegmentator v1.5.6 nnU-Net weights and bakes them into the
# image so nothing is fetched at job runtime.
set -e

weights_urls=(
  "https://github.com/wasserth/TotalSegmentator/releases/download/v1.5.6-weights/Task251_TotalSegmentator_part1_organs_1139subj.zip"
  "https://github.com/wasserth/TotalSegmentator/releases/download/v1.5.6-weights/Task252_TotalSegmentator_part2_vertebrae_1139subj.zip"
  "https://github.com/wasserth/TotalSegmentator/releases/download/v1.5.6-weights/Task253_TotalSegmentator_part3_cardiac_1139subj.zip"
  "https://github.com/wasserth/TotalSegmentator/releases/download/v1.5.6-weights/Task254_TotalSegmentator_part4_muscles_1139subj.zip"
  "https://github.com/wasserth/TotalSegmentator/releases/download/v1.5.6-weights/Task255_TotalSegmentator_part5_ribs_1139subj.zip"
  "https://github.com/wasserth/TotalSegmentator/releases/download/v1.5.6-weights/Task256_TotalSegmentator_3mm_1139subj.zip"
  "https://zenodo.org/record/7064718/files/Task258_lung_vessels_248subj.zip?download=1"
)

weights_dir="${TOTALSEG_WEIGHTS_PATH}/nnUNet/3d_fullres/"
# Set by the Dockerfile to a BuildKit cache mount so re-downloads are skipped
# across builds even when this layer's own cache is invalidated upstream.
cache_dir="${WEIGHTS_CACHE_DIR:-${weights_dir}.cache}"
mkdir -p "$weights_dir" "$cache_dir"

# Download all six archives concurrently (they're independent GitHub release
# assets), skipping any already present in the cache dir.
pids=()
for url in "${weights_urls[@]}"; do
  fn=$(basename "${url%%\?*}")
  if [ -f "$cache_dir/$fn" ]; then
    echo "$fn already cached, skipping download"
    continue
  fi
  echo "Downloading $fn from $url"
  ( wget -q -O "$cache_dir/$fn.part" "$url" && mv "$cache_dir/$fn.part" "$cache_dir/$fn" ) &
  pids+=($!)
done
for pid in "${pids[@]}"; do wait "$pid"; done

for url in "${weights_urls[@]}"; do
  fn=$(basename "${url%%\?*}")
  echo "Unzipping $fn to $weights_dir"
  unzip -q "$cache_dir/$fn" -d "$weights_dir"
done

# If WEIGHTS_CACHE_DIR wasn't supplied (no BuildKit cache mount wired up),
# cache_dir lives inside the image layer, so clean it up to avoid baking the
# zips in twice. When it *is* a cache mount, BuildKit excludes it from the
# image automatically and leaving it populated is what makes the next build's
# downloads a no-op.
if [ -z "$WEIGHTS_CACHE_DIR" ]; then
  rm -rf "$cache_dir"
fi
