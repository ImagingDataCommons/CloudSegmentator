#!/bin/bash

weights_urls=("https://zenodo.org/record/6802342/files/Task251_TotalSegmentator_part1_organs_1139subj.zip"
"https://zenodo.org/record/6802358/files/Task252_TotalSegmentator_part2_vertebrae_1139subj.zip"
"https://zenodo.org/record/6802360/files/Task253_TotalSegmentator_part3_cardiac_1139subj.zip"
"https://zenodo.org/record/6802366/files/Task254_TotalSegmentator_part4_muscles_1139subj.zip"
"https://zenodo.org/record/6802452/files/Task255_TotalSegmentator_part5_ribs_1139subj.zip"
"https://zenodo.org/record/6802052/files/Task256_TotalSegmentator_3mm_1139subj.zip"
)

weights_dir="/root/.totalsegmentator/nnunet/results/nnUNet/3d_fullres/"

for url in "${weights_urls[@]}"; do
  fn=$(basename $url)
  echo "Downloading $fn from $url to $weights_dir"
  wget --directory-prefix $weights_dir $url
  unzip $weights_dir$fn -d $weights_dir
  rm $weights_dir$fn
done
