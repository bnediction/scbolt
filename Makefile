#!/usr/bin/env make

.ONESHELL:

SHELL = /bin/bash
MAKEFLAGS += --silent
DEFAULT_PARAMS = default_params.mk
PARAMS = params.mk

include $(DEFAULT_PARAMS) $(PARAMS)

conda_activate = source $$(conda info --base)/etc/profile.d/conda.sh ; conda activate ; conda activate
conda_deactivate = source $$(conda info --base)/etc/profile.d/conda.sh ; conda deactivate ; conda deactivate

_lower2upper = a:A b:B c:C d:D e:E f:F g:G h:H i:I j:J k:K l:L m:M n:N o:O p:P q:Q r:R s:S t:T u:U v:V w:W x:X y:Y z:Z
_lower = $(word 1, $(subst :, ,$(word 1,$(1))))
_upper = $(word 2, $(subst :, ,$(word 1,$(1))))
toupper = $(eval _=$1)$(strip $(foreach pair,$(_lower2upper),$(eval _=$(subst $(call _lower,$(pair)),$(call _upper,$(pair)),$_))))$_
tolower = $(eval _=$1)$(strip $(foreach pair,$(_lower2upper),$(eval _=$(subst $(call _upper,$(pair)),$(call _lower,$(pair)),$_))))$_

plus := +
empty :=
space := $(empty) $(empty)

conditions := $(call tolower, $(CONDITIONS))
conditions_plus_integrated := $(conditions) integrated
SAMPLES := $(subst $(space),$(plus),$(conditions_plus_integrated))
_samples := $(subst $(plus),$(space),$(SAMPLES))
_samples_without_integration := $(subst $(space)integrated,,$(_samples))

## BEGIN URLS ##

cell_cycle_url = https://github.com/MarioniLab/scran/raw/master/inst/exdata/mouse_cycle_markers.rds
geiger_url = https://doi.org/10.1371/journal.pbio.2003389.s025
chambers_url = https://ars.els-cdn.com/content/image/1-s2.0-S1934590907002202-mmc3.xls
genome_url = ftp://ftp.ensembl.org/pub/release-112/fasta/mus_musculus/dna/Mus_musculus.GRCm39.dna.primary_assembly.fa.gz
transcriptome_url = https://cf.10xgenomics.com/supp/cell-exp/refdata-gex-GRCm39-2024-A.tar.gz
go_basic_url = http://purl.obolibrary.org/obo/go/go-basic.obo
go_mouse_url = https://current.geneontology.org/ontology/subsets/goslim_mouse.obo
gene2go_url = ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/gene2go.gz

## END URLS ##

## BEGIN COLORS ##

