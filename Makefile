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
REFERENCES := $(subst $(space),$(plus),$(conditions_plus_integrated))
_samples := $(subst $(plus),$(space),$(REFERENCES))
_samples_without_integration := $(subst $(space)integrated,,$(_samples))

## BEGIN URLS ##

cell_cycle_url = https://github.com/MarioniLab/scran/raw/master/inst/exdata/mouse_cycle_markers.rds
geiger_url = https://doi.org/10.1371/journal.pbio.2003389.s025
chambers_url = https://ars.els-cdn.com/content/image/1-s2.0-S1934590907002202-mmc3.xls
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
	$(if $2,@echo `date "+%Y-%m-%d %H:%M:%S.%3N"` - RULE - $(1) \(reference: $(2)\),@echo `date "+%Y-%m-%d %H:%M:%S.%3N"` - RULE - $(1))
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

define print_debug
	@echo `date "+%Y-%m-%d %H:%M:%S.%3N"` - DEBUG - $(1)
endef

define print_error
	@echo `date "+%Y-%m-%d %H:%M:%S.%3N"` - ERROR - $(1)
	exit 1
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

cc_markers = $(public)/cycle_phases/mouse_cycle_markers.rds
signatures = $(public)/signatures/geiger.xls $(public)/signatures/chambers.xls $(public)/signatures/signatures.json
go_basic = $(public)/enrichment/go-basic.obo
go_mouse = $(public)/enrichment/goslim.obo
gene2go = $(public)/enrichment/gene2go

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
deseq_$(1) = 					$(rna)/$(1)/clustering/deseq/markers.csv $(rna)/$(1)/clustering/deseq/genes.xlsx
scoring_$(1) = 					$(rna)/$(1)/clustering/scoring/phenotypes.csv
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
deseq_target :=
scoring_target :=
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
$(eval deseq_target := $(deseq_target) $(deseq_$(1)))
$(eval scoring_target := $(scoring_target) $(scoring_$(1)))
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

ifndef NORM_MAD
$(error Parameter NORM_MAD not defined)
else ifeq ($(NORM_MAD),true)
norm_mad=--consistent-mad
else ifeq ($(NORM_MAD),false)
norm_mad=
else
$(error Unsupported value for parameter NORM_MAD (supported values: true, false))
endif

ifndef FILTER_NON_HVG
$(error Parameter FILTER_NON_HVG not defined)
else ifeq ($(FILTER_NON_HVG),true)
filter_non_hvg=--filter-non-hvg
else ifeq ($(FILTER_NON_HVG),false)
filter_non_hvg=
else
$(error Unsupported value for parameter FILTER_NON_HVG (supported values: true, false))
endif

ifndef CC_CORRECTION
$(error Parameter CC_CORRECTION not defined)
else ifeq ($(CC_CORRECTION),true)
correction=--correction G2M_score S_score G1_score
else ifeq ($(CC_CORRECTION),false)
correction=
else
$(error Unsupported value for parameter CC_CORRECTION (supported values: true, false))
endif

ifndef PCA_ONLY_HVG
$(error Parameter PCA_ONLY_HVG not defined)
else ifeq ($(PCA_ONLY_HVG),true)
pca_only_hvg=--hvg
else ifeq ($(PCA_ONLY_HVG),false)
pca_only_hvg=
else
$(error Unsupported value for parameter PCA_ONLY_HVG (supported values: true, false))
endif

ifndef VELOCITY_ONLY_HVG
$(error Parameter VELOCITY_ONLY_HVG not defined)
else ifeq ($(VELOCITY_ONLY_HVG),true)
velocity_only_hvg=--hvg
else ifeq ($(VELOCITY_ONLY_HVG),false)
velocity_only_hvg=
else
$(error Unsupported value for parameter VELOCITY_ONLY_HVG (supported values: true, false))
endif

ifndef EXTEND_EPG
$(error Parameter EXTEND_EPG not defined)
else ifeq ($(EXTEND_EPG),true)
extend_epg:=--extend-epg
else ifeq ($(EXTEND_EPG),false)
extend_epg:=
else
$(error Unsupported value for parameter EXTEND_EPG (supported values: true, false))
endif

