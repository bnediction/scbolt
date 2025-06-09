[![Make](https://img.shields.io/badge/Make-%3E%3D4.3-red?style=flat)](https://www.gnu.org/software/make)

# Boolean Networks Inference for Explaining Treatment-Resistant Leukemia

## Introduction

Multi-omics sequencing has opened up new ways of modeling biological processes.
This last decade, many tools have been developed to analyze these multiscale data;
however it stills remains a major challenge to characterize data-driven biological models,
mostly due to genome-scale network complexity. In particular, biological mechanisms involved
in therapy-resistant disease are difficult to define, because of chromosal translocations
and somatic mutations leading to uncommon signaling pathways. Moreover data can come from
distinct experiments, adding integration-related issues such as batch effects.
In this context, a semi-automatic software pipeline, named scBridge, has been developed, dealing with these difficulties
for reconstructing executable qualitative models, using single-cell transcriptomics data.
Its applications are multiple:
1. predicting cellular fate decision and lineage differentiation
2. understanding disease-driving signals and finding drug-targets
3. etc.

## Method

scBridge (pipeline for Boolean network Reconstruction and Inference from multiple experimental Data in Gene Expression)
proposes a general methodology for inferring executable models reproducing *in silico*
the observed cellular dynamics from multiple conditions/experiments.

<p align="center">
<img src="man/fig/workflow-overview.png" alt="boolean network inference pipeline image" width="700"/>
<p>

scBridge follows many steps for reconstructing logic models from transcriptomics data.
Some steps require biological expertise (aided by decision-making tools):
1. cell annotation (unknown cell profile)
2. macrostate characterization (finding key phenotypic manifolds)
3. model specification (biological process dynamics poorly defined in literature)

## Installation

### Setup prerequisites

1. Verify that *GNU Make* (version >= 4.3) command-line tool is already installed. If not, please use:
```sh
apt-get install build-essential
```
2. verify that *latex* markup language is already installed. If not, please use:
```sh
apt-get install texlive dvipng texlive-latex-extra texlive-fonts-recommended cm-super texlive-extra-utils
```
3. verify that *Anaconda* package manager is already installed. If not, please install and download it [here](https://www.anaconda.com/download/).
4. verify that *Cell Ranger* bioinformatics tool is already installed. If not, please install it [here](https://www.10xgenomics.com/support/software/cell-ranger/downloads) and add it to your *PATH* environment variable.

### Configuration

Download and configure project as follows:
```sh
git clone https://gitub.u-bordeaux.fr/troncalli/retinoic-acid-resistance-leukemias.git leukemia
cd leukemia
bash config.sh
```
Also, you need to download file containing expressed repetitive elements to mask [here](https://genome.ucsc.edu/cgi-bin/hgTables?hgsid=611454127_NtvlaW6xBSIRYJEBI0iRDEWisITa&clade=mammal&org=&db=mm39&hgta_group=allTracks&hgta_track=rmsk&hgta_table=rmsk&hgta_regionType=genome&position=&hgta_outputType=gff&hgta_outFileName=repeat_msk.gtf) and move it to directory 'data/public/transcriptome/repeat_msk.gtf'.

## Use

For running the pipeline:
```sh
make [SAMPLES=<...>]
```
For using specific features, please refer to the documentation available with:
```sh
make help
```
Default parameters are available in `default_params.mk` file. To update and override parameters, please edit `params.mk` file.

## License

No license for the moment. Its purpose is only for intern usage.

## Contributors

* [Théo Roncalli](https://github.com/Theo-Roncalli)