NC = \033[0m
RED = \033[0;31m
BOLDRED = \033[1;31m
GREEN = \033[0;32m
BOLDGREEN = \033[1;32m
BOLD=\033[1m

## END COLORS ##

## BEGIN FUNCTIONS ##

define print_rule
	$(if $2,@echo `date "+%Y-%m-%d %H:%M:%S.%3N"` - RULE - $(1) \($(2)\),@echo `date "+%Y-%m-%d %H:%M:%S.%3N"` - RULE - $(1))
endef

define print_task
	@echo `date "+%Y-%m-%d %H:%M:%S.%3N"` - TASK - $(1)
endef

define print_info
	@echo `date "+%Y-%m-%d %H:%M:%S.%3N"` - INFO - $(1)
endef

define print_warning
	@echo `date "+%Y-%m-%d %H:%M:%S.%3N"` - WARNING - $(1)
endef

define print_error
	@echo `date "+%Y-%m-%d %H:%M:%S.%3N"` - ERROR - $(1)
	exit
endef

define fastq_naming
	n_fastq="$$(find $(1) -name "$(2)_[1-4].fastq.gz" -printf '.' | wc -m)"
	if [ $${n_fastq} -eq 0 ]; then \
		$(call print_error,fastq downloading failed);\
	
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
		$(call print_error,number of downloaded fastq exceeds 4);\

	fi
endef

## END FUNCTIONS ##

# BEGIN PATHS ##

public = data/public
rna = data/rna

cycle_markers = $(public)/cycle_phases/mouse_cycle_markers.rds
signatures = $(public)/signatures/geiger.xls $(public)/signatures/chambers.xls $(public)/signatures/signatures.json
go_basic = $(public)/enrichment/go-basic.obo
go_mouse = $(public)/enrichment/goslim.obo
gene2go = $(public)/enrichment/gene2go

$(eval genome := $(public)/genome/$(basename $(notdir $(genome_url))))
$(eval annotations := $(public)/genome/$(basename $(notdir $(annotations_url))))
$(eval transcriptome := $(public)/genome/$(notdir $(transcriptome_url)))
transcriptome := $(transcriptome:.tar.gz=)

define condition_dependant_paths

fastq_$(1) = 					$(rna)/$(1)/fastq
cellranger_$(1) = 				$(rna)/$(1)/counting/cellranger/$(1).mri.tgz
velocyto_$(1) = 				$(rna)/$(1)/counting/velocyto/counts.h5ad
filtering_$(1) = 				$(rna)/$(1)/preprocessing/filtering/counts.h5ad
normalization_$(1) = 			$(rna)/$(1)/preprocessing/normalization/counts.h5ad
scvelo_$(1) = 					$(rna)/$(1)/trajectories/scvelo/scvelo.h5ad
trajectories_macrostates_$(1) =	$(rna)/$(1)/trajectories/macrostates/trajectories.txt
cellrank_$(1) = 				$(rna)/$(1)/macrostates/cellrank/macrostates.h5ad
center_extremity_$(1) = 		$(rna)/$(1)/macrostates/center_extremity/macrostates.h5ad
cotan_$(1) = 					$(rna)/$(1)/macrostates/cotan/macrostates.h5ad
bdc_$(1) = 						$(rna)/$(1)/binarization/pairwise_predecessor_scores.csv

endef

define condition_plus_integrated_dependant_paths

clustering_$(1) = 				$(rna)/$(1)/clustering/clusters/counts.h5ad
markers_$(1) = 					$(rna)/$(1)/clustering/markers/genes/background.txt
goea_basic_$(1) = 				$(rna)/$(1)/clustering/goea/goea_basic.xlsx
goea_mouse_$(1) = 				$(rna)/$(1)/clustering/goea/goea_mouse.xlsx
annotation_$(1) = 				$(rna)/$(1)/clustering/clusters/annotation.h5ad
stream_pseudotime_$(1) = 		$(rna)/$(1)/trajectories/stream/pseudotime/stream.h5ad.pkl
stream_trajectories_$(1) = 		$(rna)/$(1)/trajectories/stream/trajectories/branches.txt
bin_cells_$(1) = 				$(rna)/$(1)/binarization/cells/bin.h5ad
model_specification_$(1) = 		$(rna)/$(1)/bonesis/specification_model.txt
bonesis_filter1_$(1) = 			$(rna)/$(1)/bonesis/filtering/stage1/bootstrap_filter_grn_stage1.txt
bonesis_filter2_$(1) = 			$(rna)/$(1)/bonesis/filtering/stage2/bootstrap_filter_grn_stage2.txt
bonesis_inference_min_$(1) = 	$(rna)/$(1)/bonesis/inference/min/one-min.bnet
bonesis_inference_sub_$(1) = 	$(rna)/$(1)/bonesis/inference/sub/one-sub.bnet

ifeq ($(MACROSTATES_METHOD),cellrank)
macrostates_$(1) = 				$$(cellrank_$(1))
bin_macrostates_$(1) = 			$(rna)/$(1)/binarization/cellrank/bin_macrostates.csv
else ifeq ($(MACROSTATES_METHOD),center-extremity)
macrostates_$(1) = 				$$(center_extremity_$(1))
bin_macrostates_$(1) = 			$(rna)/$(1)/binarization/center_extremity/bin_macrostates.csv
else ifeq ($(MACROSTATES_METHOD),cotan)
macrostates_$(1) = 				$$(cotan_$(1))
bin_macrostates_$(1) = 			$(rna)/$(1)/binarization/cotan/bin_macrostates.csv
else
$$(error unsupported value for `MACROSTATES_METHOD` (supported values: cellrank, center-extremity or cotan))
endif

endef

$(foreach sample,$(conditions),$(eval $(call condition_dependant_paths,$(sample))))
$(foreach sample,$(conditions_plus_integrated),$(eval $(call condition_plus_integrated_dependant_paths,$(sample))))

NODES_COMPARISON_INTEGRATED = $(RNA_INTEGRATED)/bonesis/inference/min/nodes_intersection.txt

## END PATHS ##

## BEGIN TARGETS ##

fastq_target :=
cellranger_target :=
velocyto_target :=
h5ad_target :=
filtering_target :=
normalization_target :=
clustering_target :=
markers_target :=
goea_target :=
annotation_target :=
scvelo_velocity_target :=
macrostates_target :=
stream_pseudotime_target :=
stream_trajectories_target :=
cellrank_target :=
center_extremity_target :=
cotan_target :=
bin_cells_target :=
bin_macrostates_target :=
bdc_target :=
model_specification_target :=
bonesis_filter1_target :=
bonesis_filter2_target :=
bonesis_inference_min_target :=
bonesis_inference_sub_target :=

define dependant_targets

$(eval fastq_target := $(fastq_target) $(fastq_$(1)))
$(eval cellranger_target := $(cellranger_target) $(cellranger_$(1)))
$(eval velocyto_target := $(velocyto_target) $(velocyto_$(1)))
$(eval filtering_target := $(filtering_target) $(filtering_$(1)))
$(eval normalization_target := $(normalization_target) $(normalization_$(1)))
$(eval scvelo_velocity_target := $(scvelo_velocity_target) $(scvelo_$(1)))
$(eval cellrank_target := $(cellrank_target) $(cellrank_$(1)))
$(eval center_extremity_target := $(center_extremity_target) $(center_extremity_$(1)))
$(eval cotan_target := $(cotan_target) $(cotan_$(1)))
$(eval macrostates_target := $(macrostates_target) $(macrostates_$(1)))
$(eval bdc_target := $(bdc_target) $(bdc_$(1)))

endef

define dependant_targets_with_integration

$(eval clustering_target := $(clustering_target) $(clustering_$(1)))
$(eval markers_target := $(markers_target) $(markers_$(1)))
$(eval goea_target := $(goea_target) $(goea_basic_$(1)) $(goea_mouse_$(1)))
$(eval annotation_target := $(annotation_target) $(annotation_$(1)))
$(eval stream_pseudotime_target := $(stream_pseudotime_target) $(stream_pseudotime_$(1)))
$(eval stream_trajectories_target := $(stream_trajectories_target) $(stream_trajectories_$(1)))
$(eval bin_cells_target := $(bin_cells_target) $(bin_cells_$(1)))
$(eval bin_macrostates_target := $(bin_macrostates_target) $(bin_macrostates_$(1)))
$(eval model_specification_target := $(model_specification_target) $(model_specification_$(1)))
$(eval bonesis_filter1_target := $(bonesis_filter1_target) $(bonesis_filter1_$(1)))
$(eval bonesis_filter2_target := $(bonesis_filter2_target) $(bonesis_filter2_$(1)))
$(eval bonesis_inference_min_target := $(bonesis_inference_min_target) $(bonesis_inference_min_$(1)))
$(eval bonesis_inference_sub_target := $(bonesis_inference_sub_target) $(bonesis_inference_sub_$(1)))

endef

$(foreach sample,$(_samples_without_integration),$(eval $(call dependant_targets,$(sample))))
$(foreach sample,$(_samples),$(eval $(call dependant_targets_with_integration,$(sample))))

## END TARGETS ##

## BEGIN PARAMETERS ##

ifeq ($(EXTEND_LEAF_NODES),true)
EXTEND_LEAF_NODES:=--extend-leaf-nodes
else ifeq ($(EXTEND_LEAF_NODES),false)
EXTEND_LEAF_NODES:=
else
$(error EXTEND_LEAF_NODES not set to true or false)
endif

ifeq ($(PRUNE_GRAPH),true)
PRUNE_GRAPH:=--prune-graph
else ifeq ($(PRUNE_GRAPH),false)
PRUNE_GRAPH:=
else
$(error PRUNE_GRAPH not set to true or false)
endif

define stream_root
ifndef ROOT_$(call toupper,$(1))
ROOT_$(call toupper,$(1)):=0
endif
endef
$(foreach root,$(_samples),$(eval $(call stream_root,$(root))))

define stream_ignored_nodes
ifneq ($(IGNORED_NODES_$(call toupper,$(1))),)
IGNORED_NODES_$(call toupper,$(1)):=--ignore-nodes $(IGNORED_NODES_$(call toupper,$(1)))
endif
endef
$(foreach condition,$(_samples),$(eval $(call stream_ignored_nodes,$(condition))))

ifeq ($(EXCLUDE),true)
EXCLUDE:=--exclude
else ifeq ($(EXCLUDE),false)
EXCLUDE:=
else
$(error EXCLUDE not set to true or false)
endif

ifeq ($(BINARIZATION_ONLY_HVG),true)
BINARIZATION_ONLY_HVG:=--hvg
else
BINARIZATION_ONLY_HVG:=
endif

ifeq ($(ZEROES_ARE_ZEROES),true)
ZEROES_ARE_ZEROES:=--zeroes_are_zeroes
else
ZEROES_ARE_ZEROES:=
endif

ifeq ($(MINIMIZE_AUTO_LOOPS),true)
MINIMIZE_AUTO_LOOPS:=--minimize-auto-loops
else
MINIMIZE_AUTO_LOOPS:=
endif

## END PARAMETERS ##

## BEGIN HELP ##

##@ Help

.PHONY: help
help: ## display this help and exit
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make $(GREEN)<command>$(NC) [SAMPLES=<...>] (default:SAMPLES=$(subst $(space),$(plus),$(conditions_plus_integrated)))\n\
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
	rm -rf $(rna)
	find $(public)/genome ! -name "repeat_msk.gtf" -exec rm -rf "{}" \;
	mkdir $(rna)

##@ Download

load-genome: $(genome) ## download DNA primary assembly genome
load-annotations: $(transcriptome) ## download genome-related annotations
load-fastq: $(fastq_target) ## download fastq files
load-markers: $(cycle_markers) ## download cycle phase markers
load-signatures: $(lastword $(signatures)) ## download signatures and convert it into json file
load-go: $(go_basic) $(go_mouse) $(gene2go) ## download gene ontology-related files

##@ Alignment/Counting

.PHONY: cellranger
cellranger: $(cellranger_target) ## perform alignment and counting with CellRanger
.PHONY: velocyto
velocyto: $(velocyto_target) ## perform spliced/unspliced counting with velocyto

##@ Preprocessing

.PHONY: filtering
filtering: $(filtering_target) ## filtering low quality cells and assignment of cell cycle phases
.PHONY: normalization
normalization: $(normalization_target) ## filtering low quality genes and normalization of counts

##@ Clustering

.PHONY: clustering
clustering: $(clustering_target) ## perform dimension reduction and cell clustering (and optionally integration)
.PHONY: marker-analysis
marker-analysis: $(markers_target) ## search for gene markers and compare markers and signatures
.PHONY: goea
goea: $(goea_target) ## perform gene ontology enrichment analysis
.PHONY: annotation
annotation: $(annotation_target) ## annotate clusters

##@ Trajectory inference

.PHONY: scvelo
scvelo: $(scvelo_velocity_target) ## estimate rna velocity with scvelo
.PHONY: stream-pseudotime
stream-pseudotime: $(stream_pseudotime_target) ## compute elastic principal graph and pseudotime with stream
.PHONY: stream-trajectories
stream-trajectories: $(stream_trajectories_target) ## compute trajectories with stream

##@ Macrostate characterization

.PHONY: cellrank
cellrank: $(cellrank_target) ## estimate macrostates with cellrank
.PHONY: center-extremity
center-extremity: $(center_extremity_target) ## estimate macrostates with center-extremity method
.PHONY: cotan
cotan: $(cotan_target) ## estimate macrostates with cotan
.PHONY: macrostates
macrostates: $(macrostates_target) ## estimate macrostates depending on MACROSTATES_METHOD parameter

##@ Binarization

.PHONY: bin-cells
bin-cells: $(bin_cells_target) ## binarize cells with scBoolSeq
.PHONY: bin-macrostates
bin-macrostates: $(bin_macrostates_target) ## binarize macrostates w.r.t. voting rule
.PHONY: bdc
bdc: $(bdc_target) ## perform boolean differential calculus analysis

##@ Boolean network inference

model-specification: $(model_specification_target) ## specify model for bonesis
bonesis-filter-one: $(bonesis_filter1_target) ## filter genes with Bonesis (stage 1)
bonesis-filter-two: $(bonesis_filter2_target) ## filter genes with Bonesis (stage 2)
bonesis-inference-min: $(bonesis_inference_min_target) ## infer Boolean network with Bonesis (minimal solution)
bonesis-inference-sub: $(bonesis_inference_sub_target) ## infer Boolean network with Bonesis (subset minimal solution)

## END HELP ##

## BEGIN RULES ##

$(genome):
	$(call print_rule,load-genome)
	mkdir -p $(@D)
	wget --quiet --show-progress --directory-prefix=$(@D) $(genome_url)
	gunzip $@.gz

$(transcriptome):
	$(call print_rule,load-annotations)
	mkdir -p $(@D)
	wget --quiet --show-progress --directory-prefix=$(@D) $(transcriptome_url)
	tar -zxvf $@.tar.gz -C $(@D)
	gunzip $@/genes/genes.gtf.gz

$(cycle_markers):
	$(call print_rule,load-markers)
	mkdir -p $(@D)
	wget --quiet --show-progress -cO $@ $(cell_cycle_url)

$(word 1,$(signatures)) $(word 2,$(signatures)):
	$(eval FILENAME := $(basename $(notdir $@)))
	$(call print_rule,load-signatures,$(FILENAME))
	mkdir -p $(@D)
	if [ $(FILENAME) = "geiger" ]; then \
		wget --quiet --show-progress -cO $@ $(geiger_url); \
	else \
		wget --quiet --show-progress -cO $@ $(chambers_url); \
	fi

$(lastword $(signatures)): $(word 1,$(signatures)) $(word 2,$(signatures))
	$(call print_rule,load-signatures,conversion)
	$(conda_activate) preprocess
	python scripts/utils/load_signatures.py \
		--list-infile $(firstword $^) \
		--table-infile $(lastword $^) \
  		--outfile $@
	$(conda_deactivate)

$(go_basic):
	$(call print_rule,load-go,go-basic)
	mkdir -p $(@D)
	wget --quiet --show-progress -cO $@ $(go_basic_url)

$(go_mouse):
	$(call print_rule,load-go,go-mouse)
	mkdir -p $(@D)
	wget --quiet --show-progress -cO $@ $(go_mouse_url)

$(gene2go):
	$(call print_rule,load-go,gene2go)
	mkdir -p $(@D)
	wget --quiet --show-progress --directory-prefix=$(@D) $(gene2go_url)
	gunzip $@.gz

define condition_dependant_rules

$(fastq_$(1)):
	$(call print_rule,load-fastq,$(1))
	$$(conda_activate) fastq-dump
	sample_naming="$(1)"
	lane=0
	tmp_directory=tmp/fastq-$(1)
	rm -rf $$$${tmp_directory} && mkdir $$$${tmp_directory}
	for id in $$(SRA_$(call toupper, $(1)))
	do
		let "lane++"
		parallel-fastq-dump --sra-id $$$${id} --split-files --readids --origfmt --threads $$(JOBS) --outdir $$$${tmp_directory} --gzip
		$$(call fastq_naming,$$$${tmp_directory},$$$${id},$$$${sample_naming},$$$${lane})
	done
	sleep 3
	mkdir -p $$(@)
	mv $$$${tmp_directory}/* $$(@)/
	files=$$$$(shopt -s nullglob dotglob; echo $$$${tmp_directory}/*)
	if ! (( $$$${#files} ))
	then
		rm -rf $$$${tmp_directory}
	else
		$(call print_error,fastq-dump failure)
	fi
	unset tmp_directory
	unset files
	$$(conda_deactivate)

$(cellranger_$(1)): $(fastq_$(1)) $(transcriptome)
	$(call print_rule,cellranger,$(1))
	mkdir -p $$(@D)
	cellranger count --id=$(1) \
		--fastqs=$$(firstword $$^) \
   		--transcriptome=$$(lastword $$^) \
   		--create-bam true \
   		--localcores=$(JOBS) \
   		--localmem=$(MEMORY)
	mv $(1)/* $$(@D)
	rm -rf $(1)

$(velocyto_$(1)): $(cellranger_$(1)) $(transcriptome)
	$(call print_rule,velocyto,$(1))
	$$(conda_activate) velocyto
	velocyto run10x -m data/public/genome/repeat_msk.gtf \
		--samtools-threads $(JOBS) --samtools-memory $(MEMORY) \
		$$(dir $$(firstword $$^)) $$(lastword $$^)/genes/genes.gtf
	$$(conda_deactivate)
	mkdir -p $$(@D)
	mv $$(<D)/velocyto/cellranger.loom $$(shell echo $$(@) | sed "s/h5ad/loom/")
	rm -rf $$(<D)/velocyto
	$$(conda_activate) preprocess
	python scripts/utils/adata_conversion.py $$(shell echo $$(@) | sed "s/h5ad/loom/") $$(@) --from loom --to h5ad \
		--metadata $$(METADATA_$(call toupper,$(1))) \
		--remove-positions \
		--genename-standardization
	$$(conda_deactivate)

$(filtering_$(1)): $(velocyto_$(1)) $(cycle_markers)
	$(call print_rule,filtering,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	python scripts/preprocessing/filtering.py \
		--infile $$(firstword $$^) \
		--marker $$(lastword $$^) \
		--outpath $$(@D) \
		--mitochondrial_threshold 5 \
		--upper-mad 2 \
		--lower-mad 3 \
		--consistency-mad
	$$(conda_deactivate)

$(normalization_$(1)): $(filtering_$(1))
	$(call print_rule,normalization,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	python scripts/preprocessing/normalization.py $$< $$(@) \
		--correction G2M_score S_score G1_score \
		--min-cell-expression-proportion 0.001 \
		--jobs $(JOBS)
	$$(conda_deactivate)

$(clustering_$(1)): $(normalization_$(1))
	$(call print_rule,clustering,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	python scripts/clustering/leiden_clustering.py $$< $$(@D) \
		--layer correct --hvg \
		--metric euclidean --k-neighbors $(K_NEIGHBORS) --resolution $(RESOLUTION) \
		--dim-pca $(DIM_PCA) --dim-clustering $(DIM_CLUSTERING) --dim-umap $(DIM_UMAP) \
		--add-legend --plot-3d \
		--seed $(SEED)
	$$(conda_deactivate)

ifeq ($(LABELING_FROM_INTEGRATION),true)
$(annotation_$(1)): $(annotation_integrated) $(clustering_$(1))
	$(call print_rule,annotation,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	python scripts/utils/pipe_its.py $$^ --outfiles $$@ --column leiden --condition condition
	$(call print_task,embedding component plotting)
	python fig/plot_embedding.py fig/umap_labels.json \
		--infile $$@ --outfile $$(@D)/umap_labels
	$$(conda_deactivate)
else
ifdef CLUSTER_LABEL_$(call toupper,$(1))
$(annotation_$(1)): $(clustering_$(1))
	$(call print_rule,annotation,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	python scripts/clustering/annotation.py $$< $$@ \
		--column leiden \
		--name $$(CLUSTER_LABEL_$(call toupper,$(1)))
	$(call print_task,embedding component plotting)
	python fig/plot_embedding.py fig/umap_labels.json \
		--infile $$@ --outfile $$(@D)/umap_labels
	$$(conda_deactivate)
else
$(annotation_$(1)): $(clustering_$(1))
	$(call print_rule,annotation,$(1))
	$(call print_error,LABELING_FROM_INTEGRATION set to false and CLUSTER_LABEL_$(call toupper,$(1)) not defined)
	exit 1
endif
endif

$(scvelo_$(1)): $(annotation_$(1))
	$(call print_rule,scvelo,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) scvelo
	python scripts/trajectories/scvelo_velocity.py $$< $$(@D) \
		--cluster leiden \
		--k-neighbors $(K_NEIGHBORS) \
		--dim-clustering $(DIM_CLUSTERING) \
		--mode $(SMM_MODE) \
		--add-legend
	$$(conda_deactivate)

ifndef INITIAL_STATES_$(call toupper,$(1))
$(cellrank_$(1)): $(scvelo_$(1))
	$(call print_error,INITIAL_STATES_$(call toupper,$(1)) not defined)
else ifndef TERMINAL_STATES_$(call toupper,$(1))
$(cellrank_$(1)): $(scvelo_$(1))
	$(call print_error,TERMINAL_STATES_$(call toupper,$(1)) not defined)
else
$(cellrank_$(1)): $(scvelo_$(1))
	$(call print_rule,cellrank,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) cellrank
	python scripts/macrostates/cellrank_macrostates.py $$< $$@ \
		--macrostate-size $(MACROSTATE_SIZE) \
		--initial-states $(INITIAL_STATES_$(call toupper,$(1))) \
		--terminal-states $(TERMINAL_STATES_$(call toupper,$(1))) \
		--method $(CELLRANK_METHOD) \
		--plot-3d
	$$(conda_deactivate)
endif

ifeq ($(or $(CENTER_$(call toupper,$(1))),$(EXTREMITY_$(call toupper,$(1)))),)
$(center_extremity_$(1)): $(scvelo_$(1))
	$(call print_error,CENTER_$(call toupper,$(1)) and EXTREMITY_$(call toupper,$(1)) not defined \(at least one must be defined\))
else
$(center_extremity_$(1)): $(scvelo_$(1))
	$(call print_rule,center-extremity,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	python scripts/macrostates/scbridge_macrostates.py $$< $$@ \
		--obs leiden --obsm X_umap --dimension $(DIM_UMAP) --macrostate-size $(MACROSTATE_SIZE) \
		--center $(CENTER_$(call toupper,$(1))) --extremity $(EXTREMITY_$(call toupper,$(1))) $(EXCLUDE) \
		--plot-3d
	$$(conda_deactivate)
endif

$(cotan_$(1)): $(scvelo_$(1))
	$(call print_rule,cotan,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	$(call print_task,h5ad to csv format conversion)
	python scripts/utils/adata_conversion.py $$< $$(@D)/.tmp.csv --from h5ad --to csv --layer matrix
	ruby -rcsv -e 'puts CSV.parse(STDIN).transpose.map &:to_csv' < $$(@D)/.tmp.csv > $$(@D)/counts.csv
	rm $$(@D)/.tmp.csv
	$$(conda_deactivate)
	$$(conda_activate) cotan
	Rscript scripts/macrostates/cotan_clustering.R --infile $$(@D)/counts.csv --outpath $$(@D) --sep , \
		--condition $(1) \
		--max-iterations 25 \
		--method strong-merging \
		--jobs $(JOBS)
	$$(conda_deactivate)
	sed -i '1 i\,macrostates' $$(@D)/clusters.csv
	$$(conda_activate) preprocess
	python scripts/utils/add_to_adata.py $$< $$@ --obs $$(@D)/clusters.csv --obs-type str --sep ,
	$(call print_task,embedding component plotting)
	python fig/plot_embedding.py fig/macrostates.json --infile $$@ --outfile $$(@D)/cotan_clusters
	$$(conda_deactivate)

$(bin_cells_$(1)): $(macrostates_$(1))
	$(call print_rule,bin-cells,$(1))
	$$(conda_activate) scboolseq
	python scripts/binarization/bin_cells.py $$< -o $$(@D) \
		--cluster leiden --exclude nan --layer log-normalize $(BINARIZATION_ONLY_HVG) $(ZEROES_ARE_ZEROES)
	$$(conda_deactivate)

$(bin_macrostates_$(1)): $(bin_cells_$(1))
	$(call print_rule,bin-macrostates,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	python scripts/binarization/bin_clusters.py $$< $$(@D) \
		--cluster macrostates --plot-3d
	$$(conda_deactivate)

endef

define condition_plus_integrated_dependant_rules

$(markers_$(1)): $(clustering_$(1)) $(lastword $(signatures))
	$$(eval markers_csv := $$(dir $$(@D))markers.csv)
	$(call print_rule,marker-analysis,$(1))
	$$(conda_activate) preprocess
	python scripts/clustering/markers.py $$(^) $$(dir $$(markers_csv)) \
  		--cluster leiden \
  		--logfc-threshold 0.25 \
  		--verbose
	$(call print_task, background genes computation)
	python scripts/utils/get_genes.py $$(<) $$(@)
	export clusters=`column -s, -t < $$(markers_csv) | awk 'NR>1 {print $$$$2}' | sort -u | tr '\n' ' '`
	$(call print_task, upregulated cluster-related genes computation)
	for cluster in $$$${clusters}
	do
		`column -s, -t < $$(markers_csv) | awk -v c=$$$${cluster} '$$$$2==c {print $$$$1}' > $$(@D)/cluster$$$${cluster}.txt`
		python scripts/utils/genename_standardization.py $$(@D)/cluster$$$${cluster}.txt $$(@D)/cluster$$$${cluster}.txt --quiet
	done
	unset clusters
	$$(conda_deactivate)

$(goea_basic_$(1)): $(markers_$(1)) $(go_basic) $(gene2go)
	$(call print_rule,goea,$(1) with go-basic)
	$$(conda_activate) preprocess
	python scripts/clustering/enrichment.py $$(@) \
    	--population $$(<) \
    	--study $$(<D)/cluster*.txt \
    	--go $$(word 2,$$^) \
    	--gene2go $$(lastword $$^)
	$$(conda_deactivate)

$(goea_mouse_$(1)): $(markers_$(1)) $(go_mouse) $(gene2go)
	$(call print_rule,goea,$(1) with go-mouse)
	$$(conda_activate) preprocess
	python scripts/clustering/enrichment.py $$(@) \
    	--population $$(<) \
    	--study $$(<D)/cluster*.txt \
    	--go $$(word 2,$$^) \
    	--gene2go $$(lastword $$^)
	$$(conda_deactivate)

$(stream_pseudotime_$(1)): $(annotation_$(1))
	$(call print_rule,stream-pseudotime,$(1))
	$$(conda_activate) stream
	python scripts/trajectories/stream_pseudotime.py $$< $$(@D) \
		--extension both --cluster-number $(CLUSTER_NUMBER) --groups leiden \
		--lambda $(LAMBDA) --mu $(MU) --alpha $(ALPHA) \
		$(EXTEND_LEAF_NODES) --extend-mode WeigthedCentroid --extend-parameter $(EXTEND) $(PRUNE_GRAPH) \
		--add-legend --add-graph --jobs $(JOBS)
	$$(conda_deactivate)

$(stream_trajectories_$(1)): $(stream_pseudotime_$(1))
	$(call print_rule,stream-trajectories,$(1))
	$(call print_warning,root can be modified using ROOT_$(call toupper,$(1)) \(current value: $(ROOT_$(call toupper, $(1)))\))
	$$(conda_activate) stream
	python scripts/trajectories/stream_trajectories.py $$< $$(@D) --root $(ROOT_$(call toupper, $(1))) \
		--groups leiden kmeans macrostates \
		--add-legend --add-graph $(IGNORED_NODES_$(call toupper, $(1)))
	$$(conda_deactivate)

endef

$(clustering_integrated): $(foreach condition,$(conditions),$(normalization_$(condition)))
	$(call print_rule,clustering,integrated)
	mkdir -p $(@D)
	$(conda_activate) preprocess
	python scripts/clustering/integration.py $^ --outfile $@ \
		--labels $(conditions) --method $(INTEGRATION_METHOD) --layer correct \
		--hvg $(HVG) --metric euclidean --k-neighbors $(K_NEIGHBORS) --resolution $(RESOLUTION) \
		--dim-pca $(DIM_PCA) --dim-clustering $(DIM_CLUSTERING) --dim-umap $(DIM_UMAP) \
		--add-legend --plot-3d \
		--seed $(SEED) --jobs $(JOBS)
	$(conda_deactivate)

ifdef CLUSTER_LABEL_INTEGRATED
$(annotation_integrated): $(clustering_integrated)
	$(call print_rule,annotation,integrated)
	$(conda_activate) preprocess
	python scripts/clustering/annotation.py $< $@ \
		--column leiden \
		--name $(CLUSTER_LABEL_INTEGRATED)
	$(call print_task,embedding component plotting)
	python fig/plot_embedding.py fig/umap_labels.json \
		--infile $@ --outfile $(@D)/umap_labels
	$(conda_deactivate)
else
$(annotation_integrated): $(clustering_integrated)
	$(call print_rule,annotation,integrated)
	$(call print_error,CLUSTER_LABEL_INTEGRATED not defined)
endif

ifeq ($(INTEGRATED_BINARIZATION),split)
$(bin_cells_integrated): $(foreach condition,$(conditions),$(bin_cell_$(condition)))
	$(call print_rule,bin-cells,integrated)
	$(call print_info,perform binarization using conditions independently)
	$(conda_activate) preprocess
	python scripts/utils/csv_concatenation.py $^ -o $@ --suffixes $(addprefix _,$(conditions))
	$(conda_deactivate)
else ifeq ($(INTEGRATED_BINARIZATION),merged)
$(bin_cells_integrated): $(annotation_integrated) $(foreach condition,$(conditions),$(macrostates_$(condition)))
	$(call print_rule,bin-cells,integrated)
	$(call print_info,perform binarization using conditions jointly)
	$(conda_activate) scboolseq
	python scripts/binarization/bin_cells.py $(filter-out $(annotation_integrated),$^) -o $(dir $@) \
		--cluster leiden --conditions $(conditions) --exclude nan --layer log-normalize $(BINARIZATION_ONLY_HVG) $(ZEROES_ARE_ZEROES)
	$(conda_deactivate)
	mv $@ $(@D)/tmp.h5ad
	$(conda_activate) preprocess
	python scripts/utils/transfer_info.py $< $(@D)/tmp.h5ad --outfile $@ --obs pct_bin --var distribution --layer bin --index condition
	$(conda_deactivate)
	rm $(@D)/tmp.h5ad


















else
$(bin_cells_integrated): $(foreach condition,$(conditions),$(bin_cell_$(condition))) $(foreach condition,$(conditions),$(scvelo_$(condition)))
	$(call print_rule,bin-cells,integrated)
	$(call print_error,unsupported value for `INTEGRATED_BINARIZATION` \(supported values: split or merged\))
endif

$(bin_macrostates_integrated): $(bin_cells_integrated) $(foreach condition,$(conditions),$(macrostates_$(condition)))
	$(call print_rule,bin-macrostates,integrated)
	mkdir -p $(@D)
	$(conda_activate) preprocess
	$(call print_info,all-to-one information transfer)
	python scripts/utils/pipe_sti.py $^ --conditions $(conditions) --outfile $(@D)/tmp.h5ad --column macrostates --condition-column condition
	$(call print_info,macrostate binarization)
	python scripts/binarization/bin_clusters.py $(@D)/tmp.h5ad $(@D) \
		--condition condition --cluster macrostates --plot-3d
	$(conda_deactivate)

$(foreach condition,$(conditions),$(eval $(call condition_dependant_rules,$(condition))))
$(foreach condition,$(conditions_plus_integrated),$(eval $(call condition_plus_integrated_dependant_rules,$(condition))))

$(BDC_CTRL): $(bin_cell_ctrl)
	$(call print_rule,Boolean differential calculus (control data))
	$(conda_activate) scboolseq
	python scripts/binarization/differential_analysis.py $< $(@D) --verbose
	$(conda_deactivate)

$(BDC_TREATED): $(bin_cell_treated)
	$(call print_rule,Boolean differential calculus (treated data))
	$(conda_activate) scboolseq
	python scripts/binarization/differential_analysis.py $< $(@D) --verbose
	$(conda_deactivate)

$(MODEL_SPECIFICATION_CTRL): $(TRAJECTORIES_MACROSTATES_CTRL)
	$(call print_rule,model-specification (control data))
	mkdir -p $(@D)
	python3 pipeline/inference/bonesis_specification.py $< > $@

$(MODEL_SPECIFICATION_TREATED): $(TRAJECTORIES_MACROSTATES_TREATED)
	$(call print_rule,model-specification (treated data))
	mkdir -p $(@D)
	python3 pipeline/inference/bonesis_specification.py $< > $@

$(model_specification_integrated): $(TRAJECTORIES_MACROSTATES_CTRL) $(TRAJECTORIES_MACROSTATES_TREATED)
	$(call print_rule,model-specification (integrated data))
	mkdir -p $(@D)
	python3 pipeline/inference/bonesis_specification.py $^ --conditions $(conditions) > $@

$(BONESIS_FILTER1_CTRL): $(MODEL_SPECIFICATION_CTRL) $(bin_cell_ctrl)
	$(call print_rule,Bonesis filtering (control data, stage 1))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python scripts/inference/bonesis_inference.py filter-stage1 $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(lastword $^) \
		> $@
	$(conda_deactivate)

$(BONESIS_FILTER1_TREATED): $(MODEL_SPECIFICATION_TREATED) $(bin_cell_treated)
	$(call print_rule,Bonesis filtering (treated data, stage 1))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python scripts/inference/bonesis_inference.py filter-stage1 $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(lastword $^) \
		> $@
	$(conda_deactivate)

$(BONESIS_FILTER1_INTEGRATED): $(model_specification_integrated) $(bin_cells_integrated)
	$(call print_rule,Bonesis filtering (integrated data, stage 1))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python scripts/inference/bonesis_inference.py filter-stage1 $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(lastword $^) \
		> $@
	$(conda_deactivate)

$(BONESIS_FILTER2_CTRL): $(MODEL_SPECIFICATION_CTRL) $(bin_cell_ctrl) $(BONESIS_FILTER1_CTRL) 
	$(call print_rule,Bonesis filtering (control data, stage 2))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python scripts/inference/bonesis_inference.py filter-stage2 $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^) \
		$(MINIMIZE_AUTO_LOOPS) > $@
	$(conda_deactivate)

$(BONESIS_FILTER2_TREATED): $(MODEL_SPECIFICATION_TREATED) $(bin_cell_treated) $(BONESIS_FILTER1_TREATED) 
	$(call print_rule,Bonesis filtering (treated data, stage 2))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python scripts/inference/bonesis_inference.py filter-stage2 $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^) \
		$(MINIMIZE_AUTO_LOOPS) > $@
	$(conda_deactivate)

$(BONESIS_FILTER2_INTEGRATED): $(model_specification_integrated) $(bin_cells_integrated) $(BONESIS_FILTER1_INTEGRATED) 
	$(call print_rule,Bonesis filtering (integrated data, stage 2))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python scripts/inference/bonesis_inference.py filter-stage2 $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^) \
		$(MINIMIZE_AUTO_LOOPS) > $@
	$(conda_deactivate)

$(BONESIS_INFERENCE_MIN_CTRL): $(MODEL_SPECIFICATION_CTRL) $(bin_cell_ctrl) $(BONESIS_FILTER2_CTRL)
	$(call print_rule,Bonesis inference (control data, minimal solution))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python scripts/inference/bonesis_inference.py one-min $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^) \
		$(MINIMIZE_AUTO_LOOPS)
	$(conda_deactivate)
	dot -Tpdf $(@D)/one-min.dot > $(@D)/one-min.pdf

$(BONESIS_INFERENCE_MIN_TREATED): $(MODEL_SPECIFICATION_TREATED) $(bin_cell_treated) $(BONESIS_FILTER2_TREATED)
	$(call print_rule,Bonesis inference (treated data, minimal solution))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python scripts/inference/bonesis_inference.py one-min $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^) \
		$(MINIMIZE_AUTO_LOOPS)
	$(conda_deactivate)
	dot -Tpdf $(@D)/one-min.dot > $(@D)/one-min.pdf

$(BONESIS_INFERENCE_MIN_INTEGRATED): $(model_specification_integrated) $(bin_cells_integrated) $(BONESIS_FILTER2_INTEGRATED)
	$(call print_rule,Bonesis inference (integrated data, minimal solution))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python scripts/inference/bonesis_inference.py one-min $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^) \
		$(MINIMIZE_AUTO_LOOPS)
	$(conda_deactivate)
	dot -Tpdf $(@D)/one-min.dot > $(@D)/one-min.pdf

$(BONESIS_INFERENCE_SUB_CTRL): $(MODEL_SPECIFICATION_CTRL) $(bin_cell_ctrl) $(BONESIS_FILTER2_CTRL)
	$(call print_rule,Bonesis inference (control data, subset minimal solution))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python scripts/inference/bonesis_inference.py one-sub $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^)
	$(conda_deactivate)
	dot -Tpdf $(@D)/one-sub.dot > $(@D)/one-sub.pdf

$(BONESIS_INFERENCE_SUB_TREATED): $(MODEL_SPECIFICATION_TREATED) $(bin_cell_treated) $(BONESIS_FILTER2_TREATED)
	$(call print_rule,Bonesis inference (treated data, subset minimal solution))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python scripts/inference/bonesis_inference.py one-sub $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^)
	$(conda_deactivate)
	dot -Tpdf $(@D)/one-sub.dot > $(@D)/one-sub.pdf

$(BONESIS_INFERENCE_SUB_INTEGRATED): $(model_specification_integrated) $(bin_cells_integrated) $(BONESIS_FILTER2_INTEGRATED)
	$(call print_rule,Bonesis inference (integrated data, subset minimal solution))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python scripts/inference/bonesis_inference.py one-sub $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^)
	$(conda_deactivate)
	dot -Tpdf $(@D)/one-sub.dot > $(@D)/one-sub.pdf

## END RULES