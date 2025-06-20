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

ifndef CONDITIONS
$(error Parameter CONDITIONS not defined)
endif

conditions := $(call tolower, $(CONDITIONS))
references := $(conditions) integrated
REFERENCES := $(subst $(space),$(plus),$(references))
running_references := $(subst $(plus),$(space),$(REFERENCES))
running_conditions := $(subst $(space)integrated,,$(running_references))

export tmpdir:=$(shell mktemp -d -t scbridge-XXXXXXXXXX)
$(shell { trap 'rm -rf $(tmpdir);' EXIT; tail --pid=$$PPID -f /dev/null; } </dev/null >/dev/null 2>/dev/null &)

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
binarization = data/binarization
bonesis = data/bonesis

cc_markers = $(public)/cycle_phases/mouse_cycle_markers.rds
signatures = $(public)/signatures/geiger.xls $(public)/signatures/chambers.xls $(public)/signatures/signatures.json
go_basic = $(public)/enrichment/go-basic.obo
go_mouse = $(public)/enrichment/goslim.obo
gene2go = $(public)/enrichment/gene2go

$(eval transcriptome := $(public)/genome/$(notdir $(transcriptome_url)))
transcriptome := $(transcriptome:.tar.gz=)

define find_paths_for_conditions

fastq_$(1) =                    $(rna)/$(1)/fastq
cellranger_$(1) =               $(rna)/$(1)/counting/cellranger/$(1).mri.tgz
velocyto_$(1) =                 $(rna)/$(1)/counting/velocyto/counts.h5ad
filtering_$(1) =                $(rna)/$(1)/preprocessing/filtering/counts.h5ad
normalization_$(1) =            $(rna)/$(1)/preprocessing/normalization/counts.h5ad
scvelo_$(1) =                   $(rna)/$(1)/trajectories/scvelo/scvelo.h5ad
cytotrace_$(1) =                $(rna)/$(1)/trajectories/cytotrace/cytotrace.csv
cotan_$(1) =                    $(rna)/$(1)/macrostates/cotan/macrostates.h5ad $(rna)/$(1)/macrostates/cotan/macrostates.csv
cellrank_$(1) =                 $(rna)/$(1)/macrostates/cellrank/macrostates.h5ad $(rna)/$(1)/macrostates/cellrank/macrostates.csv
stream_$(1) =                   $(rna)/$(1)/macrostates/stream/macrostates.h5ad $(rna)/$(1)/macrostates/stream/macrostates.csv
knnbs_$(1) =                    $(rna)/$(1)/macrostates/knnbs/macrostates.h5ad $(rna)/$(1)/macrostates/knnbs/macrostates.csv

ifeq ($(MACROSTATES_METHOD),cotan)
macrostates_$(1) =              $$(cotan_$(1))
else ifeq ($(MACROSTATES_METHOD),cellrank)
macrostates_$(1) =              $$(cellrank_$(1))
else ifeq ($(MACROSTATES_METHOD),stream)
macrostates_$(1) =              $$(stream_$(1))
else ifeq ($(MACROSTATES_METHOD),knnbs)
macrostates_$(1) =              $$(knnbs_$(1))
else
$$(error unsupported value for parameter MACROSTATES_METHOD (supported values: cotan, cellrank, stream or knnbs))
endif

endef

define find_paths_for_references

clustering_$(1) =               $(rna)/$(1)/clustering/clusters/counts.h5ad
dea_$(1) =                      $(rna)/$(1)/clustering/dea/markers.csv $(rna)/$(1)/clustering/dea/genes.xlsx
scoring_$(1) =                  $(rna)/$(1)/clustering/scoring/phenotypes.csv
goea_basic_$(1) =               $(rna)/$(1)/clustering/goea/goea_basic.xlsx
goea_mouse_$(1) =               $(rna)/$(1)/clustering/goea/goea_mouse.xlsx
annotation_$(1) =               $(rna)/$(1)/clustering/clusters/annotation.h5ad

endef

bin_cells =                     $(binarization)/cells/bin.h5ad $(binarization)/cells/statistics.csv
bin_scboolseq =                 $(binarization)/scboolseq/$(MACROSTATES_METHOD)/bin_macrostates.csv
bin_dea =                       $(binarization)/dea/$(MACROSTATES_METHOD)/bin_macrostates.csv
bin_merge =                     $(binarization)/merge/$(MACROSTATES_METHOD)/bin_macrostates.csv

bonesis_model =                 $(bonesis)/modeling/bo_model.txt $(bonesis)/modeling/metastates.csv $(bonesis)/modeling/mandatory_genes.txt $(bonesis)/modeling/important_genes.txt
bonesis_weak_stage1 =           $(bonesis)/filtering/weak/stage1.txt
bonesis_weak_stage2 =           $(bonesis)/filtering/weak/stage2.txt
bonesis_weak_filtering =        $(bonesis_weak_stage1) $(bonesis_weak_stage2)
bonesis_strong_filtering =      $(bonesis)/filtering/strong/stage1.txt
bonesis_inference_min =         $(bonesis)/bn/min/bn_min.bnet
bonesis_inference_sub =         $(bonesis)/bn/sub/bn_sub.bnet

