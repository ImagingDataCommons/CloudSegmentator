FROM nvidia/cuda:12.5.1-base-ubuntu24.04

ARG GIT_HASH

LABEL BASE_DOCKER_IMAGE="nvidia/cuda:12.5.1-base-ubuntu24.04"\
      MAINTAINER="IDC <idc-support@cancerimagingarchive.net>" \
      GIT_HASH=${GIT_HASH}\
      PATH_TO_DOCKERFILE="https://github.com/imagingdatacommons/CloudSegmentator/blob/${GIT_HASH}/workflows/MOOSE/Dockerfiles/inference_moose/Dockerfile"\
      IMAGE_NAME_ON_DOCKERHUB="imagingdatacommons/inference_moose"


# Set noninteractive mode to avoid geographic area prompt during package installation
ENV DEBIAN_FRONTEND=noninteractive
# Ubuntu 24.04 enforces PEP 668 (externally-managed Python); allow pip in Docker
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
    && rm -rf /var/lib/apt/lists/*

# Install moosez and its core deps first so transitive pins
# (pydicom, nibabel, nnunetv2>=2.6.0) are resolved before the second layer.
RUN pip install --no-cache-dir "nnunetv2>=2.6.0" moosez

# Install remaining packages without re-pinning what moosez already owns.
RUN pip install --no-cache-dir \
    idc-index \
    ipykernel \
    ipython \
    ipywidgets \
    jupyter \
    matplotlib \
    nvidia-ml-py3 \
    papermill \
    p_tqdm \
    requests \
    tqdm

# Patch halo for Python 3.12+ / newer IPython compatibility:
# IPython's post_run_cell event now passes a result arg, but halo's clean_up() takes none.
RUN find /usr/local/lib -name "halo.py" -path "*/halo/halo.py" \
    -exec sed -i 's/def clean_up():/def clean_up(*_):/' {} \;

# Download and install s5cmd for interacting with cloud storage
ENV S5CMD_URL="https://github.com/peak/s5cmd/releases/download/v2.2.2/s5cmd_2.2.2_Linux-64bit.tar.gz"
ENV S5CMD_FN="s5cmd_2.2.2_Linux-64bit.tar.gz"
RUN wget -q ${S5CMD_URL} 2>&1 \
  && tar -xvzf ${S5CMD_FN} \
  && rm ${S5CMD_FN} \
  && mv s5cmd /usr/local/bin/s5cmd
