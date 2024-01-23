#!/bin/bash

[ -d "config" ] && config_dir="config/" || config_dir=""

install_env() {
    if conda env list | grep -q "^$1 ";
    then
        read -p "$1 conda environment already exists. do you want to reinstall $1 environment? ([y]/n): " choice
        if [[ "$choice" == "y" || -z "$choice" ]];
        then
            conda remove --name $1
            conda env create -f ${config_dir}$1.yml
        else
            echo "$1 environment not reinstalled."
        fi
    else
        conda env create -f ${config_dir}$1.yml
    fi
}

for environment in preprocess stream
do
    install_env $environment
done
