# An example docker command to run an image:

##### `docker run --entrypoint="/bin/bash" -d --rm -it --name=get_idc_data imagingdatacommons/download_convert`

What's happening with the arguments chosen?
- `entry-point`: will switch from the default entry point to bash 
- `-d`: will keep docker running in detached mode, i.e docker will continue to run even we get out of the terminal
- `--rm`: will remove the container when it is stopped
- `--name`: sets the name of the container
