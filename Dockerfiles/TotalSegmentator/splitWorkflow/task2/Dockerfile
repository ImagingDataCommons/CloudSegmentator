FROM nvidia/cuda@sha256:bed19cc4270a4624f732de7a69beb061a7dfb2ab2e05e1a58e157a483ed25185

LABEL BASE_DOCKER_IMAGE="nvidia/cuda:12.1.0-base-ubuntu22.04"\
      MAINTAINER="IDC <vthiriveedhi@mgb.org>" \
      GIT_HASH=${GIT_HASH}\
      PATH_TO_DOCKER_FILE="https://github.com/vkt1414/Cloud-Resources-Workflows/blob/${GIT_HASH}/Dockerfiles/TotalSegmentator/splitWorkflow/task2/Dockerfile"\
      IMAGE_NAME_ON_DOCKERHUB="imagingdatacommons/inference_totalseg"

# Set noninteractive mode to avoid geographic area prompt during package installation
ENV DEBIAN_FRONTEND noninteractive

# Install some basic system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.9ubuntu3\
    ffmpeg=7:4.4.2-0ubuntu0.22.04.1 \
    lz4=1.9.3-2build2\
    python3-dev=3.10.6-1~22.04\
    python3-pip=22.0.2+dfsg-1ubuntu0.2\
    wget=1.21.2-2ubuntu1\
    unzip=6.0-26ubuntu3.1\
    xvfb=2:21.1.4-2ubuntu1.7~22.04.1\
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    ipykernel==6.22.0\
    ipython==8.12.0\
    ipywidgets==8.0.6\
    jupyter==1.0.0\
    papermill==2.4.0\
    nvidia-ml-py3==7.352.0\
    TotalSegmentator==1.5.5\
 && pip install --no-cache-dir \
    pyradiomics==3.0.1

ENV TOTALSEG_WEIGHTS_PATH /totalsegmentator_weights
RUN mkdir -p $TOTALSEG_WEIGHTS_PATH

COPY weights_download.sh /root/weights_download.sh
RUN chmod +x /root/weights_download.sh
RUN /root/weights_download.sh