ifndef PRUNE_EPG
$(error Parameter PRUNE_EPG not defined)
else ifeq ($(PRUNE_EPG),true)
prune_epg:=--prune-epg
else ifeq ($(PRUNE_EPG),false)
prune_epg:=
else
$(error Unsupported value for parameter PRUNE_EPG (supported values: true, false))
endif

ifndef BIN_ONLY_HVG
$(error Parameter BIN_ONLY_HVG not defined)
else ifeq ($(BIN_ONLY_HVG),true)
bin_only_hvg=--hvg
else ifeq ($(BIN_ONLY_HVG),false)
bin_only_hvg=
else
$(error Unsupported value for parameter BIN_ONLY_HVG (supported values: true, false))
endif

ifndef ZEROES_ARE_ZEROES
$(error Parameter ZEROES_ARE_ZEROES not defined)
else ifeq ($(ZEROES_ARE_ZEROES),true)
zeroes_are_zeroes:=--zeroes-are-zeroes
else ifeq ($(ZEROES_ARE_ZEROES),false)
zeroes_are_zeroes:=
else
$(error Unsupported value for parameter ZEROES_ARE_ZEROES (supported values: true, false))
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
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make $(GREEN)<command>$(NC) [REFERENCES=<...>] (default:REFERENCES=$(subst $(space),$(plus),$(conditions_plus_integrated)))\n\
	Semi-automatic pipeline proposing a general methodology for inferring executable models reproducing \
	the observed cellular dynamics from multiples conditions/experiments, using scRNA-seq sequencing data. \
	The pipeline is particularly useful when phenotype-related cells are not well characterized \
	and when studying almost differentiated cells, where biological process are difficult to determine. \
	Samples can be integrated at the clustering step, in order to annotate cell clusters in control and treated dependently.\n"}/^[a-zA-Z_-]+:.*?##/ \
	{ printf "  $(GREEN)%-22s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(BOLD)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Clean

.PHONY: clean
clean: ## clear cache
	find . -name "\*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf "{}" \;
	find . -type d -name "cache" -exec rm -rf "{}" \;

.PHONY: mrproper
mrproper: ## clear cache and public/private data
	find . -name "\*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf "{}" \;
	find . -type d -name "cache" -exec rm -rf "{}" \;
	rm -rf $(rna)
	mkdir $(rna)
	find $(public)/transcriptome ! -name "repeat_msk.gtf" -type f -exec rm -f "{}" \;

##@ Download

load-annotations: $(transcriptome) ## download transcriptome-related annotations
load-fastq: $(fastq_target) ## download fastq files
load-signatures: $(lastword $(signatures)) ## download signatures and convert it into json file
load-cc: $(cc_markers) ## download cell cycle phase markers
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
.PHONY: deseq
deseq: $(deseq_target) ## search for markers (differentially expressed genes) between clusters
.PHONY: scoring
scoring: $(scoring_target) ## score signature-related phenotypes with respect to cell clusters
.PHONY: goea
goea: $(goea_target) ## perform gene ontology enrichment analysis
.PHONY: annotation
annotation: $(annotation_target) ## assign names to cell clusters

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

$(transcriptome):
	$(call print_rule,load-annotations)
	mkdir -p $(@D)
	wget --quiet --show-progress --directory-prefix=$(@D) $(transcriptome_url)
	tar -zxvf $@.tar.gz -C $(@D)
	gunzip $@/genes/genes.gtf.gz

$(cc_markers):
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
	$(call print_rule,load-go \(go-basic\))
	mkdir -p $(@D)
	wget --quiet --show-progress -cO $@ $(go_basic_url)

$(go_mouse):
	$(call print_rule,load-go \(go-mouse\))
	mkdir -p $(@D)
	wget --quiet --show-progress -cO $@ $(go_mouse_url)

