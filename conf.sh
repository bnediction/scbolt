#!/usr/bin/bash

[ -d "env" ] && env_dir="./env" || env_dir="../env"
[ -d "lib" ] && lib_dir="./lib" || lib_dir="../lib"

install_env() {
    if conda env list | grep -q "^$1 ";
    then
        echo "$1 conda environment already exists"
        read -p $"Do you want to reinstall ${1} environment? ([y]/n): " choice
        if [[ "$choice" == "y" || -z "$choice" ]];
        then
            conda remove --name $1 --all --yes
            conda env create -f ${env_dir}/$1.yml --yes
            if [[ "$1" != fastq-dump ]];
            then
                conda develop --name $1 ${lib_dir};
            fi
            if [[ "$1" == bonesis ]];
            then
                conda activate $1
                pip install git+https://github.com/bnediction/bonesis.git@a40e7b49274b19aca3eeccb6e468f765153bc53f
                conda deactivate;
            fi
            if [[ "$1" == scvelo ]];
            then
                conda activate $1
                pip install git+https://github.com/theislab/scvelo.git@b2f31b345641efdccd39fbcb8c0beaa0014b4b88
                conda deactivate;
            fi

        else
            echo -e "$1 environment not reinstalled.\n"
        fi
    else
        echo "install $1 conda environment"
        conda env create -f ${env_dir}/$1.yml
        conda develop --name $1 ${lib_dir};
        if [[ "$1" == bonesis ]];
        then
            conda activate $1
            pip install git+https://github.com/bnediction/bonesistools.git@d4710d937da23b16117ce832e97a41d2a98753e2
            conda deactivate;
        fi
        if [[ "$1" == scvelo ]];
        then
            conda activate $1
            pip install git+https://github.com/theislab/scvelo.git@b2f31b345641efdccd39fbcb8c0beaa0014b4b88
            conda deactivate;
        fi
    fi
}

download_ncbi_gi() {
    if [ ! -f "$1/.mus_musculus_gene_info.tsv" ];
    then
        echo -e "download NCBI mus musculus gene info file"
        wget --quiet --show-progress --directory-prefix=$1 ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Mus_musculus.gene_info.gz
        gunzip --quiet $1/Mus_musculus.gene_info.gz
        mv $1/Mus_musculus.gene_info $1/.mus_musculus_gene_info.tsv;
    else
        echo -e "NCBI mus musculus gene info file already exists"
    fi
}

source ${HOME}/anaconda3/etc/profile.d/conda.sh

git clone https://github.com/bnediction/bonesistools.git ${lib_dir}/bonesistools

if conda env list | grep -q "^base";
then
    conda activate base
fi

for environment in fastq-dump preprocess scvelo stream scboolseq bonesis bn
do
    install_env $environment
done
