#!/usr/bin/make

.ONESHELL:

MAKEFLAGS += --silent
SHELL = /bin/bash

NC = \033[0m
RED = \033[0;31m
LIGHT_RED = \033[91m

CONDA_ACTIVATE = source $$(conda info --base)/etc/profile.d/conda.sh ; conda activate ; conda activate
CONDA_DEACTIVATE = source $$(conda info --base)/etc/profile.d/conda.sh ; conda deactivate ; conda deactivate

RNA = data/rna
PUBLIC = data/public
SIGNATURES = $(PUBLIC)/signatures

INTEGRATION_METHOD = bbknn

FILES_10XGENOMICS_CT = $(RNA)/raw/ct/matrix.mtx.gz $(RNA)/raw/ct/features.tsv.gz $(RNA)/raw/ct/barcodes.tsv.gz
FILES_10XGENOMICS_RA = $(RNA)/raw/ra/matrix.mtx.gz $(RNA)/raw/ra/features.tsv.gz $(RNA)/raw/ra/barcodes.tsv.gz
FILE_H5AD_CT = $(RNA)/raw/ct/ct.h5ad
FILE_H5AD_RA = $(RNA)/raw/ra/ra.h5ad
FILE_CYCLE_MARKERS = $(PUBLIC)/cycle_phases/mouse_cycle_markers.rds
FILE_FILTER_CT = $(RNA)/cell_filtering/ct/tables/counts.h5ad
FILE_FILTER_RA = $(RNA)/cell_filtering/ra/tables/counts.h5ad
FILE_SIGNATURES = $(SIGNATURES)/geiger.xls $(PATH_SIGNATURES)/chambers.xls $(SIGNATURES)/signatures.json
FILE_NORMALISATION_CT = $(RNA)/normalization/ct/tables/corrected.h5ad
FILE_NORMALISATION_RA = $(RNA)/normalization/ra/tables/corrected.h5ad
FILE_CLUSTER_CT = $(RNA)/cluster/ct/tables/counts.h5ad
FILE_CLUSTER_RA = $(RNA)/cluster/ra/tables/counts.h5ad
FILE_MARKERS_CT = $(RNA)/markers/ct/markers.csv
FILE_MARKERS_RA = $(RNA)/markers/ra/markers.csv
FILE_MARKERS_ALL = $(RNA)/markers/all/markers.csv

PATH_INTEGRATION = $(RNA)/integration
FILES_INTEGRATION = $(wildcard $(PATH_INTEGRATION)/tables/*.h5ad)

define section
	echo -e '$(RED)===== $(1) =====$(NC)'
endef

test:
#	$(eval directory := $(dir $(FILE_H5AD_CT)))
#	$(eval directory := $(shell echo $(directory) | sed "s/ct\///"))
	$(eval directory := $(shell echo $(dir $(FILE_FILTER_CT)) | sed "s/tables\///"))
	echo $(directory)
	echo $(shell echo $(dir $(FILE_FILTER_CT)) | sed "s/tables\///")

all: $(FILE_MARKERS_CT) $(FILE_MARKERS_RA)

integration: $(FILE_MARKERS_ALL) $(PATH_INTEGRATION)/tables/$(INTEGRATION_METHOD)_labels.h5ad

clean:
	rm -rf $(RNA)

mrproper:
	rm -rf data/*
	touch data/.placeholder

load-ctrl: $(FILES_10XGENOMICS_CT)
load-treated: $(FILES_10XGENOMICS_RA)
load: load-ctrl load-treated
convert-ctrl: $(FILE_H5AD_CT)
convert-treated: $(FILE_H5AD_RA)
convert: convert-ctrl convert-treated
load-markers: $(FILE_CYCLE_MARKERS)
filter-ctrl: $(FILE_FILTER_CT)
filter-treated: $(FILE_FILTER_RA)
filter: filter-ctrl filter-treated
load-signatures: $(word 1,$(FILE_SIGNATURES)) $(word 2,$(FILE_SIGNATURES))
convert-signatures: $(lastword $(FILE_SIGNATURES))
normalize-ctrl: $(FILE_NORMALISATION_CT)
normalize-treated: $(FILE_NORMALISATION_RA)
normalize: normalize-ctrl normalize-treated
cluster-ctrl: $(FILE_CLUSTER_CT)
cluster-treated: $(FILE_CLUSTER_RA)
cluster: cluster-ctrl cluster-treated

$(FILES_10XGENOMICS_CT):
	$(call section,download 10X genomics data (control data))
	mkdir -p $(@D)
	wget --quiet --recursive --no-parent -nd --reject "index.html" \
  		--directory-prefix=$(@D) \
  		ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSM5492nnn/GSM5492245/suppl/
	mv $(@D)/*matrix.mtx.gz $(word 1,$(FILES_10XGENOMICS_CT))
	mv $(@D)/*genes.tsv.gz $(word 2,$(FILES_10XGENOMICS_CT))
	mv $(@D)/*barcodes.tsv.gz $(word 3,$(FILES_10XGENOMICS_CT))

$(FILES_10XGENOMICS_RA):
	$(call section,download 10X genomics data (treated data))
	mkdir -p $(@D)
	wget --quiet --recursive --no-parent -nd --reject "index.html" \
		--directory-prefix=$(@D) \
		ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSM5492nnn/GSM5492246/suppl/
	mv $(@D)/*matrix.mtx.gz $(word 1,$(FILES_10XGENOMICS_RA))
	mv $(@D)/*genes.tsv.gz $(word 2,$(FILES_10XGENOMICS_RA))
	mv $(@D)/*barcodes.tsv.gz $(word 3,$(FILES_10XGENOMICS_RA))

$(FILE_H5AD_CT): $(FILES_10XGENOMICS_CT)
	$(call section,conversion (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/load_10X.py $(<D) $@ \
		--sample-info age=adult date=29-09-2020 sample_name=ctrl condition=control
	$(CONDA_DEACTIVATE)

$(FILE_H5AD_RA): $(FILES_10XGENOMICS_RA)
	$(call section,conversion (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/load_10X.py $(<D) $@ \
		--sample-info age=adult date=29-09-2020 sample_name=ra condition=treated
	$(CONDA_DEACTIVATE)

$(FILE_CYCLE_MARKERS):
	$(call section,download cycle phase markers)
	mkdir -p $(@D)
	wget -cO $@ \
		https://github.com/MarioniLab/scran/raw/master/inst/exdata/mouse_cycle_markers.rds

$(FILE_FILTER_CT): $(FILE_H5AD_CT) $(FILE_CYCLE_MARKERS)
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

$(FILE_FILTER_RA): $(FILE_H5AD_RA) $(FILE_CYCLE_MARKERS)
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

$(word 1,$(FILE_SIGNATURES)) $(word 2,$(FILE_SIGNATURES)):
	$(call section,download signatures)
	mkdir -p $(SIGNATURES)
	wget --quiet -cO $(firstword $@) https://doi.org/10.1371/journal.pbio.2003389.s025 
	wget --quiet -cO $(lastword $@) https://ars.els-cdn.com/content/image/1-s2.0-S1934590907002202-mmc3.xls

$(lastword $(FILE_SIGNATURES)): $(word 1,$(FILE_SIGNATURES)) $(word 2,$(FILE_SIGNATURES))
	$(call section,convert signatures)
	python pipeline/preprocess/load_signatures.py \
		--list-infile $(firstword $^) \
		--table-infile $(lastword $^) \
  		--outfile $@

$(FILE_NORMALISATION_CT): $(FILE_FILTER_CT)
	$(call section,normalization (control data))
	$(eval JOBS := $(shell getconf _NPROCESSORS_ONLN))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/normalization.py $< $(shell echo $(dir $@) | sed "s/tables\///") \
		--correction G2M_score S_score G1_score \
		--min-cell-expression-proportion 0.001 \
		--jobs $(JOBS)
	$(CONDA_DEACTIVATE)

$(FILE_NORMALISATION_RA): $(FILE_FILTER_RA)
	$(call section,normalization (treated data))
	$(eval JOBS := $(shell getconf _NPROCESSORS_ONLN))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/normalization.py $< $(shell echo $(dir $@) | sed "s/tables\///") \
		--correction G2M_score S_score G1_score \
		--min-cell-expression-proportion 0.001 \
		--jobs $(JOBS)
	$(CONDA_DEACTIVATE)

$(FILE_CLUSTER_CT): $(FILE_NORMALISATION_CT) $(lastword $(FILE_SIGNATURES))
	$(call section,clustering (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/clusters.py $< $(shell echo $(dir $@) | sed "s/tables\///") \
		--hvg --metric euclidean --k-neighbors 20 --resolution 0.5 \
		--dim-pca 50 --dim-clustering 15 --dim-umap 2 \
		--add-legend \
		--seed 0 --verbose
	$(CONDA_DEACTIVATE)

$(FILE_CLUSTER_RA): $(FILE_NORMALISATION_RA)
	$(call section,clustering (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/clusters.py $< $(shell echo $(dir $@) | sed "s/tables\///") \
		--hvg --metric euclidean --k-neighbors 20 --resolution 0.5 \
		--dim-pca 50 --dim-clustering 15 --dim-umap 2 \
		--add-legend \
		--seed 10 --verbose
	$(CONDA_DEACTIVATE)

$(FILE_MARKERS_CT): $(FILE_CLUSTER_CT) $(lastword $(FILE_SIGNATURES))
	$(call section,analyse cell types (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/analyse_markers.py $^ $(@D) \
  		--group leiden \
  		--logfc-threshold 0.25 \
  		--verbose
	$(CONDA_DEACTIVATE)

$(FILE_MARKERS_RA): $(FILE_CLUSTER_RA)/tables/counts.h5ad $(lastword $(FILE_SIGNATURES))
	$(call section,analyse cell types (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/analyse_markers.py $^ $(@D) \
  		--group leiden \
  		--logfc-threshold 0.25 \
  		--verbose
	$(CONDA_DEACTIVATE)

$(PATH_INTEGRATION)/tables/$(INTEGRATION_METHOD).h5ad: $(FILE_NORMALISATION_CT) $(FILE_NORMALISATION_RA)
	$(call section,integration)
	$(eval JOBS := $(shell getconf _NPROCESSORS_ONLN))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/integration.py $^ $(PATH_INTEGRATION) \
		--label condition --method $(INTEGRATION_METHOD) \
		--dim-pca 50 --dim-clustering 15 --dim-integration 3 \
		--hvg --metric euclidean --k-neighbors 20 --resolution 0.38 \
		--add-legend --plot-3d \
		--jobs $(JOBS) --seed 10 \
		--verbose
	$(CONDA_DEACTIVATE)

$(FILE_MARKERS_ALL): $(PATH_INTEGRATION)/tables/bbknn.h5ad $(lastword $(FILE_SIGNATURES))
	$(call section,analyse cell types (integrated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/analyse_markers.py $^ $(@D) \
		--condition condition --group leiden \
		--logfc-threshold 0.25 \
		--verbose
	$(CONDA_DEACTIVATE)

$(PATH_INTEGRATION)/tables/$(INTEGRATION_METHOD)_labels.h5ad: $(PATH_INTEGRATION)/tables/$(INTEGRATION_METHOD).h5ad
	$(call section,assign cell types (integrated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/label_clusters.py $< $@ \
		--column leiden \
		--name 0=Unknown 1=Rep 2=Prom1 3=Prom2 4=Gran 5=Prom3
	python figures/plot_embedding.py figures/umap_labels.json
	$(CONDA_DEACTIVATE)
