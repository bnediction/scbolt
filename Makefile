#!/usr/bin/env make

.ONESHELL:

SHELL = /bin/bash
MAKEFLAGS += --silent
DEFAULT_CONFIG = default_config.mk
CONFIG = config.mk

include $(DEFAULT_CONFIG) $(CONFIG)

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
	$(if $2,@echo `date "+%Y-%m-%d %H:%M:%S"` - RULE - $(1) \($(2)\),@echo `date "+%Y-%m-%d %H:%M:%S"` - RULE - $(1))
endef

define print_task
	@echo `date "+%Y-%m-%d %H:%M:%S"` - TASK - $(1)
endef

define print_info
	@echo `date "+%Y-%m-%d %H:%M:%S"` - INFO - $(1)
endef

define print_error
	@echo `date "+%Y-%m-%d %H:%M:%S"` - ERROR - $(1)
	exit
endef

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

fastq_$(1) = $(rna)/$(1)/fastq
cellranger_$(1) = $(rna)/$(1)/counting/cellranger/$(1).mri.tgz
velocyto_$(1) = $(rna)/$(1)/counting/velocyto/counts.h5ad
filtering_$(1) = $(rna)/$(1)/preprocessing/filtering/counts.h5ad
normalization_$(1) = $(rna)/$(1)/preprocessing/normalization/counts.h5ad
scvelo_$(1) = $(rna)/$(1)/trajectories/scvelo/scvelo.h5ad
pseudotime_stream_$(1) = $(rna)/$(1)/trajectories/stream/pseudotime/stream.h5ad.pkl
trajectories_stream_$(1) = $(rna)/$(1)/trajectories/stream/trajectories/branches.txt
trajectories_macrostates_$(1) = $(rna)/$(1)/trajectories/macrostates/trajectories.txt
cellrank_$(1) = $(rna)/$(1)/macrostates/cellrank/adata.h5ad
center_extremity_$(1) = $(rna)/$(1)/macrostates/center_extremity/adata.h5ad
cotan_$(1) = $(rna)/$(1)/macrostates/cotan/adata.h5ad
bdc_$(1) = $(Rrna)/$(1)/binarization/pairwise_predecessor_scores.csv

ifeq ($(MACROSTATES_METHOD),cellrank)
macrostates_$(1) = cellrank_$(1)
bin_macrostates_$(1) = $(rna)/$(1)/macrostates/cellrank/macrostates_bin.csv
else ifeq ($(MACROSTATES_METHOD),center-extremity)
macrostates_$(1) = center_extremity_$(1)
bin_macrostates_$(1) = $(rna)/$(1)/macrostates/center_extremity/macrostates_bin.csv
else ifeq ($(MACROSTATES_METHOD),cotan)
macrostates_$(1) = cotan_$(1)
bin_macrostates_$(1) = $(rna)/$(1)/macrostates/cotan/macrostates_bin.csv
else
macrostates_$(1) bin_macrostates_$(1):
	$(call print_error,unsupported values for `MACROSTATES_METHOD` \(supported values: cellrank, center-extremity or cotan\))
endif

endef

define condition_plus_integrated_dependant_paths

clustering_$(1) = $(rna)/$(1)/clustering/clusters/counts.h5ad
markers_$(1) = $(rna)/$(1)/clustering/markers/genes/background.txt
goea_basic_$(1) = $(rna)/$(1)/clustering/goea/goea_basic.xlsx
goea_mouse_$(1) = $(rna)/$(1)/clustering/goea/goea_mouse.xlsx
annotation_$(1) = $(rna)/$(1)/clustering/clusters/annotation.h5ad
bin_cells_$(1) = $(rna)/$(1)/binarization/cluster_bin_macrostates.csv
model_specification_$(1) = $(rna)/$(1)/bonesis/specification_model.txt
bonesis_filter1_$(1) = $(rna)/$(1)/bonesis/filtering/stage1/bootstrap_filter_grn_stage1.txt
bonesis_filter2_$(1) = $(rna)/$(1)/bonesis/filtering/stage2/bootstrap_filter_grn_stage2.txt
bonesis_inference_min_$(1) = $(rna)/$(1)/bonesis/inference/min/one-min.bnet
bonesis_inference_sub_$(1) = $(rna)/$(1)/bonesis/inference/sub/one-sub.bnet

endef