$(foreach condition,$(conditions),$(eval $(call find_paths_for_conditions,$(condition))))
$(foreach reference,$(references),$(eval $(call find_paths_for_references,$(reference))))

ifeq ($(BIN_METHOD),scboolseq)
bin = 		$(bin_scboolseq)
else ifeq ($(BIN_METHOD),dea)
bin = 		$(bin_dea)
else ifeq ($(BIN_METHOD),merge)
bin = 		$(bin_merge)
else
$(error unsupported value for parameter BIN_METHOD (supported values: scboolseq, dea, merge))
endif

## END PATHS ##

## BEGIN TARGETS ##

fastq_target :=
cellranger_target :=
velocyto_target :=
h5ad_target :=
filtering_target :=
normalization_target :=
clustering_target :=
dea_target :=
scoring_target :=
goea_target :=
annotation_target :=
scvelo_velocity_target :=
cytotrace_velocity_target :=
macrostates_target :=
stream_target :=
cellrank_target :=
knnbs_target :=
cotan_target :=

define find_targets_for_conditions

$(eval fastq_target := $(fastq_target) $(fastq_$(1)))
$(eval cellranger_target := $(cellranger_target) $(cellranger_$(1)))
$(eval velocyto_target := $(velocyto_target) $(velocyto_$(1)))
$(eval filtering_target := $(filtering_target) $(filtering_$(1)))
$(eval normalization_target := $(normalization_target) $(normalization_$(1)))
$(eval scvelo_velocity_target := $(scvelo_velocity_target) $(scvelo_$(1)))
$(eval cytotrace_velocity_target := $(cytotrace_velocity_target) $(cytotrace_$(1)))
$(eval cotan_target := $(cotan_target) $(cotan_$(1)))
$(eval cellrank_target := $(cellrank_target) $(cellrank_$(1)))
$(eval stream_target := $(stream_target) $(stream_$(1)))
$(eval knnbs_target := $(knnbs_target) $(knnbs_$(1)))
$(eval macrostates_target := $(macrostates_target) $(macrostates_$(1)))
$(eval bdc_target := $(bdc_target) $(bdc_$(1)))

endef

define find_targets_for_references

$(eval clustering_target := $(clustering_target) $(clustering_$(1)))
$(eval dea_target := $(dea_target) $(dea_$(1)))
$(eval scoring_target := $(scoring_target) $(scoring_$(1)))
$(eval goea_target := $(goea_target) $(goea_basic_$(1)) $(goea_mouse_$(1)))
$(eval annotation_target := $(annotation_target) $(annotation_$(1)))

endef

$(foreach condition,$(running_conditions),$(eval $(call find_targets_for_conditions,$(condition))))
$(foreach reference,$(running_references),$(eval $(call find_targets_for_references,$(reference))))

## END TARGETS ##

## BEGIN PARAMETERS ##

ifndef JOBS
$(error Parameter JOBS not defined)
else
try_open_allocated_cpu=$(shell echo $$(($(JOBS) / 2)))
open_allocated_cpu=$(if $(findstring $(try_open_allocated_cpu),0),1,$(try_open_allocated_cpu))
endif

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
pca_only_hvg=--only-hvg
else ifeq ($(PCA_ONLY_HVG),false)
pca_only_hvg=
else
$(error Unsupported value for parameter PCA_ONLY_HVG (supported values: true, false))
endif

ifndef VELOCITY_ONLY_HVG
$(error Parameter VELOCITY_ONLY_HVG not defined)
else ifeq ($(VELOCITY_ONLY_HVG),true)
velocity_only_hvg=--only-hvg
else ifeq ($(VELOCITY_ONLY_HVG),false)
velocity_only_hvg=
else
$(error Unsupported value for parameter VELOCITY_ONLY_HVG (supported values: true, false))
endif

ifndef COTAN_ONLY_HVG
$(error Parameter COTAN_ONLY_HVG not defined)
else ifeq ($(COTAN_ONLY_HVG),true)
cotan_only_hvg=--only-hvg
else ifeq ($(COTAN_ONLY_HVG),false)
cotan_only_hvg=
else
$(error Unsupported value for parameter COTAN_ONLY_HVG (supported values: true, false))
endif

ifndef EXTEND_EPG
$(error Parameter EXTEND_EPG not defined)
else ifeq ($(EXTEND_EPG),true)
extend_epg=--extend-epg
else ifeq ($(EXTEND_EPG),false)
extend_epg=
else
$(error Unsupported value for parameter EXTEND_EPG (supported values: true, false))
endif

ifndef PRUNE_EPG
$(error Parameter PRUNE_EPG not defined)
else ifeq ($(PRUNE_EPG),true)
prune_epg=--prune-epg
else ifeq ($(PRUNE_EPG),false)
prune_epg=
else
$(error Unsupported value for parameter PRUNE_EPG (supported values: true, false))
endif

ifneq ($(filter-out pca umap,$(KNNBS_EMBEDDING)),)
$(error Unsupported value for parameter KNNBS_EMBEDDING (supported values: pca, umap))
endif

