#!/bin/bash

weights_urls=("https://zenodo.org/record/6802342/files/Task251_TotalSegmentator_part1_organs_1139subj.zip"
"https://zenodo.org/record/6802358/files/Task252_TotalSegmentator_part2_vertebrae_1139subj.zip"
"https://zenodo.org/record/6802360/files/Task253_TotalSegmentator_part3_cardiac_1139subj.zip"
"https://zenodo.org/record/6802366/files/Task254_TotalSegmentator_part4_muscles_1139subj.zip"
"https://zenodo.org/record/6802452/files/Task255_TotalSegmentator_part5_ribs_1139subj.zip"
#"https://zenodo.org/record/6802052/files/Task256_TotalSegmentator_3mm_1139subj.zip"
"https://zenodo.org/record/7064718/files/Task258_lung_vessels_248subj.zip"
"https://zenodo.org/record/7079161/files/Task150_icb_v0.zip"
"https://zenodo.org/record/7234263/files/Task260_hip_implant_71subj.zip"
"https://zenodo.org/record/7334272/files/Task269_Body_extrem_6mm_1200subj.zip"
"https://zenodo.org/record/7271576/files/Task503_cardiac_motion.zip"
"https://zenodo.org/record/7510286/files/Task273_Body_extrem_1259subj.zip"
"https://zenodo.org/record/7510288/files/Task315_thoraxCT.zip"
)

weights_dir="/root/.totalsegmentator/nnunet/results/nnUNet/3d_fullres/"

for url in "${weights_urls[@]}"; do
  fn=$(basename $url)
  echo "Downloading $fn from $url to $weights_dir"
  wget --directory-prefix $weights_dir $url
  unzip $weights_dir$fn -d $weights_dir
  rm $weights_dir$fn
done