$(foreach l,$(conditions),$(eval $(call condition_dependant_paths,$(l))))
$(foreach l,$(conditions_plus_integrated),$(eval $(call condition_plus_integrated_dependant_paths,$(l))))

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
$(eval stream_pseudotime_target := $(stream_pseudotime_target) $(pseudotime_stream_$(1)))
$(eval stream_trajectories_target := $(stream_trajectories_target) $(trajectories_stream_$(1)))
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
$(eval bin_cells_target := $(scboolseq_target) $(bin_cell_$(1)))
$(eval model_specification_target := $(model_specification_target) $(model_specification_$(1)))
$(eval bonesis_filter1_target := $(bonesis_filter1_target) $(bonesis_filter1_$(1)))
$(eval bonesis_filter2_target := $(bonesis_filter2_target) $(bonesis_filter2_$(1)))
$(eval bonesis_inference_min_target := $(bonesis_inference_min_target) $(bonesis_inference_min_$(1)))
$(eval bonesis_inference_sub_target := $(bonesis_inference_sub_target) $(bonesis_inference_sub_$(1)))

endef

$(foreach l,$(_samples),$(eval $(call dependant_targets,$(l))))
$(foreach l,$(_samples_without_integration),$(eval $(call dependant_targets_with_integration,$(l))))

## END TARGETS ##

## BEGIN PARAMETERS ##

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
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make $(GREEN)<command>$(NC) [SAMPLES=control+treated+integrated] (default:SAMPLES=$(SAMPLES))\n\
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
scvelo: $(scvelo_velocity_target) ## compute rna velocity with scvelo
.PHONY: stream-pseudotime
stream-pseudotime: $(stream_pseudotime_target) ## compute elastic principal graph and pseudotime with stream
.PHONY: stream-trajectories
stream-trajectories: $(stream_trajectories_target) ## compute trajectories with stream

##@ Macrostate characterization

.PHONY: cellrank
cellrank: $(cellrank_target) ## compute macrostates with cellrank
.PHONY: center-extremity
center-extremity: $(center_extremity_target) ## compute macrostates with center-extremity method
.PHONY: cotan
cotan: $(cotan_target) ## compute macrostates with cotan
.PHONY: macrostates
macrostates: $(macrostates_target) ## compute macrostates depending on MACROSTATES_METHOD parameter

##@ Macrostate binarization