ifeq ($(KNNBS_DIMENSION),)
knnbs_dimension=
else
knnbs_dimension=--dimension $(KNNBS_DIMENSION)
endif

ifndef ZEROES_ARE_ZEROES
$(error Parameter ZEROES_ARE_ZEROES not defined)
else ifeq ($(ZEROES_ARE_ZEROES),true)
zeroes_are_zeroes=--zeroes-are-zeroes
else ifeq ($(ZEROES_ARE_ZEROES),false)
zeroes_are_zeroes=
else
$(error Unsupported value for parameter ZEROES_ARE_ZEROES (supported values: true, false))
endif

ifndef YAML_MODEL
$(error Parameter YAML_MODEL not defined)
endif

ifneq ($(filter-out seurat_v3 seurat cell_ranger,$(MODEL_HVG_METHOD)),)
$(error Unsupported value for parameter MODEL_HVG_METHOD (supported values: seurat, cell_ranger or seurat_v3))
endif

ifndef FILTER_MIN_FEEDBACKS
$(error Parameter FILTER_MIN_FEEDBACKS not defined)
else ifeq ($(FILTER_MIN_FEEDBACKS),true)
filter_min_feedbacks=--minimize-feedbacks
else ifeq ($(FILTER_MIN_FEEDBACKS),false)
filter_min_feedbacks=
else
$(error Unsupported value for parameter FILTER_MIN_FEEDBACKS (supported values: true, false))
endif

ifndef MIN_FEEDBACKS
$(error Parameter MIN_FEEDBACKS not defined)
else ifeq ($(MIN_FEEDBACKS),true)
MIN_FEEDBACKS:=--minimize-feedbacks
else ifeq ($(MIN_FEEDBACKS),false)
MIN_FEEDBACKS:=
else
$(error Unsupported value for parameter MIN_FEEDBACKS (supported values: true, false))
endif

## END PARAMETERS ##

## BEGIN HELP ##

##@ Help

.PHONY: help
help: ## display this help and exit
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make $(GREEN)<command>$(NC) [REFERENCES=<...>] (default:REFERENCES=$(subst $(space),$(plus),$(references)))\n\
	scBridge (pipeline for Boolean network Reconstruction and Inference from multiple experimental Data in Gene Expression) proposes \
	a general methodology for inferring logical models reproducing the observed transcriptomic cell dynamics by using scRNA-seq data as input. \
	Its implementation in make offers a wide range of advanced features for guiding and helping users in reconstructing data-driven \
	Boolean networks.\n"}/^[a-zA-Z_-]+:.*?##/ \
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
.PHONY: dea
dea: $(dea_target) ## perform differential expression analysis
.PHONY: scoring
scoring: $(scoring_target) ## score signature-related phenotypes with respect to cell clusters
.PHONY: goea
goea: $(goea_target) ## perform gene ontology enrichment analysis
.PHONY: annotation
annotation: $(annotation_target) ## assign names to cell clusters

##@ Trajectory inference

.PHONY: scvelo
scvelo: $(scvelo_velocity_target) ## estimate rna velocity with scvelo
.PHONY: cytotrace
cytotrace: $(cytotrace_velocity_target) ## estimate cell potencies with CytoTRACE

##@ Macrostate characterization

.PHONY: cotan
cotan: $(cotan_target) ## estimate macrostates using zero counts co-expression
.PHONY: cellrank
cellrank: $(cellrank_target) ## estimate macrostates using rna velocities
.PHONY: stream
stream: $(stream_target) ## compute macrostates using elastic principal graph
.PHONY: knnbs
knnbs: $(knnbs_target) ## compute macrostates using k-nearest neighbors-based subclusters algorithm
.PHONY: macrostates
macrostates: $(macrostates_target) ## define macrostates depending on 'MACROSTATES_METHOD' parameter value

##@ Binarization

.PHONY: bin-cells
bin-cells: $(bin_cells) ## binarize cells using gene specific-distributions derived from ScBoolSeq
.PHONY: bin-scboolseq
bin-scboolseq: $(bin_scboolseq) ## binarize macrostates by aggregating ScBoolSeq binarized cells w.r.t. voting rules
.PHONY: bin-dea
bin-dea: $(bin_dea) ## binarize macrostates using differential expression analysis
.PHONY: bin-merge
bin-merge: $(bin_merge) ## binarize macrostates by merging ScBoolSeq and dea results
.PHONY: binarization
binarization: $(bin) ## binarize macrostates depending on 'BIN_METHOD' parameter value

##@ Boolean network inference

.PHONY: modeling
modeling: $(bonesis_model) ## specify model using BoNesis syntax
.PHONY: weak-filtering
weak-filtering: $(bonesis_weak_filtering) ## filter genes by using only weak Boolean dynamical constraints
.PHONY: strong-filtering
strong-filtering: $(bonesis_strong_filtering) ## filter genes by using weak and strong Boolean dynamical constraints
.PHONY: bonesis-min
bonesis-min: $(bonesis_inference_min) ## infer Boolean network with BoNesis (minimal solution)
.PHONY: bonesis-sub
bonesis-sub: $(bonesis_inference_sub) ## infer Boolean network with BoNesis (subset minimal solution)

## END HELP ##

