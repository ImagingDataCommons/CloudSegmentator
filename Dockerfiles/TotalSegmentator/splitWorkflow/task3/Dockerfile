FROM python:3.11.2-slim-buster

#ARG GIT_HASH=

# ENV TERM=xterm-256color \
#     BAMID_URL=https://github.com/Griffan/VerifyBamID/archive \
#     TINI_VERSION=v0.19.0

LABEL MAINTAINER="IDC <vthiriveedhi@mgb.org>" \
        GIT_HASH=${GIT_HASH}

# Install some basic system utilities
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    build-essential=12.6\
    #dcm2niix\
    lz4=1.8.3-1+deb10u1\
    pigz=2.4-1\
    plastimatch=1.7.4+dfsg.1-2\
    python3-dev=3.7.3-1\
    unzip=6.0-23+deb10u3\
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
    nibabel== 5.1.0\
    pandas==1.5.3\
    papermill==2.4.0\
    p_tqdm==1.4.0\
    pydicom==2.4.1\
    tqdm==4.65.0\
 && pip install --no-cache-dir \
    pyradiomics==3.0.1

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


#Install dcm2niix
ENV DCM2NIIX_URL="https://github.com/rordenlab/dcm2niix/releases/download/v1.0.20230411/dcm2niix_lnx.zip"
ENV DCM2NIIX_FN="dcm2niix_lnx.zip"
RUN wget ${DCM2NIIX_URL} \
  && unzip ${DCM2NIIX_FN} \
  && rm ${DCM2NIIX_FN} \
  && mv dcm2niix /usr/local/bin/dcm2niix
