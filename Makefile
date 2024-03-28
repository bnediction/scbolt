#!/usr/bin/make

.ONESHELL:

MAKEFLAGS += --silent
SHELL = /bin/bash

NC = \033[0m
RED = \033[0;31m
LIGHT_RED = \033[91m

CONDA_ACTIVATE = source $$(conda info --base)/etc/profile.d/conda.sh ; conda activate ; conda activate
CONDA_DEACTIVATE = source $$(conda info --base)/etc/profile.d/conda.sh ; conda deactivate ; conda deactivate

DATA = data/rna

10XGENOMICS_CT = $(DATA)/raw/ct/matrix.mtx.gz $(DATA)/raw/ct/features.tsv.gz $(DATA)/raw/ct/barcodes.tsv.gz
10XGENOMICS_RA = $(DATA)/raw/ra/matrix.mtx.gz $(DATA)/raw/ra/features.tsv.gz $(DATA)/raw/ra/barcodes.tsv.gz
H5AD_CT = $(DATA)/raw/ct/ct.h5ad
H5AD_RA = $(DATA)/raw/ra/ra.h5ad

define section
	echo -e '$(RED)===== $(1) =====$(NC)'
endef

all: $(H5AD_CT) $(H5AD_RA)

clean:
	rm -rf $(DATA)

mrproper:
	rm -rf data

loadctrl: $(10XGENOMICS_CT)

$(10XGENOMICS_CT):
	$(call section,download 10X genomics data (control sample))
	$(eval FOLDER := $(DATA)/raw/ct)
	mkdir -p $(FOLDER)
	wget --quiet --recursive --no-parent -nd --reject "index.html" \
  		--directory-prefix=$(FOLDER) \
  		ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSM5492nnn/GSM5492245/suppl/
	mv $(FOLDER)/*matrix.mtx.gz $(word 1,$(10XGENOMICS_CT))
	mv $(FOLDER)/*genes.tsv.gz $(word 2,$(10XGENOMICS_CT))
	mv $(FOLDER)/*barcodes.tsv.gz $(word 3,$(10XGENOMICS_CT))

loadtreated: $(10XGENOMICS_RA)

$(10XGENOMICS_RA):
	$(call section,download 10X genomics data (treated sample))
	$(eval FOLDER := $(DATA)/raw/ra)
	mkdir -p $(FOLDER)
	wget --quiet --recursive --no-parent -nd --reject "index.html" \
		--directory-prefix=$(FOLDER) \
		ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSM5492nnn/GSM5492246/suppl/
	mv $(FOLDER)/*matrix.mtx.gz $(word 1,$(10XGENOMICS_RA))
	mv $(FOLDER)/*genes.tsv.gz $(word 2,$(10XGENOMICS_RA))
	mv $(FOLDER)/*barcodes.tsv.gz $(word 3,$(10XGENOMICS_RA))

$(H5AD_CT): $(10XGENOMICS_CT)
	$(call section,conversion (control sample))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/load_10X.py $(<D) $@ \
		--sample-info age=adult date=29-09-2020 sample_name=ctrl condition=control
	$(CONDA_DEACTIVATE)

$(H5AD_RA): $(10XGENOMICS_RA)
	$(call section,conversion (treated sample))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/load_10X.py $(<D) $@ \
		--sample-info age=adult date=29-09-2020 sample_name=ra condition=treated
	$(CONDA_DEACTIVATE)
