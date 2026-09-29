# syntax=docker/dockerfile:1
# ============================================================================
# imagingdatacommons/cloudsegmentator-inference-totalseg
# ----------------------------------------------------------------------------
# TotalSegmentator inference image for the harmonized Segmentator workflow.
# Derives FROM cloudsegmentator-base and adds ONLY the TotalSegmentator framework +
# baked nnU-Net weights. Conversion (nb1) / output conversion (nb3) tooling is
# inherited from base; this image runs nb2 (inference) on the GPU VM.
# ============================================================================
# Registry/tag of the base image are build-args so the whole stack can be pushed
# to a personal Docker Hub org during dev, e.g.
#   --build-arg BASE_IMAGE=imagingdatacommons/cloudsegmentator-base
ARG BASE_IMAGE=imagingdatacommons/cloudsegmentator-base
ARG BASE_TAG=main
FROM ${BASE_IMAGE}:${BASE_TAG}

ARG GIT_HASH

LABEL MAINTAINER="IDC <idc-support@cancerimagingarchive.net>" \
      GIT_HASH=${GIT_HASH} \
      PATH_TO_DOCKERFILE="https://github.com/imagingdatacommons/CloudSegmentator/blob/${GIT_HASH}/workflows/models/totalseg/Dockerfile" \
      IMAGE_NAME_ON_DOCKERHUB="imagingdatacommons/cloudsegmentator-inference-totalseg"

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# TotalSegmentator v2 (v2.17+ dropped the pkg_resources dependency and the
# torch<2.6 requirement that forced pins on the v1.5.6 image; nnunetv2 and a
# current torch resolve as normal dependencies).
# Cache mount keyed on /root/.cache/pip: wheels already downloaded in a prior
# build are reused even when this layer's own cache is invalidated (e.g. by a
# BASE_IMAGE/BASE_TAG bump during dev iteration).
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install TotalSegmentator==2.18.0

# Bake the nnU-Net weights for the tasks the harmonized workflow exposes so
# nothing is fetched at job runtime (v2 auto-downloads missing tasks, which we
# do not want on a per-VM basis). TOTALSEG_HOME_DIR is v2's weights/config
# root (replaces v1's TOTALSEG_WEIGHTS_PATH).
#   total      - 117-class full-body model (tasks 291-295, 1.5 mm)
#   total_fast - 3 mm model used by --fast and by v2's internal FOV cropping
#                for subtasks (lung_vessels crops to the lung lobes with it)
#   lung_vessels - task 117; v2 retrained this as 4 classes (lung_airways,
#                lung_airways_wall, lung_arteries, lung_veins), no license
# One RUN per task so Docker caches partial progress across network hiccups.
ENV TOTALSEG_HOME_DIR=/totalsegmentator_weights
RUN mkdir -p $TOTALSEG_HOME_DIR && totalseg_download_weights -t total
RUN totalseg_download_weights -t total_fast
RUN totalseg_download_weights -t lung_vessels
