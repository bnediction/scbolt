#!/usr/bin/env make

.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c

SHELL := /bin/bash
MAKEFLAGS += --silent
DEFAULT_PARAMS = default_params.mk
__check_externals__ ?= true

include $(DEFAULT_PARAMS)
include $(PARAMS)

_lower2upper = a:A b:B c:C d:D e:E f:F g:G h:H i:I j:J k:K l:L m:M n:N o:O p:P q:Q r:R s:S t:T u:U v:V w:W x:X y:Y z:Z
_lower = $(word 1, $(subst :, ,$(word 1,$(1))))
_upper = $(word 2, $(subst :, ,$(word 1,$(1))))
toupper = $(eval _=$1)$(strip $(foreach pair,$(_lower2upper),$(eval _=$(subst $(call _lower,$(pair)),$(call _upper,$(pair)),$_))))$_
tolower = $(eval _=$1)$(strip $(foreach pair,$(_lower2upper),$(eval _=$(subst $(call _upper,$(pair)),$(call _lower,$(pair)),$_))))$_

comma := ,
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
running_conditions := $(filter-out integrated,$(running_references))

results := $(patsubst %/,%,$(RESULTS))

log_target := $(patsubst __%,%,$(or $(firstword $(MAKECMDGOALS)),default))
LOGFILE := $(results)/logs/$(shell date '+%Y%m%d_%H%M%S')_$(log_target).log
export tmpdir := $(shell mktemp -d -t scbolt-XXXXXXXXXX)
$(shell { trap 'rm -rf $(tmpdir);' EXIT; tail --pid=$$PPID -f /dev/null; } </dev/null >/dev/null 2>/dev/null &)
$(shell mkdir -p $(results))

## BEGIN URLS ##

cycle_url := https://github.com/MarioniLab/scran/raw/master/inst/exdata/mouse_cycle_markers.rds
go_basic_url := http://purl.obolibrary.org/obo/go/go-basic.obo
geiger_url := https://doi.org/10.1371/journal.pbio.2003389.s025
chambers_url := https://ars.els-cdn.com/content/image/1-s2.0-S1934590907002202-mmc3.xls
gene2go_url := ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/gene2go.gz

## END URLS ##

## BEGIN COLORS ##