$(gene2go):
	$(call print_rule,load-go \(gene2go\))
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
		$(call print_error,cannot download fastq files: fastq-dump failed)
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
	if [ -f data/public/transcriptome/repeat_msk.gtf ]; then
		$$(conda_activate) velocyto
		velocyto run10x -m data/public/transcriptome/repeat_msk.gtf \
			--samtools-threads $(JOBS) --samtools-memory $(MEMORY) \
			$$(dir $$(firstword $$^)) $$(lastword $$^)/genes/genes.gtf
		$$(conda_deactivate)
		mkdir -p $$(@D)
		mv $$(<D)/velocyto/cellranger.loom $$(shell echo $$@ | sed "s/h5ad/loom/")
		rm -rf $$(<D)/velocyto
		$$(conda_activate) preprocess
		$(call print_debug,converting $$(shell echo $$@ | sed "s/h5ad/loom/") into $$@ and standardizing gene names)
		python scripts/utils/adata_conversion.py $$(shell echo $$@ | sed "s/h5ad/loom/") $$@ --from loom --to h5ad \
			--remove-positions \
			--genename-standardization
		$$(conda_deactivate)
	else
		$(call print_error,cannot run velocyto: file data/public/transcriptome/repeat_msk.gtf does not exist \(please refer to documentation for downloading it\))
	fi

