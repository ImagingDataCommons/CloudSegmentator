FROM python@sha256:5b287042a6150052420e6a7fb7c1606b6403740880897ae9610faf434da28693

ARG GIT_HASH

LABEL PYTHON_BASE_DOCKER_IMAGE="python:3.11.2-slim-buster"\
      MAINTAINER="IDC <vthiriveedhi@mgb.org>" \
      GIT_HASH=${GIT_HASH}\
      PATH_TO_DOCKER_FILE="https://github.com/imagingdatacommons/CloudSegmentator/blob/${GIT_HASH}/workflows/TotalSegmentator/Dockerfiles/download_convert/Dockerfile"\
      IMAGE_NAME_ON_DOCKERHUB="imagingdatacommons/download_convert"
      
# Install some basic system utilities
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    dcm2niix\
    lz4\
    pigz\
    wget\
    zip\
  && rm -rf /var/lib/apt/lists/*


# Install Jupyter utilities
RUN pip3 install --no-cache-dir \
    idc-index==0.2.8\
    matplotlib==3.7.1\
    ipykernel==6.22.0\
    ipython==8.11.0\
    ipywidgets==8.0.5\
    jupyter==1.0.0\
    pandas==1.5.3\
    papermill==2.4.0

# Download and install s5cmd for interacting with cloud storage
ENV S5CMD_URL="https://github.com/peak/s5cmd/releases/download/v2.2.2/s5cmd_2.2.2_Linux-64bit.tar.gz"
ENV S5CMD_FN="s5cmd_2.2.2_Linux-64bit.tar.gz"
RUN wget -q ${S5CMD_URL} 2>&1 \
  && tar -xvzf ${S5CMD_FN} \
  && rm ${S5CMD_FN} \
  && mv s5cmd /usr/local/bin/s5cmd
