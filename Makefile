#!/usr/bin/env make

.ONESHELL:

MAKEFLAGS += --silent
CONFIG_FILE = config.mk

include $(CONFIG_FILE)

CONDA_ACTIVATE = source $$(conda info --base)/etc/profile.d/conda.sh ; conda activate ; conda activate
CONDA_DEACTIVATE = source $$(conda info --base)/etc/profile.d/conda.sh ; conda deactivate ; conda deactivate

sample = control+treated

# urls
CELL_CYCLE_URL = https://github.com/MarioniLab/scran/raw/master/inst/exdata/mouse_cycle_markers.rds
GEIGER_URL = https://doi.org/10.1371/journal.pbio.2003389.s025
CHAMBERS_URL = https://ars.els-cdn.com/content/image/1-s2.0-S1934590907002202-mmc3.xls
GENOME_URL = ftp://ftp.ensembl.org/pub/release-112/fasta/mus_musculus/dna/Mus_musculus.GRCm39.dna.primary_assembly.fa.gz
TRANSCRIPTOME_URL = https://cf.10xgenomics.com/supp/cell-exp/refdata-gex-GRCm39-2024-A.tar.gz
GO_BASIC_URL = http://purl.obolibrary.org/obo/go/go-basic.obo
GO_MOUSE_URL = https://current.geneontology.org/ontology/subsets/goslim_mouse.obo

