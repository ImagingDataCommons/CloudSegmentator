FROM nvidia/cuda@sha256:bed19cc4270a4624f732de7a69beb061a7dfb2ab2e05e1a58e157a483ed25185

ARG GIT_HASH

LABEL BASE_DOCKER_IMAGE="nvidia/cuda:12.1.0-base-ubuntu22.04"\
      MAINTAINER="IDC <vthiriveedhi@mgb.org>" \
      GIT_HASH=${GIT_HASH}\
      PATH_TO_DOCKER_FILE="https://github.com/imagingdatacommons/Cloud-Resources-Workflows/blob/${GIT_HASH}/Dockerfiles/inference_totalseg/Dockerfile"\
      IMAGE_NAME_ON_DOCKERHUB="imagingdatacommons/inference_totalseg"

# Set noninteractive mode to avoid geographic area prompt during package installation
ENV DEBIAN_FRONTEND noninteractive

# Install some basic system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential\
    ffmpeg \
    lz4\
    python3-dev\
    python3-pip\
    wget\
    unzip\
    xvfb\
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    ipykernel==6.22.0\
    ipython==8.12.0\
    ipywidgets==8.0.6\
    jupyter==1.0.0\
    papermill==2.4.0\
    nvidia-ml-py3==7.352.0\
    TotalSegmentator==1.5.6\
 && pip install --no-cache-dir \
    pyradiomics==3.0.1

ENV TOTALSEG_WEIGHTS_PATH /totalsegmentator_weights
RUN mkdir -p $TOTALSEG_WEIGHTS_PATH

COPY weights_download.sh /root/weights_download.sh
RUN chmod +x /root/weights_download.sh
RUN /root/weights_download.sh
