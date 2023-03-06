# Specify the base image for the environment
FROM mhubai/totalsegmentator:nocuda

# Install some basic system utilities
RUN apt update \
  && apt install -y --no-install-recommends \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    subversion \
    zip \
  && rm -rf /var/lib/apt/lists/*

# Install the Google Cloud SDK (gcloud) to enable gsutil
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
  && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - \
  && apt-get update -y \
  && apt-get install google-cloud-cli -y

# Install Jupyter utilities
RUN pip3 install --no-cache-dir \
    dask\
    db_dtypes \
    google-cloud-bigquery \
    google-cloud-storage \
    ipykernel \
    ipython \
    ipywidgets \
    jupyter \
    papermill \
    thedicomsort \
    yamlmagic

# Copy a script for downloading pre-trained model weights and make it executable
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