.PHONY: scboolseq
scboolseq: $(scboolseq_target) ## binarize cell counts with scBoolSeq
.PHONY: macrostate-binarization
bin-macrostates: $(bin-macrostate_target) ## binarize macrostates w.r.t. voting rule
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
	python pipeline/utils/load_signatures.py \
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
	cellranger count --id=ctrl \
		--fastqs=$$(firstword $$^) \
   		--transcriptome=$$(lastword $$^) \
   		--create-bam true \
   		--localcores=$(JOBS) \
   		--localmem=$(MEMORY)
	mv ctrl/* $$(@D)
	rm -rf ctrl

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
	python bonesistools/clitools/adata_conversion.py $$(shell echo $$(@) | sed "s/h5ad/loom/") $$(@) --from loom --to h5ad \
		--metadata $$(METADATA_$(call toupper,$(1))) \
		--remove-positions \
		--genename-standardization
	$$(conda_deactivate)

$(filtering_$(1)): $(velocyto_$(1)) $(cycle_markers)
	$(call print_rule,filtering,$(1))
	$$(conda_activate) preprocess
	mkdir -p $$(@D)
	python pipeline/preprocessing/filtering.py \
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
	$$(conda_activate) preprocess
	mkdir -p $$(@D)
	python pipeline/preprocessing/normalization.py $$< $$(@) \
		--correction G2M_score S_score G1_score \
		--min-cell-expression-proportion 0.001 \
		--jobs $(JOBS)
	$$(conda_deactivate)

$(clustering_$(1)): $(normalization_$(1))
	$(call print_rule,clustering,$(1))
	mkdir -p $$(@D)
	$$(conda_activate) preprocess
	python pipeline/clustering/leiden_clustering.py $$< $$(@D) \
		--layer correct --hvg \
		--metric euclidean --k-neighbors $(K_NEIGHBORS) --resolution $(RESOLUTION) \
		--dim-pca $(DIM_PCA) --dim-clustering $(DIM_CLUSTERING) --dim-umap $(DIM_UMAP) \
		--add-legend --plot-3d \
		--seed $(SEED)
	$$(conda_deactivate)

ifeq ($$(LABELING_FROM_INTEGRATION),true)
$(annotation_$(1)): $(annotation_integrated) $(clustering_$(1))
	$(call print_rule,annotation,$(1))
	$$(conda_activate) preprocess
	python pipeline/utils/pipe.py $$^ --outfiles $$@ --column leiden --condition condition
	python figures/plot_embedding.py figures/umap_labels.json \
		--infile $$@ --outfile $$(@D)/umap_labels
	$$(conda_deactivate)
else
ifdef CLUSTER_LABEL_$(call toupper,$(1))
$(annotation_$(1)): $(clustering_$(1))
	$(call print_rule,annotation,$(1))
	$$(conda_activate) preprocess
	python pipeline/clustering/annotation.py $$< $$@ \
		--column leiden \
		--name $$(CLUSTER_LABEL_$(call toupper,$(1)))
	python figures/plot_embedding.py figures/umap_labels.json \
		--infile $$@ --outfile $$(@D)/umap_labels
	$$(conda_deactivate)
else
$(annotation_$(1)): $(clustering_$(1))
	$(call print_rule,annotation,$(1))
	$(call print_error,LABELING_FROM_INTEGRATION set to false and CLUSTER_LABEL_$(call toupper,$(1)) not defined)
	exit 1
endif
endif

endef

define condition_plus_integrated_dependant_rules

$(markers_$(1)): $(clustering_$(1)) $(lastword $(signatures))
	$$(eval markers_csv_ctrl := $$(dir $$(@D))markers.csv)
	$(call print_rule,marker-analysis,$(1))
	$$(conda_activate) preprocess
	python pipeline/clustering/markers.py $$(^) $$(dir $$(markers_csv_ctrl)) \
  		--cluster leiden \
  		--logfc-threshold 0.25 \
  		--verbose
	$(call print_task, background genes computation)
	python bonesistools/clitools/get_genes.py $$(<) $$(@)
	export clusters=`column -s, -t < $$(markers_csv_ctrl) | awk 'NR>1 {print $$$$2}' | sort -u | tr '\n' ' '`
	$(call print_task, upregulated cluster-related genes computation)
	for cluster in $$$${clusters}
	do
		`column -s, -t < $$(markers_csv_ctrl) | awk -v c=$$$${cluster} '$$$$2==c {print $$$$1}' > $$(@D)/cluster$$$${cluster}.txt`
		python bonesistools/clitools/genename_standardization.py $$(@D)/cluster$$$${cluster}.txt $$(@D)/cluster$$$${cluster}.txt --quiet
	done
	unset clusters
	$$(conda_deactivate)

$(goea_basic_$(1)): $(markers_$(1)) $(go_basic) $(gene2go)
	$(call print_rule,goea,$(1) with go-basic)
	$$(conda_activate) preprocess
	python pipeline/clustering/enrichment.py $$(@) \
    	--population $$(<) \
    	--study $$(<D)/cluster*.txt \
    	--go $$(word 2,$$^) \
    	--gene2go $$(lastword $$^)
	$$(conda_deactivate)

$(goea_mouse_$(1)): $(markers_$(1)) $(go_mouse) $(gene2go)
	$(call print_rule,goea,$(1) with go-mouse)
	$$(conda_activate) preprocess
	python pipeline/clustering/enrichment.py $$(@) \
    	--population $$(<) \
    	--study $$(<D)/cluster*.txt \
    	--go $$(word 2,$$^) \
    	--gene2go $$(lastword $$^)
	$$(conda_deactivate)

endef

$(clustering_integrated): $(foreach condition,$(conditions),$(normalization_$(condition)))
	$(call print_rule,clustering,integrated)
	mkdir -p $(@D)
	$(conda_activate) preprocess
	python pipeline/clustering/integration.py $^ $@ \
		--labels $(conditions) --method $(INTEGRATION_METHOD) --layer correct \
		--hvg --metric euclidean --k-neighbors $(K_NEIGHBORS) --resolution $(RESOLUTION) \
		--dim-pca $(DIM_PCA) --dim-clustering $(DIM_CLUSTERING) --dim-umap $(DIM_UMAP) \
		--add-legend --plot-3d \
		--seed $(SEED) \
		--jobs $(JOBS) \
	$(conda_deactivate)

ifdef CLUSTER_LABEL_INTEGRATED
$(annotation_integrated): $(clustering_integrated)
	$(call print_rule,annotation,integrated)
	$(conda_activate) preprocess
	python pipeline/clustering/annotation.py $< $@ \
		--column leiden \
		--name $(CLUSTER_LABEL_INTEGRATED)
	python figures/plot_embedding.py figures/umap_labels.json \
		--infile $@ --outfile $(@D)/umap_labels
	$(conda_deactivate)
else
$(labels_annotation): $(cluster_integrated)
	$(call print_rule,annotation,integrated)
	$(call print_error,CLUSTER_LABEL_INTEGRATED not defined)
	exit 1
endif

$(foreach condition,$(conditions),$(eval $(call condition_dependant_rules,$(condition))))
$(foreach condition,$(conditions_plus_integrated),$(eval $(call condition_plus_integrated_dependant_rules,$(condition))))


$(scvelo_ctrl): $(labels_ctrl)
	$(call section,scvelo (control data))
	$(conda_activate) scvelo
	python pipeline/trajectories/scvelo_velocity.py $< $(@D) \
		--cluster leiden \
		--k-neighbors $(SCVELO_K_NEIGHBORS_CTRL) \
		--dim-clustering $(SCVELO_DIM_CLUSTERING_CTRL) \
		--mode $(SMM_MODE_CTRL) \
		--add-legend
	$(conda_deactivate)

$(SCVELO_TREATED): $(LABELS_TREATED)
	$(call section,scvelo (treated data))
	$(conda_activate) scvelo
	python pipeline/trajectories/scvelo_velocity.py $< $(@D) \
		--cluster leiden \
		--k-neighbors $(SCVELO_K_NEIGHBORS_TREATED) \
		--dim-clustering $(SCVELO_DIM_CLUSTERING_TREATED) \
		--mode $(SMM_MODE_TREATED) \
		--add-legend
	$(conda_deactivate)

$(pseudotime_stream_ctrl): $(labels_ctrl)
	$(call section,stream-pseudotime (control data))
	$(conda_activate) stream
	python pipeline/trajectories/stream_pseudotime.py $< $(@D) \
		--extension both --cluster-number 6 --groups leiden \
		--lambda $(LAMBDA_CTRL) --mu $(MU_CTRL) --alpha $(ALPHA_CTRL) \
		--extend-leaf-nodes --extend-mode WeigthedCentroid --extend-parameter $(EXTEND_CTRL) \
		--add-legend --add-graph \
		--jobs $(JOBS)
	$(conda_deactivate)

$(pseudotime_stream_treated): $(LABELS_TREATED)
	$(call section,stream-pseudotime (treated data))
	$(conda_activate) stream
	python pipeline/trajectories/stream_pseudotime.py $< $(@D) \
		--extension both --cluster-number 6 --groups leiden \
		--lambda $(LAMBDA_TREATED) --mu $(MU_TREATED) --alpha $(ALPHA_TREATED) \
		--extend-leaf-nodes --extend-mode WeigthedCentroid --extend-parameter $(EXTEND_TREATED) \
		--add-legend --add-graph \
		--jobs $(JOBS)
	$(conda_deactivate)

$(trajectories_stream_ctrl): $(pseudotime_stream_ctrl)
	$(call section,stream-trajectories (control data))
	@echo -e '$(BOLDGREEN)Warning: root can be modified depending on scvelo and BDC analysis$(NC)'
	$(conda_activate) stream
	python pipeline/trajectories/stream_trajectories.py $< $(@D) --root $(ROOT_CTRL) \
		--groups leiden kmeans node_clusters \
		--add-legend --add-graph $(IGNORED_NODES_CTRL)
	$(conda_deactivate)

$(trajectories_stream_treated): $(pseudotime_stream_treated)
	$(call section,stream-trajectories (control data))
	@echo -e '$(BOLDGREEN)Warning: root can be modified depending on scvelo and BDC analysis$(NC)'
	$(conda_activate) stream
	python pipeline/trajectories/stream_trajectories.py $< $(@D) --root $(ROOT_TREATED) \
		--groups leiden kmeans node_clusters \
		--add-legend --add-graph $(IGNORED_NODES_TREATED)
	$(conda_deactivate)

$(cellrank_ctrl): $(scvelo_ctrl)
	$(call section,cellrank (control data))
	$(conda_activate) cellrank
	python pipeline/macrostates/cellrank_macrostates.py $< $(@D) \
		--macrostate-size $(MACROSTATE_SIZE) \
		--initial-states $(INITIAL_STATES_CTRL) \
		--terminal-states $(TERMINAL_STATES_CTRL) \
		--method $(CELLRANK_METHOD) \
		--plot-3d
	$(conda_deactivate)

$(cellrank_treated): $(SCVELO_TREATED)
	$(call section,cellrank (treated data))
	$(conda_activate) cellrank
	python pipeline/macrostates/cellrank_macrostates.py $< $(@D) \
		--macrostate-size $(MACROSTATE_SIZE) \
		--initial-states $(INITIAL_STATES_TREATED) \
		--terminal-states $(TERMINAL_STATES_TREATED) \
		--method $(CELLRANK_METHOD) \
		--plot-3d
	$(conda_deactivate)

$(center_extremity_ctrl): $(scvelo_ctrl)
	$(call section,center-extremity (control data))
	$(conda_activate) preprocess
	python pipeline/macrostates/scbridge_macrostates.py $< $(@D) \
		--obs leiden --obsm X_umap \
		--dimension $(DIM_UMAP_CTRL) \
		--center $(CENTER_CTRL) --extremity $(EXTREMITY_CTRL) $(EXCLUDE_CTRL) \
		--macrostate-size $(MACROSTATE_SIZE) \
		--plot-3d
	$(conda_deactivate)

$(center_extremity_treated): $(SCVELO_TREATED)
	$(call section,macrostates (treated data))
	$(conda_activate) preprocess
	python pipeline/macrostates/scbridge_macrostates.py $< $(@D) \
		--obs leiden --obsm X_umap \
		--dimension $(DIM_UMAP_TREATED) \
		--center $(CENTER_TREATED) --extremity $(EXTREMITY_TREATED) $(EXCLUDE_TREATED) \
		--macrostate-size $(MACROSTATE_SIZE) \
		--plot-3d
	$(conda_deactivate)

$(COTAN_CTRL): $(scvelo_ctrl)
	$(call section,cotan (control data))
	mkdir -p $(@D)
	$(conda_activate) preprocess
	python bonesistools/clitools/adata_conversion.py $< $(@D)/.tmp.csv --from h5ad --to csv --layer matrix
	ruby -rcsv -e 'puts CSV.parse(STDIN).transpose.map &:to_csv' < $(@D)/.tmp.csv > $(@D)/counts.csv
	rm $(@D)/.tmp.csv
	$(conda_deactivate)
	$(conda_activate) cotan
	Rscript pipeline/macrostates/cotan_clustering.R --infile $(@D)/counts.csv --outpath $(@D) --sep , \
		--condition ctrl \
		--cotan-filtering \
		--min-ude 0.3 \
		--max-iterations 25 \
		--method strong-merging \
		--jobs $(JOBS)
	$(conda_deactivate)
	sed -i '1 i\,cotan' $(@D)/clusters.csv
	$(conda_activate) preprocess
	python bonesistools/clitools/add_to_adata.py $< $@ --obs $(@D)/clusters.csv --obs-type str --sep ,
	python figures/plot_embedding.py figures/cotan_clusters.json --infile $@ --outfile $(@D)/cotan_clusters
	$(conda_deactivate)

$(COTAN_TREATED): $(SCVELO_TREATED)
	$(call section,cotan (control data))
	mkdir -p $(@D)
	$(conda_activate) preprocess
	python bonesistools/clitools/adata_conversion.py $< $(@D)/.tmp.csv --from h5ad --to csv --layer matrix
	ruby -rcsv -e 'puts CSV.parse(STDIN).transpose.map &:to_csv' < $(@D)/.tmp.csv > $(@D)/counts.csv
	rm $(@D)/.tmp.csv
	$(conda_deactivate)
	$(conda_activate) cotan
	Rscript pipeline/macrostates/cotan_clustering.R --infile $(@D)/counts.csv --outpath $(@D) --sep , \
		--condition treated \
		--cotan-filtering \
		--min-ude 0.3 \
		--max-iterations 25 \
		--method strong-merging \
		--jobs $(JOBS)
	$(conda_deactivate)
	sed -i '1 i\,cotan' $(@D)/clusters.csv
	$(conda_activate) preprocess
	python bonesistools/clitools/add_to_adata.py $< $@ --obs $(@D)/clusters.csv --obs-type str --sep ,
	python figures/plot_embedding.py figures/cotan_clusters.json --infile $@ --outfile $(@D)/cotan_clusters
	$(conda_deactivate)

$(bin_cell_ctrl): $(MACROSTATES_CTRL)
	$(call section,scboolseq (control data))
	$(conda_activate) scboolseq
	python pipeline/binarization/scboolseq_bin.py $< -o $(dir $@) \
		--cluster leiden macrostates \
		--exclude nan --layer log-normalize $(BINARIZATION_ONLY_HVG) $(ZEROES_ARE_ZEROES) --verbose
	$(conda_deactivate)

$(bin_cell_treated): $(MACROSTATES_TREATED)
	$(call section,scboolseq (control data))
	$(conda_activate) scboolseq
	python pipeline/binarization/scboolseq_bin.py $< -o $(dir $@) \
		--cluster leiden macrostates \
		--exclude nan --layer log-normalize $(BINARIZATION_ONLY_HVG) $(ZEROES_ARE_ZEROES) --verbose
	$(conda_deactivate)

ifeq ($(INTEGRATED_BINARIZATION),split)
$(bin_cells_integrated): $(bin_cell_ctrl) $(bin_cell_treated)
	$(call section,scboolseq (integrated data))
	$(conda_activate) preprocess
	python pipeline/utils/csv_concatenation.py $^ --suffixes $(addprefix _,$(conditions)) -o $@
	$(conda_deactivate)
else
$(bin_cells_integrated): $(MACROSTATES_CTRL) $(MACROSTATES_TREATED)
	$(call section,scboolseq (integrated data))
	$(conda_activate) scboolseq
	python pipeline/binarization/scboolseq_bin.py $^ -o $(dir $@) \
		--cluster leiden macrostates \
		--conditions $(conditions) --exclude nan --layer log-normalize $(BINARIZATION_ONLY_HVG) $(ZEROES_ARE_ZEROES) --verbose
	$(conda_deactivate)
endif

$(BDC_CTRL): $(bin_cell_ctrl)
	$(call section,Boolean differential calculus (control data))
	$(conda_activate) scboolseq
	python pipeline/binarization/differential_analysis.py $< $(@D) --verbose
	$(conda_deactivate)

$(BDC_TREATED): $(bin_cell_treated)
	$(call section,Boolean differential calculus (treated data))
	$(conda_activate) scboolseq
	python pipeline/binarization/differential_analysis.py $< $(@D) --verbose
	$(conda_deactivate)

$(MODEL_SPECIFICATION_CTRL): $(TRAJECTORIES_MACROSTATES_CTRL)
	$(call section,model-specification (control data))
	mkdir -p $(@D)
	python3 pipeline/inference/bonesis_specification.py $< > $@

$(MODEL_SPECIFICATION_TREATED): $(TRAJECTORIES_MACROSTATES_TREATED)
	$(call section,model-specification (treated data))
	mkdir -p $(@D)
	python3 pipeline/inference/bonesis_specification.py $< > $@

$(model_specification_integrated): $(TRAJECTORIES_MACROSTATES_CTRL) $(TRAJECTORIES_MACROSTATES_TREATED)
	$(call section,model-specification (integrated data))
	mkdir -p $(@D)
	python3 pipeline/inference/bonesis_specification.py $^ --conditions $(conditions) > $@

$(BONESIS_FILTER1_CTRL): $(MODEL_SPECIFICATION_CTRL) $(bin_cell_ctrl)
	$(call section,Bonesis filtering (control data, stage 1))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python pipeline/inference/bonesis_inference.py filter-stage1 $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(lastword $^) \
		> $@
	$(conda_deactivate)

$(BONESIS_FILTER1_TREATED): $(MODEL_SPECIFICATION_TREATED) $(bin_cell_treated)
	$(call section,Bonesis filtering (treated data, stage 1))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python pipeline/inference/bonesis_inference.py filter-stage1 $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(lastword $^) \
		> $@
	$(conda_deactivate)

$(BONESIS_FILTER1_INTEGRATED): $(model_specification_integrated) $(bin_cells_integrated)
	$(call section,Bonesis filtering (integrated data, stage 1))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python pipeline/inference/bonesis_inference.py filter-stage1 $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(lastword $^) \
		> $@
	$(conda_deactivate)

$(BONESIS_FILTER2_CTRL): $(MODEL_SPECIFICATION_CTRL) $(bin_cell_ctrl) $(BONESIS_FILTER1_CTRL) 
	$(call section,Bonesis filtering (control data, stage 2))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python pipeline/inference/bonesis_inference.py filter-stage2 $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^) \
		$(MINIMIZE_AUTO_LOOPS) > $@
	$(conda_deactivate)

$(BONESIS_FILTER2_TREATED): $(MODEL_SPECIFICATION_TREATED) $(bin_cell_treated) $(BONESIS_FILTER1_TREATED) 
	$(call section,Bonesis filtering (treated data, stage 2))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python pipeline/inference/bonesis_inference.py filter-stage2 $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^) \
		$(MINIMIZE_AUTO_LOOPS) > $@
	$(conda_deactivate)

$(BONESIS_FILTER2_INTEGRATED): $(model_specification_integrated) $(bin_cells_integrated) $(BONESIS_FILTER1_INTEGRATED) 
	$(call section,Bonesis filtering (integrated data, stage 2))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python pipeline/inference/bonesis_inference.py filter-stage2 $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^) \
		$(MINIMIZE_AUTO_LOOPS) > $@
	$(conda_deactivate)

$(BONESIS_INFERENCE_MIN_CTRL): $(MODEL_SPECIFICATION_CTRL) $(bin_cell_ctrl) $(BONESIS_FILTER2_CTRL)
	$(call section,Bonesis inference (control data, minimal solution))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python pipeline/inference/bonesis_inference.py one-min $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^) \
		$(MINIMIZE_AUTO_LOOPS)
	$(conda_deactivate)
	dot -Tpdf $(@D)/one-min.dot > $(@D)/one-min.pdf

$(BONESIS_INFERENCE_MIN_TREATED): $(MODEL_SPECIFICATION_TREATED) $(bin_cell_treated) $(BONESIS_FILTER2_TREATED)
	$(call section,Bonesis inference (treated data, minimal solution))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python pipeline/inference/bonesis_inference.py one-min $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^) \
		$(MINIMIZE_AUTO_LOOPS)
	$(conda_deactivate)
	dot -Tpdf $(@D)/one-min.dot > $(@D)/one-min.pdf

$(BONESIS_INFERENCE_MIN_INTEGRATED): $(model_specification_integrated) $(bin_cells_integrated) $(BONESIS_FILTER2_INTEGRATED)
	$(call section,Bonesis inference (integrated data, minimal solution))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python pipeline/inference/bonesis_inference.py one-min $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^) \
		$(MINIMIZE_AUTO_LOOPS)
	$(conda_deactivate)
	dot -Tpdf $(@D)/one-min.dot > $(@D)/one-min.pdf

$(BONESIS_INFERENCE_SUB_CTRL): $(MODEL_SPECIFICATION_CTRL) $(bin_cell_ctrl) $(BONESIS_FILTER2_CTRL)
	$(call section,Bonesis inference (control data, subset minimal solution))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python pipeline/inference/bonesis_inference.py one-sub $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^)
	$(conda_deactivate)
	dot -Tpdf $(@D)/one-sub.dot > $(@D)/one-sub.pdf

$(BONESIS_INFERENCE_SUB_TREATED): $(MODEL_SPECIFICATION_TREATED) $(bin_cell_treated) $(BONESIS_FILTER2_TREATED)
	$(call section,Bonesis inference (treated data, subset minimal solution))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python pipeline/inference/bonesis_inference.py one-sub $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^)
	$(conda_deactivate)
	dot -Tpdf $(@D)/one-sub.dot > $(@D)/one-sub.pdf

$(BONESIS_INFERENCE_SUB_INTEGRATED): $(model_specification_integrated) $(bin_cells_integrated) $(BONESIS_FILTER2_INTEGRATED)
	$(call section,Bonesis inference (integrated data, subset minimal solution))
	mkdir -p $(@D)
	$(conda_activate) bonesis
	python pipeline/inference/bonesis_inference.py one-sub $(@D) \
		--organism $(ORGANISM) \
		--model-specification $(firstword $^) \
		--bin-metastates $(word 2, $^) \
  		--filter-grn $(lastword $^)
	$(conda_deactivate)
	dot -Tpdf $(@D)/one-sub.dot > $(@D)/one-sub.pdf

## END RULES