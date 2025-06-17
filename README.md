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

The semi-automatic workflow scBridge (pipeline for Boolean network Reconstruction and Inference
from multiple experimental Data in Gene Expression) proposes a general methodology for
inferring logical models reproducing the observed transcriptomic cellular dynamics by using scRNA-seq data as input.
Its implementation in `make` offers a wide range of advanced features for guiding and helping users
in reconstructing data-driven Boolean networks. Also, scBridge aims to provide an answer to the following challenges:
* automatize the stages of model reconstruction as much as possible;
* incorporate multicondition aspect by managing experiment-related factors.

Pipeline is based on the BoNesis framework, where the synthesis of BNs
requires a partially defined transition graph and a domain restricting the model search
space. To achieve these goals, scBridge proposes a guideline made up of many computational
steps (see Figure below). The first ones are classic methods for the
feature counting and preprocessing. As scBridge aims to decipher biolgical processes from
multiple high-throughput sequencing experiments, batch effects are identified and removed for avoiding
inaccurate analysis. Once condition-related data are integrated, cell profiles have to be defined,
a major step for characterizing observed biological processes later. It is the first step
requiring user intervention, but some decision-making tools are provided to help user in this task,
such as differentia expression analysis (dea), gene ontology enrichment analysis (goea) and signature scoring.
Nevertheless, cell annotation is often not sufficient to deduce transcriptomic dynamics,
limiting its application to well-documented processes. Some inference trajectory tools
can be run to analyze the temporal cell behaviors. Then scBridge searches for key phenotypic manifolds,
-- called macrostates -- and maps feature counting to Boolean values. Serving
as Boolean states, user can specify dynamical Boolean properties between those states.
Using as domain a gene-regulatory network such as Collectri, scBridge can then infer BNs
satisfying the dynamical properties given by the user.

<p align="center">
<img src="man/fig/scbridge-overview.png" alt="scbridge-overview" width="700"/>
<p>

*note:* computational steps are either automated (gray), require some user decisions (red) or help user in decisions (green).

For a proper use of the pipeline, an advanced documentation is provided [here](https://github.com/bnediction/scBridge/tree/main/man).
User can also find a summary documentation using `make help`.

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
