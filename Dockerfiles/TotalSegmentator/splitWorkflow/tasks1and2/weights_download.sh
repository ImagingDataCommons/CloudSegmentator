#!/bin/bash

weights_urls=(
    "http://94.16.105.223/static/Task251_TotalSegmentator_part1_organs_1139subj.zip"
    "http://94.16.105.223/static/Task252_TotalSegmentator_part2_vertebrae_1139subj.zip"
    "http://94.16.105.223/static/Task253_TotalSegmentator_part3_cardiac_1139subj.zip"
    "http://94.16.105.223/static/Task254_TotalSegmentator_part4_muscles_1139subj.zip"
    "http://94.16.105.223/static/Task255_TotalSegmentator_part5_ribs_1139subj.zip"
    "http://94.16.105.223/static/Task256_TotalSegmentator_3mm_1139subj.zip"
)

weights_dir="${TOTALSEG_WEIGHTS_PATH}/nnUNet/3d_fullres/"

for url in "${weights_urls[@]}"; do
  fn=$(basename $url)
  echo "Downloading $fn from $url to $weights_dir"
  wget --directory-prefix $weights_dir $url
  unzip $weights_dir$fn -d $weights_dir
  rm $weights_dir$fn
done
