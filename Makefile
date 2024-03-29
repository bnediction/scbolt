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

INTEGRATION_METHOD = bbknn

FILES_10XGENOMICS_CT = $(RNA)/raw/ct/matrix.mtx.gz $(RNA)/raw/ct/features.tsv.gz $(RNA)/raw/ct/barcodes.tsv.gz
FILES_10XGENOMICS_RA = $(RNA)/raw/ra/matrix.mtx.gz $(RNA)/raw/ra/features.tsv.gz $(RNA)/raw/ra/barcodes.tsv.gz
FILE_H5AD_CT = $(RNA)/raw/ct/ct.h5ad
FILE_H5AD_RA = $(RNA)/raw/ra/ra.h5ad
FILE_CYCLE_MARKERS = $(PUBLIC)/cycle_phases/mouse_cycle_markers.rds
PATH_FILTER_CT = $(RNA)/cell_filtering/ct
PATH_FILTER_RA = $(RNA)/cell_filtering/ra
PATH_SIGNATURES = $(PUBLIC)/signatures
PATH_NORMALISATION_CT = $(RNA)/normalization/ct
PATH_NORMALISATION_RA = $(RNA)/normalization/ra
PATH_CLUSTER_CT = $(RNA)/cluster/ct
PATH_CLUSTER_RA = $(RNA)/cluster/ra
PATH_MARKERS_CT = $(RNA)/markers/ct
PATH_MARKERS_RA = $(RNA)/markers/ra
PATH_INTEGRATION = $(RNA)/integration
FILES_INTEGRATION = $(wildcard $(PATH_INTEGRATION)/tables/*.h5ad)
PATH_MARKERS_ALL = $(RNA)/markers/all

define section
	echo -e '$(RED)===== $(1) =====$(NC)'
endef

all: $(PATH_MARKERS_CT) $(PATH_MARKERS_RA)

integration: $(PATH_MARKERS_ALL)/bbknn_labels.h5ad

clean:
	rm -rf $(RNA)

mrproper:
	rm -rf data/*
	touch data/.placeholder

load-ctrl: $(FILES_10XGENOMICS_CT)
load-treated: $(FILES_10XGENOMICS_RA)
convert-ctrl: $(FILE_H5AD_CT)
convert-treated: $(FILE_H5AD_RA)
load-markers: $(PUBLIC)/cycle_phases/mouse_cycle_markers.rds
filter-ctrl: $(PATH_FILTER_CT)
filter-treated: $(PATH_FILTER_RA)
load-signatures: $(PATH_SIGNATURES)/geiger.xls $(PATH_SIGNATURES)/chambers.xls
convert-signatures: $(PATH_SIGNATURES)/signatures.json
normalize-ctrl: $(PATH_NORMALISATION_CT)
normalize-treated: $(PATH_NORMALISATION_RA)

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
	wget --quiet -cO $@ \
		https://github.com/MarioniLab/scran/raw/master/inst/exdata/mouse_cycle_markers.rds

$(PATH_FILTER_CT)/tables/counts.h5ad: $(FILE_H5AD_CT) $(FILE_CYCLE_MARKERS)
	$(call section,filtering (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/filter_cells.py \
		--infile $(word 1,$^) \
		--marker $(word 2,$^) \
		--outpath $(PATH_FILTER_CT) \
		--mitochondrial_threshold 5 \
		--upper-mad 2 \
		--lower-mad 3 \
		--consistency-mad
	$(CONDA_DEACTIVATE)

$(PATH_FILTER_RA)/tables/counts.h5ad: $(FILE_H5AD_RA) $(FILE_CYCLE_MARKERS)
	$(call section,filtering (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/filter_cells.py \
		--infile $(word 1,$^) \
		--marker $(word 2,$^) \
		--outpath $(PATH_FILTER_RA) \
		--mitochondrial_threshold 5 \
		--upper-mad 2 \
		--lower-mad 3 \
		--consistency-mad
	$(CONDA_DEACTIVATE)

$(PATH_SIGNATURES)/geiger.xls $(PATH_SIGNATURES)/chambers.xls:
	$(call section,download signatures)
	mkdir -p $(PATH_SIGNATURES)
	wget --quiet -cO $(PATH_SIGNATURES)/geiger.xls https://doi.org/10.1371/journal.pbio.2003389.s025 
	wget --quiet -cO $(PATH_SIGNATURES)/chambers.xls https://ars.els-cdn.com/content/image/1-s2.0-S1934590907002202-mmc3.xls

$(PATH_SIGNATURES)/signatures.json: $(PATH_SIGNATURES)/geiger.xls $(PATH_SIGNATURES)/chambers.xls
	$(call section,convert signatures)
	python pipeline/preprocess/load_signatures.py \
  		--list-infile $(word 1,$^) \
  		--table-infile $(word 2,$^) \
  		--outfile $@

$(PATH_NORMALISATION_CT)/tables/corrected.h5ad: $(PATH_FILTER_CT)/tables/counts.h5ad
	$(call section,normalization (control data))
	$(eval JOBS := $(shell getconf _NPROCESSORS_ONLN))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/normalization.py $< $(PATH_NORMALISATION_CT) \
		--correction G2M_score S_score G1_score \
		--min-cell-expression-proportion 0.001 \
		--jobs $(JOBS)
	$(CONDA_DEACTIVATE)

$(PATH_NORMALISATION_RA)/tables/corrected.h5ad: $(PATH_FILTER_RA)/tables/counts.h5ad
	$(call section,normalization (treated data))
	$(eval JOBS := $(shell getconf _NPROCESSORS_ONLN))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/normalization.py $< $(PATH_NORMALISATION_RA) \
		--correction G2M_score S_score G1_score \
		--min-cell-expression-proportion 0.001 \
		--jobs $(JOBS)
	$(CONDA_DEACTIVATE)

$(PATH_CLUSTER_CT)/tables/counts.h5ad: $(PATH_NORMALISATION_CT)/tables/corrected.h5ad $(PATH_SIGNATURES)/signatures.json
	$(call section,clustering (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/clusters.py $< $(PATH_CLUSTER_CT) \
		--k-neighbors 20 \
		--neighborhood-graph knn \
		--dimensions 15 \
		--resolution 0.6 \
		--verbose
	$(CONDA_DEACTIVATE)

$(PATH_CLUSTER_RA)/tables/counts.h5ad: $(PATH_NORMALISATION_RA)/tables/corrected.h5ad
	$(call section,clustering (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/clusters.py $< $(PATH_CLUSTER_RA) \
		--k-neighbors 20 \
		--neighborhood-graph knn \
		--dimensions 15 \
		--resolution 0.6 \
		--verbose
	$(CONDA_DEACTIVATE)

$(PATH_MARKERS_CT): $(PATH_CLUSTER_CT)/tables/counts.h5ad $(PATH_SIGNATURES)/signatures.json
	$(call section,analyse cell types (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/analyse_markers.py $^ $@ \
  		--group leiden \
  		--logfc-threshold 0.25 \
  		--verbose
	$(CONDA_DEACTIVATE)

$(PATH_MARKERS_RA): $(PATH_CLUSTER_RA)/tables/counts.h5ad $(PATH_SIGNATURES)/signatures.json
	$(call section,analyse cell types (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/analyse_markers.py $^ $@ \
  		--group leiden \
  		--logfc-threshold 0.25 \
  		--verbose
	$(CONDA_DEACTIVATE)

$(PATH_INTEGRATION)/tables/$(INTEGRATION_METHOD).h5ad: $(PATH_NORMALISATION_CT)/tables/corrected.h5ad $(PATH_NORMALISATION_RA)/tables/corrected.h5ad
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

$(PATH_MARKERS_ALL)/bbknn.h5ad: $(PATH_INTEGRATION)/tables/bbknn.h5ad $(PATH_SIGNATURES)/signatures.json
	$(call section,analyse cell types (integrated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/analyse_markers.py $^ $@ \
		--condition condition --group leiden \
		--logfc-threshold 0.25 \
		--verbose
	$(CONDA_DEACTIVATE)

$(PATH_MARKERS_ALL)/bbknn_labels.h5ad: $(PATH_MARKERS_ALL)/bbknn.h5ad
	$(call section,assign cell types (integrated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/label_clusters.py $< $@ \
		--column leiden \
		--name 0=Unknown 1=Rep 2=Prom1 3=Prom2 4=Gran 5=Prom3
	python figures/plot_embedding.py figures/umap_labels.json
	$(CONDA_DEACTIVATE)
