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
    google-cloud-secret-manager \
    google-cloud-storage \
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

# Pre-download all moosez model weights used by the workflow so they are baked
# into the image layer and never fetched at job runtime.
# Each model is in its own RUN layer so Docker can cache partial progress —
# a network interruption only requires re-downloading the failed model onward.
# Models are stored inside the installed package at:
#   <site-packages>/moosez/models/nnunet_trained_models/<folder_name>/
# moosez.models.Model.__init__ calls __download() which checks for an existing
# local copy (by URL hash) and skips the download if already present.
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_body',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_body_composition',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_cardiac',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_digestive',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_lungs',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_muscles',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_organs',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_peripheral_bones',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_ribs',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_vertebrae',m)"

# Download and install s5cmd for interacting with cloud storage
ENV S5CMD_URL="https://github.com/peak/s5cmd/releases/download/v2.2.2/s5cmd_2.2.2_Linux-64bit.tar.gz"
ENV S5CMD_FN="s5cmd_2.2.2_Linux-64bit.tar.gz"
RUN wget -q ${S5CMD_URL} 2>&1 \
  && tar -xvzf ${S5CMD_FN} \
  && rm ${S5CMD_FN} \
  && mv s5cmd /usr/local/bin/s5cmd
