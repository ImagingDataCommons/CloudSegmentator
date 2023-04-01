FROM nvidia/cuda:12.1.0-runtime-ubuntu20.04

# Set noninteractive mode to avoid geographic area prompt during package installation
ENV DEBIAN_FRONTEND noninteractive

# Remove any third-party apt sources to avoid issues with expiring keys.
RUN rm -f /etc/apt/sources.list.d/*.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential\
    dcm2niix\
    ffmpeg\
    lz4\
    pigz\
    plastimatch\
    python3-dev\
    python3-pip\
    wget\
    zip\
    unzip\
    xvfb\
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    ipykernel\
    ipython\
    ipywidgets\
    jupyter\
    papermill\
    nvidia-ml-py3 \
    "scipy>=1.8,<1.9.2; python_version <= '3.9'" \
    scikit-learn\
    scikit-image\
    TotalSegmentator \
 && pip install --no-cache-dir \
    pyradiomics


COPY weights_download.sh /root/weights_download.sh
RUN chmod +x /root/weights_download.sh
RUN /root/weights_download.sh


# Download and install s5cmd for interacting with cloud storage
ENV S5CMD_URL="https://github.com/peak/s5cmd/releases/download/v2.0.0/s5cmd_2.0.0_Linux-64bit.tar.gz"
ENV S5CMD_FN="s5cmd_2.0.0_Linux-64bit.tar.gz"
RUN wget ${S5CMD_URL} \
  && tar -xvzf ${S5CMD_FN} \
  && rm ${S5CMD_FN} \
  && mv s5cmd /usr/local/bin/s5cmd
