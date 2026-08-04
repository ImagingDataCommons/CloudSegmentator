# ============================================================================
# imagingdatacommons/inference_totalseg
# ----------------------------------------------------------------------------
# TotalSegmentator inference image for the harmonized Segmentator workflow.
# Derives FROM segmentator-base and adds ONLY the TotalSegmentator framework +
# baked nnU-Net weights. Conversion (nb1) / output conversion (nb3) tooling is
# inherited from base; this image runs nb2 (inference) on the GPU VM.
# ============================================================================
# Registry/tag of the base image are build-args so the whole stack can be pushed
# to a personal Docker Hub org during dev, e.g.
#   --build-arg BASE_IMAGE=sunderlandkyl/segmentator-base
ARG BASE_IMAGE=imagingdatacommons/segmentator-base
ARG BASE_TAG=main
FROM ${BASE_IMAGE}:${BASE_TAG}

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


# TotalSegmentator's console-script entry point does `from pkg_resources import
# require`. setuptools>=81 dropped pkg_resources entirely, and one of
# TotalSegmentator/nnU-Net's transitive deps upgrades past the apt-provided
# 68.1.2 (which still has it) — pin below 81 so the CLI has pkg_resources at
# runtime.
#
# torch>=2.6 flipped torch.load's default to weights_only=True, which rejects
# the numpy.core.multiarray.scalar global used by the baked nnU-Net checkpoints
# (predates safetensors-style loading) — pin below 2.6 so nnU-Net can load them.
RUN pip install --no-cache-dir \
    "setuptools<81" \
    "torch<2.6" \
    nvidia-ml-py3==7.352.0 \
    TotalSegmentator==1.5.6

# Bake TotalSegmentator v1.5.6 nnU-Net weights into the image so nothing is
# fetched at job runtime.
ENV TOTALSEG_WEIGHTS_PATH=/totalsegmentator_weights
RUN mkdir -p $TOTALSEG_WEIGHTS_PATH
COPY weights_download.sh /root/weights_download.sh
# Strip any CR (Windows CRLF checkout) so the shebang isn't `/bin/bash\r`.
RUN sed -i 's/\r$//' /root/weights_download.sh \
 && chmod +x /root/weights_download.sh \
 && /root/weights_download.sh
