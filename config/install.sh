#!/bin/bash

[ -d "config" ] && config_dir="config/" || config_dir=""
[ -d "anndatatools" ] && dev_dir="." || dev_dir=".."

install_env() {
    if conda env list | grep -q "^$1 ";
    then
        read -p "$1 conda environment already exists. do you want to reinstall $1 environment? ([y]/n): " choice
        if [[ "$choice" == "y" || -z "$choice" ]];
        then
            conda remove --name $1 --all --yes
            conda env create -f ${config_dir}$1.yml --force
            if [[ "$1" =~ ^(preprocess|stream|binarization)$ ]];
            then
                conda develop --name $1 $dev_dir;
            fi
        else
            echo "$1 environment not reinstalled."
        fi
    else
        conda env create -f ${config_dir}$1.yml
        if [[ "$1" =~ ^(preprocess|stream|binarization)$ ]];
        then
            conda develop --name $1 $dev_dir;
        fi
    fi
}

source ${HOME}/anaconda3/etc/profile.d/conda.sh

if conda env list | grep -q "^base";
then
    conda activate base
fi

for environment in preprocess stream binarization
do
    install_env $environment
done