nc        = \033[0m
green     = \033[0;32m
bold      = \033[1m

## END COLORS ##

## BEGIN FUNCTIONS ##

log = printf '%s - %s - %s\n' "`date '+%Y-%m-%d %H:%M:%S.%3N'`" "$(1)" "$(2)"

print_rule    = $(call log,RULE,$(1)$(if $(2), (reference: $(2))))
print_task    = $(call log,TASK,$(1))
print_info    = $(call log,INFO,$(1))
print_warning = $(call log,WARNING,$(1))
print_debug   = $(call log,DEBUG,$(1))
print_error   = $(call log,ERROR,$(1)); exit 1

check_file = [ -n "$(1)" ] || { $(call print_error,required file parameter not defined: $(2)); }; [ -f "$(1)" ] || { $(call print_error,required file not found: $(1)); }
check_command = command -v $(1) >/dev/null 2>&1 || { $(call print_error,required command not found: $(1)); }
check_conda_env = conda env list | awk '{print $$1}' | grep -qx "$(1)" || { $(call print_error,required conda environment not found: $(1)); }
check_parameter = [ -n "$(strip $(1))" ] || { $(call print_error,required parameter not defined: $(2)); }
report_check_error = missing=1; $(call log,ERROR,$(1))
check_file_diagnostic = if [ -z "$(1)" ]; then $(call report_check_error,required file parameter not defined: $(2)); elif [ ! -f "$(1)" ]; then $(call report_check_error,required file not found: $(1)); fi
check_command_diagnostic = command -v $(1) >/dev/null 2>&1 || { $(call report_check_error,required command not found: $(1)); }
check_conda_env_diagnostic = conda env list | awk '{print $$1}' | grep -qx "$(1)" || { $(call report_check_error,required conda environment not found: $(1)); }
check_parameter_diagnostic = [ -n "$(strip $(1))" ] || { $(call report_check_error,required parameter not defined: $(2)); }
knnbs_centrality = $(KNNBS_CENTRALITY_$(call toupper,$(1)))
knnbs_periphery = $(KNNBS_PERIPHERY_$(call toupper,$(1)))

conda_run = conda run --no-capture-output -n $(1)
inference_timeout = $(if $(filter-out 0,$(strip $(1))),timeout --foreground $(strip $(1)),)

ifndef LOGGING
$(error Parameter LOGGING not defined)
else ifeq ($(LOGGING),true)
run_logged = \
	mkdir -p $(dir $(LOGFILE)); \
	{ \
		printf 'DATE=%s\n' "`date '+%Y-%m-%d %H:%M:%S'`"; \
		printf 'TARGET=%s\n' "$(1)"; \
		printf 'RESULTS=%s\n' "$(RESULTS)"; \
		printf 'PARAMS=%s\n' "$(PARAMS)"; \
		printf 'SEED=%s\n' "$(SEED)"; \
		printf 'JOBS=%s\n' "$(JOBS)"; \
		printf 'CONDITIONS=%s\n' "$(CONDITIONS)"; \
		printf 'LOGFILE=%s\n' "$(LOGFILE)"; \
		printf 'GIT_HASH=%s\n' "`git rev-parse HEAD 2>/dev/null || echo unknown`"; \
		printf '\n'; \
	} >> "$(LOGFILE)"; \
	PYTHONUNBUFFERED=1 TQDM_TO_TTY=1 $(MAKE) LOGGING=false __$(1) LOGFILE="$(LOGFILE)" 2>&1 | tee -a "$(LOGFILE)"
else ifeq ($(LOGGING),false)
run_logged = $(MAKE) LOGGING=false __$(1) LOGFILE="$(LOGFILE)"
else
$(error Unsupported value for parameter LOGGING (supported values: true, false))
endif

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

define check_inference_status
	if [ $$exit_status -eq 124 ]; then \
		echo -e ''; \
		if [ -s $@ ]; then \
			echo "_LOCAL_OPTIMUM" > $(@D)/__SOLUTION; \
			$(call print_warning,user-defined time limit reached \($(1)\): local optimum found); \
		else \
			echo "_FAILURE" > $(@D)/__SOLUTION; \
			$(call print_error,user-defined time limit reached \($(1)\): no solution found); \
		fi; \
	elif [ $$exit_status -eq 130 ] || [ $$exit_status -eq 143 ]; then \
		echo -e ''; \
		if [ -s $@ ]; then \
			echo "_PARTIAL_SOLUTIONS" > $(@D)/__SOLUTION; \
			$(call print_warning,inference interrupted: keeping partial solutions); \
		else \
			echo "_FAILURE" > $(@D)/__SOLUTION; \
			$(call log,ERROR,inference interrupted: no partial solution found); \
		fi; \
		exit $$exit_status; \
	elif [ $$exit_status -ne 0 ]; then \
		echo "_FAILURE" > $(@D)/__SOLUTION; \
		exit $$exit_status; \
	else \
		echo "_GLOBAL_OPTIMUM" > $(@D)/__SOLUTION; \
		$(call print_debug,global optimum found); \
	fi
endef

define check_partial_bn_outputs
@if [ -d "$(1)" ] && [ ! -f "$(1)/.done" ]; then \
	echo "" > /dev/tty; \
	echo "Detected incomplete outputs for target '$(2)'." > /dev/tty; \
	echo "Output directory: $(1)" > /dev/tty; \
	echo "" > /dev/tty; \
	printf "Remove partial outputs and rerun inference? [y/N] " > /dev/tty; \
	read ans; \
	if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ]; then \
		rm -rf "$(1)"; \
		echo "Partial outputs removed." > /dev/tty; \
	else \
		echo "Inference aborted." > /dev/tty; \
		exit 1; \
	fi; \
fi
endef

## END FUNCTIONS ##

## BEGIN PATHS ##

cc_markers  = public/cycle/mouse_cycle_markers.rds
signatures  = public/signatures/geiger.xls public/signatures/chambers.xls public/signatures/sig.json
go_basic    = public/go/go_basic.obo
go_organism = public/go/goslim_$(ORGANISM).obo
gene2go     = public/go/gene2go
dorothea_legacy = public/omnipath/dorothea_legacy_$(ORGANISM).csv

$(eval genome_ref := public/ref/$(notdir $(genome_url)))
genome_ref := $(genome_ref:.tar.gz=)

define find_paths_for_conditions

fastq_$(1) =                    $(results)/$(1)/fastq
cellranger_$(1) =               $(results)/$(1)/count/cellranger/$(1).mri.tgz
velocyto_$(1) =                 $(results)/$(1)/count/counts.h5ad
filtering_$(1) =                $(results)/$(1)/prep/filter/counts.h5ad
normalization_$(1) =            $(results)/$(1)/prep/norm/counts.h5ad
velocity_$(1) =                 $(results)/$(1)/trajectories/velocity/velocity.h5ad
potency_$(1) =                  $(results)/$(1)/trajectories/potency/potency.csv
cotan_$(1) =                    $(results)/$(1)/mstates/cotan/mstates.h5ad    $(results)/$(1)/mstates/cotan/mstates.csv
cellrank_$(1) =                 $(results)/$(1)/mstates/cellrank/mstates.h5ad $(results)/$(1)/mstates/cellrank/mstates.csv
stream_$(1) =                   $(results)/$(1)/mstates/stream/mstates.h5ad   $(results)/$(1)/mstates/stream/mstates.csv
knnbs_$(1) =                    $(results)/$(1)/mstates/knnbs/mstates.h5ad    $(results)/$(1)/mstates/knnbs/mstates.csv

ifeq ($(MACROSTATE_METHOD),cotan)
macrostates_$(1) =              $$(cotan_$(1))
else ifeq ($(MACROSTATE_METHOD),cellrank)
macrostates_$(1) =              $$(cellrank_$(1))
else ifeq ($(MACROSTATE_METHOD),stream)
macrostates_$(1) =              $$(stream_$(1))
else ifeq ($(MACROSTATE_METHOD),knnbs)
macrostates_$(1) =              $$(knnbs_$(1))
else
$$(error unsupported value for parameter MACROSTATE_METHOD (supported values: cotan, cellrank, stream, knnbs))
endif

endef

define find_paths_for_references

clustering_$(1) =               $(results)/$(1)/clust/clust.h5ad
dea_$(1) =                      $(results)/$(1)/clust/dea/markers.csv         $(results)/$(1)/clust/dea/genes.xlsx
scoring_$(1) =                  $(results)/$(1)/clust/sig.csv
goea_basic_$(1) =               $(results)/$(1)/clust/goea/basic.xlsx
goea_organism_$(1) =            $(results)/$(1)/clust/goea/$(ORGANISM).xlsx
annotation_$(1) =               $(results)/$(1)/clust/annot.h5ad

endef

bin_cells =                     $(results)/bin/scboolseq/cell/cells_bin.h5ad  $(results)/bin/scboolseq/cell/cells_stats.csv
bin_macrostates =               $(results)/bin/scboolseq/macro/$(MACROSTATE_METHOD)/mstates_bin.csv
bin_dea =                       $(results)/bin/dea/$(MACROSTATE_METHOD)/mstates_bin.csv
bin_consensus =                 $(results)/bin/consensus/$(MACROSTATE_METHOD)/mstates_bin.csv

bonesis_model =                 $(results)/infer/spec/model.bo $(results)/infer/spec/mstates.csv $(results)/infer/spec/important.txt $(results)/infer/spec/mandatory.txt
max_nodes_soft =                $(results)/infer/genes/soft/comps.txt
max_consts_soft =               $(results)/infer/genes/consts/comps.txt
max_nodes_relaxed =             $(results)/infer/genes/relaxed/comps.txt
max_nodes_seed =                $(results)/infer/genes/seed/comps.txt
max_nodes_lock =                $(results)/infer/genes/lock/comps.txt
bn_min =                        $(results)/infer/bn/min/model.bnet

bn_submin_dir = $(results)/infer/bn/submin
ifneq ($(filter-out 0,$(strip $(INFER_LIMIT))),)
bn_submin_indices := $(shell seq 0 $$(($(INFER_LIMIT)-1)))
bn_submin = $(foreach i,$(bn_submin_indices),$(bn_submin_dir)/$(i)/model.bnet $(bn_submin_dir)/$(i)/state.cfg)
else
bn_submin = $(bn_submin_dir)/.done
endif

bn_diverse_dir = $(results)/infer/bn/diverse
ifneq ($(filter-out 0,$(strip $(INFER_LIMIT))),)
bn_diverse_indices := $(shell seq 0 $$(($(INFER_LIMIT)-1)))
bn_diverse = $(foreach i,$(bn_diverse_indices),$(bn_diverse_dir)/$(i)/model.bnet $(bn_diverse_dir)/$(i)/state.cfg)
else
bn_diverse = $(bn_diverse_dir)/.done
endif

$(foreach condition,$(conditions),$(eval $(call find_paths_for_conditions,$(condition))))
$(foreach reference,$(references),$(eval $(call find_paths_for_references,$(reference))))

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
velocity_target :=
potency_target :=
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
$(eval velocity_target := $(velocity_target) $(velocity_$(1)))
$(eval potency_target := $(potency_target) $(potency_$(1)))
$(eval cotan_target := $(cotan_target) $(cotan_$(1)))
$(eval cellrank_target := $(cellrank_target) $(cellrank_$(1)))
$(eval stream_target := $(stream_target) $(stream_$(1)))
$(eval knnbs_target := $(knnbs_target) $(knnbs_$(1)))
$(eval macrostates_target := $(macrostates_target) $(macrostates_$(1)))

endef

define find_targets_for_references

$(eval clustering_target := $(clustering_target) $(clustering_$(1)))
$(eval dea_target := $(dea_target) $(dea_$(1)))
$(eval scoring_target := $(scoring_target) $(scoring_$(1)))
$(eval goea_target := $(goea_target) $(goea_basic_$(1)) $(goea_organism_$(1)))
$(eval annotation_target := $(annotation_target) $(annotation_$(1)))

endef

$(foreach condition,$(running_conditions),$(eval $(call find_targets_for_conditions,$(condition))))
$(foreach reference,$(running_references),$(eval $(call find_targets_for_references,$(reference))))

## END TARGETS ##

ifeq ($(words $(CONDITIONS)),1)
batch =
else
batch = --batch condition
endif

## BEGIN PARAMETERS ##

ifndef JOBS
$(error Parameter JOBS not defined)
else
try_open_allocated_cpu := $(shell echo $$(($(JOBS) / 2)))
open_allocated_cpu := $(if $(findstring $(try_open_allocated_cpu),0),1,$(try_open_allocated_cpu))
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
  ifneq ($(ORGANISM),mouse)
    $(error CC_CORRECTION=true is only supported for mouse (current: $(ORGANISM)))
  endif
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

label_ids = $(if $(LABEL),$(shell seq 0 1 $$(($(words $(LABEL))-1))))
label_map = $(join $(label_ids),$(addprefix :,$(LABEL)))

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

ifndef SCBOOLSEQ_HVG_METHOD
scboolseq_layer=
else ifeq ($(SCBOOLSEQ_HVG_METHOD),seurat)
scboolseq_layer=--layer log-norm
else ifeq ($(SCBOOLSEQ_HVG_METHOD),cell_ranger)
scboolseq_layer=--layer log-norm
else ifeq ($(SCBOOLSEQ_HVG_METHOD),seurat_v3)
scboolseq_layer=--layer counts
ifndef SCBOOLSEQ_TOP_HVG
$(error parameter SCBOOLSEQ_TOP_HVG is required when parameter SCBOOLSEQ_HVG_METHOD is equal to seurat_v3)
endif
else
$(error Unsupported value for parameter SCBOOLSEQ_HVG_METHOD (supported values: seurat, cell_ranger, seurat_v3))
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

ifndef DEA_HVG_METHOD
dea_layer=
else ifeq ($(DEA_HVG_METHOD),seurat)
dea_layer=--layer log-norm
else ifeq ($(DEA_HVG_METHOD),cell_ranger)
dea_layer=--layer log-norm
else ifeq ($(DEA_HVG_METHOD),seurat_v3)
dea_layer=--layer counts
ifndef DEA_TOP_HVG
$(error parameter DEA_TOP_HVG is required when parameter DEA_HVG_METHOD is equal to seurat_v3)
endif
else
$(error Unsupported value for parameter DEA_HVG_METHOD (supported values: seurat, cell_ranger, seurat_v3))
endif

ifeq ($(BIN_METHOD),scboolseq)
default_bin = $(bin_macrostates)
else ifeq ($(BIN_METHOD),dea)
default_bin = $(bin_dea)
else ifeq ($(BIN_METHOD),consensus)
default_bin = $(bin_consensus)
else
$(error unsupported value for parameter BIN_METHOD (supported values: scboolseq, dea, consensus))
endif
bin = $(if $(BINARIZATION_FILE),$(BINARIZATION_FILE),$(default_bin))

ifndef YAML_MODEL
$(error Parameter YAML_MODEL not defined)
endif

ifneq ($(filter-out seurat_v3 seurat cell_ranger,$(MODEL_HVG_METHOD)),)
$(error Unsupported value for parameter MODEL_HVG_METHOD (supported values: seurat, cell_ranger, seurat_v3))
endif

known_prior_knowledge = collectri dorothea
dorothea_apis = current legacy
dorothea_levels = A B C D

ifndef PRIOR_KNOWLEDGE
$(error Parameter PRIOR_KNOWLEDGE not defined)
endif

ifneq ($(filter-out $(dorothea_levels),$(DOROTHEA_LEVELS)),)
$(error Unsupported value for parameter DOROTHEA_LEVELS (supported values: $(subst $(space),$(comma) ,$(strip $(dorothea_levels)))))
endif

# Resolve the user-facing prior knowledge parameter to the actual domain passed
# to BoNesis scripts. Only dorothea+legacy is materialized as a custom file,
# because decoupler.get_dorothea lives in the legacy environment.
ifeq ($(PRIOR_KNOWLEDGE),collectri)
prior_knowledge = collectri
else ifeq ($(PRIOR_KNOWLEDGE),dorothea)
ifneq ($(filter $(strip $(DOROTHEA_API)),$(dorothea_apis)),)
ifeq ($(strip $(DOROTHEA_API)),legacy)
prior_knowledge = $(dorothea_legacy)
else
prior_knowledge = dorothea
endif
else
$(error Unsupported value for parameter DOROTHEA_API (supported values: $(subst $(space),$(comma) ,$(strip $(dorothea_apis)))))
endif
else ifneq ($(wildcard $(PRIOR_KNOWLEDGE)),)
prior_knowledge = $(PRIOR_KNOWLEDGE)
else
$(error Unsupported value for parameter PRIOR_KNOWLEDGE (supported values: $(subst $(space),$(comma) ,$(strip $(known_prior_knowledge))) or an existing file path))
endif
dorothea_levels_arg = $(if $(filter dorothea,$(prior_knowledge)),$(if $(strip $(DOROTHEA_LEVELS)),--dorothea-levels $(DOROTHEA_LEVELS)))

ifndef MODEL_HVG_METHOD
model_layer=
else ifeq ($(MODEL_HVG_METHOD),seurat)
model_layer=--layer log-norm
else ifeq ($(MODEL_HVG_METHOD),cell_ranger)
model_layer=--layer log-norm
else ifeq ($(MODEL_HVG_METHOD),seurat_v3)
model_layer=--layer counts
ifndef MODEL_TOP_HVG
$(error parameter MODEL_TOP_HVG is required when parameter MODEL_HVG_METHOD is equal to seurat_v3)
endif
else
$(error Unsupported value for parameter MODEL_HVG_METHOD (supported values: seurat, cell_ranger, seurat_v3))
endif

ifndef MIN_SELF_LOOP_CONSTS
$(error Parameter MIN_SELF_LOOP_CONSTS not defined)
else ifeq ($(MIN_SELF_LOOP_CONSTS),true)
min_self_loop_consts=--minimize-self-loops
else ifeq ($(MIN_SELF_LOOP_CONSTS),false)
min_self_loop_consts=
else
$(error Unsupported value for parameter MIN_SELF_LOOP_CONSTS (supported values: true, false))
endif

ifndef MIN_SELF_LOOP_INFER
$(error Parameter MIN_SELF_LOOP_INFER not defined)
else ifeq ($(MIN_SELF_LOOP_INFER),true)
min_self_loop_infer:=--minimize-self-loops
else ifeq ($(MIN_SELF_LOOP_INFER),false)
min_self_loop_infer:=
else
$(error Unsupported value for parameter MIN_SELF_LOOP_INFER (supported values: true, false))
endif

## END PARAMETERS ##

## BEGIN HELP ##

##@ Utilities

.PHONY: help
help: ## display this help and exit
	@awk 'BEGIN {FS = ":.*##"; printf "usage: make $(green)<module>$(nc) [REFERENCES=<...>] (current value:$(subst $(space),$(plus),$(references)))\n\n\
	scBOLT is a semi-automated pipeline for Boolean network inference from multi-condition single-cell transcriptomes. \
	The workflow includes: alignment and preprocessing, integration and clustering, cell annotation, trajectory inference, \
	macrostate characterization, macrostate binarization, Boolean constraint specification, gene selection, \
	and Boolean network inference.\n"}/^[a-zA-Z_-]+:.*?##/ \
	{ printf "  $(green)%-22s$(nc) %s\n", $$1, $$2 } /^##@/ { printf "\n$(bold)%s$(nc)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.PHONY: config
config: ## display effective configuration and exit
	$(eval config_candidates := $(filter A% B% C% D% E% F% G% H% I% J% K% L% M% N% O% P% Q% R% S% T% U% V% W% X% Y% Z%,$(.VARIABLES)))
	$(eval config_vars := $(sort $(foreach var,$(config_candidates),$(if $(filter file command line override,$(origin $(var))),$(var)))))
	$(eval config_vars := $(filter-out LOGFILE TARGET DEFAULT_PARAMS __check_externals__ MAKEFLAGS MAKEFILE_LIST MAKECMDGOALS SHELL,$(config_vars)))
	$(foreach var,$(config_vars),$(info $(var)=$($(var))))
	@:

.PHONY: check
check: ## check Make-level dependencies, configuration and external tools required to build TARGET
	@if [ -z "$(TARGET)" ]; then \
		$(call print_error,missing TARGET \(usage: make check TARGET=<module>\)); \
	fi
	@dry_run="$$(mktemp)"; \
	missing=0; \
	$(MAKE) --always-make --dry-run LOGGING=false __$(TARGET) LOGFILE="$(LOGFILE)" > "$${dry_run}"; \
	if [ "$(__check_externals__)" = "true" ]; then \
		$(call check_command_diagnostic,conda); \
		for env in $$({ grep -oE 'conda run[^;|&]* -n [^ ]+' "$${dry_run}" || true; } | awk '{print $$NF}' | sort -u); do \
			$(call check_conda_env_diagnostic,$${env}); \
		done; \
		if grep -qE '(^|[[:space:]])cellranger count([[:space:]]|$$)' "$${dry_run}"; then \
			$(call check_command_diagnostic,cellranger); \
		fi; \
		if grep -q 'repeat_msk.gtf' "$${dry_run}"; then \
			$(call check_file_diagnostic,public/transcriptome/repeat_msk.gtf,repeat_msk.gtf); \
		fi; \
	fi; \
	if grep -q 'scripts/inference/specification.py' "$${dry_run}"; then \
		$(call check_file_diagnostic,$(YAML_MODEL),YAML_MODEL); \
	fi; \
	if grep -q -- '--solution $(max_nodes_seed)' "$${dry_run}"; then \
		$(call check_parameter_diagnostic,$(TIMEOUT_SEED),TIMEOUT_SEED (needed by target '$(TARGET)')); \
	fi; \
	if grep -q 'parallel-fastq-dump' "$${dry_run}"; then \
		$(foreach condition,$(running_conditions),$(call check_parameter_diagnostic,$(SRA_$(call toupper,$(condition))),SRA_$(call toupper,$(condition)) (needed by target '$(TARGET)'));) \
	fi; \
	if grep -q 'scripts/clustering/annotation.py' "$${dry_run}"; then \
		$(call check_parameter_diagnostic,$(LABEL),LABEL (needed by target '$(TARGET)')); \
	fi; \
	if grep -q 'scripts/macrostates/knnbs_macrostates.py' "$${dry_run}" || grep -q 'KNNBS_CENTRALITY_' "$${dry_run}"; then \
		$(foreach condition,$(running_conditions),$(call check_parameter_diagnostic,$(call knnbs_centrality,$(condition)) $(call knnbs_periphery,$(condition)),KNNBS_CENTRALITY_$(call toupper,$(condition)) or KNNBS_PERIPHERY_$(call toupper,$(condition)) (needed by target '$(TARGET)'));) \
	fi; \
	if grep -q -- '--graph-formats' "$${dry_run}"; then \
		if [ "$(__check_externals__)" = "true" ]; then \
			$(foreach program,$(GRAPH_FORMATS),$(call check_command_diagnostic,$(program));) \
		fi; \
	fi; \
	if [ "$${missing}" -ne 0 ]; then \
		rm -f "$${dry_run}"; \
		$(call print_error,check failed for target '$(TARGET)'); \
	fi; \
	rm -f "$${dry_run}"; \
	$(call print_debug,configuration and tools successfully checked for target '$(TARGET)')

.PHONY: dry-run
dry-run: ## display modules required to build TARGET without executing them
	@if [ -z "$(TARGET)" ]; then \
		$(call print_error,missing TARGET \(usage: make dry-run TARGET=<module>\)); \
	fi
	$(MAKE) --dry-run LOGGING=false __$(TARGET) LOGFILE="$(LOGFILE)"

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
	test -n "$(results)" && test "$(results)" != "/"
	rm -rf $(results)
	mkdir -p $(results)
	[ ! -d public/transcriptome ] || find public/transcriptome ! -name "repeat_msk.gtf" -type f -exec rm -f "{}" \;

##@ Download

.PHONY: load-genome __load-genome
load-genome: ## download the reference genome
	$(call run_logged,load-genome)
__load-genome: $(genome_ref)

.PHONY: load-fastq __load-fastq
load-fastq: ## download FASTQ files
	$(call run_logged,load-fastq)
__load-fastq: $(fastq_target)

.PHONY: load-signatures __load-signatures
load-signatures: ## download phenotype-related signatures
	$(call run_logged,load-signatures)
__load-signatures: $(lastword $(signatures))

.PHONY: load-cc __load-cc
load-cc: ## download cell-cycle markers
	$(call run_logged,load-cc)
__load-cc: $(cc_markers)

.PHONY: load-go __load-go
load-go: ## download Gene Ontology resources
	$(call run_logged,load-go)
__load-go: $(go_basic) $(go_organism) $(gene2go)

.PHONY: load-dorothea __load-dorothea
load-dorothea: ## download DoRothEA through the legacy decoupler wrapper
	$(call run_logged,load-dorothea)
__load-dorothea: $(dorothea_legacy)

##@ Alignment/Counting

.PHONY: cellranger __cellranger
cellranger: ## run Cell Ranger for alignment and counting
	$(call run_logged,cellranger)
__cellranger: $(cellranger_target)

.PHONY: velocyto __velocyto
velocyto: ## run Velocyto for spliced and unspliced counting
	$(call run_logged,velocyto)
__velocyto: $(velocyto_target)

##@ Preprocessing

.PHONY: filtering __filtering
filtering: ## filter low-quality cells and genes, and optionally assign cell-cycle phases
	$(call run_logged,filtering)
__filtering: $(filtering_target)

.PHONY: normalization __normalization
normalization: ## normalize counts and optionally correct for cell-cycle effects
	$(call run_logged,normalization)
__normalization: $(normalization_target)

##@ Clustering

.PHONY: clustering __clustering
clustering: ## cluster cells after dimensionality reduction, with optional integration
	$(call run_logged,clustering)
__clustering: $(clustering_target)

.PHONY: dea __dea
dea: ## identify cluster-specific upregulated genes for marker detection
	$(call run_logged,dea)
__dea: $(dea_target)

.PHONY: scoring __scoring
scoring: ## score phenotype-related signatures to support cluster annotation
	$(call run_logged,scoring)
__scoring: $(scoring_target)

.PHONY: goea __goea
goea: ## perform Gene Ontology enrichment analysis to support cluster annotation
	$(call run_logged,goea)
__goea: $(goea_target)

.PHONY: annotation __annotation
annotation: ## assign names to cell clusters
	$(call run_logged,annotation)
__annotation: $(annotation_target)

##@ Trajectory inference

.PHONY: velocity __velocity
velocity: ## estimate RNA velocity to infer cell-state transitions
	$(call run_logged,velocity)
__velocity: $(velocity_target)

.PHONY: potency __potency
potency: ## estimate cell differentiation potential
	$(call run_logged,potency)
__potency: $(potency_target)

##@ Macrostate characterization

.PHONY: cotan __cotan
cotan: ## estimate macrostates from zero-count co-expression
	$(call run_logged,cotan)
__cotan: $(cotan_target)

.PHONY: cellrank __cellrank
cellrank: ## estimate macrostates using similarity-, potency-, and RNA-velocity-based kernels
	$(call run_logged,cellrank)
__cellrank: $(cellrank_target)

.PHONY: stream __stream
stream: ## estimate macrostates using an elastic principal graph
	$(call run_logged,stream)
__stream: $(stream_target)

.PHONY: knnbs __knnbs
knnbs: ## estimate macrostates using k-nearest-neighbors-based subclustering
	$(call run_logged,knnbs)
__knnbs: $(knnbs_target)

.PHONY: macrostates __macrostates
macrostates: ## define groups of cells sharing similar phenotypic profiles according to MACROSTATE_METHOD
	$(call run_logged,macrostates)
__macrostates: $(macrostates_target)

##@ Binarization

.PHONY: bin-cells __bin-cells
bin-cells: ## binarize cells using gene-specific distributions from ScBoolSeq
	$(call run_logged,bin-cells)
__bin-cells: $(bin_cells)

.PHONY: bin-macrostates __bin-macrostates
bin-macrostates: ## binarize macrostates by aggregating ScBoolSeq-binarized cells using voting rules
	$(call run_logged,bin-macrostates)
__bin-macrostates: $(bin_macrostates)

.PHONY: bin-dea __bin-dea
bin-dea: ## binarize macrostates using differential expression analysis
	$(call run_logged,bin-dea)
__bin-dea: $(bin_dea)

.PHONY: bin-consensus __bin-consensus
bin-consensus: ## binarize macrostates by combining ScBoolSeq and DEA results
	$(call run_logged,bin-consensus)
__bin-consensus: $(bin_consensus)

.PHONY: binarization __binarization
binarization: ## derive partially defined Boolean states from macrostates according to BIN_METHOD
	$(call run_logged,binarization)
__binarization: $(bin)

##@ Boolean network inference

.PHONY: spec __spec
spec: ## specify Boolean constraints using the BoNesis language
	$(call run_logged,spec)
__spec: $(bonesis_model)

.PHONY: max-nodes-soft __max-nodes-soft
max-nodes-soft: ## maximise nodes without non-reachability and universal constraints (soft constraints)
	$(call run_logged,max-nodes-soft)
__max-nodes-soft: $(max_nodes_soft)

.PHONY: max-consts-soft __max-consts-soft
max-consts-soft: ## maximise strong constants without non-reachability and universal constraints (soft constraints)
	$(call run_logged,max-consts-soft)
__max-consts-soft: $(max_consts_soft)

.PHONY: max-nodes-relaxed __max-nodes-relaxed
max-nodes-relaxed: ## maximise nodes without universal constraints (relaxed constraints)
	$(call run_logged,max-nodes-relaxed)
__max-nodes-relaxed: $(max_nodes_relaxed)

.PHONY: max-nodes-seed __max-nodes-seed
max-nodes-seed: ## maximise nodes (hard constraints, stage 1)
	$(call run_logged,max-nodes-seed)
__max-nodes-seed: $(max_nodes_seed)

.PHONY: max-nodes-lock __max-nodes-lock
max-nodes-lock: ## maximise nodes (hard constraints, stage 2)
	$(call run_logged,max-nodes-lock)
__max-nodes-lock: $(max_nodes_lock)

.PHONY: bn-min __bn-min
bn-min: ## infer a minimum-edge Boolean network with BoNesis (one minimal solution)
	$(call run_logged,bn-min)
__bn-min: $(bn_min)

.PHONY: bn-submin __bn-submin
bn-submin: ## enumerate subset-minimal Boolean network solutions
	$(call run_logged,bn-submin)
__bn-submin: $(bn_submin)

.PHONY: bn-diverse __bn-diverse
bn-diverse: ## sampling of diverse sparsest Boolean network solutions
	$(call run_logged,bn-diverse)
__bn-diverse: $(bn_diverse)

## END HELP ##

## preserve target even if make is killed or interrupted
.PRECIOUS: $(max_nodes_soft)
.PRECIOUS: $(max_consts_soft)
.PRECIOUS: $(max_nodes_seed)
.PRECIOUS: $(max_nodes_lock)
.PRECIOUS: $(dir $(bn_submin))
.PRECIOUS: $(dir $(bn_diverse))

$(bin_cells)&: export OPENBLAS_NUM_THREADS = $(open_allocated_cpu)
$(bin_cells)&: export OMP_NUM_THREADS = $(open_allocated_cpu)

## BEGIN RULES ##

$(genome_ref):
	$(call print_rule,load-genome)
	mkdir -p $(@D)
	wget --quiet --show-progress -cO $@.tar.gz $(genome_url)
	tar -zxvf $@.tar.gz -C $(@D)
	[ -f $@/genes/genes.gtf.gz ] && gunzip $@/genes/genes.gtf.gz

$(cc_markers):
	$(call print_rule,load-cc)
	mkdir -p $(@D)
	wget --quiet --show-progress -cO $@ $(cycle_url)

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
	$(call conda_run,scbolt-core) python scripts/utils/load_signatures.py \
		--list-infile $(firstword $^) \
		--table-infile $(lastword $^) \
		--outfile $@

$(go_basic):
	$(call print_rule,load-go,go_basic)
	mkdir -p $(@D)
	wget --quiet --show-progress -cO $@ $(go_basic_url)

$(go_organism):
	$(call print_rule,load-go,go_$(ORGANISM))
	mkdir -p $(@D)
	wget --quiet --show-progress -cO $@ $(go_organism_url)

$(gene2go):
	$(call print_rule,load-go,gene2go)
	mkdir -p $(@D)
	wget --quiet --show-progress --directory-prefix=$(@D) $(gene2go_url)
	[ -f $@.gz ] && gunzip $@.gz

$(dorothea_legacy):
	$(call print_rule,load-dorothea)
	mkdir -p $(@D)
	$(call conda_run,scbolt-decoupler-legacy) python scripts/utils/load_dorothea_legacy.py \
		--organism $(ORGANISM) \
		--outfile $@

define compute_rules_for_conditions

$(fastq_$(1)):
	$(call print_rule,load-fastq,$(1))
	$$(call check_parameter,$$(SRA_$(call toupper, $(1))),SRA_$(call toupper, $(1)) \(needed by target 'load-fastq'\))
	sample_naming="$(1)"
	lane=0
	rm -rf $(tmpdir)/$(1)/fastq && mkdir -p $(tmpdir)/$(1)/fastq
	for id in $$(SRA_$(call toupper, $(1)))
	do
		((++lane))
		$(call conda_run,scbolt-fastq) parallel-fastq-dump --sra-id $$$${id} --split-files --readids --origfmt --threads $$(JOBS) --outdir $(tmpdir)/$(1)/fastq --gzip
		$$(call fastq_naming,$(tmpdir)/$(1)/fastq,$$$${id},$$$${sample_naming},$$$${lane})
	done
	sleep 3
	mkdir -p $$@
	files=$$$$(shopt -s nullglob dotglob; echo $(tmpdir)/$(1)/fastq/*)
	if (( $$$${#files} )); then \
		mv $$$${files} $$@/; \
		rm -rf $(tmpdir)/$(1)/fastq; \
	else \
		$(call print_error,cannot download fastq files: fastq-dump failed); \
	fi
	unset files

$(cellranger_$(1)): $(fastq_$(1)) $(genome_ref)
	$(call print_rule,cellranger,$(1))
	mkdir -p $(tmpdir)/cellranger $$(@D)
	(
		cd $(tmpdir)/cellranger
		cellranger count --id=$(1) \
			--fastqs=$$(realpath $$(firstword $$^)) \
			--transcriptome=$$(realpath $$(lastword $$^)) \
			--create-bam true \
			--localcores=$(JOBS) \
			--localmem=$(MEMORY)
	)
	mv $(tmpdir)/cellranger/$(1)/* $$(@D)
	rm -rf $(tmpdir)/cellranger/$(1)

$(velocyto_$(1)): $(cellranger_$(1)) $(genome_ref)
	$(call print_rule,velocyto,$(1))
	$(call check_file,public/transcriptome/repeat_msk.gtf,repeat_msk.gtf)
	$(call conda_run,scbolt-velocyto) velocyto run10x \
		-m public/transcriptome/repeat_msk.gtf \
		--samtools-threads $(JOBS) --samtools-memory $(MEMORY) \
		$$(dir $$(firstword $$^)) $$(lastword $$^)/genes/genes.gtf
	mkdir -p $$(@D)
	mv $$(<D)/velocyto/cellranger.loom $$(shell echo $$@ | sed "s/h5ad/loom/")
	rm -rf $$(<D)/velocyto
	$(call print_debug,standardizing gene names and converting loom to h5ad)
	$(call conda_run,scbolt-core) python scripts/utils/adata_conversion.py \
		$$(shell echo $$@ | sed "s/h5ad/loom/") $$@ --from loom --to h5ad \
		--remove-positions --sort --standardization

$(filtering_$(1)): $(velocyto_$(1)) $(if $(filter mouse,$(ORGANISM)),$(cc_markers))
	$(call print_rule,filtering,$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python scripts/preprocessing/filtering.py \
		$$(firstword $$^) $$@ $(if $(filter mouse,$(ORGANISM)),--marker $$(lastword $$^)) \
		--gene-dropout $(GENE_DROPOUT) --gene-expression $(GENE_EXPRESSION) --gene-counts $(GENE_COUNTS) \
		--cell-dropout $(CELL_DROPOUT) --cell-expression $(CELL_EXPRESSION) --cell-reads $(CELL_READS) \
		--mad-deviation $(MAD_DEVIATION) $(norm_mad) --mt $(MT) \
		--hvg $(HVG) $(filter_non_hvg)

$(normalization_$(1)): $(filtering_$(1))
	$(call print_rule,normalization,$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python scripts/preprocessing/normalization.py $$< $$@ $(correction) --jobs $(JOBS)

$(clustering_$(1)): $(normalization_$(1))
	$(call print_rule,clustering,$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python scripts/clustering/clustering.py $$< $$@ \
		--layer correct --adjacency knn --embedding umap \
		--pca-dimension $(DIM_PCA) --clustering-dimension $(DIM_CLUSTERING) --embedding-dimension $(DIM_EMBEDDING) \
		$(pca_only_hvg) --neighbors $(NEIGHBORS) --metric $(METRIC) --resolution $(RESOLUTION) --min-dist $(MIN_DIST) --spread $(SPREAD) --seed $(SEED)
	$(call print_task,plotting embedding colored by cell-cycle phase)
	$(call conda_run,scbolt-core) python fig/plot_embedding.py fig/cc.json --infile $$@ --outfile $$(@D)/cc.pdf --use-rep $(USE_REP)

$(annotation_$(1)): $(annotation_integrated) $(clustering_$(1))
	$(call print_rule,annotation,$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python scripts/utils/pipe_its.py $$^ --outfiles $$@ --labels $(1) --obs-label condition --obs $(LABEL_COL)
	$(call print_task,plotting embedding colored by labels)
	$(call conda_run,scbolt-core) python fig/plot_embedding.py fig/generic.json --infile $$@ --outfile $$(@D)/labels.pdf --obs $(LABEL_COL) --use-rep $(USE_REP)

$(velocity_$(1)): $(annotation_$(1))
	$(call print_rule,velocity,$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-velocity) python scripts/trajectories/velocity.py $$< $$@ \
		--layer counts --cluster label --moment-dimension $(DIM_MOMENT) \
		$(velocity_only_hvg) --mode $(SMM_MODE) --embedding umap --jobs $(JOBS)

$(potency_$(1)): $(annotation_$(1))
	$(call print_rule,potency,$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-potency) python scripts/trajectories/potency.py $$< $$(@D) \
		--csv $$(notdir $$@) --h5ad $$(basename $$(notdir $$@)).h5ad \
		--layer counts --cluster label --batch-size $(BATCH_SIZE) --smooth-batch-size $(SMOOTH_BATCH_SIZE) \
		--organism $(ORGANISM) --embedding umap --seed $(SEED) --jobs $(JOBS)

$(cotan_$(1))&: $(annotation_$(1))
	$(call print_rule,cotan,$(1))
	mkdir -p $$(@D) $(tmpdir)/$(1)/cotan
	$(call print_debug,loading file $$< \(layer 'matrix'\))
	$(call conda_run,scbolt-core) python scripts/utils/adata_conversion.py $$< $(tmpdir)/$(1)/cotan/barcts.csv --from h5ad --to csv --layer matrix $(cotan_only_hvg)
	$(call print_debug,transposing counts matrix)
	ruby -rcsv -e 'puts CSV.parse(STDIN).transpose.map &:to_csv' < $(tmpdir)/$(1)/cotan/barcts.csv > $(tmpdir)/$(1)/cotan/gencts.csv
	$(call conda_run,scbolt-cotan) Rscript scripts/macrostates/cotan_macrostates.R \
		--infile $(tmpdir)/$(1)/cotan/gencts.csv --outfile $$(@D)/cotan.RDS --csv $$(lastword $$(cotan_$(1))) \
		--sep , --name $(1) --max-iterations $(MAX_ITER) --method $(COTAN_METHOD) --min-ude 0.3 --jobs $(JOBS)
	sed -i '1 i\,macrostate' $$(lastword $$(cotan_$(1)))
	$(call print_debug,adding cotan macrostates to AnnData)
	$(call conda_run,scbolt-core) python scripts/utils/add_to_anndata.py $$< $$(firstword $$(cotan_$(1))) --csv $$(lastword $$(cotan_$(1))) --axis 0 --sep , --type category
	$(call print_task,plotting embedding colored by cotan macrostates)
	$(call conda_run,scbolt-core) python fig/plot_embedding.py fig/macrostates.json --infile $$(firstword $$(cotan_$(1))) --outfile $$(@D)/umap_cotan.pdf --use-rep $(USE_REP)

$(cellrank_$(1))&: $(velocity_$(1)) $(potency_$(1))
	$(call print_rule,cellrank,$(1))
	mkdir -p $$(@D) $(tmpdir)/$(1)/cellrank
	$(call print_debug,adding potency scores to AnnData)
	awk -F, -v txt="score" 'FNR==1{for(col=1;$$$$col!=txt;col++);next} {print $$$$1 "," $$$$col}' $$(lastword $$^) > $(tmpdir)/$(1)/cellrank/potency_scores.csv
	sed -i '1 i\,cytotrace_score' $(tmpdir)/$(1)/cellrank/potency_scores.csv
	$(call conda_run,scbolt-core) python scripts/utils/add_to_anndata.py \
		$$(firstword $$^) $(tmpdir)/$(1)/cellrank/kernels.h5ad --csv $(tmpdir)/$(1)/cellrank/potency_scores.csv --axis 0 --sep , --type float
	$(call conda_run,scbolt-cellrank) python scripts/macrostates/cellrank_macrostates.py \
		$(tmpdir)/$(1)/cellrank/kernels.h5ad $$(firstword $$(cellrank_$(1))) --csv $$(lastword $$(cellrank_$(1))) \
		--obs $(LABEL_COL) --method $(CELLRANK_METHOD) \
		--cytotrace-score cytotrace_score --scvelo-velocity velocity \
		--states $(STATES) --initial-states $(INITIAL_STATES) --terminal-states $(TERMINAL_STATES) \
		--stability $(CELLRANK_STABILITY) --alpha $(CELLRANK_ALPHA) --size $(MACROSTATE_SIZE) --seed $(SEED)

$(stream_$(1))&: $(annotation_$(1))
	$(call print_rule,stream,$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-stream) python scripts/macrostates/stream_macrostates.py $$< $$(firstword $$(stream_$(1))) --csv $$(lastword $$(stream_$(1))) \
		--use-rep $(USE_REP) --obs $(LABEL_COL) --clustering $(CLUSTERING_METHOD) --cluster-number $(CLUSTER_NUMBER) \
		--alpha $(ALPHA_EPG) --mu $(MU_EPG) --lambda $(LAMBDA_EPG) \
		$(extend_epg) $(if $(filter $(EXTEND_EPG),true),--extend-mode $(EXTEND_MODE),) $(if $(filter $(EXTEND_EPG),true),--extend-parameter $(EXTEND_PARAMETER),) \
		$(prune_epg) $(if $(filter $(PRUNE_EPG),true),--collapse-parameter $(COLLAPSE_PARAMETER),) --size $(MACROSTATE_SIZE) --jobs $(JOBS)

ifeq ($(or $(call knnbs_centrality,$(1)),$(call knnbs_periphery,$(1))),)
$(knnbs_$(1))&: $(annotation_$(1))
	$(call print_error,required parameter not defined: KNNBS_CENTRALITY_$(call toupper,$(1)) or KNNBS_PERIPHERY_$(call toupper,$(1)) \(needed by target 'knnbs'\))
else
$(knnbs_$(1))&: $(annotation_$(1))
	$(call print_rule,knnbs,$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python scripts/macrostates/knnbs_macrostates.py $$< $$(firstword $$(knnbs_$(1))) --csv $$(lastword $$(knnbs_$(1))) \
		--obs $(LABEL_COL) --embedding $(KNNBS_EMBEDDING) --neighbors $(KNNBS_NEIGHBORS) \
		$(knnbs_dimension) --metric $(METRIC) --size $(MACROSTATE_SIZE) \
		$(if $(call knnbs_centrality,$(1)),--centrality $(call knnbs_centrality,$(1)),) \
		$(if $(call knnbs_periphery,$(1)),--periphery $(call knnbs_periphery,$(1)),) \
		--jobs $(JOBS)
	$(call print_task,plotting embedding colored by knnbs macrostates)
	$(call conda_run,scbolt-core) python fig/plot_embedding.py fig/macrostates.json --infile $$(firstword $$(knnbs_$(1))) --outfile $$(@D)/knnbs.pdf --use-rep $(USE_REP)
endif

endef

define compute_rules_for_references

$(dea_$(1))&: $(clustering_$(1))
	$(call print_rule,dea,$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python scripts/clustering/markers.py $$< $(firstword $(dea_$(1))) --xlsx $(lastword $(dea_$(1))) \
		--cluster leiden --layer log-norm --is-log \
		--logfc $(LOGFC) --alpha $(ALPHA) --correction $(CORRECTION)

$(scoring_$(1)): $(clustering_$(1)) $(lastword $(signatures)) $(lastword $(dea_$(1)))
	$(call print_rule,scoring,$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python scripts/clustering/scoring.py $$^ $$@ --cluster leiden --ignore-sheets background

$(goea_basic_$(1)): $(lastword $(dea_$(1))) $(go_basic) $(gene2go)
	$(call print_rule,goea,go_basic/$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python scripts/clustering/goea.py $$< $$@ --background background --go $$(word 2,$$^) --gene2go $$(lastword $$^) 

$(goea_organism_$(1)): $(lastword $(dea_$(1))) $(go_organism) $(gene2go)
	$(call print_rule,goea,go_$(ORGANISM)/$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python scripts/clustering/goea.py $$< $$@ --background background --go $$(word 2,$$^) --gene2go $$(lastword $$^)

endef

$(clustering_integrated): $(foreach condition,$(conditions),$(normalization_$(condition)))
	$(call print_rule,clustering,integrated)
	mkdir -p $(@D)
	$(call conda_run,scbolt-core) python scripts/clustering/integration.py $^ --outfile $@ --labels $(conditions) \
		--layer correct --adjacency knn --integration $(INTEGRATION) --embedding umap \
		--pca-dimension $(DIM_PCA) --clustering-dimension $(DIM_CLUSTERING) --embedding-dimension $(DIM_EMBEDDING) \
		$(if $(filter $(PCA_ONLY_HVG),true),--hvg $(HVG),) --neighbors $(NEIGHBORS) --metric $(METRIC) --resolution $(RESOLUTION) \
		--min-dist $(MIN_DIST) --spread $(SPREAD) --seed $(SEED) --jobs $(JOBS)

$(annotation_integrated): $(clustering_integrated)
	$(call print_rule,annotation,integrated)
	if [ -z "$(LABEL)" ]; then \
			$(call print_error,required parameter not defined: LABEL \(needed by target 'annotation'\). Review DEA/GOEA/signature outputs and set LABEL in your parameter file); \
	fi
	mkdir -p $(@D)
	$(call conda_run,scbolt-core) python scripts/clustering/annotation.py $< $@ \
		--obs leiden --new-obs $(LABEL_COL) --labels $(label_map)
	$(call print_task,plotting embedding colored by labels)
	$(call conda_run,scbolt-core) python fig/plot_embedding.py fig/generic.json --infile $@ --outfile $(@D)/labels.pdf --obs $(LABEL_COL) --use-rep $(USE_REP)

ifdef SCBOOLSEQ_HVG_METHOD
$(bin_cells)&: $(if $(filter-out $(words $(CONDITIONS)),1),$(annotation_integrated),$(annotation_$(conditions)))
	$(call print_rule,bin-cells)
	mkdir -p $(@D) $(tmpdir)/bin/cell
	$(call print_task,estimating top$(if $(SCBOOLSEQ_TOP_HVG), $(SCBOOLSEQ_TOP_HVG),) highly variable genes with $(SCBOOLSEQ_HVG_METHOD))
	$(call conda_run,scbolt-core) python scripts/preprocessing/hvg.py $(lastword $^) $(tmpdir)/bin/cell/top_genes.txt \
		--method $(SCBOOLSEQ_HVG_METHOD) $(scboolseq_layer) $(if $(SCBOOLSEQ_TOP_HVG),--hvg $(SCBOOLSEQ_TOP_HVG),) $(batch)
	$(call conda_run,scbolt-scboolseq) python scripts/binarization/bin_cells_scboolseq.py $< --outfile $(firstword $(bin_cells)) \
		--bin $(shell echo $@ | sed "s/.h5ad/.csv/") --statistics $(lastword $(bin_cells)) \
		--layer log-norm --quantile $(UNIMODAL_QUANTILE) $(zeroes_are_zeroes) --filter-genes $(tmpdir)/bin/cell/top_genes.txt
	$(call print_task,plotting embedding colored by binarization percentage)
	$(call conda_run,scbolt-core) python fig/plot_embedding.py fig/bin.json --infile $(firstword $(bin_cells)) --outfile $(@D)/pct_bin.pdf --use-rep $(USE_REP)
else
$(bin_cells)&: $(if $(filter-out $(words $(CONDITIONS)),1),$(annotation_integrated),$(annotation_$(conditions)))
	$(call print_rule,bin-cells)
	mkdir -p $(@D)
	$(call conda_run,scbolt-scboolseq) python scripts/binarization/bin_cells_scboolseq.py $< --outfile $(firstword $(bin_cells)) \
		--bin $(shell echo $@ | sed "s/.h5ad/.csv/") --statistics $(lastword $(bin_cells)) \
		--layer log-norm --quantile $(UNIMODAL_QUANTILE) $(zeroes_are_zeroes)
	$(call print_task,plotting embedding colored by binarization percentage)
	$(call conda_run,scbolt-core) python fig/plot_embedding.py fig/bin.json --infile $(firstword $(bin_cells)) --outfile $(@D)/pct_bin.pdf --use-rep $(USE_REP)
endif

$(bin_macrostates): $(firstword $(bin_cells)) $(foreach condition,$(conditions),$(lastword $(macrostates_$(condition))))
	$(call print_rule,bin-macrostates)
	mkdir -p $(@D) $(tmpdir)/integrated/bin/aggr
	$(call print_debug,adding macrostates to AnnData)
	$(call conda_run,scbolt-core) python scripts/utils/add_to_anndata.py $(firstword $^) $(tmpdir)/integrated/bin/aggr/mcts.h5ad --csv $(filter-out $<, $^) \
	$(if $(filter-out $(words $(CONDITIONS)),1),--labels $(conditions) --label-column condition --add-prefix macrostate,) --axis 0 --sep , --type category
	$(call conda_run,scbolt-core) python scripts/binarization/bin_clusters_scboolseq.py $(tmpdir)/integrated/bin/aggr/mcts.h5ad $@ --counts $(@D)/counts_bin.csv \
		--layer bin --distribution distribution --cluster macrostate --use-rep $(USE_REP) \
		--nans-threshold $(NANS_THRESHOLD) --bimodal-threshold $(BIMODAL_THRESHOLD) \
		--zeroinf-threshold $(ZEROINF_THRESHOLD) --unimodal-threshold $(UNIMODAL_THRESHOLD)
	$(call print_task,plotting embedding colored by macrostates)
	$(call conda_run,scbolt-core) python fig/plot_embedding.py fig/macrostates.json --infile $(tmpdir)/integrated/bin/aggr/mcts.h5ad --outfile $(@D)/macrostates.pdf --use-rep $(USE_REP)

ifdef DEA_HVG_METHOD
$(bin_dea): $(if $(filter-out $(words $(CONDITIONS)),1),$(annotation_integrated),$(annotation_$(conditions))) $(foreach condition,$(conditions),$(lastword $(macrostates_$(condition))))
	$(call print_rule,bin-dea)
	mkdir -p $(@D) $(tmpdir)/integrated/bin/dea
	$(call print_debug,adding macrostates to AnnData)
	$(call conda_run,scbolt-core) python scripts/utils/add_to_anndata.py $(firstword $^) $(tmpdir)/integrated/bin/dea/mcts.h5ad --csv $(filter-out $<, $^) \
		$(if $(filter-out $(words $(CONDITIONS)),1),--labels $(conditions) --label-column condition --add-prefix macrostate,) --axis 0 --sep , --type category
	$(call print_task,estimating top$(if $(DEA_TOP_HVG), $(DEA_TOP_HVG),) highly variable genes with $(DEA_HVG_METHOD))
	$(call conda_run,scbolt-core) python scripts/preprocessing/hvg.py $(firstword $^) $(tmpdir)/bin/dea/top_genes.txt --method $(DEA_HVG_METHOD) \
		$(dea_layer) $(if $(DEA_TOP_HVG),--hvg $(DEA_TOP_HVG),) $(batch)
	$(call conda_run,scbolt-core) python scripts/binarization/bin_dea.py $(tmpdir)/integrated/bin/dea/mcts.h5ad $@ \
		--cluster macrostate --layer log-norm --is-log --method wilcoxon --use-rep $(USE_REP) \
		--logfc $(BIN_LOGFC) --alpha $(BIN_ALPHA) --correction $(BIN_CORRECTION) --filter-genes $(tmpdir)/bin/dea/top_genes.txt
	$(call print_task,plotting embedding colored by macrostates)
	$(call conda_run,scbolt-core) python fig/plot_embedding.py fig/macrostates.json --infile $(tmpdir)/integrated/bin/dea/mcts.h5ad --outfile $(@D)/macrostates.pdf --use-rep $(USE_REP)
else
$(bin_dea): $(if $(filter-out $(words $(CONDITIONS)),1),$(annotation_integrated),$(annotation_$(conditions))) $(foreach condition,$(conditions),$(lastword $(macrostates_$(condition))))
	$(call print_rule,bin-dea)
	mkdir -p $(@D) $(tmpdir)/integrated/bin/dea
	$(call print_debug,adding macrostates to AnnData)
	$(call conda_run,scbolt-core) python scripts/utils/add_to_anndata.py $(firstword $^) $(tmpdir)/integrated/bin/dea/mcts.h5ad --csv $(filter-out $<, $^) \
		$(if $(filter-out $(words $(CONDITIONS)),1),--labels $(conditions) --label-column condition --add-prefix macrostate,) --axis 0 --sep , --type category
	$(call conda_run,scbolt-core) python scripts/binarization/bin_dea.py $(tmpdir)/integrated/bin/dea/mcts.h5ad $@ \
		--cluster macrostate --layer log-norm --is-log --method wilcoxon --use-rep $(USE_REP) \
		--logfc $(BIN_LOGFC) --alpha $(BIN_ALPHA) --correction $(BIN_CORRECTION)
	$(call print_task,plotting embedding colored by macrostates)
	$(call conda_run,scbolt-core) python fig/plot_embedding.py fig/macrostates.json --infile $(tmpdir)/integrated/bin/dea/mcts.h5ad --outfile $(@D)/macrostates.pdf --use-rep $(USE_REP)
endif

$(bin_consensus): $(bin_macrostates) $(lastword $(bin_cells)) $(bin_dea)
	$(call print_rule,bin-consensus)
	mkdir -p $(@D) $(tmpdir)/bin/consensus
	$(call print_debug,extracting scBoolSeq distributions)
	col=`head $(word 2, $^) -n 1 | sed "s/,/\n/g" | awk -F, '{printf("%d %s\n", NR-1, $$0)}' | grep Category | awk '{print $$1}'`
	((col++))
	cut -f 1,$$col -d ',' $(word 2, $^) > $(tmpdir)/bin/consensus/distributions.csv
	unset col
	$(call conda_run,scbolt-core) python scripts/binarization/bin_consensus.py \
		--scboolseq $< $(tmpdir)/bin/consensus/distributions.csv --dea $(lastword $^) \
		--outfile $@ --pct-bin $(@D)/pct_bin.csv

ifdef MODEL_HVG_METHOD
$(bonesis_model)&: $(bin) $(if $(filter-out $(words $(CONDITIONS)),1),$(annotation_integrated),$(annotation_$(conditions))) | $(if $(filter dorothea,$(PRIOR_KNOWLEDGE)),$(if $(filter legacy,$(DOROTHEA_API)),$(dorothea_legacy)))
	$(call print_rule,spec)
	$(call check_file,$(YAML_MODEL),YAML_MODEL)
	mkdir -p $(tmpdir)/bonesis/hvg $(dir $(word 1,$(bonesis_model))) $(dir $(word 2,$(bonesis_model))) $(dir $(word 3,$(bonesis_model))) $(dir $(word 4,$(bonesis_model)))
	$(call print_task,estimating top$(if $(MODEL_TOP_HVG), $(MODEL_TOP_HVG),) highly variable genes with $(MODEL_HVG_METHOD))
	$(call conda_run,scbolt-core) python scripts/preprocessing/hvg.py $(lastword $^) $(tmpdir)/bonesis/hvg/top_genes.txt \
		--method $(MODEL_HVG_METHOD) $(model_layer) $(if $(MODEL_TOP_HVG),--hvg $(MODEL_TOP_HVG),) $(batch)
	$(call conda_run,scbolt-bonesis) python scripts/inference/specification.py $(YAML_MODEL) $< \
		--model $(word 1,$(bonesis_model)) --metastates $(word 2,$(bonesis_model)) \
		--important-genes $(word 3,$(bonesis_model)) --mandatory-genes $(word 4,$(bonesis_model)) \
		--filter-genes $(tmpdir)/bonesis/hvg/top_genes.txt --domain $(prior_knowledge) --organism $(ORGANISM) $(dorothea_levels_arg)
	sort -u $(word 3,$(bonesis_model)) -o $(word 3,$(bonesis_model))
	sort -u $(word 4,$(bonesis_model)) -o $(word 4,$(bonesis_model))
else
$(bonesis_model)&: $(bin) | $(if $(filter dorothea,$(PRIOR_KNOWLEDGE)),$(if $(filter legacy,$(DOROTHEA_API)),$(dorothea_legacy)))
	$(call print_rule,spec)
	$(call check_file,$(YAML_MODEL),YAML_MODEL)
	mkdir -p $(dir $(word 1,$(bonesis_model))) $(dir $(word 2,$(bonesis_model))) $(dir $(word 3,$(bonesis_model))) $(dir $(word 4,$(bonesis_model)))
	$(call conda_run,scbolt-bonesis) python scripts/inference/specification.py $(YAML_MODEL) $< \
		--model $(word 1,$(bonesis_model)) --metastates $(word 2,$(bonesis_model)) \
		--important-genes $(word 3,$(bonesis_model)) --mandatory-genes $(word 4,$(bonesis_model)) \
		--domain $(prior_knowledge) --organism $(ORGANISM) $(dorothea_levels_arg)
	sort -u $(word 3,$(bonesis_model)) -o $(word 3,$(bonesis_model))
	sort -u $(word 4,$(bonesis_model)) -o $(word 4,$(bonesis_model))
endif

$(max_nodes_soft): $(bonesis_model)
	$(call print_rule,max-nodes-soft)
	mkdir -p $(@D)
	set +e; \
	$(call inference_timeout,$(TIMEOUT_SOFT)) $(call conda_run,scbolt-bonesis) python scripts/inference/inference.py filter-nodes \
		$(word 1,$^) $(word 2,$^) --important-genes $(word 3,$^) --mandatory-genes $(word 4,$^) --asp $(@D)/nodes.sh --solution $@ \
		--domain $(prior_knowledge) --organism $(ORGANISM) $(dorothea_levels_arg) --bonesis-mode soft --max-clause $(MAX_CLAUSE) \
		--clingo-opt-mode $(CLINGO_OPT_MODE_SOFT) --clingo-opt-strategy $(CLINGO_OPT_STRATEGY_SOFT) --jobs $(JOBS_SOFT); \
	exit_status=$$?; \
	set -e; \
	$(call check_inference_status, $(TIMEOUT_SOFT))

$(max_consts_soft): $(bonesis_model) $(max_nodes_soft)
	$(call print_rule,max-consts-soft)
	mkdir -p $(@D)
	set +e; \
	$(call inference_timeout,$(TIMEOUT_CONSTS)) $(call conda_run,scbolt-bonesis) python scripts/inference/inference.py filter-consts \
		$(word 1,$^) $(word 2,$^) --mandatory-genes $(word 4,$^) --filter-grn $(lastword $^) --asp $(@D)/nodes.sh --solution $@ \
		--domain $(prior_knowledge) --organism $(ORGANISM) $(dorothea_levels_arg) --bonesis-mode soft --max-clause $(MAX_CLAUSE) $(min_self_loop_consts) \
		--clingo-opt-mode $(CLINGO_OPT_MODE_CONSTS) --clingo-opt-strategy $(CLINGO_OPT_STRATEGY_CONSTS) --jobs $(JOBS_CONSTS); \
	exit_status=$$?; \
	set -e; \
	$(call check_inference_status, $(TIMEOUT_CONSTS))

$(max_nodes_relaxed): $(bonesis_model) $(max_consts_soft)
	$(call print_rule,max-nodes-relaxed)
	mkdir -p $(@D)
	set +e; \
	$(call inference_timeout,$(TIMEOUT_RELAXED)) $(call conda_run,scbolt-bonesis) python scripts/inference/inference.py filter-nodes \
		$(word 1,$^) $(word 2,$^) --important-genes $(word 3,$^) --mandatory-genes $(word 4,$^) --filter-grn $(lastword $^) --asp $(@D)/nodes.sh --solution $@ \
		--domain $(prior_knowledge) --organism $(ORGANISM) $(dorothea_levels_arg) --bonesis-mode relaxed --max-clause $(MAX_CLAUSE) \
		--clingo-opt-mode $(CLINGO_OPT_MODE_RELAXED) --clingo-opt-strategy $(CLINGO_OPT_STRATEGY_RELAXED) --jobs $(JOBS_RELAXED); \
	exit_status=$$?; \
	set -e; \
	$(call check_inference_status, $(TIMEOUT_RELAXED))

$(max_nodes_seed): $(bonesis_model) $(max_nodes_relaxed)
	$(call print_rule,max-nodes-seed)
	$(call check_parameter,$(TIMEOUT_SEED),TIMEOUT_SEED (needed by target 'max-nodes-seed'))
	mkdir -p $(@D)
	set +e; \
	$(call inference_timeout,$(TIMEOUT_SEED)) $(call conda_run,scbolt-bonesis) python scripts/inference/inference.py filter-nodes \
		$(word 1,$^) $(word 2,$^) --important-genes $(word 3,$^) --mandatory-genes $(word 4,$^) --filter-grn $(lastword $^) --asp $(@D)/nodes.sh --solution $@ \
		--domain $(prior_knowledge) --organism $(ORGANISM) $(dorothea_levels_arg) --bonesis-mode hard --max-clause $(MAX_CLAUSE) \
		--clingo-opt-mode $(CLINGO_OPT_MODE_SEED) --clingo-opt-strategy $(CLINGO_OPT_STRATEGY_SEED) --jobs $(JOBS_SEED); \
	exit_status=$$?; \
	set -e; \
	$(call check_inference_status, $(TIMEOUT_SEED))

$(max_nodes_lock): $(bonesis_model) $(max_nodes_relaxed) $(max_nodes_seed)
	$(call print_rule,max-nodes-lock)
	mkdir -p $(@D)
	if [ -f $(dir $(lastword $^))__SOLUTION ] && [ "$$(cat $(dir $(lastword $^))__SOLUTION)" = "_GLOBAL_OPTIMUM" ]; then \
		$(call print_debug,solution already globally optimal: skipping lock optimization); \
		cp $(lastword $^) $@; \
		echo "_GLOBAL_OPTIMUM" > $(@D)/__SOLUTION; \
	else \
		set +e; \
		cat $(word 4,$^) $(word 6,$^) | sort -u > $(@D)/mandatory.txt; \
		$(call inference_timeout,$(TIMEOUT_LOCK)) $(call conda_run,scbolt-bonesis) python scripts/inference/inference.py filter-nodes \
			$(word 1,$^) $(word 2,$^) --important-genes $(word 3,$^) --mandatory-genes $(@D)/mandatory.txt --filter-grn $(word 5,$^) --asp $(@D)/nodes.sh --solution $@ \
			--domain $(prior_knowledge) --organism $(ORGANISM) $(dorothea_levels_arg) --bonesis-mode hard --max-clause $(MAX_CLAUSE) \
			--clingo-opt-mode $(CLINGO_OPT_MODE_LOCK) --clingo-opt-strategy $(CLINGO_OPT_STRATEGY_LOCK) --jobs $(JOBS_LOCK); \
		exit_status=$$?; \
		set -e; \
		$(call check_inference_status,$(TIMEOUT_LOCK)); \
	fi

$(bn_min): $(bonesis_model) $(max_nodes_lock)
	$(call print_rule,bn-min)
	mkdir -p $(@D)
	$(call conda_run,scbolt-bonesis) python scripts/inference/inference.py min \
		$(word 1,$^) $(word 2,$^) --filter-grn $(lastword $^) --asp $(@D)/min.sh --solution $(basename $@) \
		--domain $(prior_knowledge) --organism $(ORGANISM) $(dorothea_levels_arg) --max-clause $(MAX_CLAUSE) $(min_self_loop_infer) \
		--clingo-opt-mode $(CLINGO_OPT_MODE_MIN) --jobs 1 \
		--graph-formats $(GRAPH_FORMATS)
		if command -v dot >/dev/null 2>&1; then
		    for file in $(@D)/*.dot; do
		        [ -e "$${file}" ] || continue
		        dot -Tpdf "$${file}" -o "$${file%.dot}.pdf"
		    done
		fi

$(bn_submin)&: $(bonesis_model) $(max_nodes_lock)
	$(call print_rule,bn-submin)
	$(call check_partial_bn_outputs,$(bn_submin_dir),bn-submin)
	mkdir -p $(bn_submin_dir)
	$(call conda_run,scbolt-bonesis) python scripts/inference/inference.py submin \
		$(word 1,$^) $(word 2,$^) \
		--filter-grn $(lastword $^) \
		--asp $(bn_submin_dir)/submin.sh \
		--solution $(bn_submin_dir) \
		--domain $(prior_knowledge) \
		--organism $(ORGANISM) \
		$(dorothea_levels_arg) \
		--max-clause $(MAX_CLAUSE) \
		--jobs $(JOBS) \
		$(if $(strip $(INFER_LIMIT)),--limit $(INFER_LIMIT)) \
		--config-formats $(CONFIG_FORMATS) \
		--graph-formats $(GRAPH_FORMATS) \
		--remove-isolated-nodes
	touch $(bn_submin_dir)/.done

$(bn_diverse)&: $(bonesis_model) $(max_nodes_lock)
	$(call print_rule,bn-diverse)
	$(call check_partial_bn_outputs,$(bn_diverse_dir),bn-diverse)
	mkdir -p $(bn_diverse_dir)
	$(call conda_run,scbolt-bonesis) python scripts/inference/inference.py diverse \
		$(word 1,$^) $(word 2,$^) \
		--filter-grn $(lastword $^) \
		--asp $(bn_diverse_dir)/diverse.sh \
		--solution $(bn_diverse_dir) \
		--domain $(prior_knowledge) \
		--organism $(ORGANISM) \
		$(dorothea_levels_arg) \
		--max-clause $(MAX_CLAUSE) \
		--jobs $(JOBS) \
		$(if $(strip $(INFER_LIMIT)),--limit $(INFER_LIMIT)) \
		--config-formats $(CONFIG_FORMATS) \
		--graph-formats $(GRAPH_FORMATS) \
		--remove-isolated-nodes
	touch $(bn_diverse_dir)/.done

$(foreach condition,$(conditions),$(eval $(call compute_rules_for_conditions,$(condition))))
$(foreach reference,$(references),$(eval $(call compute_rules_for_references,$(reference))))

## END RULES
