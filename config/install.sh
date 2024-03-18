#!/usr/bin/bash

[ -d "config" ] && config_dir="config/" || config_dir=""
[ -d "anndatatools" ] && develop_dir="." || develop_dir=".."

install_env() {
    if conda env list | grep -q "^$1 ";
    then
        echo "${1} conda environment already exists."
        read -p $"Do you want to reinstall ${1} environment? ([y]/n): " choice
        if [[ "$choice" == "y" || -z "$choice" ]];
        then
            conda remove --name $1 --all --yes
            conda env create -f ${config_dir}$1.yml --force
            conda develop --name $1 $develop_dir;
            if [[ "$1" == bonesis ]];
            then
                conda activate $1
                pip install git+https://github.com/bnediction/bonesis.git@6fb47aad96bd2d07ba3c137842d632bc2c783712
                conda deactivate;
            fi
        else
            echo -e "$1 environment not reinstalled.\n"
        fi
    else
        echo "Install ${1} conda environment."
        conda env create -f ${config_dir}$1.yml
        conda develop --name $1 $develop_dir;
        if [[ "$1" == bonesis ]];
        then
            conda activate $1
            pip install git+https://github.com/bnediction/bonesis.git@6fb47aad96bd2d07ba3c137842d632bc2c783712
            conda deactivate;
        fi
    fi
}

download_ncbi_gi() {
    if [ ! -f "$1/.mus_musculus_gene_info.tsv" ];
    then
        echo -e "Download NCBI mus musculus gene info file."
        wget --quiet --directory-prefix=$1 ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Mus_musculus.gene_info.gz
        gunzip --quiet $1/Mus_musculus.gene_info.gz
        mv $1/Mus_musculus.gene_info $1/.mus_musculus_gene_info.tsv;
    else
        echo -e "NCBI mus musculus gene info file already exists."
    fi
}

source ${HOME}/anaconda3/etc/profile.d/conda.sh

if conda env list | grep -q "^base";
then
    conda activate base
fi

for environment in preprocess stream binarization bonesis
do
    install_env $environment
done

download_ncbi_gi ${develop_dir}/utils
