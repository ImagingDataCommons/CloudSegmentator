FROM nvidia/cuda@sha256:e1a2b842633d9b48588553c699fe5369199fba724729ea165fd0e1c7a5baf3cb

LABEL BASE_DOCKER_IMAGE="nvidia/cuda:12.1.0-base-ubuntu20.04"\
      MAINTAINER="IDC <vthiriveedhi@mgb.org>" \
      GIT_HASH=${GIT_HASH}\
      PATH_TO_DOCKER_FILE="https://github.com/vkt1414/Cloud-Resources-Workflows/blob/${GIT_HASH}/Dockerfiles/TotalSegmentator/splitWorkflow/endtoend/Dockerfile"\
      IMAGE_NAME_ON_DOCKERHUB="imagingdatacommons/download_convert_inference_totalseg_radiomics"


# Set noninteractive mode to avoid geographic area prompt during package installation
ENV DEBIAN_FRONTEND noninteractive
       
# Remove any third-party apt sources to avoid issues with expiring keys.
RUN rm -f /etc/apt/sources.list.d/*.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.8ubuntu1.1\
    dcm2niix=1.0.20181125-1build1\
    ffmpeg=7:4.2.7-0ubuntu0.1\
    lz4=1.9.2-2ubuntu0.20.04.1\
    pigz=2.4-1\
    plastimatch=1.8.0+dfsg.1-2build1\
    python3-dev=3.8.2-0ubuntu2\
    python3-pip\
    unzip=6.0-25ubuntu1.1\
    wget=1.20.3-1ubuntu2\
    xvfb=2:1.20.13-1ubuntu1~20.04.8\
    zip=3.0-11build1\
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    ipykernel==6.22.0\
    ipython==8.12.0\
    ipywidgets==8.0.6 \
    jupyter==1.0.0\
    matplotlib==3.7.1\
    nibabel==5.1.0\
    nvidia-ml-py3==7.352.0\
    papermill==2.4.0\
    p_tqdm==1.4.0\
    pydicom==2.3.1\
    "scipy>=1.8,<1.9.2; python_version <= '3.9'"\
    scikit-learn==1.2.2\
    scikit-image==0.20.0\
    TotalSegmentator==1.5.5\
    tqdm==4.65.0\
 && pip install --no-cache-dir\
    pyradiomics==3.0.1

ENV TOTALSEG_WEIGHTS_PATH /totalsegmentator_weights
RUN mkdir -p $TOTALSEG_WEIGHTS_PATH

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

# Download dcmqi for itkimage2segimage
ENV DCMQI_URL="https://github.com/QIICR/dcmqi/releases/download/v1.2.5/dcmqi-1.2.5-linux.tar.gz"
ENV DCMQI_FN="dcmqi-1.2.5-linux.tar.gz"
RUN wget ${DCMQI_URL} \
  && tar -xvzf ${DCMQI_FN} \
  && rm ${DCMQI_FN} \
  && mv dcmqi-1.2.5-linux/bin/* /bin
