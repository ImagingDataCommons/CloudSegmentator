#!/bin/bash

weights_urls=(
  "https://github.com/wasserth/TotalSegmentator/releases/download/v1.5.6-weights/Task251_TotalSegmentator_part1_organs_1139subj.zip"
  "https://github.com/wasserth/TotalSegmentator/releases/download/v1.5.6-weights/Task252_TotalSegmentator_part2_vertebrae_1139subj.zip"
  "https://github.com/wasserth/TotalSegmentator/releases/download/v1.5.6-weights/Task253_TotalSegmentator_part3_cardiac_1139subj.zip"
  "https://github.com/wasserth/TotalSegmentator/releases/download/v1.5.6-weights/Task254_TotalSegmentator_part4_muscles_1139subj.zip"
  "https://github.com/wasserth/TotalSegmentator/releases/download/v1.5.6-weights/Task255_TotalSegmentator_part5_ribs_1139subj.zip"
  "https://github.com/wasserth/TotalSegmentator/releases/download/v1.5.6-weights/Task256_TotalSegmentator_3mm_1139subj.zip"
)

weights_dir="${TOTALSEG_WEIGHTS_PATH}/nnUNet/3d_fullres/"

for url in "${weights_urls[@]}"; do
  fn=$(basename $url)
  echo "Downloading $fn from $url to $weights_dir"
  wget --directory-prefix $weights_dir $url
  unzip $weights_dir$fn -d $weights_dir
  rm $weights_dir$fn
done
