FROM python@sha256:5b287042a6150052420e6a7fb7c1606b6403740880897ae9610faf434da28693

ARG GIT_HASH

LABEL BASE_DOCKER_IMAGE="python:3.11.2-slim-buster"\
      MAINTAINER="IDC <vthiriveedhi@mgb.org>" \
      GIT_HASH=${GIT_HASH}\
      PATH_TO_DOCKER_FILE="https://github.com/imagingdatacommons/Cloud-Resources-Workflows/blob/${GIT_HASH}/Dockerfiles/per_frame_functional_group_sequence/Dockerfile"\
      IMAGE_NAME_ON_DOCKERHUB="imagingdatacommons/inference_totalseg"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    lz4=1.8.3-1+deb10u1\
    curl\
    wget&&\
    rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir\   
    db-dtypes\
    ipykernel==6.22.0\    
    ipython==8.11.0\    
    ipywidgets==8.0.5\    
    jupyter==1.0.0\    
    matplotlib==3.7.1\    
    pandas==1.5.3\    
    papermill==2.4.0\    
    p_tqdm==1.4.0\    
    pydicom==2.4.1\    
    pyarrow\   
    tqdm==4.65.0 

RUN apt-get update && \
    apt-get install -y curl gnupg && \
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg  add - && \
    apt-get update -y && \
    apt-get install google-cloud-sdk -y
      

ENV PATH $PATH:/usr/local/gcloud/google-cloud-sdk/bin
