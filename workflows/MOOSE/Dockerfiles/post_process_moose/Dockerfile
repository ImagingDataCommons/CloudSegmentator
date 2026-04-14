FROM python:3.11-slim-bookworm

ARG GIT_HASH

LABEL PYTHON_BASE_DOCKER_IMAGE="python:3.11-slim-bookworm"\
      MAINTAINER="IDC <idc-support@cancerimagingarchive.net>" \
      GIT_HASH=${GIT_HASH}\
      PATH_TO_DOCKER_FILE="https://github.com/imagingdatacommons/CloudSegmentator/blob/${GIT_HASH}/workflows/MOOSE/Dockerfiles/post_process_moose/Dockerfile"\
      IMAGE_NAME_ON_DOCKERHUB="imagingdatacommons/post_process_moose"

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

RUN pip3 install --no-cache-dir \
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
    tqdm==4.65.0

# Download and install s5cmd for interacting with cloud storage
ENV S5CMD_URL="https://github.com/peak/s5cmd/releases/download/v2.2.2/s5cmd_2.2.2_Linux-64bit.tar.gz"
ENV S5CMD_FN="s5cmd_2.2.2_Linux-64bit.tar.gz"
RUN wget -q ${S5CMD_URL} 2>&1 \
  && tar -xvzf ${S5CMD_FN} \
  && rm ${S5CMD_FN} \
  && mv s5cmd /usr/local/bin/s5cmd

# Download dcmqi 1.5.4 — minimum version for --segmentationType labelmap support
# (added in https://github.com/QIICR/dcmqi/pull/536, released 2026-05-18)
ENV DCMQI_URL="https://github.com/QIICR/dcmqi/releases/download/v1.5.4/dcmqi-1.5.4-linux.tar.gz"
ENV DCMQI_FN="dcmqi-1.5.4-linux.tar.gz"
RUN wget -q ${DCMQI_URL} 2>&1 \
  && tar -xvzf ${DCMQI_FN} \
  && rm ${DCMQI_FN} \
  && mv dcmqi-1.5.4-linux/bin/* /bin

# Install dcm2niix
ENV DCM2NIIX_URL="https://github.com/rordenlab/dcm2niix/releases/download/v1.0.20230411/dcm2niix_lnx.zip"
ENV DCM2NIIX_FN="dcm2niix_lnx.zip"
RUN wget -q ${DCM2NIIX_URL} 2>&1 \
  && unzip ${DCM2NIIX_FN} \
  && rm ${DCM2NIIX_FN} \
  && mv dcm2niix /usr/local/bin/dcm2niix