# colors
NC = \033[0m
RED = \033[0;31m
BOLDRED = \033[1;31m
GREEN = \033[0;32m
BOLDGREEN = \033[1;32m
BOLD=\033[1m

define section
	@echo -e '$(GREEN)===== $(1) =====$(NC)'
endef

define fastq_naming
	n_fastq="$$(find $(1) -name "$(2)_[1-4].fastq.gz" -printf '.' | wc -m)"
	if [ $${n_fastq} -eq 0 ]; then \
		@echo -e '$(RED)ERROR: fastq downloading failed.$(NC)';\
	elif [ $${n_fastq} -eq 1 ]; then \
		mv $(1)/$(2)_1.fastq.gz $(1)/$(3)_S1_L00$(4)_R1_001.fastq.gz;\
	elif [ $${n_fastq} -eq 2 ]; then \
		mv $(1)/$(2)_1.fastq.gz $(1)/$(3)_S1_L00$(4)_R1_001.fastq.gz
		mv $(1)/$(2)_2.fastq.gz $(1)/$(3)_S1_L00$(4)_R2_001.fastq.gz;\
	elif [ $${n_fastq} -eq 3 ]; then \
		mv $(1)/$(2)_1.fastq.gz $(1)/$(3)_S1_L00$(4)_I1_001.fastq.gz
		mv $(1)/$(2)_2.fastq.gz $(1)/$(3)_S1_L00$(4)_R1_001.fastq.gz
		mv $(1)/$(2)_3.fastq.gz $(1)/$(3)_S1_L00$(4)_R2_001.fastq.gz;\
	elif [ $${n_fastq} -eq 4 ]; then \
		mv $(1)/$(2)_1.fastq.gz $(1)/$(3)_S1_L00$(4)_I1_001.fastq.gz
		mv $(1)/$(2)_2.fastq.gz $(1)/$(3)_S1_L00$(4)_I2_001.fastq.gz
		mv $(1)/$(2)_3.fastq.gz $(1)/$(3)_S1_L00$(4)_R1_001.fastq.gz
		mv $(1)/$(2)_4.fastq.gz $(1)/$(3)_S1_L00$(4)_R2_001.fastq.gz;\
	else \
		@echo -e '$(RED)ERROR: number of downloaded fastq exceeds 4.$(NC)';\
	fi
endef

# directories
PUBLIC = data/public
RNA = data/rna
RNA_CTRL = data/rna/ctrl
RNA_TREATED = data/rna/treated
RNA_INTEGRATED = data/rna/integrated

CYCLE_MARKERS = $(PUBLIC)/cycle_phases/mouse_cycle_markers.rds
SIGNATURES = $(PUBLIC)/signatures/geiger.xls $(PUBLIC)/signatures/chambers.xls $(PUBLIC)/signatures/signatures.json
GO_BASIC = $(PUBLIC)/enrichment/go-basic.obo
GO_MOUSE = $(PUBLIC)/enrichment/goslim.obo
GENE2GO = $(PUBLIC)/enrichment/gene2go

$(eval GENOME := $(PUBLIC)/genome/$(basename $(notdir $(GENOME_URL))))
$(eval ANNOTATIONS := $(PUBLIC)/genome/$(basename $(notdir $(ANNOTATIONS_URL))))
$(eval TRANSCRIPTOME := $(PUBLIC)/genome/$(notdir $(TRANSCRIPTOME_URL)))
TRANSCRIPTOME := $(TRANSCRIPTOME:.tar.gz=)

FASTQ_CTRL = $(RNA_CTRL)/fastq
FASTQ_TREATED = $(RNA_TREATED)/fastq

CELLRANGER_CTRL = $(RNA_CTRL)/counting/cellranger/ctrl.mri.tgz
CELLRANGER_TREATED = $(RNA_TREATED)/counting/cellranger/treated.mri.tgz

VELOCYTO_CTRL = $(RNA_CTRL)/counting/velocyto/ctrl.h5ad
VELOCYTO_TREATED = $(RNA_TREATED)/counting/velocyto/treated.h5ad

FILTER_CTRL = $(RNA_CTRL)/preprocessing/filtering/counts.h5ad
FILTER_TREATED = $(RNA_TREATED)/preprocessing/filtering/counts.h5ad

NORMALISATION_CTRL = $(RNA_CTRL)/preprocessing/normalization/corrected.h5ad
NORMALISATION_TREATED = $(RNA_TREATED)/preprocessing/normalization/corrected.h5ad

CLUSTER_CTRL = $(RNA_CTRL)/clustering/clusters/counts.h5ad
CLUSTER_TREATED = $(RNA_TREATED)/clustering/clusters/tables/counts.h5ad
CLUSTER_INTEGRATED = $(RNA_INTEGRATED)/clustering/clusters/tables/integrated.h5ad

MARKERS_CTRL = $(RNA_CTRL)/clustering/markers/genes/background.txt
MARKERS_TREATED = $(RNA_TREATED)/clustering/markers/genes/background.txt
MARKERS_INTEGRATED = $(RNA_INTEGRATED)/clustering/markers/genes/background.txt

GOEA_BASIC_CTRL = $(RNA_CTRL)/clustering/goea/goea_basic.xlsx
GOEA_MOUSE_CTRL = $(RNA_CTRL)/clustering/goea/goea_mouse.xlsx
GOEA_BASIC_TREATED = $(RNA_TREATED)/clustering/goea/goea_basic.xlsx
GOEA_MOUSE_TREATED = $(RNA_TREATED)/clustering/goea/goea_mouse.xlsx
GOEA_BASIC_INTEGRATED = $(RNA_INTEGRATED)/clustering/goea/goea_basic.xlsx
GOEA_MOUSE_INTEGRATED = $(RNA_INTEGRATED)/clustering/goea/goea_mouse.xlsx

LABELS_CTRL = $(dir $(CLUSTER_CTRL))counts_labels.h5ad
LABELS_TREATED = $(dir $(CLUSTER_TREATED))counts_labels.h5ad
LABELS_INTEGRATED = $(dir $(CLUSTER_INTEGRATED))counts_labels.h5ad

SCVELO_CTRL = $(RNA_CTRL)/trajectories/scvelo/scvelo.h5ad
SCVELO_TREATED = $(RNA_TREATED)/trajectories/scvelo/scvelo.h5ad

PSEUDOTIME_STREAM_CTRL = $(RNA_CTRL)/trajectories/stream/pseudotime/stream.h5ad.pkl
PSEUDOTIME_STREAM_TREATED = $(RNA_TREATED)/trajectories/stream/pseudotime/stream.h5ad.pkl

TRAJECTORIES_STREAM_CTRL = $(RNA_CTRL)/trajectories/stream/trajectories/branches.txt
TRAJECTORIES_STREAM_TREATED = $(RNA_TREATED)/trajectories/stream/trajectories/branches.txt

MACROSTATES_CTRL = $(RNA_CTRL)/trajectories/macrostates/adata.h5ad
MACROSTATES_TREATED = $(RNA_TREATED)/trajectories/macrostates/adata.h5ad

SCBOOLSEQ_CTRL = $(RNA_CTRL)/binarization/cluster_bin_node_clusters.csv
SCBOOLSEQ_TREATED = $(RNA_TREATED)/binarization/cluster_bin_node_clusters.csv

BDC_CTRL = $(RNA_CTRL)/binarization/pairwise_predecessor_scores.csv
BDC_TREATED = $(RNA_TREATED)/binarization/pairwise_predecessor_scores.csv

MODEL_SPECIFICATION_CTRL = $(RNA_CTRL)/bonesis/specification_model.txt
MODEL_SPECIFICATION_TREATED = $(RNA_TREATED)/bonesis/specification_model.txt

FILTER1_CTRL = $(RNA_CTRL)/bonesis/ct/bootstrap_filter_grn_stage1.txt
FILTER2_CTRL = $(RNA_CTRL)/bonesis/ct/bootstrap_filter_grn_stage2.txt
INFERENCE_SUB_CTRL = $(RNA_CTRL)/bonesis/ct/sub.bn
INFERENCE_MIN_CTRL = $(RNA_CTRL)/bonesis/ct/min.bn

# targets
fastq_target :=
cellranger_target :=
velocyto_target :=
h5ad_target :=
filter_target :=
normalization_target :=
cluster_target :=
markers_target :=
goea_target :=
label_target :=
scvelo_velocity_target :=
macrostates_target :=
stream_pseudotime_target :=
stream_trajectories_target :=
scboolseq_target :=
bdc_target :=
model_specification_target :=

ifeq (control,$(findstring control,$(sample)))
 $(eval fastq_target := $(fastq_target) $(FASTQ_CTRL))
 $(eval cellranger_target := $(cellranger_target) $(CELLRANGER_CTRL))
 $(eval velocyto_target := $(velocyto_target) $(VELOCYTO_CTRL))
 $(eval filter_target := $(filter_target) $(FILTER_CTRL))
 $(eval normalization_target := $(normalization_target) $(NORMALISATION_CTRL))
 $(eval cluster_target := $(cluster_target) $(CLUSTER_CTRL))
 $(eval markers_target := $(markers_target) $(MARKERS_CTRL))
 $(eval goea_target := $(goea_target) $(GOEA_BASIC_CTRL) $(GOEA_MOUSE_CTRL))
 $(eval label_target := $(label_target) $(LABELS_CTRL))
 $(eval scvelo_velocity_target := $(scvelo_velocity_target) $(SCVELO_CTRL))
 $(eval macrostates_target := $(macrostates_target) $(MACROSTATES_CTRL))
 $(eval stream_pseudotime_target := $(stream_pseudotime_target) $(PSEUDOTIME_STREAM_CTRL))
 $(eval stream_trajectories_target := $(stream_trajectories_target) $(TRAJECTORIES_STREAM_CTRL))
 $(eval scboolseq_target := $(scboolseq_target) $(SCBOOLSEQ_CTRL))
 $(eval bdc_target := $(bdc_target) $(BDC_CTRL))
 $(eval model_specification_target := $(model_specification_target) $(MODEL_SPECIFICATION_CTRL))
endif
ifeq (treated,$(findstring treated,$(sample)))
 $(eval fastq_target := $(fastq_target) $(FASTQ_TREATED))
 $(eval cellranger_target := $(cellranger_target) $(CELLRANGER_TREATED))
 $(eval velocyto_target := $(velocyto_target) $(VELOCYTO_TREATED))
 $(eval filter_target := $(filter_target) $(FILTER_TREATED))
 $(eval normalization_target := $(normalization_target) $(NORMALISATION_TREATED))
 $(eval cluster_target := $(cluster_target) $(CLUSTER_TREATED))
 $(eval markers_target := $(markers_target) $(MARKERS_TREATED))
 $(eval goea_target := $(goea_target) $(GOEA_BASIC_TREATED) $(GOEA_MOUSE_TREATED))
 $(eval label_target := $(label_target) $(LABELS_TREATED))
 $(eval scvelo_velocity_target := $(scvelo_velocity_target) $(SCVELO_TREATED))
 $(eval macrostates_target := $(macrostates_target) $(MACROSTATES_TREATED))
 $(eval stream_pseudotime_target := $(stream_pseudotime_target) $(PSEUDOTIME_STREAM_TREATED))
 $(eval stream_trajectories_target := $(stream_trajectories_target) $(TRAJECTORIES_STREAM_TREATED))
 $(eval scboolseq_target := $(scboolseq_target) $(SCBOOLSEQ_TREATED))
 $(eval bdc_target := $(bdc_target) $(BDC_TREATED))
 $(eval model_specification_target := $(model_specification_target) $(MODEL_SPECIFICATION_TREATED))
endif
ifeq (integrated,$(findstring integrated,$(sample)))
 $(eval fastq_target := $(FASTQ_CTRL) $(FASTQ_TREATED))
 $(eval cellranger_target := $(CELLRANGER_CTRL) $(CELLRANGER_TREATED))
 $(eval velocyto_target := $(VELOCYTO_CTRL) $(VELOCYTO_TREATED))
 $(eval filter_target := $(FILTER_CTRL) $(FILTER_TREATED))
 $(eval normalization_target := $(NORMALISATION_CTRL) $(NORMALISATION_TREATED))
 $(eval cluster_target := $(cluster_target) $(CLUSTER_INTEGRATED))
 $(eval markers_target := $(markers_target) $(MARKERS_INTEGRATED))
 $(eval goea_target := $(goea_target) $(GOEA_BASIC_INTEGRATED) $(GOEA_MOUSE_INTEGRATED))
 $(eval label_target := $(label_target) $(LABELS_INTEGRATED))
endif

ifneq ($(IGNORED_NODES_CTRL),)
IGNORED_NODES_CTRL:=--ignore-nodes $(IGNORED_NODES_CTRL)
endif

ifneq ($(IGNORED_NODES_TREATED),)
IGNORED_NODES_TREATED:=--ignore-nodes $(IGNORED_NODES_TREATED)
endif

ifeq ($(EXCLUDE_CTRL),true)
EXCLUDE_CTRL:=--exclude
else
EXCLUDE_CTRL:=
endif

ifeq ($(EXCLUDE_TREATED),true)
EXCLUDE_TREATED:=--exclude
else
EXCLUDE_TREATED:=
endif

##@ Help

.PHONY: help
help: ## display this help and exit
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make $(GREEN)<command>$(NC) [sample=control+treated+integrated] (default:sample=control+treated)\n\
	Semi-automatic pipeline proposing a general methodology for inferring executable models reproducing \
	the observed cellular dynamics from two conditions/experiences (control and treated), \
	using scRNA-seq and scATAC-seq sequencing data. The pipeline is particularly useful when phenotype-related cells are not well characterized \
	and when studying almost differentiated cells, where biological process are difficult to determine. \
	Samples can be integrated at the clustering step, in order to annotate cell clusters in control and treated dependently.\n"}/^[a-zA-Z_-]+:.*?##/ \
	{ printf "  $(GREEN)%-22s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(BOLD)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Clean

.PHONY: clean
clean: ## clear cache
	find . -name "\*.pyc" -delete
	find . -name "__pycache__" -delete
	find . -type d -name "cache" -exec rm -rf "{}" \;

.PHONY: mrproper
mrproper: ## clear cache and public/private data
	find . -name "\*.pyc" -delete
	find . -name "__pycache__" -delete
	find . -type d -name "cache" -exec rm -rf "{}" \;
	rm -rf $(RNA)
	find $(PUBLIC)/genome ! -name "repeat_msk.gtf" -exec rm -rf "{}" \;
	mkdir $(RNA_CTRL) $(RNA_TREATED) $(RNA_INTEGRATED)

##@ Download

load-genome: $(GENOME) ## download DNA primary assembly genome
load-annotations: $(TRANSCRIPTOME) ## download genome-related annotations
load-fastq: $(fastq_target) ## download fastq files
load-markers: $(CYCLE_MARKERS) ## download cycle phase markers
load-signatures: $(lastword $(SIGNATURES)) ## download signatures and convert it into json file
load-go: $(GO_BASIC) $(GO_MOUSE) $(GENE2GO) ## download gene ontology-related files

##@ Counting

.PHONY: cellranger
cellranger: $(cellranger_target) ## perform alignment and counting with CellRanger
.PHONY: velocyto
velocyto: $(velocyto_target) ## perform spliced/unspliced counting with velocyto

##@ Preprocessing

.PHONY: filtering
filtering: $(filter_target) ## filtering low quality cells and assignment of cell cycle phases
.PHONY: normalization
normalization: $(normalization_target) ## filtering low quality genes and normalization of counts

##@ Clustering

.PHONY: clustering
clustering: $(cluster_target) ## perform dimension reduction and cell clustering (and optionally INTEGRATION)
.PHONY: marker-analysis
marker-analysis: $(markers_target) ## search for gene markers and compare markers and signatures
.PHONY: goea
goea: $(goea_target) ## perform gene ontology enrichment analysis
.PHONY: cluster-annotation
cluster-annotation: $(label_target) ## annotate clusters

##@ Trajectory inference

.PHONY: scvelo
scvelo: $(scvelo_velocity_target) ## compute rna velocity with scvelo
.PHONY: stream-pseudotime
stream-pseudotime: $(stream_pseudotime_target) ## compute elastic principal graph and pseudotime with stream
.PHONY: stream-trajectories
stream-trajectories: $(stream_trajectories_target) ## compute trajectories with stream
.PHONY: macrostates
macrostates: $(macrostates_target) ## compute macrostates with cellrank or center-extremity method

##@ Binarization

scboolseq: $(scboolseq_target) ## binarize normalized counts with scBoolSeq
bdc: $(bdc_target) ## perform boolean differential calculus analysis

##@ Boolean inference

model-specification: $(model_specification_target) ## specify model for bonesis
filter-one: $(FILTER1_CTRL) ## filter genes (stage 1) with Bonesis
filter-two: $(FILTER1_CTRL) ## filter genes (stage 2) with Bonesis
inference-sub: $(INFERENCE_SUB_CTRL) ## infer boolean network (subminimal) with Bonesis
inference-min: $(INFERENCE_MIN_CTRL) ## infer boolean network (minimal) with Bonesis

filter-stage1-ctrl: $(FILTER1_CTRL)
filter-stage2-ctrl: $(FILTER2_CTRL)
inference-sub-ctrl: $(INFERENCE_SUB_CTRL)
inference-min-ctrl: $(INFERENCE_MIN_CTRL)
# all: $(INFERENCE_SUB_CTRL) $(INFERENCE_MIN_CTRL)  $(MARKERS_TREATED)

$(GENOME):
	$(call section, load-genome)
	mkdir -p $(@D)
	wget --quiet --show-progress --directory-prefix=$(@D) $(GENOME_URL)
	gunzip $@.gz

$(TRANSCRIPTOME):
	$(call section, load-annotations)
	mkdir -p $(@D)
	wget --quiet --show-progress --directory-prefix=$(@D) $(TRANSCRIPTOME_URL)
	tar -zxvf $@.tar.gz -C $(@D)
	gunzip $@/genes/genes.gtf.gz

$(CYCLE_MARKERS):
	$(call section,download cycle phase markers)
	mkdir -p $(@D)
	wget --quiet --show-progress -cO $@ $(CELL_CYCLE_URL)

$(word 1,$(SIGNATURES)) $(word 2,$(SIGNATURES)):
	$(call section,download $(FILENAME) signatures)
	mkdir -p $(@D)
	$(eval FILENAME := $(basename $(notdir $@)))
	if [ $(FILENAME) = "geiger" ]; then \
		wget --quiet --show-progress -cO $@ $(GEIGER_URL); \
	else \
		wget --quiet --show-progress -cO $@ $(CHAMBERS_URL); \
	fi

$(lastword $(SIGNATURES)): $(word 1,$(SIGNATURES)) $(word 2,$(SIGNATURES))
	$(call section,convert-signatures)
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/load_signatures.py \
		--list-infile $(firstword $^) \
		--table-infile $(lastword $^) \
  		--outfile $@
	$(CONDA_DEACTIVATE)

$(GO_BASIC):
	$(call section,load-go-basic)
	mkdir -p $(@D)
	wget --quiet --show-progress -cO $@ $(GO_BASIC_URL)

$(GO_MOUSE):
	$(call section,load-goslim-mouse)
	mkdir -p $(@D)
	wget --quiet --show-progress -cO $@ $(GO_MOUSE_URL)

$(GENE2GO):
	$(call section,load-gene2go)
	mkdir -p $(@D)
	wget --quiet --show-progress --directory-prefix=$(@D) ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/gene2go.gz
	gunzip $@.gz

$(FASTQ_CTRL):
	$(call section,load-fastq (control data))
	$(CONDA_ACTIVATE) fastq-dump
	sample_naming="ctrl"
	lane=0
	tmp_directory=tmp/fastq-ctrl
	rm -rf $${tmp_directory} && mkdir $${tmp_directory}
	for id in $(SRA_CTRL)
	do
		let "lane++"
		parallel-fastq-dump --sra-id $${id} --split-files --readids --origfmt --threads $(JOBS) --outdir $${tmp_directory} --gzip
		$(call fastq_naming,$${tmp_directory},$${id},$${sample_naming},$${lane})
	done
	mkdir $@
	mv $${tmp_directory}/* $@/
	files=$(shopt -s nullglob dotglob; echo $${tmp_directory}/*)
	if ! (( ${#files} ))
	then
		rm -rf $${tmp_directory}
	fi
	unset tmp_directory
	unset files
	$(CONDA_DEACTIVATE)

$(FASTQ_TREATED):
	$(call section,load-fastq (treated data))
	$(CONDA_ACTIVATE) fastq-dump
	sample_naming="treated"
	lane=0
	tmp_directory=tmp/fastq-treated
	rm -rf $${tmp_directory} && mkdir $${tmp_directory}
	for id in $(SRA_TREATED)
	do
		let "lane++"
		parallel-fastq-dump --sra-id $${id} --split-files --readids --origfmt --threads $(JOBS) --outdir $${tmp_directory} --gzip
		$(call fastq_naming,$${tmp_directory},$${id},$${sample_naming},$${lane})
	done
	mkdir $@
	mv $${tmp_directory}/* $@/
	files=$(shopt -s nullglob dotglob; echo $${tmp_directory}/*)
	if ! (( ${#files} ))
	then
		rm -rf $${tmp_directory}
	fi
	unset tmp_directory
	unset files
	$(CONDA_DEACTIVATE)

$(CELLRANGER_CTRL): $(FASTQ_CTRL) $(TRANSCRIPTOME)
	$(call section,cellranger (control data))
	mkdir -p $(@D)
	cellranger count --id=ctrl \
		--fastqs=$(firstword $^) \
   		--transcriptome=$(lastword $^) \
   		--create-bam true \
   		--localcores=$(JOBS) \
   		--localmem=$(MEMORY)
	mv ctrl/* $(@D)
	rm -rf ctrl

$(CELLRANGER_TREATED): $(FASTQ_TREATED) $(TRANSCRIPTOME)
	$(call section,cellranger (treated data))
	mkdir -p $(@D)
	cellranger count --id=treated \
   		--fastqs=$(firstword $^) \
   		--transcriptome=$(lastword $^) \
   		--create-bam true \
   		--localcores=$(JOBS) \
   		--localmem=$(MEMORY)
	mv treated/* $(@D)
	rm -rf treated

$(VELOCYTO_CTRL): $(CELLRANGER_CTRL) $(TRANSCRIPTOME)
	$(call section,velocyto (control data))
	$(CONDA_ACTIVATE) velocyto
	velocyto run10x -m data/public/genome/repeat_msk.gtf \
		--samtools-threads $(JOBS) --samtools-memory $(MEMORY) \
		$(dir $(firstword $^)) $(lastword $^)/genes/genes.gtf
	$(CONDA_DEACTIVATE)
	mkdir -p $(@D)
	mv $(<D)/velocyto/cellranger.loom $(shell echo $@ | sed "s/h5ad/loom/")
	rm -rf $(<D)/velocyto
	$(CONDA_ACTIVATE) preprocess
	python bonesis-tools/clitools/conversion_to_h5ad.py $(shell echo $@ | sed "s/h5ad/loom/") $@ \
		--sample-info $(METADATA_CTRL) \
		--remove-positions
	$(CONDA_DEACTIVATE)

$(VELOCYTO_TREATED): $(CELLRANGER_TREATED) $(TRANSCRIPTOME)
	$(call section,velocyto (control data))
	$(CONDA_ACTIVATE) velocyto
	velocyto run10x -m data/public/genome/repeat_msk.gtf \
		--samtools-threads $(JOBS) --samtools-memory $(MEMORY) \
		$(dir $(firstword $^)) $(lastword $^)/genes/genes.gtf
	$(CONDA_DEACTIVATE)
	mkdir -p $(@D)
	mv $(<D)/velocyto/cellranger.loom $(shell echo $@ | sed "s/h5ad/loom/")
	rm -rf $(<D)/velocyto
	$(CONDA_ACTIVATE) preprocess
	python bonesis-tools/clitools/conversion_to_h5ad.py $(shell echo $@ | sed "s/h5ad/loom/") $@ \
		--sample-info $(METADATA_TREATED) \
		--remove-positions
	$(CONDA_DEACTIVATE)

$(FILTER_CTRL): $(VELOCYTO_CTRL) $(CYCLE_MARKERS)
	$(call section,filtering (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/filter_cells.py \
		--infile $(firstword $^) \
		--marker $(lastword $^) \
		--outpath $(@D) \
		--mitochondrial_threshold 5 \
		--upper-mad 2 \
		--lower-mad 3 \
		--consistency-mad
	$(CONDA_DEACTIVATE)

$(FILTER_TREATED): $(VELOCYTO_TREATED) $(CYCLE_MARKERS)
	$(call section,filtering (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/filter_cells.py \
		--infile $(firstword $^) \
		--marker $(lastword $^) \
		--outpath $(@D) \
		--mitochondrial_threshold 5 \
		--upper-mad 2 \
		--lower-mad 3 \
		--consistency-mad
	$(CONDA_DEACTIVATE)

$(NORMALISATION_CTRL): $(FILTER_CTRL)
	$(call section,normalization (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/normalization.py $< $(@D) \
		--correction G2M_score S_score G1_score \
		--min-cell-expression-proportion 0.001 \
		--jobs $(JOBS)
	$(CONDA_DEACTIVATE)

$(NORMALISATION_TREATED): $(FILTER_TREATED)
	$(call section,normalization (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/normalization.py $< $(@D) \
		--correction G2M_score S_score G1_score \
		--min-cell-expression-proportion 0.001 \
		--jobs $(JOBS)
	$(CONDA_DEACTIVATE)

$(CLUSTER_CTRL): $(NORMALISATION_CTRL)
	$(call section,clustering (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/clusters.py $< $(@D) \
		--hvg --metric euclidean --k-neighbors $(K_NEIGHBORS_CTRL) --resolution $(RESOLUTION_LEIDEN_CTRL) \
		--dim-pca $(DIM_PCA_CTRL) --dim-clustering $(DIM_CLUSTERING_CTRL) --dim-umap $(DIM_UMAP_CTRL) \
		--add-legend --plot-3d \
		--seed $(SEED_CLUSTER_CTRL) \
		--verbose
	$(CONDA_DEACTIVATE)

$(CLUSTER_TREATED): $(NORMALISATION_TREATED)
	$(call section,clustering (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/clusters.py $< $(@D) \
		--hvg --metric euclidean --k-neighbors $(K_NEIGHBORS_TREATED) --resolution $(RESOLUTION_LEIDEN_TREATED) \
		--dim-pca $(DIM_PCA_TREATED) --dim-clustering $(DIM_CLUSTERING_TREATED) --dim-umap $(DIM_UMAP_TREATED) \
		--add-legend --plot-3d \
		--seed $(SEED_CLUSTER_TREATED) \
		--verbose
	$(CONDA_DEACTIVATE)

$(CLUSTER_INTEGRATED): $(NORMALISATION_CTRL) $(NORMALISATION_TREATED)
	$(call section,clustering (integrated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/integration.py $^ $(shell echo $(dir $@) | sed "s/tables\///") \
		--label condition --method $(INTEGRATION_METHOD) \
		--hvg --metric euclidean --k-neighbors $(K_NEIGHBORS_INTEGRATED) --resolution $(RESOLUTION_LEIDEN_INTEGRATED) \
		--dim-pca $(DIM_PCA_INTEGRATED) --dim-clustering $(DIM_CLUSTERING_INTEGRATED) --dim-umap $(DIM_UMAP_INTEGRATED) \
		--add-legend --plot-3d \
		--seed $(SEED_CLUSTER_INTEGRATED) \
		--jobs $(JOBS) \
		--verbose
	$(CONDA_DEACTIVATE)

$(MARKERS_CTRL): $(CLUSTER_CTRL) $(lastword $(SIGNATURES))
	$(eval MARKERS_CSV_CTRL := $(dir $(@D))markers.csv)
	$(call section,marker-analysis (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/markers.py $^ $(dir $(MARKERS_CSV_CTRL)) \
  		--cluster leiden \
  		--logfc-threshold 0.25 \
  		--verbose
	@echo -e 'Compute background genes...'
	python bonesis-tools/clitools/genename.py $< $@
	export clusters=`column -s, -t < $(MARKERS_CSV_CTRL) | awk 'NR>1 {print $$2}' | sort -u | tr '\n' ' '`
	@echo -e 'Compute upregulated cluster-related genes...'
	for cluster in $${clusters}
	do
		`column -s, -t < $(MARKERS_CSV_CTRL) | awk -v c=$${cluster} '$$2==c {print $$1}' > $(@D)/cluster$${cluster}.txt`
		python bonesis-tools/clitools/genename_standardization.py $(@D)/cluster$${cluster}.txt $(@D)/cluster$${cluster}.txt --quiet
	done
	unset clusters
	$(CONDA_DEACTIVATE)

$(MARKERS_TREATED): $(CLUSTER_TREATED) $(lastword $(SIGNATURES))
	$(eval MARKERS_CSV_TREATED := $(dir $(@D))markers.csv)
	$(call section,marker-analysis (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/markers.py $^ $(dir $(MARKERS_CSV_TREATED)) \
  		--cluster leiden \
  		--logfc-threshold 0.25 \
  		--verbose
	@echo -e 'Compute background genes...'
	python bonesis-tools/clitools/genename.py $< $@
	export clusters=`column -s, -t < $(MARKERS_CSV_TREATED) | awk 'NR>1 {print $$2}' | sort -u | tr '\n' ' '`
	@echo -e 'Compute upregulated cluster-related genes...'
	for cluster in $${clusters}
	do
		`column -s, -t < $(MARKERS_CSV_TREATED) | awk -v c=$${cluster} '$$2==c {print $$1}' > $(@D)/cluster$${cluster}.txt`
		python bonesis-tools/clitools/genename_standardization.py $(@D)/cluster$${cluster}.txt $(@D)/cluster$${cluster}.txt --quiet
	done
	unset clusters
	$(CONDA_DEACTIVATE)

$(MARKERS_INTEGRATED): $(CLUSTER_INTEGRATED) $(lastword $(SIGNATURES))
	$(eval MARKERS_CSV_INTEGRATED := $(dir $(@D))markers.csv)
	$(call section,marker-analysis (integrated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/markers.py $^ $(dir $(MARKERS_CSV_INTEGRATED)) \
  		--cluster leiden \
  		--logfc-threshold 0.25 \
  		--verbose
	@echo -e 'Compute background genes...'
	python bonesis-tools/clitools/genename.py $< $@
	export clusters=`column -s, -t < $(MARKERS_CSV_INTEGRATED) | awk 'NR>1 {print $$2}' | sort -u | tr '\n' ' '`
	@echo -e 'Compute upregulated cluster-related genes...'
	for cluster in $${clusters}
	do
		`column -s, -t < $(MARKERS_CSV_INTEGRATED) | awk -v c=$${cluster} '$$2==c {print $$1}' > $(@D)/cluster$${cluster}.txt`
		python bonesis-tools/clitools/genename_standardization.py $(@D)/cluster$${cluster}.txt $(@D)/cluster$${cluster}.txt --quiet
	done
	unset clusters
	$(CONDA_DEACTIVATE)

$(GOEA_BASIC_CTRL): $(MARKERS_CTRL) $(GO_BASIC) $(GENE2GO)
	$(call section,goea (control data, with go-basic.obo))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/enrichment.py $@ \
    	--population $< \
    	--study $(<D)/cluster*.txt \
    	--go $(word 2,$^) \
    	--gene2go $(lastword $^) \
    	--verbose
	$(CONDA_DEACTIVATE)

$(GOEA_MOUSE_CTRL): $(MARKERS_CTRL) $(GO_MOUSE) $(GENE2GO)
	$(call section,goea (control data, with goslim_mouse.obo))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/enrichment.py $@ \
    	--population $< \
    	--study $(<D)/cluster*.txt \
    	--go $(word 2,$^) \
    	--gene2go $(lastword $^) \
    	--verbose
	$(CONDA_DEACTIVATE)

$(GOEA_BASIC_TREATED): $(MARKERS_TREATED) $(GO_BASIC) $(GENE2GO)
	$(call section,goea (treated data, with go-basic.obo))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/enrichment.py $@ \
    	--population $< \
    	--study $(<D)/cluster*.txt \
    	--go $(word 2,$^) \
    	--gene2go $(lastword $^) \
    	--verbose
	$(CONDA_DEACTIVATE)

$(GOEA_MOUSE_TREATED): $(MARKERS_TREATED) $(GO_MOUSE) $(GENE2GO)
	$(call section,goea (treated data, with goslim_mouse.obo))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/enrichment.py $@ \
    	--population $< \
    	--study $(<D)/cluster*.txt \
    	--go $(word 2,$^) \
    	--gene2go $(lastword $^) \
    	--verbose
	$(CONDA_DEACTIVATE)

$(GOEA_BASIC_INTEGRATED): $(MARKERS_INTEGRATED) $(GO_BASIC) $(GENE2GO)
	$(call section,goea (integrated data, with go-basic.obo))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/enrichment.py $@ \
    	--population $< \
    	--study $(<D)/cluster*.txt \
    	--go $(word 2,$^) \
    	--gene2go $(lastword $^) \
    	--verbose
	$(CONDA_DEACTIVATE)

$(GOEA_MOUSE_INTEGRATED): $(MARKERS_INTEGRATED) $(GO_MOUSE) $(GENE2GO)
	$(call section,goea (integrated data, with goslim_mouse.obo))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/enrichment.py $@ \
    	--population $< \
    	--study $(<D)/cluster*.txt \
    	--go $(word 2,$^) \
    	--gene2go $(lastword $^) \
    	--verbose
	$(CONDA_DEACTIVATE)

ifdef CLUSTER_LABEL_INTEGRATED
 $(LABELS_INTEGRATED): $(CLUSTER_INTEGRATED)
	$(call section,cluster-annotation (integrated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/cluster_annotation.py $< $@ \
		--column leiden \
		--name $(CLUSTER_LABEL_INTEGRATED)
	python figures/plot_embedding.py figures/umap_labels.json \
		--infile $@ --outfile $(shell echo $(dir $@) | sed "s/tables/figures\/umap_labels/")
	$(CONDA_DEACTIVATE)
else
 $(LABELS_INTEGRATED): $(CLUSTER_INTEGRATED)
	@echo -e '$(BOLDRED)CLUSTER_LABEL_INTEGRATED is not defined. Please define it in the command-line or in $(CONFIG_FILE). Aborting.$(NC)'
	exit
endif

ifeq ($(LABELING_FROM_INTEGRATION),true)
$(LABELS_CTRL): $(LABELS_INTEGRATED) $(CLUSTER_CTRL)
	$(call section,cluster-annotation (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/pipe.py $^ --outfiles $@ --column leiden --condition condition
	python figures/plot_embedding.py figures/umap_labels.json \
		--infile $@ --outfile $(shell echo $(dir $@) | sed "s/tables/figures\/umap_labels/")
	$(CONDA_DEACTIVATE)
$(LABELS_TREATED): $(LABELS_INTEGRATED) $(CLUSTER_TREATED)
	$(call section,cluster-annotation (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/pipe.py $^ --outfiles $@ --column leiden --condition condition
	python figures/plot_embedding.py figures/umap_labels.json \
		--infile $@ --outfile $(shell echo $(dir $@) | sed "s/tables/figures\/umap_labels/")
	$(CONDA_DEACTIVATE)
else
ifdef CLUSTER_LABEL_CTRL
$(LABELS_CTRL): $(CLUSTER_CTRL)
	$(call section,cluster-annotation (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/cluster_annotation.py $< $@ \
		--column leiden \
		--name $(CLUSTER_LABEL_CTRL)
	python figures/plot_embedding.py figures/umap_labels.json \
		--infile $@ --outfile $(shell echo $(dir $@) | sed "s/tables/figures\/umap_labels/")
	$(CONDA_DEACTIVATE)
else
$(LABELS_CTRL): $(CLUSTER_CTRL)
	@echo -e '$(BOLDRED)CLUSTER_LABEL_CTRL is not defined. Please define it in the command-line or in $(CONFIG_FILE). Aborting.$(NC)'
	exit
endif
ifdef CLUSTER_LABEL_TREATED
$(LABELS_TREATED): $(CLUSTER_TREATED)
	$(call section,cluster-annotation (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/cluster_annotation.py $< $@ \
		--column leiden \
		--name $(CLUSTER_LABEL_TREATED)
	python figures/plot_embedding.py figures/umap_labels.json \
		--infile $@ --outfile $(shell echo $(dir $@) | sed "s/tables/figures\/umap_labels/")
	$(CONDA_DEACTIVATE)
else
$(LABELS_TREATED): $(CLUSTER_TREATED)
	@echo -e '$(BOLDRED)CLUSTER_LABEL_TREATED is not defined. Please define it in the command-line or in $(CONFIG_FILE). Aborting.$(NC)'
	exit
endif
endif

$(SCVELO_CTRL): $(LABELS_CTRL)
	$(call section,scvelo (control data))
	$(CONDA_ACTIVATE) scvelo
	python pipeline/trajectories/scvelo_velocity.py $< $(@D) \
		--cluster leiden \
		--k-neighbors $(SCVELO_K_NEIGHBORS_CTRL) \
		--dim-clustering $(SCVELO_DIM_CLUSTERING_CTRL) \
		--mode $(SMM_MODE_CTRL) \
		--add-legend
	$(CONDA_DEACTIVATE)

$(SCVELO_TREATED): $(LABELS_TREATED)
	$(call section,scvelo (treated data))
	$(CONDA_ACTIVATE) scvelo
	python pipeline/trajectories/scvelo_velocity.py $< $(@D) \
		--cluster leiden \
		--k-neighbors $(SCVELO_K_NEIGHBORS_TREATED) \
		--dim-clustering $(SCVELO_DIM_CLUSTERING_TREATED) \
		--mode $(SMM_MODE_TREATED) \
		--add-legend
	$(CONDA_DEACTIVATE)

$(PSEUDOTIME_STREAM_CTRL): $(LABELS_CTRL)
	$(call section,stream-pseudotime (control data))
	$(CONDA_ACTIVATE) stream
	python pipeline/trajectories/stream_pseudotime.py $< $(@D) \
		--extension both --cluster-number 6 --groups leiden \
		--lambda $(LAMBDA_CTRL) --mu $(MU_CTRL) --alpha $(ALPHA_CTRL) \
		--extend-leaf-nodes --extend-mode WeigthedCentroid --extend-parameter $(EXTEND_CTRL) \
		--add-legend --add-graph \
		--jobs $(JOBS)
	$(CONDA_DEACTIVATE)

$(PSEUDOTIME_STREAM_TREATED): $(LABELS_TREATED)
	$(call section,stream-pseudotime (treated data))
	$(CONDA_ACTIVATE) stream
	python pipeline/trajectories/stream_pseudotime.py $< $(@D) \
		--extension both --cluster-number 6 --groups leiden \
		--lambda $(LAMBDA_TREATED) --mu $(MU_TREATED) --alpha $(ALPHA_TREATED) \
		--extend-leaf-nodes --extend-mode WeigthedCentroid --extend-parameter $(EXTEND_TREATED) \
		--add-legend --add-graph \
		--jobs $(JOBS)
	$(CONDA_DEACTIVATE)

$(TRAJECTORIES_STREAM_CTRL): $(PSEUDOTIME_STREAM_CTRL)
	$(call section,stream-trajectories (control data))
	@echo -e '$(BOLDGREEN)Warning: root can be modified depending on scvelo and BDC analysis$(NC)'
	$(CONDA_ACTIVATE) stream
	python pipeline/trajectories/stream_trajectories.py $< $(@D) --root $(ROOT_CTRL) \
		--groups leiden kmeans node_clusters \
		--add-legend --add-graph $(IGNORED_NODES_CTRL)
	$(CONDA DEACTIVATE)

$(TRAJECTORIES_STREAM_TREATED): $(PSEUDOTIME_STREAM_TREATED)
	$(call section,stream-trajectories (control data))
	@echo -e '$(BOLDGREEN)Warning: root can be modified depending on scvelo and BDC analysis$(NC)'
	$(CONDA_ACTIVATE) stream
	python pipeline/trajectories/stream_trajectories.py $< $(@D) --root $(ROOT_TREATED) \
		--groups leiden kmeans node_clusters \
		--add-legend --add-graph $(IGNORED_NODES_TREATED)
	$(CONDA DEACTIVATE)

ifeq ($(MACROSTATES_FROM_CELLRANK),true)
$(MACROSTATES_CTRL): $(SCVELO_CTRL)
	$(call section,macrostates (control data))
	$(CONDA_ACTIVATE) cellrank
	python pipeline/trajectories/cellrank_macrostates.py $< $(@D) \
		--macrostate-size $(MACROSTATE_SIZE) \
		--initial-states $(INITIAL_STATES_CTRL) \
		--terminal-states $(TERMINAL_STATES_CTRL) \
		--method $(CELLRANK_METHOD) \
		--plot-3d
	$(CONDA_DEACTIVATE)
$(MACROSTATES_TREATED): $(SCVELO_TREATED)
	$(call section,macrostates (treated data))
	$(CONDA_ACTIVATE) cellrank
	python pipeline/trajectories/cellrank_macrostates.py $< $(@D) \
		--macrostate-size $(MACROSTATE_SIZE) \
		--initial-states $(INITIAL_STATES_TREATED) \
		--terminal-states $(TERMINAL_STATES_TREATED) \
		--method $(CELLRANK_METHOD) \
		--plot-3d
	$(CONDA_DEACTIVATE)
else
$(MACROSTATES_CTRL): $(SCVELO_CTRL)
	$(call section,macrostates (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/trajectories/macrostates.py $< $(@D) \
		--obs leiden --obsm X_umap \
		--dimension $(DIM_UMAP_CTRL) \
		--center $(CENTER_CTRL) --extremity $(EXTREMITY_CTRL) $(EXCLUDE_CTRL) \
		--macrostate-size $(MACROSTATE_SIZE) \
		--plot-3d
	$(CONDA_DEACTIVATE)
$(MACROSTATES_TREATED): $(SCVELO_TREATED)
	$(call section,macrostates (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/trajectories/macrostates.py $< $(@D) \
		--obs leiden --obsm X_umap \
		--dimension $(DIM_UMAP_TREATED) \
		--center $(CENTER_TREATED) --extremity $(EXTREMITY_TREATED) $(EXCLUDE_TREATED) \
		--macrostate-size $(MACROSTATE_SIZE) \
		--plot-3d
	$(CONDA_DEACTIVATE)
endif

$(SCBOOLSEQ_CTRL): $(PSEUDOTIME_STREAM_CTRL)
	$(call section,scboolseq (control data))
	$(CONDA_ACTIVATE) scboolseq
	python pipeline/binarization/bin_clusters.py $(shell echo $< | sed "s/.pkl//") $(dir $@) \
		--cluster leiden node_clusters --exclude nan \
		--layer log-normalize --hvg \
		--verbose
	$(CONDA DEACTIVATE)

$(SCBOOLSEQ_TREATED): $(PSEUDOTIME_STREAM_TREATED)
	$(call section,scboolseq (control data))
	$(CONDA_ACTIVATE) scboolseq
	python pipeline/binarization/bin_clusters.py $(shell echo $< | sed "s/.pkl//") $(dir $@) \
		--cluster leiden node_clusters --exclude nan \
		--layer log-normalize --hvg \
		--verbose
	$(CONDA DEACTIVATE)

$(BDC_CTRL): $(SCBOOLSEQ_CTRL)
	$(call section,Boolean differential calculus (control data))
	$(CONDA_ACTIVATE) scboolseq
	python pipeline/binarization/differential_analysis.py $< $(@D) --verbose
	$(CONDA DEACTIVATE)

$(BDC_TREATED): $(SCBOOLSEQ_TREATED)
	$(call section,Boolean differential calculus (treated data))
	$(CONDA_ACTIVATE) scboolseq
	python pipeline/binarization/differential_analysis.py $< $(@D) --verbose
	$(CONDA DEACTIVATE)

$(MODEL_SPECIFICATION_CTRL): $(TRAJECTORIES_STREAM_CTRL)
	$(call section,model-specification (control data))
	mkdir -p $(@D)
	python3 pipeline/bonesis/design_bo.py $< > $@

$(MODEL_SPECIFICATION_TREATED): $(TRAJECTORIES_STREAM_TREATED)
	$(call section,model-specification (treated data))
	mkdir -p $(@D)
	python3 pipeline/bonesis/design_bo.py $< > $@

#$(10XGENOMICS_CTRL):
#	$(call section,download 10X genomics data (control data))
#	mkdir -p $(@D)
#	wget --quiet --show-progress --recursive --no-parent -nd --reject "index.html" \
#  		--directory-prefix=$(@D) \
#  		ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSM5492nnn/GSM5492245/suppl/
#	mv $(@D)/*matrix.mtx.gz $(word 1,$(10XGENOMICS_CTRL))
#	mv $(@D)/*genes.tsv.gz $(word 2,$(10XGENOMICS_CTRL))
#	mv $(@D)/*barcodes.tsv.gz $(word 3,$(10XGENOMICS_CTRL))

#$(10XGENOMICS_TREATED):
#	$(call section,download 10X genomics data (treated data))
#	mkdir -p $(@D)
#	wget --quiet --show-progress --recursive --no-parent -nd --reject "index.html" \
#		--directory-prefix=$(@D) \
#		ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSM5492nnn/GSM5492246/suppl/
#	mv $(@D)/*matrix.mtx.gz $(word 1,$(10XGENOMICS_TREATED))
#	mv $(@D)/*genes.tsv.gz $(word 2,$(10XGENOMICS_TREATED))
#	mv $(@D)/*barcodes.tsv.gz $(word 3,$(10XGENOMICS_TREATED))



$(FILTER1_CTRL): $(SPECIFICATION_CTRL) $(SCBOOLSEQ_CTRL)
	$(call section,Bonesis filtering (control data, stage 1))
	$(CONDA_ACTIVATE) bonesis
	mkdir -p $(@D)
	python pipeline/bonesis/infer_bo.py filter_stage1 $(dir $<) \
		--organism $(ORGANISM) \
		--bin-metastates $(lastword $^) \
  		--model-specification $(firstword $^) > $@
	$(CONDA_DEACTIVATE)

$(FILTER2_CTRL): $(FILTER1_CTRL) $(SPECIFICATION_CTRL) $(SCBOOLSEQ_CTRL)
	$(call section,Bonesis filtering (control data, stage 2))
	$(CONDA_ACTIVATE) bonesis
	python pipeline/bonesis/infer_bo.py filter_stage2 $(dir $<) \
		--organism $(ORGANISM) \
		--bin-metastates $(lastword $^) \
  		--model-specification $(word 2, $^) \
  		--filter-grn $(firstword $^) > $@
	$(CONDA_DEACTIVATE)

$(INFERENCE_SUB_CTRL): $(FILTER2_CTRL) $(SPECIFICATION_CTRL) $(SCBOOLSEQ_CTRL)
	$(call section,Bonesis inference (control data, one-sub))
	$(CONDA_ACTIVATE) bonesis
	mkdir -p $(@D)
	python pipeline/bonesis/infer_bo.py one-sub $(dir $<) \
		--organism $(ORGANISM) \
		--bin-metastates $(lastword $^) \
  		--model-specification $(word 2, $^) \
		--filter-grn $(firstword $^)
	$(CONDA_DEACTIVATE)

$(INFERENCE_MIN_CTRL): $(FILTER2_CTRL) $(SPECIFICATION_CTRL) $(SCBOOLSEQ_CTRL)
	$(call section,Bonesis inference (control data, one-min))
	$(CONDA_ACTIVATE) bonesis
	mkdir -p $(@D)
	python pipeline/bonesis/infer_bo.py one-min $(dir $<) \
		--bin-metastates $(lastword $^) \
		--model-specification $(word 2, $^) \
		--filter-grn $(firstword $^)
	$(CONDA_DEACTIVATE)

# 10XGENOMICS_CTRL = $(RNA_CTRL)/raw/matrix.mtx.gz $(RNA_CTRL)/raw/features.tsv.gz $(RNA_CTRL)/raw/barcodes.tsv.gz
# 10XGENOMICS_TREATED = $(RNA_TREATED)/raw/ra/matrix.mtx.gz $(RNA_TREATED)/raw/ra/features.tsv.gz $(RNA_TREATED)/raw/ra/barcodes.tsv.gz
# MGI_GAF = $(PUBLIC)/enrichment/mgi.gaf
# ANNOTATIONS_URL = ftp://ftp.ensembl.org/pub/release-112/gtf/mus_musculus/Mus_musculus.GRCm39.112.chr.gtf.gz

#$(ANNOTATIONS):
#	$(call section, load-annotations)
#	mkdir -p $(@D)
#	wget --quiet --show-progress --directory-prefix=$(@D) $(ANNOTATIONS_URL)
#	gunzip $@.gz

#$(MGI_GAF):
#	$(call section,download mgi.gaf file)
#	mkdir -p $(@D)
#	wget --quiet --show-progress --directory-prefix=$(@D) https://current.geneontology.org/annotations/mgi.gaf.gz
#	gunzip $@.gz
