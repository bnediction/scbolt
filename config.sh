#!/usr/bin/bash

[ -d "envs" ] && env_dir="./envs" || env_dir="../envs"
[ -d "lib" ] && lib_dir="./lib" || lib_dir="../lib"

bonesis_hash="${BONESIS_HASH:-24c4f9c91a4496b9777043e17e504ecc31312d87}"
scvelo_hash="${SCVELO_HASH:-b2f31b345641efdccd39fbcb8c0beaa0014b4b88}"

install_bonesis_git() {
    conda activate "$1"
    pip install --force-reinstall --no-deps "git+https://github.com/bnediction/bonesis.git@${bonesis_hash}"
    conda deactivate
}

install_scvelo_git() {
    conda activate "$1"
    pip install "git+https://github.com/theislab/scvelo.git@${scvelo_hash}"
    conda deactivate
}

install_env() {
    if conda env list | grep -q "^$1 ";
    then
        echo "conda environment '$1' already exists"
        read -p $"Do you want to reinstall conda environment '${1}'? ([y]/n): " choice
        if [[ $choice == "y" || -z $choice ]];
        then
            conda remove --name $1 --all --yes
            conda env create -f $2 --yes
            if [ $1 != "scbolt-fastq" ] && [ $1 != "scbolt-velocyto" ];
            then
                conda develop --name $1 ${lib_dir};
            fi
            if [ $1 == "scbolt-velocity" ];
            then
                install_scvelo_git "$1"
            fi
            if [ $1 == "scbolt-bonesis" ];
            then
                install_bonesis_git "$1"
            fi

        else
            echo -e "conda environment '$1' not reinstalled.\n"
        fi
    else
        echo "installing conda environment '$1'"
        conda env create -f $2
        conda develop --name $1 ${lib_dir};
        if [ $1 == "scbolt-bonesis" ];
        then
            install_bonesis_git "$1"
        fi
        if [ $1 == "scbolt-velocity" ];
        then
            install_scvelo_git "$1"
        fi
    fi
}

source ${HOME}/anaconda3/etc/profile.d/conda.sh

if conda env list | grep -q "^base";
then
    conda activate base
fi

for file in ${env_dir}/*.yml
do
    env=scbolt-`basename ${file%.yml}`
    install_env $env $file
done
