FROM python@sha256:5b287042a6150052420e6a7fb7c1606b6403740880897ae9610faf434da28693

ARG GIT_HASH

LABEL PYTHON_BASE_DOCKER_IMAGE="python:3.11.2-slim-buster"\
      MAINTAINER="IDC <vthiriveedhi@mgb.org>" \
      GIT_HASH=${GIT_HASH}\
      PATH_TO_DOCKER_FILE="https://github.com/imagingdatacommons/Cloud-Resources-Workflows/blob/${GIT_HASH}/Dockerfiles/download_convert/Dockerfile"\
      IMAGE_NAME_ON_DOCKERHUB="imagingdatacommons/download_convert"
      
# Install some basic system utilities
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    dcm2niix=1.0.20181125-1\
    lz4=1.8.3-1+deb10u1\
    pigz=2.4-1\
    plastimatch=1.7.4+dfsg.1-2\
    wget=1.20.1-1.1\
    zip=3.0-11+b1\
  && rm -rf /var/lib/apt/lists/*


# Install Jupyter utilities
RUN pip3 install --no-cache-dir \
    matplotlib==3.7.1\
    ipykernel==6.22.0\
    ipython==8.11.0\
    ipywidgets==8.0.5\
    jupyter==1.0.0\
    pandas==1.5.3\
    papermill==2.4.0

# Download and install s5cmd for interacting with cloud storage
ENV S5CMD_URL="https://github.com/peak/s5cmd/releases/download/v2.0.0/s5cmd_2.0.0_Linux-64bit.tar.gz"
ENV S5CMD_FN="s5cmd_2.0.0_Linux-64bit.tar.gz"
RUN wget ${S5CMD_URL} \
  && tar -xvzf ${S5CMD_FN} \
  && rm ${S5CMD_FN} \
  && mv s5cmd /usr/local/bin/s5cmd
