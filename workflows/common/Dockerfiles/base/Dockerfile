# ============================================================================
# imagingdatacommons/segmentator-base
# ----------------------------------------------------------------------------
# Shared base image for the harmonized Segmentator workflow. Holds every tool
# common to input conversion (nb1) and output conversion (nb3):
#   dcm2niix, dcmqi (itkimage2segimage), s5cmd, pyradiomics, papermill/jupyter,
#   nibabel, pydicom, pandas, idc-index, google-cloud-{storage,secret-manager}.
#
# - nb1 (convert) and nb3 (output conversion) run on THIS image directly.
# - Per-model inference images (nb2) derive `FROM segmentator-base` and add only
#   their ML framework + baked weights — see workflows/models/<model>/Dockerfile.
#
# CUDA base so the derived GPU inference images inherit drivers cleanly; the
# CPU-only output-conversion task runs this image too (it just ignores the GPU).
# ============================================================================
FROM nvidia/cuda:12.5.1-base-ubuntu24.04

ARG GIT_HASH

LABEL BASE_DOCKER_IMAGE="nvidia/cuda:12.5.1-base-ubuntu24.04" \
      MAINTAINER="IDC <idc-support@cancerimagingarchive.net>" \
      GIT_HASH=${GIT_HASH} \
      PATH_TO_DOCKERFILE="https://github.com/imagingdatacommons/CloudSegmentator/blob/${GIT_HASH}/workflows/common/Dockerfiles/base/Dockerfile" \
      IMAGE_NAME_ON_DOCKERHUB="imagingdatacommons/segmentator-base"

ENV DEBIAN_FRONTEND=noninteractive
# Ubuntu 24.04 enforces PEP 668 (externally-managed Python); allow pip in Docker.
ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    dcm2niix \
    ffmpeg \
    lz4 \
    pigz \
    python3-dev \
    python3-pip \
    unzip \
    wget \
    zip \
    && rm -rf /var/lib/apt/lists/*

# Shared Python stack for conversion + output conversion.
# dcmqi provides itkimage2segimage. The PyPI `dcmqi` package bundles the compiled
# CLI binaries; package 0.4.1 ships dcmqi binaries v1.5.5 (first with
# --segmentationType labelmap). Pin the package version, not "1.5.5".
RUN pip3 install --no-cache-dir \
    dcmqi==0.4.1 \
    google-auth==2.29.0 \
    google-cloud-secret-manager==2.20.0 \
    google-cloud-storage==2.16.0 \
    idc-index \
    ipykernel==6.22.0 \
    ipython==8.11.0 \
    ipywidgets==8.0.5 \
    jupyter==1.0.0 \
    nibabel==5.1.0 \
    "numpy<2" \
    pandas==1.5.3 \
    papermill==2.4.0 \
    pydicom==2.4.1 \
    pyradiomics==3.0.1 \
    requests==2.31.0 \
    SimpleITK==2.3.1 \
    tqdm==4.65.0

# s5cmd — private-bucket (HMAC) staging for GCS input/output.
ENV S5CMD_URL="https://github.com/peak/s5cmd/releases/download/v2.2.2/s5cmd_2.2.2_Linux-64bit.tar.gz"
ENV S5CMD_FN="s5cmd_2.2.2_Linux-64bit.tar.gz"
RUN wget -q ${S5CMD_URL} \
  && tar -xvzf ${S5CMD_FN} \
  && rm ${S5CMD_FN} \
  && mv s5cmd /usr/local/bin/s5cmd

# Newer dcm2niix than the apt package, matching the pinned CPU post-process image
# used by the previous MOOSE/TotalSegmentator workflows.
ENV DCM2NIIX_URL="https://github.com/rordenlab/dcm2niix/releases/download/v1.0.20230411/dcm2niix_lnx.zip"
ENV DCM2NIIX_FN="dcm2niix_lnx.zip"
RUN wget -q ${DCM2NIIX_URL} \
  && unzip ${DCM2NIIX_FN} \
  && rm ${DCM2NIIX_FN} \
  && mv dcm2niix /usr/local/bin/dcm2niix
