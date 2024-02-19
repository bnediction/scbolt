# Boolean Networks Inference for Explaining Treatment-Resistant Leukemia

# Description

This project proposes a general methodology for inferring executable models reproducing *in silico*
the observed cellular dynamics from two conditions/experiences. The result is a semi-automatic software
pipeline using scRNA-seq and scATAC-seq sequencing data. Here, the project is based on a acute promyelocytic
leukemia (granulocyte lineage hematopoietic cells remain immature promyelocytic cells and proliferate)
niche for which the current usual treatment is inefficient: the PLZF-RARA variant which does not
answer to the retinoic acid treatment.

# Installation

## Using *Bash*

Setup prerequisites must be verified:
1. verify that *latex* markup language is already installed. If not, please use:
```sh
apt-get install texlive dvipng texlive-latex-extra texlive-fonts-recommended
```
2. verify that *Anaconda* package manager is already installed. If not, please install and download it [here](https://www.anaconda.com/download/).

Download and configure project:
```sh
git clone https://gitub.u-bordeaux.fr/troncalli/retinoic-acid-resistance-leukemias.git leukemia
cd leukemia
bash config/env_installation.sh
```
Run the pipeline:
```sh
bash pipeline.sh
```

# Pipeline

<img src=".pipeline.png" alt="boolean network inference pipeline image" width="600"/>

# License

For open source projects, say how it is licensed.

# Project status

Ongoing
