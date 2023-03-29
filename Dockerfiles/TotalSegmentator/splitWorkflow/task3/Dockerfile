FROM python:3.11.2-slim-buster

# Install some basic system utilities
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    lz4=1.8.3-1+deb10u1\
    wget=1.20.1-1.1\
  && rm -rf /var/lib/apt/lists/*

# Install Jupyter utilities
RUN pip3 install --no-cache-dir \
    matplotlib==3.7.1\
    ipykernel==6.22.0\
    ipython==8.11.0\
    ipywidgets==8.0.5\
    jupyter==1.0.0\
    pandas==1.5.3\
    papermill==2.4.0

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
