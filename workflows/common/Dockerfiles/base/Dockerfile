# syntax=docker/dockerfile:1
# ============================================================================
# imagingdatacommons/segmentator-base
# ----------------------------------------------------------------------------
# Shared CUDA base for the GPU side of the harmonized Segmentator workflow.
# Holds only the tooling needed by input conversion (nb1) and inherited by each
# model's inference image (nb2):
#   dcm2niix, s5cmd, lz4, papermill/jupyter, idc-index, pydicom, nibabel,
#   google-cloud-{storage,secret-manager}.
#
# - nb1 (convert) runs on this image (via the model inference image, which is
#   FROM segmentator-base).
# - Per-model inference images (nb2) derive `FROM segmentator-base` and add only
#   their ML framework + baked weights — see workflows/models/<model>/Dockerfile.
#
# The DICOM-SEG / pyradiomics stack (dcmqi, pyradiomics, pinned pandas) is NOT
# here: those packages have no Python 3.12 wheels, and this CUDA base is 3.12.
# Output conversion (nb3) therefore runs on a separate Python 3.11 image —
# workflows/common/Dockerfiles/output_conversion/Dockerfile — which the WDL
# targets via `outputConversionDocker`.
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
    lz4 \
    pigz \
    python3-dev \
    python3-pip \
    unzip \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Shared conversion / orchestration stack. Left unpinned so pip resolves wheels
# compatible with this base's Python 3.12 (idc-index pulls a matching pandas).
# These are all pure-Python or ship cp312 wheels — no source builds.
# Cache mount so re-pulling this layer (e.g. after editing anything below it
# in images that derive FROM this one) reuses previously downloaded wheels.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install \
    PyYAML \
    google-auth \
    google-cloud-secret-manager \
    google-cloud-storage \
    idc-index \
    ipykernel \
    jupyter \
    nibabel \
    papermill \
    pydicom \
    requests \
    tqdm

# s5cmd — private-bucket (HMAC) staging for GCS input.
ENV S5CMD_URL="https://github.com/peak/s5cmd/releases/download/v2.2.2/s5cmd_2.2.2_Linux-64bit.tar.gz"
ENV S5CMD_FN="s5cmd_2.2.2_Linux-64bit.tar.gz"
RUN wget -q ${S5CMD_URL} \
  && tar -xvzf ${S5CMD_FN} \
  && rm ${S5CMD_FN} \
  && mv s5cmd /usr/local/bin/s5cmd

# Newer dcm2niix than the apt package, matching the previous workflow images.
ENV DCM2NIIX_URL="https://github.com/rordenlab/dcm2niix/releases/download/v1.0.20230411/dcm2niix_lnx.zip"
ENV DCM2NIIX_FN="dcm2niix_lnx.zip"
RUN wget -q ${DCM2NIIX_URL} \
  && unzip ${DCM2NIIX_FN} \
  && rm ${DCM2NIIX_FN} \
  && mv dcm2niix /usr/local/bin/dcm2niix