$(filtering_$(1)): $(velocyto_$(1)) $(cc_markers)
	$(call print_rule,filtering,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	python scripts/preprocessing/filtering.py $$(firstword $$^) $$@ --marker $$(lastword $$^) \
		--gene-dropout $(GENE_DROPOUT) --gene-expression $(GENE_EXPRESSION) --gene-counts $(GENE_COUNTS) \
		--cell-dropout $(CELL_DROPOUT) --cell-expression $(CELL_EXPRESSION) --cell-reads $(CELL_READS) \
		--mad $(MAD_DEVIATION) $(norm_mad) --mt $(MT) \
		--hvg $(HVG) $(filter_non_hvg)
	$$(conda_deactivate)

$(normalization_$(1)): $(filtering_$(1))
	$(call print_rule,normalization,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	python scripts/preprocessing/normalization.py $$< $$(@) $(correction) --jobs $(JOBS)
	$$(conda_deactivate)

$(clustering_$(1)): $(normalization_$(1))
	$(call print_rule,clustering,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	python scripts/clustering/clustering.py $$< $$@ \
		--layer correct --adjacency knn --embedding umap \
		--pca-dimension $(DIM_PCA) --clustering-dimension $(DIM_CLUSTERING) --embedding-dimension $(DIM_EMBEDDING) \
		$(pca_only_hvg) --neighbors $(NEIGHBORS) --metric $(METRIC) --resolution $(RESOLUTION) --min-dist $(MIN_DIST) --spread $(SPREAD) --seed $(SEED)
	$(call print_task,plotting umap with respect to cell cycle phases)
	python fig/plot_embedding.py fig/cc_umap.json --infile $$@ --outfile $$(@D)/cc_umap.pdf 
	$$(conda_deactivate)

ifeq ($(LABELING_FROM_INTEGRATION),true)
$(annotation_$(1)): $(annotation_integrated) $(clustering_$(1))
	$(call print_rule,annotation,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	python scripts/utils/pipe_its.py $$^ --outfiles $$@ --labels $(1) --obs-label condition --obs leiden
	$(call print_task,plotting umap with respect to annotated clusters)
	python fig/plot_embedding.py fig/leiden_umap.json --infile $$@ --outfile $$(@D)/umap_annotation.pdf
	$$(conda_deactivate)
else
ifdef LABEL_$(call toupper,$(1))
$(annotation_$(1)): $(clustering_$(1))
	$(call print_rule,annotation,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	python scripts/clustering/annotation.py $< $@ \
		--obs leiden --labels $(join $(shell seq 0 1 $$(( $(words $$(LABEL_$(call toupper,$(1))))-1 ))),$(addprefix :,$(LABEL_INTEGRATED)))
	$(call print_task,embedding component plotting)
	python fig/plot_embedding.py fig/umap_labels.json \
		--infile $$@ --outfile $$(@D)/umap_labels.pdf
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
	python scripts/trajectories/velocity.py $$< $$@ \
		--layer counts --cluster leiden --moment-dimension $(DIM_MOMENT) \
		$(velocity_only_hvg) --mode $(SMM_MODE) --embedding umap --jobs $(JOBS)
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

$(cotan_$(1)): $(annotation_$(1))
	$(call print_rule,cotan,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	tmp_file=$$(@D)/tmp.csv
	$(call print_debug,converting $$< into $$$${tmp_file})
	python scripts/utils/adata_conversion.py $$< $$$${tmp_file} --from h5ad --to csv --layer matrix
	$(call print_debug,transposing $$$${tmp_file} and saving results in $$(@D)/counts.csv)
	ruby -rcsv -e 'puts CSV.parse(STDIN).transpose.map &:to_csv' < $$$${tmp_file} > $$(@D)/counts.csv
	rm $$$${tmp_file}
	unset tmp_file
	$$(conda_deactivate)
	$$(conda_activate) cotan
	Rscript scripts/macrostates/cotan_clustering.R --infile $$(@D)/counts.csv --outpath $$(@D) --sep , \
		--condition $(1) --max-iterations 25 --method strong-merging --jobs $(JOBS)
	$$(conda_deactivate)
	sed -i '1 i\,macrostates' $$(@D)/clusters.csv
	$$(conda_activate) preprocess
	$(call print_debug,adding cotan clusters to anndata object)
	python scripts/utils/add_to_adata.py $$< $$@ --obs $$(@D)/clusters.csv --obs-type str --sep ,
	$(call print_task,plotting umap with respect to cotan clusters)
	python fig/plot_embedding.py fig/macrostates.json --infile $$@ --outfile $$(@D)/cotan_clusters.pdf
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

$(deseq_$(1))&: $(clustering_$(1))
	$(call print_rule,deseq,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	python scripts/clustering/markers.py $$< $(firstword $(deseq_$(1))) --xlsx $(lastword $(deseq_$(1))) \
		--cluster leiden --layer log-norm --are-log \
		--logfc $(LOGFC) --alpha $(ALPHA) --correction $(CORRECTION)
	$$(conda_deactivate)

$(scoring_$(1)): $(clustering_$(1)) $(lastword $(signatures)) $(lastword $(deseq_$(1)))
	$(call print_rule,scoring,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	python scripts/clustering/scoring.py $$^ $$@ --cluster leiden --ignore-sheets background
	$$(conda_deactivate)

$(goea_basic_$(1)): $(lastword $(deseq_$(1))) $(go_basic) $(gene2go)
	$(call print_rule,goea with go-basic,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	python scripts/clustering/goea.py $$< $$@ --background background --go $$(word 2,$$^) --gene2go $$(lastword $$^) 
	$$(conda_deactivate)

$(goea_mouse_$(1)): $(lastword $(deseq_$(1))) $(go_mouse) $(gene2go)
	$(call print_rule,goea with go-mouse,$(1))
	$$(conda_activate) preprocess
	python scripts/clustering/goea.py $$< $$@ --background background --go $$(word 2,$$^) --gene2go $$(lastword $$^)
	$$(conda_deactivate)

$(stream_pseudotime_$(1)): $(annotation_$(1))
	$(call print_rule,stream-pseudotime,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) stream
	python scripts/trajectories/stream_pseudotime.py $$< $$@ --h5ad $$(shell echo $$@ | sed "s/.pkl//") \
		--embedding umap --obs leiden --cluster-number $(CLUSTER_NUMBER) \
		--lambda $(LAMBDA_EPG) --mu $(MU_EPG) --alpha $(ALPHA_EPG) \
		$(extend_epg) $(if $(filter $(EXTEND_EPG),true),--extend-parameter $(EXTEND_PARAMETER),) \
		$(prune_epg) $(if$(filter $(PRUNE_EPG),true),--collapse-parameter $(COLLAPSE_PARAMETER),) \
		--jobs $(JOBS)
	$$(conda_deactivate)

$(stream_trajectories_$(1)): $(stream_pseudotime_$(1))
	$(call print_rule,stream-trajectories,$(1))
	$(call print_warning,root can be modified using ROOT_$(call toupper,$(1)) \(current value: $(ROOT_$(call toupper, $(1)))\))
	$$(conda_activate) stream
	python scripts/trajectories/stream_trajectories.py $$< $$(@D) --root $(ROOT_$(call toupper, $(1))) \
		--groups leiden kmeans macrostates \
		--add-legend --add-graph $(IGNORED_NODES_$(call toupper, $(1)))
	$$(conda_deactivate)

$(bin_cells_$(1)): $(clustering_$(1))
	$(call print_rule,bin-cells,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) scboolseq
	python scripts/binarization/bin_cells.py $$< --outfile $$@ --bin $$(shell echo $$@ | sed "s/.h5ad/.csv/") --statistics $$(@D)/statistics.csv \
		--layer log-norm $(bin_only_hvg) --quantile $(UNIMODAL_QUANTILE) $(zeroes_are_zeroes)
	$(call print_task,plotting umap with respect to binarization percentage)
	python fig/plot_embedding.py fig/bin_umap.json --infile $$@ --outfile $$(@D)/pct_bin.pdf
	$$(conda_deactivate)

endef

$(clustering_integrated): $(foreach condition,$(conditions),$(normalization_$(condition)))
	$(call print_rule,clustering,integrated)
	mkdir -p $(@D)
	$(conda_activate) preprocess
	python scripts/clustering/integration.py $^ --outfile $@ --labels $(conditions) \
		--layer correct --adjacency knn --integration $(INTEGRATION) --embedding umap \
		--pca-dimension $(DIM_PCA) --clustering-dimension $(DIM_CLUSTERING) --embedding-dimension $(DIM_EMBEDDING) \
		$(if $(filter $(PCA_ONLY_HVG),true),--hvg $(HVG),) --neighbors $(NEIGHBORS) --metric $(METRIC) --resolution $(RESOLUTION) \
		--min-dist $(MIN_DIST) --spread $(SPREAD) --seed $(SEED) --jobs $(JOBS)
	$(conda_deactivate)

ifdef LABEL_INTEGRATED
$(annotation_integrated): $(clustering_integrated)
	$(call print_rule,annotation,integrated)
	mkdir -p $(@D)
	$(conda_activate) preprocess
	python scripts/clustering/annotation.py $< $@ \
		--obs leiden --labels $(join $(shell seq 0 1 $$(( $(words $(LABEL_INTEGRATED))-1 ))),$(addprefix :,$(LABEL_INTEGRATED)))
	$(call print_task,plotting umap with respect to labels)
	python fig/plot_embedding.py fig/umap_labels.json --infile $@ --outfile $(@D)/umap_labels.pdf
	$(conda_deactivate)
else
$(annotation_integrated): $(clustering_integrated)
	$(call print_rule,annotation,integrated)
	$(call print_error,parameter LABEL_INTEGRATED not defined)
endif

$(bin_macrostates_integrated): $(bin_cells_integrated) $(foreach condition,$(conditions),$(macrostates_$(condition)))
	$(call print_rule,bin-macrostates,integrated)
	mkdir -p $(@D)
	$(conda_activate) preprocess
	$(call print_debug,transferring information from integrated dataset to specific datasets)
	python scripts/utils/pipe_sti.py $^ --outfile $(@D)/tmp.h5ad --labels $(conditions) --obs-label condition --obs macrostates
	$(call print_info,binarizing macrostates)
	python scripts/binarization/bin_clusters.py $(@D)/tmp.h5ad $(@D) --condition condition --cluster macrostates --plot-3d
	rm $(@D)/tmp.h5ad
	$(call print_info,plotting macrostate labels)
	python fig/plot_embedding.py fig/macrostates.json --infile $(@D)/bin_clusters.h5ad --outfile $(@D)/macrostates
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