## preserve target even if make is killed or interrupted
.PRECIOUS: $(bonesis_weak_stage1)
.PRECIOUS: $(bonesis_weak_stage2)
.PRECIOUS: $(bonesis_strong_filtering)

$(bin_cells)&: export OPENBLAS_NUM_THREADS = $(open_allocated_cpu)
$(bin_cells)&: export OMP_NUM_THREADS = $(open_allocated_cpu)

## BEGIN RULES ##

$(transcriptome):
	$(call print_rule,load-annotations)
	mkdir -p $(@D)
	wget --quiet --show-progress --directory-prefix=$(@D) $(transcriptome_url)
	tar -zxvf $@.tar.gz -C $(@D)
	gunzip $@/genes/genes.gtf.gz

$(cc_markers):
	$(call print_rule,load-cc)
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
	$(conda_activate) scbridge-anndata
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

define compute_rules_for_conditions

$(fastq_$(1)):
	$(call print_rule,load-fastq,$(1))
	$$(conda_activate) scbridge-fastq
	sample_naming="$(1)"
	lane=0
	rm -rf $(tmpdir)/$(1)/fastq && mkdir $(tmpdir)/$(1)/fastq
	for id in $$(SRA_$(call toupper, $(1)))
	do
		let "lane++"
		parallel-fastq-dump --sra-id $$$${id} --split-files --readids --origfmt --threads $$(JOBS) --outdir $(tmpdir)/$(1)/fastq --gzip
		$$(call fastq_naming,$(tmpdir)/$(1)/fastq,$$$${id},$$$${sample_naming},$$$${lane})
	done
	sleep 3
	mkdir -p $$@
	mv $(tmpdir)/$(1)/fastq/* $$@/
	files=$$$$(shopt -s nullglob dotglob; echo $(tmpdir)/$(1)/fastq/*)
	if ! (( $$$${#files} ))
	then
		rm -rf $(tmpdir)/$(1)/fastq
	else
		$(call print_error,cannot download fastq files: fastq-dump failed)
	fi
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
		$$(conda_activate) scbridge-velocyto
		velocyto run10x -m data/public/transcriptome/repeat_msk.gtf \
			--samtools-threads $(JOBS) --samtools-memory $(MEMORY) \
			$$(dir $$(firstword $$^)) $$(lastword $$^)/genes/genes.gtf
		$$(conda_deactivate)
		mkdir -p $$(@D)
		mv $$(<D)/velocyto/cellranger.loom $$(shell echo $$@ | sed "s/h5ad/loom/")
		rm -rf $$(<D)/velocyto
		$$(conda_activate) scbridge-anndata
		$(call print_debug,standardizing gene names and converting loom format into h5ad format)
		python scripts/utils/adata_conversion.py $$(shell echo $$@ | sed "s/h5ad/loom/") $$@ --from loom --to h5ad \
			--remove-positions --sort --standardization
		$$(conda_deactivate)
	else
		$(call print_error,cannot run velocyto: file data/public/transcriptome/repeat_msk.gtf does not exist \(please refer to documentation for downloading it\))
	fi

$(filtering_$(1)): $(velocyto_$(1)) $(cc_markers)
	$(call print_rule,filtering,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) scbridge-anndata
	python scripts/preprocessing/filtering.py $$(firstword $$^) $$@ --marker $$(lastword $$^) \
		--gene-dropout $(GENE_DROPOUT) --gene-expression $(GENE_EXPRESSION) --gene-counts $(GENE_COUNTS) \
		--cell-dropout $(CELL_DROPOUT) --cell-expression $(CELL_EXPRESSION) --cell-reads $(CELL_READS) \
		--mad $(MAD_DEVIATION) $(norm_mad) --mt $(MT) \
		--hvg $(HVG) $(filter_non_hvg)
	$$(conda_deactivate)

$(normalization_$(1)): $(filtering_$(1))
	$(call print_rule,normalization,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) scbridge-anndata
	python scripts/preprocessing/normalization.py $$< $$@ $(correction) --jobs $(JOBS)
	$$(conda_deactivate)

$(clustering_$(1)): $(normalization_$(1))
	$(call print_rule,clustering,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) scbridge-anndata
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
	$$(conda_activate) scbridge-anndata
	python scripts/utils/pipe_its.py $$^ --outfiles $$@ --labels $(1) --obs-label condition --obs leiden
	$(call print_task,plotting umap with respect to annotated clusters)
	python fig/plot_embedding.py fig/leiden_umap.json --infile $$@ --outfile $$(@D)/umap_annotation.pdf
	$$(conda_deactivate)
else
ifdef LABEL_$(call toupper,$(1))
$(annotation_$(1)): $(clustering_$(1))
	$(call print_rule,annotation,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) scbridge-anndata
	python scripts/clustering/annotation.py $< $@ \
		--obs leiden --labels $(join $(shell seq 0 1 $$(( $(words $$(LABEL_$(call toupper,$(1))))-1 ))),$(addprefix :,$(LABEL_INTEGRATED)))
	$(call print_task,embedding component plotting)
	python fig/plot_embedding.py fig/leiden_umap.json \
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
	$$(conda_activate) scbridge-scvelo
	python scripts/trajectories/velocity.py $$< $$@ \
		--layer counts --cluster leiden --moment-dimension $(DIM_MOMENT) \
		$(velocity_only_hvg) --mode $(SMM_MODE) --embedding umap --jobs $(JOBS)
	$$(conda_deactivate)

$(cytotrace_$(1)): $(annotation_$(1))
	$(call print_rule,cytotrace,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) scbridge-cytotrace
	python scripts/trajectories/potency.py $$< $$(@D) --csv $$(notdir $$@) --h5ad $$(basename $$(notdir $$@)).h5ad \
		--layer counts --cluster leiden --batch-size $(BATCH_SIZE) --smooth-batch-size $(SMOOTH_BATCH_SIZE) \
		--organism $(ORGANISM) --embedding umap --seed $(SEED) --jobs $(JOBS)
	$$(conda_deactivate)

$(cotan_$(1))&: $(annotation_$(1))
	$(call print_rule,cotan,$(1))
	mkdir -p $$(@D) $(tmpdir)/$(1)/cotan
	$$(conda_activate) scbridge-anndata
	$(call print_debug,loading file $$< \(layer 'matrix'\))
	python scripts/utils/adata_conversion.py $$< $(tmpdir)/$(1)/cotan/barcts.csv --from h5ad --to csv --layer matrix $(cotan_only_hvg)
	$(call print_debug,transposing counts matrix)
	ruby -rcsv -e 'puts CSV.parse(STDIN).transpose.map &:to_csv' < $(tmpdir)/$(1)/cotan/barcts.csv > $(tmpdir)/$(1)/cotan/gencts.csv
	$$(conda_deactivate)
	$$(conda_activate) scbridge-cotan
	Rscript scripts/macrostates/cotan_macrostates.R --infile $(tmpdir)/$(1)/cotan/gencts.csv --outfile $$(@D)/cotan.RDS --csv $$(lastword $$(cotan_$(1))) \
		--sep , --name $(1) --max-iterations $(MAX_ITER) --method $(COTAN_METHOD) --min-ude 0.3 --jobs $(JOBS)
	$$(conda_deactivate)
	sed -i '1 i\,macrostates' $$(lastword $$(cotan_$(1)))
	$$(conda_activate) scbridge-anndata
	$(call print_debug,adding cotan clusters to anndata object)
	python scripts/utils/add_to_anndata.py $$< $$(firstword $$(cotan_$(1))) --csv $$(lastword $$(cotan_$(1))) --axis 0 --sep , --type category
	$(call print_task,plotting umap with respect to cotan clusters)
	python fig/plot_embedding.py fig/macrostates_umap.json --infile $$(firstword $$(cotan_$(1))) --outfile $$(@D)/umap_cotan.pdf
	$$(conda_deactivate)

$(cellrank_$(1))&: $(scvelo_$(1)) $(cytotrace_$(1))
	$(call print_rule,cellrank,$(1))
	mkdir -p $$(@D) $(tmpdir)/$(1)/cellrank
	$(call print_debug,adding cytotrace scores to anndata object)
	awk -F, -v txt="score" 'FNR==1{for(col=1;$$$$col!=txt;col++);next} {print $$$$1 "," $$$$col}' $$(lastword $$^) > $(tmpdir)/$(1)/cellrank/cytotrace_scores.csv
	sed -i '1 i\,cytotrace_score' $(tmpdir)/$(1)/cellrank/cytotrace_scores.csv
	$$(conda_activate) scbridge-anndata
	python scripts/utils/add_to_anndata.py $$(firstword $$^) $(tmpdir)/$(1)/cellrank/kernels.h5ad --csv $(tmpdir)/$(1)/cellrank/cytotrace_scores.csv --axis 0 --sep , --type float
	$$(conda_deactivate); $$(conda_activate) scbridge-cellrank
	python scripts/macrostates/cellrank_macrostates.py $(tmpdir)/$(1)/cellrank/kernels.h5ad $$(firstword $$(cellrank_$(1))) --csv $$(lastword $$(cellrank_$(1))) \
		--obs leiden --method $(CELLRANK_METHOD) \
		--cytotrace-score cytotrace_score --scvelo-velocity velocity \
		--states $(STATES) --initial-states $(INITIAL_STATES) --terminal-states $(TERMINAL_STATES) \
		--stability $(CELLRANK_STABILITY) --alpha $(CELLRANK_ALPHA) --size $(MACROSTATE_SIZE) --seed $(SEED)
	$$(conda_deactivate)

$(stream_$(1))&: $(annotation_$(1))
	$(call print_rule,stream,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) scbridge-stream
	python scripts/macrostates/stream_macrostates.py $$< $$(firstword $$(stream_$(1))) \
		--pkl $$(firstword $$(stream_$(1))).pkl --csv $$(lastword $$(stream_$(1))) \
		--embedding umap --obs leiden --cluster-number $(CLUSTER_NUMBER) \
		--lambda $(LAMBDA_EPG) --mu $(MU_EPG) --alpha $(ALPHA_EPG) \
		$(extend_epg) $(if $(filter $(EXTEND_EPG),true),--extend-parameter $(EXTEND_PARAMETER),) \
		$(prune_epg) $(if $(filter $(PRUNE_EPG),true),--collapse-parameter $(COLLAPSE_PARAMETER),) \
		--jobs $(JOBS)
	$$(conda_deactivate)

ifeq ($(or $(MIN_DIST_$(call toupper,$(1))),$(MAX_DIST_$(call toupper,$(1)))),)
$(knnbs_$(1))&: $(annotation_$(1))
	$(call print_error,parameters MIN_DIST_$(call toupper,$(1)) and MAX_DIST_$(call toupper,$(1)) not defined \(at least one must be defined\))
else
$(knnbs_$(1))&: $(annotation_$(1))
	$(call print_rule,knnbs,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) scbridge-anndata
	python scripts/macrostates/knnbs_macrostates.py $$< $$(firstword $$(knnbs_$(1))) --csv $$(lastword $$(knnbs_$(1))) \
		--obs leiden --embedding $(KNNBS_EMBEDDING) --neighbors $(KNNBS_NEIGHBORS) \
		$(knnbs_dimension) --metric $(METRIC) --size $(MACROSTATE_SIZE) \
		--max-distances $(MAX_DIST_$(call toupper,$(1))) --min-distances $(MIN_DIST_$(call toupper,$(1))) \
		--jobs $(JOBS)
	$(call print_task,plotting umap with respect to knnbs clusters)
	python fig/plot_embedding.py fig/macrostates_umap.json --infile $$(firstword $$(knnbs_$(1))) --outfile $$(@D)/umap_knnbs.pdf
	$$(conda_deactivate)
endif

endef

define compute_rules_for_references

$(dea_$(1))&: $(clustering_$(1))
	$(call print_rule,dea,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) scbridge-anndata
	python scripts/clustering/markers.py $$< $(firstword $(dea_$(1))) --xlsx $(lastword $(dea_$(1))) \
		--cluster leiden --layer log-norm --is-log \
		--logfc $(LOGFC) --alpha $(ALPHA) --correction $(CORRECTION)
	$$(conda_deactivate)

$(scoring_$(1)): $(clustering_$(1)) $(lastword $(signatures)) $(lastword $(dea_$(1)))
	$(call print_rule,scoring,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) scbridge-anndata
	python scripts/clustering/scoring.py $$^ $$@ --cluster leiden --ignore-sheets background
	$$(conda_deactivate)

$(goea_basic_$(1)): $(lastword $(dea_$(1))) $(go_basic) $(gene2go)
	$(call print_rule,goea with go-basic,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) scbridge-anndata
	python scripts/clustering/goea.py $$< $$@ --background background --go $$(word 2,$$^) --gene2go $$(lastword $$^) 
	$$(conda_deactivate)

$(goea_mouse_$(1)): $(lastword $(dea_$(1))) $(go_mouse) $(gene2go)
	$(call print_rule,goea with go-mouse,$(1))
	$$(conda_activate) scbridge-anndata
	python scripts/clustering/goea.py $$< $$@ --background background --go $$(word 2,$$^) --gene2go $$(lastword $$^)
	$$(conda_deactivate)

endef

$(clustering_integrated): $(foreach condition,$(conditions),$(normalization_$(condition)))
	$(call print_rule,clustering,integrated)
	mkdir -p $(@D)
	$(conda_activate) scbridge-anndata
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
	$(conda_activate) scbridge-anndata
	python scripts/clustering/annotation.py $< $@ \
		--obs leiden --labels $(join $(shell seq 0 1 $$(( $(words $(LABEL_INTEGRATED))-1 ))),$(addprefix :,$(LABEL_INTEGRATED)))
	$(call print_task,plotting umap with respect to labels)
	python fig/plot_embedding.py fig/leiden_umap.json --infile $@ --outfile $(@D)/umap_labels.pdf
	$(conda_deactivate)
else
$(annotation_integrated): $(clustering_integrated)
	$(call print_rule,annotation,integrated)
	$(call print_error,parameter LABEL_INTEGRATED not defined)
endif

$(bin_cells)&: $(clustering_integrated)
	$(call print_rule,bin-cells)
	mkdir -p $(@D)
	$(conda_activate) scbridge-scboolseq
	python scripts/binarization/bin_cells_scboolseq.py $< --outfile $(firstword $(bin_cells)) --bin $(shell echo $@ | sed "s/.h5ad/.csv/") --statistics $(lastword $(bin_cells)) \
		--layer log-norm --quantile $(UNIMODAL_QUANTILE) $(zeroes_are_zeroes)
	$(call print_task,plotting umap with respect to binarization percentage)
	python fig/plot_embedding.py fig/bin_umap.json --infile $(firstword $(bin_cells)) --outfile $(@D)/pct_bin.pdf
	$(conda_deactivate)

$(bin_scboolseq): $(firstword $(bin_cells)) $(foreach condition,$(conditions),$(lastword $(macrostates_$(condition))))
	$(call print_rule,bin-scboolseq)
	mkdir -p $(@D) $(tmpdir)/integrated/bin/aggr
	$(conda_activate) scbridge-anndata
	$(call print_debug,adding macrostates to anndata object)
	python scripts/utils/add_to_anndata.py $(firstword $^) $(tmpdir)/integrated/bin/aggr/mcts.h5ad --csv $(filter-out $<, $^) \
		--labels $(conditions) --label-column condition --add-prefix macrostates --axis 0 --sep , --type category
	python scripts/binarization/bin_clusters_scboolseq.py $(tmpdir)/integrated/bin/aggr/mcts.h5ad $@ --counts $(@D)/counts_bin.csv \
		--layer bin --distribution distribution --cluster macrostates --embedding umap \
		--nans-threshold $(NANS_THRESHOLD) --bimodal-threshold $(BIMODAL_THRESHOLD) \
		--zeroinf-threshold $(ZEROINF_THRESHOLD) --unimodal-threshold $(UNIMODAL_THRESHOLD)
	$(call print_task,plotting umap with respect to macrostates)
	python fig/plot_embedding.py fig/macrostates_umap.json --infile $(tmpdir)/integrated/bin/aggr/mcts.h5ad --outfile $(@D)/umap_macrostates.pdf
	$(conda_deactivate)

$(bin_dea): $(clustering_integrated) $(foreach condition,$(conditions),$(lastword $(macrostates_$(condition))))
	$(call print_rule,bin-dea)
	mkdir -p $(@D) $(tmpdir)/integrated/bin/dea
	$(conda_activate) scbridge-anndata
	$(call print_debug,adding macrostates to anndata object)
	python scripts/utils/add_to_anndata.py $(firstword $^) $(tmpdir)/integrated/bin/dea/mcts.h5ad --csv $(filter-out $<, $^) \
		--labels $(conditions) --label-column condition --add-prefix macrostates --axis 0 --sep , --type category
	python scripts/binarization/bin_dea.py $(tmpdir)/integrated/bin/dea/mcts.h5ad $@ \
		--cluster macrostates --layer log-norm --is-log --embedding umap \
		--logfc $(BIN_LOGFC) --alpha $(BIN_ALPHA) --correction $(BIN_CORRECTION)
	$(call print_task,plotting umap with respect to macrostates)
	python fig/plot_embedding.py fig/macrostates_umap.json --infile $(tmpdir)/integrated/bin/dea/mcts.h5ad --outfile $(@D)/umap_macrostates.pdf
	$(conda_deactivate)

$(bin_merge): $(bin_scboolseq) $(lastword $(bin_cells)) $(bin_dea)
	$(call print_rule,bin-merge)
	mkdir -p $(@D) $(tmpdir)/bin/merge
	$(call print_debug,retrieving scboolseq distributions)
	col=`head $(word 2, $^) -n 1 | sed "s/,/\n/g" | awk -F, '{printf("%d %s\n", NR-1, $$0)}' | grep Category | awk '{print $$1}'`
	((col++))
	cut -f 1,$$col -d ',' $(word 2, $^) > $(tmpdir)/bin/merge/distributions.csv
	unset col
	$(conda_activate) scbridge-anndata
	python scripts/binarization/bin_merge.py --scboolseq $< $(tmpdir)/bin/merge/distributions.csv --dea $(lastword $^) \
		--outfile $@ --pct-bin $(@D)/pct_bin.csv
	$(conda_deactivate)

ifdef MODEL_TOP_HVG
$(bonesis_model)&: $(bin) $(clustering_integrated)
	$(call print_rule,modeling)
	if ! [ -f $(YAML_MODEL) ]; then
		$(call print_error,file $(YAML_MODEL) not found \(see documentation for details about command \'modeling\'\))
	fi
		mkdir -p $(tmpdir)/bonesis/hvg $(dir $(word 1,$(bonesis_model))) $(dir $(word 2,$(bonesis_model))) $(dir $(word 3,$(bonesis_model))) $(dir $(word 4,$(bonesis_model)))
		$(conda_activate) scbridge-anndata
		$(call print_task,estimating top $(MODEL_TOP_HVG) highly variable genes with $(MODEL_HVG_METHOD))
		python scripts/preprocessing/hvg.py $(lastword $^) $(tmpdir)/hvg/top_genes.txt --hvg $(MODEL_TOP_HVG) --method $(MODEL_HVG_METHOD)
		$(conda_deactivate)
		$(conda_activate) scbridge-bonesis
		python scripts/inference/specification.py $(YAML_MODEL) $< \
			--model $(word 1,$(bonesis_model)) --metastates $(word 2,$(bonesis_model)) \
			--mandatory-genes $(word 3,$(bonesis_model)) --important-genes $(word 4,$(bonesis_model)) \
			--filter-genes $(tmpdir)/hvg/top_genes.txt --organism $(ORGANISM)
		$(conda_deactivate)
else
$(bonesis_model)&: $(bin)
	$(call print_rule,modeling)
	if ! [ -f $(YAML_MODEL) ]; then
		$(call print_error,file $(YAML_MODEL) not found \(see documentation for details about command \'modeling\'\))
	fi
		mkdir -p $(dir $(word 1,$(bonesis_model))) $(dir $(word 2,$(bonesis_model))) $(dir $(word 3,$(bonesis_model))) $(dir $(word 4,$(bonesis_model)))
		$(conda_activate) scbridge-bonesis
		python scripts/inference/specification.py $(YAML_MODEL) $< \
			--model $(word 1,$(bonesis_model)) --metastates $(word 2,$(bonesis_model)) \
			--mandatory-genes $(word 3,$(bonesis_model)) --important-genes $(word 4,$(bonesis_model)) \
			--organism $(ORGANISM)
		$(conda_deactivate)
endif

$(bonesis_weak_stage1): $(bonesis_model)
	$(call print_rule,weak-filtering \(stage 1\))
	mkdir -p $(@D)
	$(conda_activate) scbridge-bonesis
	timeout $(TIMEOUT) python scripts/inference/inference.py filter-stage1 $(word 1,$^) $(word 2,$^) \
		--mandatory-genes $(word 3,$^) --important-genes $(word 4,$^) \
		--asp $(@D)/stage1.sh --solution $@ \
		--only-weak-constraints --max-clause $(MAX_CLAUSE) --organism $(ORGANISM)
	exit_status=$$?
	$(conda_deactivate)
	if [ $$exit_status -eq 124 ]; then
		echo -e ''
		if [ -f $@ ]; then
			$(call print_debug,user-defined time limit reached \($(TIMEOUT)\): optimal local solution found)
		else
			$(call print_error,user-defined time limit reached \($(TIMEOUT)\): optimal local solution not found)
		fi
	else
		$(call print_debug,optimal global solution found)
	fi

$(bonesis_weak_stage2): $(bonesis_model) $(bonesis_weak_stage1)
	$(call print_rule,weak-filtering \(stage 2\))
	mkdir -p $(@D)
	$(conda_activate) scbridge-bonesis
	timeout $(TIMEOUT) python scripts/inference/inference.py filter-stage2 $(word 1,$^) $(word 2,$^) \
		--mandatory-genes $(word 3,$^) --important-genes $(word 4,$^) \
		--asp $(@D)/stage2.sh --solution $@ \
		--only-weak-constraints --filter-grn $(lastword $^) $(filter_min_feedbacks) --max-clause $(MAX_CLAUSE) --organism $(ORGANISM)
	exit_status=$$?
	$(conda_deactivate)
	if [ $$exit_status -eq 124 ]; then
		echo -e ''
		if [ -f $@ ]; then
			$(call print_debug,user-defined time limit reached \($(TIMEOUT)\): optimal local solution found)
		else
			$(call print_error,user-defined time limit reached \($(TIMEOUT)\): optimal local solution not found)
		fi
	else
		$(call print_debug,optimal global solution found)
	fi

$(bonesis_strong_filtering): $(bonesis_model) $(bonesis_weak_stage2)
	$(call print_rule,strong-filtering)
	mkdir -p $(@D)
	$(conda_activate) scbridge-bonesis
	timeout $(TIMEOUT) python scripts/inference/inference.py filter-stage1 $(word 1,$^) $(word 2,$^) \
		--mandatory-genes $(word 3,$^) --important-genes $(word 4,$^) \
		--asp $(@D)/stage1.sh --solution $@ \
		--filter-grn $(lastword $^) --max-clause $(MAX_CLAUSE) --organism $(ORGANISM)
	exit_status=$$?
	$(conda_deactivate)
	if [ $$exit_status -eq 124 ]; then
		echo -e ''
		if [ -f $@ ]; then
			$(call print_debug,user-defined time limit reached \($(TIMEOUT)\): optimal local solution found)
		else
			$(call print_error,user-defined time limit reached \($(TIMEOUT)\): optimal local solution not found)
		fi
	else
		$(call print_debug,optimal global solution found)
	fi

$(bonesis_inference_min): $(bonesis_model) $(bonesis_filtering_two)
	$(call print_rule,bonesis-min)
	mkdir -p $(@D)
	$(conda_activate) scbridge-bonesis
	python scripts/inference/inference.py one-min $(word 1,$^) $(word 2,$^) \
		--mandatory-genes $(word 3,$^) --important-genes $(word 4,$^) \
		--asp $(@D)/bonesis_min.sh --solution $@ \
		--filter-grn $(lastword $^) $(filter_min_feedbacks) --max-clause $(MAX_CLAUSE) --organism $(ORGANISM)
	$(conda_deactivate)

$(bonesis_inference_sub): $(bonesis_model) $(bonesis_filtering_two)
	$(call print_rule,bonesis-min)
	mkdir -p $(@D)
	$(conda_activate) scbridge-bonesis
	python scripts/inference/inference.py one-sub $(word 1,$^) $(word 2,$^) \
		--mandatory-genes $(word 3,$^) --important-genes $(word 4,$^) \
		--asp $(@D)/bonesis_min.sh --solution $@ \
		--filter-grn $(lastword $^) $(filter_min_feedbacks) --max-clause $(MAX_CLAUSE) --organism $(ORGANISM)
	$(conda_deactivate)

$(foreach condition,$(conditions),$(eval $(call compute_rules_for_conditions,$(condition))))
$(foreach reference,$(references),$(eval $(call compute_rules_for_references,$(reference))))

## END RULES
