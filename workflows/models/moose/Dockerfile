# ============================================================================
# imagingdatacommons/inference_moose
# ----------------------------------------------------------------------------
# MOOSE (moosez) inference image for the harmonized Segmentator workflow.
# Derives FROM segmentator-base and adds ONLY the moosez framework + baked
# model weights. Conversion (nb1) / output conversion (nb3) tooling is inherited
# from the base image; this image runs nb2 (inference) on the GPU VM.
# ============================================================================
ARG BASE_TAG=main
FROM imagingdatacommons/segmentator-base:${BASE_TAG}

ARG GIT_HASH

LABEL MAINTAINER="IDC <idc-support@cancerimagingarchive.net>" \
      GIT_HASH=${GIT_HASH} \
      PATH_TO_DOCKERFILE="https://github.com/imagingdatacommons/CloudSegmentator/blob/${GIT_HASH}/workflows/models/moose/Dockerfile" \
      IMAGE_NAME_ON_DOCKERHUB="imagingdatacommons/inference_moose"

ENV PIP_BREAK_SYSTEM_PACKAGES=1

# moosez + its core deps (nnU-Net v2). Install first so transitive pins
# (pydicom, nibabel, nnunetv2>=2.6.0) resolve before anything else.
RUN pip install --no-cache-dir "nnunetv2>=2.6.0" moosez p_tqdm nvidia-ml-py3

# Patch halo for Python 3.12+ / newer IPython compatibility:
# IPython's post_run_cell event now passes a result arg, but halo's clean_up() takes none.
RUN find /usr/local/lib -name "halo.py" -path "*/halo/halo.py" \
    -exec sed -i 's/def clean_up():/def clean_up(*_):/' {} \;

# Pre-download all moosez clinical-CT model weights so they are baked into the
# image and never fetched at job runtime. One RUN per model so Docker caches
# partial progress across a network interruption.
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_body',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_body_composition',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_cardiac',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_digestive',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_lungs',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_muscles',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_organs',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_peripheral_bones',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_ribs',m)"
RUN python3 -c "from moosez import system; from moosez.models import Model; m=system.OutputManager(verbose_console=True,verbose_log=False); Model('clin_ct_vertebrae',m)"
