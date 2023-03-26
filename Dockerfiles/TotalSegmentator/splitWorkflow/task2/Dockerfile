FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

# Set noninteractive mode to avoid geographic area prompt during package installation
ENV DEBIAN_FRONTEND noninteractive

# Install some basic system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.9ubuntu3\
    python3-dev=3.10.6-1~22.04\
    python3-pip=22.0.2+dfsg-1ubuntu0.2\
    xvfb=2:21.1.3-2ubuntu2.8 \
    unzip\
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    ipykernel==6.22.0\
    ipython==8.11.0\
    ipywidgets==8.0.5\
    jupyter==1.0.0\
    papermill==2.4.0\
    nvidia-ml-py3==7.352.0 \
    TotalSegmentator==1.5.3 \
 && pip install --no-cache-dir \
    pyradiomics==3.0.1

COPY weights_download.sh /root/weights_download.sh
RUN chmod +x /root/weights_download.sh
RUN /root/weights_download.sh
