#!/usr/bin/bash

[ -d "env" ] && env_dir="./env" || env_dir="../env"
[ -d "lib" ] && lib_dir="./lib" || lib_dir="../lib"

install_env() {
    if conda env list | grep -q "^$1 ";
    then
        echo "conda environment '$1' already exists"
        read -p $"Do you want to reinstall conda environment '${1}'? ([y]/n): " choice
        if [[ $choice == "y" || -z $choice ]];
        then
            conda remove --name $1 --all --yes
            conda env create -f $2 --yes
            if [ $1 != "scbridge-fastq" ] && [ $1 != "scbridge-velocyto" ];
            then
                conda develop --name $1 ${lib_dir};
            fi
            if [ $1 == "scbridge-bonesis" ];
            then
                conda activate $1
                pip install git+https://github.com/bnediction/bonesis.git@a40e7b49274b19aca3eeccb6e468f765153bc53f
                conda deactivate;
            fi
            if [ $1 == "scbridge-scvelo" ];
            then
                conda activate $1
                pip install git+https://github.com/theislab/scvelo.git@b2f31b345641efdccd39fbcb8c0beaa0014b4b88
                conda deactivate;
            fi

        else
            echo -e "conda environment '$1' not reinstalled.\n"
        fi
    else
        echo "installing conda environment '$1'"
        conda env create -f $2
        conda develop --name $1 ${lib_dir};
        if [ $1 == "scbridge-bonesis" ];
        then
            conda activate $1
            pip install git+https://github.com/bnediction/bonesistools.git@d4710d937da23b16117ce832e97a41d2a98753e2
            conda deactivate;
        fi
        if [ $1 == "scbridge-scvelo" ];
        then
            conda activate $1
            pip install git+https://github.com/theislab/scvelo.git@b2f31b345641efdccd39fbcb8c0beaa0014b4b88
            conda deactivate;
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
    env=scbridge-`basename ${file%.yml}`
    install_env $env $file
done
