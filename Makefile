#!/usr/bin/env make

.ONESHELL:

MAKEFLAGS += --silent

include config.mk

CONDA_ACTIVATE = source $$(conda info --base)/etc/profile.d/conda.sh ; conda activate ; conda activate
CONDA_DEACTIVATE = source $$(conda info --base)/etc/profile.d/conda.sh ; conda deactivate ; conda deactivate

sample = all

# colors
NC = \033[0m
RED = \033[0;31m
GREEN = \033[0;32m
BOLDGREEN = \033[1;32m
BOLD=\033[1m

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

ifeq ($(sample), control)
 $(eval fastq_target := $(FASTQ_CTRL))
 $(eval cellranger_target := $(CELLRANGER_CTRL))
 $(eval velocyto_target := $(VELOCYTO_CTRL))
 $(eval h5ad_target := $(H5AD_CTRL))
 $(eval filter_target := $(FILTER_CTRL))
 $(eval normalization_target := $(NORMALISATION_CTRL))
 $(eval cluster_target := $(CLUSTER_CTRL))
 $(eval label_target := $(LABELS_CTRL))
else ifeq ($(sample), treated)
 $(eval fastq_target := $(FASTQ_TREATED))
 $(eval cellranger_target := $(CELLRANGER_TREATED))
 $(eval velocyto_target := $(VELOCYTO_TREATED))
 $(eval h5ad_target := $(H5AD_TREATED))
 $(eval filter_target := $(FILTER_TREATED))
 $(eval normalization_target := $(NORMALISATION_TREATED))
 $(eval cluster_target := $(CLUSTER_TREATED))
 $(eval label_target := $(LABELS_TREATED))
else
 $(eval fastq_target := $(FASTQ_CTRL) $(FASTQ_TREATED))
 $(eval cellranger_target := $(CELLRANGER_CTRL) $(CELLRANGER_TREATED))
 $(eval velocyto_target := $(VELOCYTO_CTRL) $(VELOCYTO_TREATED))
 $(eval h5ad_target := $(H5AD_CTRL) $(H5AD_TREATED))
 $(eval filter_target := $(FILTER_CTRL) $(FILTER_TREATED))
 $(eval normalization_target := $(NORMALISATION_CTRL) $(NORMALISATION_TREATED))
 $(eval cluster_target := $(CLUSTER_CTRL) $(CLUSTER_TREATED))
 $(eval label_target := $(LABELS_CTRL) $(LABELS_TREATED))
endif

##@ Help

.PHONY: help
help: ## display this help and exit
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make $(GREEN)<command>$(NC) [sample=control|treated|all]\n"}/^[a-zA-Z_-]+:.*?##/ \
	{ printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(BOLD)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Clean

.PHONY: clean
clean: ## clear cache and private data
	find . -name "\*.pyc" -delete
	find . -name "__pycache__" -delete
	find . -type d -name "cache" -exec rm -rf "{}" \;
	rm -rf $(RNA)
	mkdir $(RNA) $(RNA_CTRL) $(RNA_TREATED) $(RNA_INTEGRATED)

.PHONY: mrproper
mrproper: ## clear cache and public/private data
	find . -name "\*.pyc" -delete
	find . -name "__pycache__" -delete
	find . -type d -name "cache" -exec rm -rf "{}" \;
	rm -rf $(RNA)
	rm -rf $(PUBLIC)/genome
	find $(PUBLIC)/genome ! -name "repeat_msk.gtf" -exec rm -rf "{}" \;
	mkdir $(RNA_CTRL) $(RNA_TREATED) $(RNA_INTEGRATED)

##@ Download

load-genome: $(GENOME) ## download DNA primary assembly genome
load-annotations: $(TRANSCRIPTOME) ## download genome-related annotations
load-fastq: $(fastq_target) ## download fastq files
load-markers: $(CYCLE_MARKERS) ## download cycle phase markers
load-signatures: $(lastword $(SIGNATURES)) ## download signatures and convert it into json file

##@ Counting

.PHONY: cellranger
cellranger: $(cellranger_target) ## perform alignment and counting with Cell Ranger
.PHONY: velocyto
velocyto: $(velocyto_target) ## perform spliced/unspliced counting with velocyto

##@ Preprocessing

.PHONY: conversion
conversion: $(h5ad_target) ## convert loom file into h5ad file
.PHONY: filtering
filtering: $(filter_target) ## filtering low quality cells and assignment of cell cycle phases
.PHONY: normalization
normalization: $(normalization_target) ## filtering low quality genes and normalization of counts
.PHONY: clustering
clustering: $(cluster_target) ## perform dimension reduction and cell clustering
.PHONY: labeling
labeling: $(label_target) ## analyse cell clusters


#all: $(INFERENCE_SUB_CTRL) $(INFERENCE_MIN_CTRL)  $(MARKERS_TREATED)
# integration: $(MARKERS_ALL) $(INTEGRATION)
# load-ctrl: $(10XGENOMICS_CTRL)
# load-treated: $(10XGENOMICS_TREATED)
# load: load-ctrl load-treated
load-go: $(GO) $(GENE2GO) $(MGI_GAF)
go-enrichment: $(ENRICHMENT_BASIC_CTRL) $(ENRICHMENT_MOUSE_CTRL)
pseudotime-ctrl: $(PSEUDOTIME_CTRL)
trajectories-ctrl: $(TRAJECTORIES_CTRL)
stream-ctrl: trajectories-ctrl
scboolseq-ctrl: $(SCBOOLSEQ_CTRL)
bdc-ctrl: $(BDC_CTRL)
specification-ctrl: $(SPECIFICATION_CTRL)
filter-stage1-ctrl: $(FILTER1_CTRL)
filter-stage2-ctrl: $(FILTER2_CTRL)
inference-sub-ctrl: $(INFERENCE_SUB_CTRL)
inference-min-ctrl: $(INFERENCE_MIN_CTRL)

$(GENOME):
	$(call section, download genome)
	mkdir -p $(@D)
	wget --quiet --show-progress --directory-prefix=$(@D) $(GENOME_URL)
	gunzip $@.gz

$(ANNOTATIONS):
	$(call section, download annotations)
	mkdir -p $(@D)
	wget --quiet --show-progress --directory-prefix=$(@D) $(ANNOTATIONS_URL)
	gunzip $@.gz

$(TRANSCRIPTOME):
	$(call section, download transcriptome)
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
	$(call section,convert signatures)
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/load_signatures.py \
		--list-infile $(firstword $^) \
		--table-infile $(lastword $^) \
  		--outfile $@
	$(CONDA_DEACTIVATE)

$(FASTQ_CTRL):
	$(call section,download fastq file (control data))
	$(CONDA_ACTIVATE) fastq-dump
	sample_naming="ctrl"
	lane=0
	tmp_directory=/tmp/fastq-ctrl
	rm -rf $${tmp_directory} && mkdir $${tmp_directory}
	for id in $(SRA_CTRL)
	do
		let "lane++"
		parallel-fastq-dump --sra-id $${id} --split-files --readids --origfmt --threads $(JOBS) --outdir $${tmp_directory} --gzip
		$(call fastq_naming,$${tmp_directory},$${id},$${sample_naming},$${lane})
	done
	mkdir $@
	mv $${tmp_directory}/* $@/
	rm -rf $${tmp_directory}
	$(CONDA_DEACTIVATE)

$(FASTQ_TREATED):
	$(call section,download fastq file (treated data))
	$(CONDA_ACTIVATE) fastq-dump
	sample_naming="treated"
	lane=0
	tmp_directory=/tmp/fastq-treated
	rm -rf $${tmp_directory} && mkdir $${tmp_directory}
	for id in $(SRA_TREATED)
	do
		let "lane++"
		parallel-fastq-dump --sra-id $${id} --split-files --readids --origfmt --threads $(JOBS) --outdir $${tmp_directory} --gzip
		$(call fastq_naming,$${tmp_directory},$${id},$${sample_naming},$${lane})
	done
	mkdir $@
	mv $${tmp_directory}/* $@/
	rm -rf $${tmp_directory}
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
	mv $(<D)/velocyto/cellranger.loom $@
	rm -rf $(<D)/velocyto

$(VELOCYTO_TREATED): $(CELLRANGER_TREATED) $(TRANSCRIPTOME)
	$(call section,velocyto (treated data))
	$(CONDA_ACTIVATE) velocyto
	velocyto run10x -m data/public/genome/repeat_msk.gtf \
		--samtools-threads $(JOBS) --samtools-memory $(MEMORY) \
		$(dir $(firstword $^)) $(lastword $^)/genes/genes.gtf
	$(CONDA_DEACTIVATE)
	mkdir -p $(@D)
	mv $(<D)/velocyto/cellranger.loom $@
	rm -rf $(<D)/velocyto

$(H5AD_CTRL): $(VELOCYTO_CTRL)
	$(call section,format conversion from loom to h5ad (control data))
	$(CONDA_ACTIVATE) preprocess
	python bonesis-tools/clitools/conversion_to_h5ad.py $< $@ \
		--sample-info $(METADATA_CTRL) \
		--remove-positions
	$(CONDA_DEACTIVATE)

$(H5AD_TREATED): $(VELOCYTO_TREATED)
	$(call section,format conversion from loom to h5ad (treated data))
	$(CONDA_ACTIVATE) preprocess
	python bonesis-tools/clitools/conversion_to_h5ad.py $< $@ \
		--sample-info $(METADATA_CTRL) \
		--remove-positions
	$(CONDA_DEACTIVATE)

$(FILTER_CTRL): $(H5AD_CTRL) $(CYCLE_MARKERS)
	$(call section,filtering (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/filter_cells.py \
		--infile $(firstword $^) \
		--marker $(lastword $^) \
		--outpath $(shell echo $(dir $@) | sed "s/tables\///") \
		--mitochondrial_threshold 5 \
		--upper-mad 2 \
		--lower-mad 3 \
		--consistency-mad
	$(CONDA_DEACTIVATE)

$(FILTER_TREATED): $(H5AD_TREATED) $(CYCLE_MARKERS)
	$(call section,filtering (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/filter_cells.py \
		--infile $(firstword $^) \
		--marker $(lastword $^) \
		--outpath $(shell echo $(dir $@) | sed "s/tables\///") \
		--mitochondrial_threshold 5 \
		--upper-mad 2 \
		--lower-mad 3 \
		--consistency-mad
	$(CONDA_DEACTIVATE)

$(NORMALISATION_CTRL): $(FILTER_CTRL)
	$(call section,normalization (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/normalization.py $< $(shell echo $(dir $@) | sed "s/tables\///") \
		--correction G2M_score S_score G1_score \
		--min-cell-expression-proportion 0.001 \
		--jobs $(JOBS)
	$(CONDA_DEACTIVATE)

$(NORMALISATION_TREATED): $(FILTER_TREATED)
	$(call section,normalization (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/normalization.py $< $(shell echo $(dir $@) | sed "s/tables\///") \
		--correction G2M_score S_score G1_score \
		--min-cell-expression-proportion 0.001 \
		--jobs $(JOBS)
	$(CONDA_DEACTIVATE)

$(CLUSTER_CTRL): $(NORMALISATION_CTRL)
	$(call section,clustering (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/clusters.py $< $(shell echo $(dir $@) | sed "s/tables\///") \
		--hvg --metric euclidean --k-neighbors 20 --resolution 0.45 \
		--dim-pca 50 --dim-clustering 15 --dim-umap 2 \
		--add-legend \
		--seed $(SEED_CLUSTER_CTRL) --verbose
	$(CONDA_DEACTIVATE)

$(CLUSTER_TREATED): $(NORMALISATION_TREATED)
	$(call section,clustering (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/clusters.py $< $(shell echo $(dir $@) | sed "s/tables\///") \
		--hvg --metric euclidean --k-neighbors 20 --resolution 0.4 \
		--dim-pca 50 --dim-clustering 15 --dim-umap 2 \
		--add-legend \
		--seed 1 --verbose
	$(CONDA_DEACTIVATE)

$(MARKERS_CTRL): $(CLUSTER_CTRL) $(lastword $(SIGNATURES))
	$(call section,analyse cell types (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/markers.py $^ $(@D) \
  		--group leiden \
  		--logfc-threshold 0.25 \
  		--verbose
	$(CONDA_DEACTIVATE)

$(MARKERS_TREATED): $(CLUSTER_TREATED) $(lastword $(SIGNATURES))
	$(call section,analyse cell types (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/markers.py $^ $(@D) \
  		--group leiden \
  		--logfc-threshold 0.25 \
  		--verbose
	$(CONDA_DEACTIVATE)

#############

$(10XGENOMICS_CTRL):
	$(call section,download 10X genomics data (control data))
	mkdir -p $(@D)
	wget --quiet --show-progress --recursive --no-parent -nd --reject "index.html" \
  		--directory-prefix=$(@D) \
  		ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSM5492nnn/GSM5492245/suppl/
	mv $(@D)/*matrix.mtx.gz $(word 1,$(10XGENOMICS_CTRL))
	mv $(@D)/*genes.tsv.gz $(word 2,$(10XGENOMICS_CTRL))
	mv $(@D)/*barcodes.tsv.gz $(word 3,$(10XGENOMICS_CTRL))

$(10XGENOMICS_TREATED):
	$(call section,download 10X genomics data (treated data))
	mkdir -p $(@D)
	wget --quiet --show-progress --recursive --no-parent -nd --reject "index.html" \
		--directory-prefix=$(@D) \
		ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSM5492nnn/GSM5492246/suppl/
	mv $(@D)/*matrix.mtx.gz $(word 1,$(10XGENOMICS_TREATED))
	mv $(@D)/*genes.tsv.gz $(word 2,$(10XGENOMICS_TREATED))
	mv $(@D)/*barcodes.tsv.gz $(word 3,$(10XGENOMICS_TREATED))









$(OVER_REPRESENTATION_CTRL): $(CLUSTER_CTRL) $(MARKERS_CTRL)
	$(call section,over-representation gene set (control data))
	$(CONDA_ACTIVATE) preprocess
	@echo -e 'compute background genes'
	python bonesis-tools/clitools/genename.py $< $@
	$(eval CLUSTER := $(shell column -s, -t < $(lastword $^) | awk 'NR>1 {print $$2}' | sort -u))
	@echo -e 'compute over-representated cluster-related genes'
	for cluster in $(CLUSTER)
	do
		`column -s, -t < $(lastword $^) | awk -v c=$${cluster} '$$2==c {print $$1}' > $(@D)/cluster$${cluster}.txt`
		python bonesis-tools/clitools/genename_standardization.py $(@D)/cluster$${cluster}.txt $(@D)/cluster$${cluster}.txt --quiet
	done
	$(CONDA_DEACTIVATE)

$(ENRICHMENT_BASIC_CTRL): $(OVER_REPRESENTATION_CTRL) $(GO_BASIC) $(GENE2GO)
	$(call section,gene ontology enrichment analysis (control data, with go-basic.obo))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/enrichment.py $@ \
    	--population $< \
    	--study $(<D)/cluster*.txt \
    	--go $(word 2,$^) \
    	--gene2go $(lastword $^) \
    	--verbose
	$(CONDA_DEACTIVATE)

$(ENRICHMENT_MOUSE_CTRL): $(OVER_REPRESENTATION_CTRL) $(GO_MOUSE) $(GENE2GO)
	$(call section,gene ontology enrichment analysis (control data, with goslim_mouse.obo))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/enrichment.py $@ \
    	--population $< \
    	--study $(<D)/cluster*.txt \
    	--go $(word 2,$^) \
    	--gene2go $(lastword $^) \
    	--verbose
	$(CONDA_DEACTIVATE)

$(OVER_REPRESENTATION_TREATED): $(CLUSTER_TREATED) $(MARKERS_TREATED)
	$(call section,over-representation gene set (treated data))
	$(CONDA_ACTIVATE) preprocess
	@echo -e 'compute background genes'
	python bonesis-tools/clitools/genename.py $< $@
	$(eval CLUSTER := $(shell column -s, -t < $(lastword $^) | awk 'NR>1 {print $$2}' | sort -u))
	@echo -e 'compute over-representated cluster-related genes'
	for cluster in $(CLUSTER)
	do
		`column -s, -t < $(lastword $^) | awk -v c=$${cluster} '$$2==c {print $$1}' > $(@D)/cluster$${cluster}.txt`
		python bonesis-tools/clitools/genename_standardization.py $(@D)/cluster$${cluster}.txt $(@D)/cluster$${cluster}.txt --quiet
	done
	$(CONDA_DEACTIVATE)

$(ENRICHMENT_BASIC_TREATED): $(OVER_REPRESENTATION_TREATED) $(GO_BASIC) $(GENE2GO)
	$(call section,gene ontology enrichment analysis (treated data, with go-basic.obo))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/enrichment.py $@ \
    	--population $< \
    	--study $(<D)/cluster*.txt \
    	--go $(word 2,$^) \
    	--gene2go $(lastword $^) \
    	--verbose
	$(CONDA_DEACTIVATE)

$(ENRICHMENT_MOUSE_TREATED): $(OVER_REPRESENTATION_TREATED) $(GO_MOUSE) $(GENE2GO)
	$(call section,gene ontology enrichment analysis (treated data, with goslim_mouse.obo))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/enrichment.py $@ \
    	--population $< \
    	--study $(<D)/cluster*.txt \
    	--go $(word 2,$^) \
    	--gene2go $(lastword $^) \
    	--verbose
	$(CONDA_DEACTIVATE)

$(LABELS_CTRL): $(CLUSTER_CTRL)
	$(call section,assign cell types (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/label_clusters.py $< $@ \
		--column leiden \
		--name 0=Prom2 1=Trans 2=Rep 3=Prom1 4=Prom3 5=Gran
	python figures/plot_embedding.py figures/umap_labels.json \
		--infile $@ --outfile $(shell echo $(dir $@) | sed "s/tables/figures\/umap_labels/")
	$(CONDA_DEACTIVATE)

$(PSEUDOTIME_CTRL): $(LABELS_CTRL)
	$(call section,trajectory analysis (stream pseudotime, control data))
	$(CONDA_ACTIVATE) stream
	python pipeline/stream/pseudotime.py $< $(shell echo $(dir $@) | sed "s/tables\///") \
		--extension both --cluster-number 6 --groups leiden \
		--lambda 0.05 --mu 0.03 --alpha 0.03 \
		--extend-leaf-nodes --extend-mode WeigthedCentroid --extend-parameter 0.8 \
		--add-legend --add-graph \
		--jobs $(JOBS)
	$(CONDA_DEACTIVATE)

$(SCBOOLSEQ_CTRL): $(PSEUDOTIME_CTRL)
	$(call section,scBoolSeq binarization (control data))
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

$(TRAJECTORIES_CTRL): $(PSEUDOTIME_CTRL)
	$(call section,trajectory analysis (stream trajectories, control data))
	@echo -e '$(BOLDGREEN)Warning: root can be modified depending on previous Boolean differential calculus analysis$(NC)'
	$(CONDA_ACTIVATE) stream
	python pipeline/stream/trajectories.py $< $(@D) --root $(ROOT) \
		--groups leiden kmeans node_clusters \
		--add-legend --add-graph \
		--ignore-nodes $(IGNORED_NODES)
	$(CONDA DEACTIVATE)

$(SPECIFICATION_CTRL): $(TRAJECTORIES_CTRL)
	$(call section,Bonesis model specification (control data))
	mkdir -p $(@D)
	python3 pipeline/bonesis/design_bo.py $< > $@

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


### INTEGRATION ###

$(INTEGRATION): $(NORMALISATION_CTRL) $(NORMALISATION_TREATED)
	$(call section,integration)
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/integration.py $^ $(shell echo $(dir $@) | sed "s/tables\///") \
		--label condition --method $(INTEGRATION_METHOD) \
		--dim-pca 50 --dim-clustering 15 --dim-umap 3 \
		--hvg --metric euclidean --k-neighbors 20 --resolution 0.38 \
		--add-legend --plot-3d \
		--jobs $(JOBS) --seed 10 \
		--verbose
	$(CONDA_DEACTIVATE)

$(MARKERS_ALL): $(INTEGRATION) $(lastword $(SIGNATURES))
	$(call section,analyse cell types (integrated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/markers.py $^ $(@D) \
		--condition condition --group leiden \
		--logfc-threshold 0.25 \
		--verbose
	$(CONDA_DEACTIVATE)

$(PATH_INTEGRATION)/tables/$(INTEGRATION_METHOD)_labels.h5ad: $(INTEGRATION)
	$(call section,assign cell types (integrated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/label_clusters.py $< $@ \
		--column leiden \
		--name 0=Unknown 1=Rep 2=Prom1 3=Prom2 4=Gran 5=Prom3
	python figures/plot_embedding.py figures/umap_labels.json
	$(CONDA_DEACTIVATE)


$(GO_BASIC):
	$(call section,download GO go-basic.obo file)
	mkdir -p $(@D)
	wget --quiet --show-progress -cO $@ http://purl.obolibrary.org/obo/go/go-basic.obo

$(GO_MOUSE):
	$(call section,download GO goslim_mouse.obo)
	mkdir -p $(@D)
	wget --quiet --show-progress -cO $@ https://current.geneontology.org/ontology/subsets/goslim_mouse.obo

$(GENE2GO):
	$(call section,download NCBI gene2go file)
	mkdir -p $(@D)
	wget --quiet --show-progress --directory-prefix=$(@D) ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/gene2go.gz
	gunzip $@.gz

$(MGI_GAF):
	$(call section,download mgi.gaf file)
	mkdir -p $(@D)
	wget --quiet --show-progress --directory-prefix=$(@D) https://current.geneontology.org/annotations/mgi.gaf.gz
	gunzip $@.gz

