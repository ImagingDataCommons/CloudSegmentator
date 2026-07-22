# ============================================================================
# imagingdatacommons/inference_totalseg
# ----------------------------------------------------------------------------
# TotalSegmentator inference image for the harmonized Segmentator workflow.
# Derives FROM segmentator-base and adds ONLY the TotalSegmentator framework +
# baked nnU-Net weights. Conversion (nb1) / output conversion (nb3) tooling is
# inherited from base; this image runs nb2 (inference) on the GPU VM.
# ============================================================================
ARG BASE_TAG=main
FROM imagingdatacommons/segmentator-base:${BASE_TAG}

ARG GIT_HASH

LABEL MAINTAINER="IDC <idc-support@cancerimagingarchive.net>" \
      GIT_HASH=${GIT_HASH} \
      PATH_TO_DOCKERFILE="https://github.com/imagingdatacommons/CloudSegmentator/blob/${GIT_HASH}/workflows/models/totalseg/Dockerfile" \
      IMAGE_NAME_ON_DOCKERHUB="imagingdatacommons/inference_totalseg"

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# xvfb is required by TotalSegmentator 1.5.6's plotting/roi-subset path.
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    nvidia-ml-py3==7.352.0 \
    TotalSegmentator==1.5.6

# Bake TotalSegmentator v1.5.6 nnU-Net weights into the image so nothing is
# fetched at job runtime.
ENV TOTALSEG_WEIGHTS_PATH=/totalsegmentator_weights
RUN mkdir -p $TOTALSEG_WEIGHTS_PATH
COPY weights_download.sh /root/weights_download.sh
RUN chmod +x /root/weights_download.sh && /root/weights_download.sh
