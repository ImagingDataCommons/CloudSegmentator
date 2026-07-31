# ============================================================================
# imagingdatacommons/output_conversion
# ----------------------------------------------------------------------------
# CPU-only image for the harmonized workflow's output-conversion step (nb3):
#   DICOM-SEG (dcmqi itkimage2segimage) + pyradiomics + delivery.
#
# Python 3.11 (NOT the CUDA base's 3.12) because dcmqi==0.4.1, pyradiomics==3.0.1
# and pandas==1.5.3 have no cp312 wheels — this is the same proven Python 3.11
# environment the previous MOOSE post_process / TotalSegmentator dicomseg images
# used, with pyradiomics added so radiomics is produced for every model.
#
# The WDL targets this image via `outputConversionDocker`; nb1/nb2 run on the
# CUDA segmentator-base instead.
# ============================================================================
FROM python:3.11-slim-bookworm

ARG GIT_HASH

LABEL PYTHON_BASE_DOCKER_IMAGE="python:3.11-slim-bookworm" \
      MAINTAINER="IDC <idc-support@cancerimagingarchive.net>" \
      GIT_HASH=${GIT_HASH} \
      PATH_TO_DOCKERFILE="https://github.com/imagingdatacommons/CloudSegmentator/blob/${GIT_HASH}/workflows/common/Dockerfiles/output_conversion/Dockerfile" \
      IMAGE_NAME_ON_DOCKERHUB="imagingdatacommons/output_conversion"

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    build-essential \
    lz4 \
    pigz \
    python3-dev \
    unzip \
    wget \
    zip \
  && rm -rf /var/lib/apt/lists/*

# pyradiomics 3.0.1 has no cp311 wheel, so it builds from source; its setup.py
# does `import numpy` at build time. Install numpy + cython first, then build
# pyradiomics with --no-build-isolation so it can see them (otherwise pip's
# isolated build env raises ModuleNotFoundError: No module named 'numpy').
RUN pip3 install --no-cache-dir "numpy<2" cython
RUN pip3 install --no-cache-dir --no-build-isolation pyradiomics==3.0.1

# dcmqi provides itkimage2segimage. PyPI `dcmqi` 0.4.1 ships dcmqi binaries
# v1.5.5 (first with --segmentationType labelmap). pandas==1.5.3 / numpy<2 are
# the proven Python 3.11 pins from the previous post-process images.
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
    pandas==1.5.3 \
    papermill==2.4.0 \
    pydicom==2.4.1 \
    requests==2.31.0 \
    SimpleITK==2.3.1 \
    tqdm==4.65.0

# s5cmd — private-bucket (HMAC) staging when nb3 re-downloads reference DICOM.
ENV S5CMD_URL="https://github.com/peak/s5cmd/releases/download/v2.2.2/s5cmd_2.2.2_Linux-64bit.tar.gz"
ENV S5CMD_FN="s5cmd_2.2.2_Linux-64bit.tar.gz"
RUN wget -q ${S5CMD_URL} \
  && tar -xvzf ${S5CMD_FN} \
  && rm ${S5CMD_FN} \
  && mv s5cmd /usr/local/bin/s5cmd

# dcm2niix — nb3 converts the reference DICOM series to a NIfTI intensity volume
# for pyradiomics feature extraction.
ENV DCM2NIIX_URL="https://github.com/rordenlab/dcm2niix/releases/download/v1.0.20230411/dcm2niix_lnx.zip"
ENV DCM2NIIX_FN="dcm2niix_lnx.zip"
RUN wget -q ${DCM2NIIX_URL} \
  && unzip ${DCM2NIIX_FN} \
  && rm ${DCM2NIIX_FN} \
  && mv dcm2niix /usr/local/bin/dcm2niix
