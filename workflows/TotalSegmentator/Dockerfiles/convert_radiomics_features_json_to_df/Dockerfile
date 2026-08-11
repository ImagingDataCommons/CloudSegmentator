FROM python:3.11-slim-bookworm@sha256:d29f48a31a8b408ed19272ca1e7b10ebae13b240a27e862d3d4217c528e2e0c3

ARG GIT_HASH

LABEL BASE_DOCKER_IMAGE="python:3.11.2-slim-buster"\
      MAINTAINER="IDC <vthiriveedhi@mgb.org>" \
      GIT_HASH=${GIT_HASH}\
      PATH_TO_DOCKER_FILE="https://github.com/imagingdatacommons/CloudSegmentator/blob/${GIT_HASH}/workflows/TotalSegmentator/Dockerfiles/convert_radiomics_features_json_to_dataframe/Dockerfile"\
      IMAGE_NAME_ON_DOCKERHUB="imagingdatacommons/convert_radiomics_features_json_to_dataframe"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    lz4\
    curl\
    wget\
    && rm -rf /var/lib/apt/lists/*
    
RUN pip3 install --no-cache-dir\   
    ipykernel==6.22.0\    
    ipython==8.11.0\    
    ipywidgets==8.0.5\    
    jupyter==1.0.0\     
    pandas==1.5.3\    
    papermill==2.4.0\
    pyarrow==16.1.0
