#!/usr/bin/env make

.ONESHELL:

MAKEFLAGS += --silent
SHELL = /bin/bash

NC = \033[0m
RED = \033[0;31m
BOLDGREEN = \033[1;32m

SRA_CT = SRR15305311 SRR15305312 SRR15305313 SRR15305314
SRA_RA = SRR15305315 SRR15305316 SRR15305317 SRR15305318

ORGANISM = mouse
SEED_CLUSTER_CT = 0
ROOT = 3
IGNORED_NODES = 4

GENOME_URL = ftp://ftp.ensembl.org/pub/release-112/fasta/mus_musculus/dna/Mus_musculus.GRCm39.dna.primary_assembly.fa.gz
ANNOTATIONS_URL = ftp://ftp.ensembl.org/pub/release-112/gtf/mus_musculus/Mus_musculus.GRCm39.112.chr.gtf.gz
TRANSCRIPTOME_URL = https://cf.10xgenomics.com/supp/cell-exp/refdata-gex-GRCm39-2024-A.tar.gz

$(eval JOBS := $(shell getconf _NPROCESSORS_ONLN))

CONDA_ACTIVATE = source $$(conda info --base)/etc/profile.d/conda.sh ; conda activate ; conda activate
CONDA_DEACTIVATE = source $$(conda info --base)/etc/profile.d/conda.sh ; conda deactivate ; conda deactivate

RNA = data/rna
PUBLIC = data/public

INTEGRATION_METHOD = bbknn

$(eval GENOME := $(PUBLIC)/genome/$(basename $(notdir $(GENOME_URL))))
$(eval ANNOTATIONS := $(PUBLIC)/genome/$(basename $(notdir $(ANNOTATIONS_URL))))
$(eval TRANSCRIPTOME := $(PUBLIC)/genome/$(notdir $(TRANSCRIPTOME_URL)))
TRANSCRIPTOME := $(TRANSCRIPTOME:.tar.gz=)
FASTQ_CT = $(RNA)/fastq/ct/ct.fastq.gz
FASTQ_RA = $(RNA)/fastq/ra/ra.fastq.gz
10XGENOMICS_CT = $(RNA)/raw/ct/matrix.mtx.gz $(RNA)/raw/ct/features.tsv.gz $(RNA)/raw/ct/barcodes.tsv.gz
10XGENOMICS_RA = $(RNA)/raw/ra/matrix.mtx.gz $(RNA)/raw/ra/features.tsv.gz $(RNA)/raw/ra/barcodes.tsv.gz
H5AD_CT = $(RNA)/raw/ct/ct.h5ad
H5AD_RA = $(RNA)/raw/ra/ra.h5ad
CYCLE_MARKERS = $(PUBLIC)/cycle_phases/mouse_cycle_markers.rds
FILTER_CT = $(RNA)/cell_filtering/ct/tables/counts.h5ad
FILTER_RA = $(RNA)/cell_filtering/ra/tables/counts.h5ad
SIGNATURES = $(PUBLIC)/signatures/geiger.xls $(PUBLIC)/signatures/chambers.xls $(PUBLIC)/signatures/signatures.json
NORMALISATION_CT = $(RNA)/normalization/ct/tables/corrected.h5ad
NORMALISATION_RA = $(RNA)/normalization/ra/tables/corrected.h5ad
CLUSTER_CT = $(RNA)/cluster/ct/tables/counts.h5ad
CLUSTER_RA = $(RNA)/cluster/ra/tables/counts.h5ad
MARKERS_CT = $(RNA)/markers/ct/markers.csv
MARKERS_RA = $(RNA)/markers/ra/markers.csv
GO_BASIC = $(PUBLIC)/enrichment/go-basic.obo
GO_MOUSE = $(PUBLIC)/enrichment/goslim_mouse.obo
GENE2GO = $(PUBLIC)/enrichment/gene2go
MGI_GAF = $(PUBLIC)/enrichment/mgi.gaf
OVER_REPRESENTATION_CT = $(RNA)/enrichment/ct/background.txt
ENRICHMENT_BASIC_CT = $(RNA)/enrichment/ct/goea_basic.xlsx
ENRICHMENT_MOUSE_CT = $(RNA)/enrichment/ct/goea_mouse.xlsx
ENRICHMENT_BASIC_RA = $(RNA)/enrichment/ra/goea_basic.xlsx
ENRICHMENT_MOUSE_RA = $(RNA)/enrichment/ra/goea_mouse.xlsx
LABELS_CT = $(dir $(CLUSTER_CT))/counts_labels.h5ad
PSEUDOTIME_CT = $(RNA)/stream/pseudotime/ct/tables/stream.h5ad.pkl
TRAJECTORIES_CT = $(RNA)/stream/trajectories/ct/branches.txt
SCBOOLSEQ_CT = $(RNA)/binarization/ct/cluster_bin_node_clusters.csv
BDC_CT = $(RNA)/binarization/ct/pairwise_predecessor_scores.csv
SPECIFICATION_CT = $(RNA)/bonesis/ct/plzf_rara_model.txt
FILTER1_CT = $(RNA)/bonesis/ct/bootstrap_filter_grn_stage1.txt
FILTER2_CT = $(RNA)/bonesis/ct/bootstrap_filter_grn_stage2.txt
INFERENCE_SUB_CT = $(RNA)/bonesis/ct/sub.bn
INFERENCE_MIN_CT = $(RNA)/bonesis/ct/min.bn

INTEGRATION = $(foreach METHOD,$(INTEGRATION_METHOD),$(RNA)/integration/tables/$(METHOD).h5ad)
MARKERS_ALL = $(RNA)/markers/all/markers.csv

define section
	@echo -e '$(RED)===== $(1) =====$(NC)'
endef

define fastq_naming
	N_FASTQ="$$(find $(1) -name "$(2)_[1-4].fastq.gz" -printf '.' | wc -m)"
	if [ $${N_FASTQ} -eq 0 ]; then \
		@echo -e '$(RED)ERROR: fastq downloading failed.$(NC)';\
	elif [ $${N_FASTQ} -eq 1 ]; then \
		mv $(1)/$(2)_1.fastq.gz $(1)/$(2)_R1.fastq.gz;\
	elif [ $${N_FASTQ} -eq 2 ]; then \
		mv $(1)/$(2)_1.fastq.gz $(1)/$(2)_R1.fastq.gz
		mv $(1)/$(2)_2.fastq.gz $(1)/$(2)_R2.fastq.gz;\
	elif [ $${N_FASTQ} -eq 3 ]; then \
		mv $(1)/$(2)_1.fastq.gz $(1)/$(2)_I1.fastq.gz
		mv $(1)/$(2)_2.fastq.gz $(1)/$(2)_R1.fastq.gz
		mv $(1)/$(2)_3.fastq.gz $(1)/$(2)_R2.fastq.gz;\
	elif [ $${N_FASTQ} -eq 4 ]; then \
		mv $(1)/$(2)_1.fastq.gz $(1)/$(2)_I1.fastq.gz
		mv $(1)/$(2)_2.fastq.gz $(1)/$(2)_I2.fastq.gz
		mv $(1)/$(2)_3.fastq.gz $(1)/$(2)_R1.fastq.gz
		mv $(1)/$(2)_4.fastq.gz $(1)/$(2)_R2.fastq.gz;\
	else \
		@echo -e '$(RED)ERROR: number of downloaded fastq exceeds 4.$(NC)';\
	fi
endef

all: $(INFERENCE_SUB_CT) $(INFERENCE_MIN_CT)  $(MARKERS_RA)

integration: $(MARKERS_ALL) $(INTEGRATION)

clean:
	rm -rf $(RNA)

mrproper:
	clean
	rm -rf $(PUBLIC)/genome

load-genome: $(GENOME)
load-annotations: $(ANNOTATIONS)
load-transcriptome: $(TRANSCRIPTOME)
load-fastq-ctrl: $(FASTQ_CT)
load-fastq-treated: $(FASTQ_RA)
load-ctrl: $(10XGENOMICS_CT)
load-treated: $(10XGENOMICS_RA)
load: load-ctrl load-treated
convert-ctrl: $(H5AD_CT)
convert-treated: $(H5AD_RA)
convert: convert-ctrl convert-treated
load-markers: $(CYCLE_MARKERS)
filter-ctrl: $(FILTER_CT)
filter-treated: $(FILTER_RA)
filter: filter-ctrl filter-treated
load-signatures: $(word 1,$(SIGNATURES)) $(word 2,$(SIGNATURES))
convert-signatures: $(lastword $(SIGNATURES))
normalize-ctrl: $(NORMALISATION_CT)
normalize-treated: $(NORMALISATION_RA)
normalize: normalize-ctrl normalize-treated
cluster-ctrl: $(CLUSTER_CT)
cluster-treated: $(CLUSTER_RA)
cluster: cluster-ctrl cluster-treated
load-go: $(GO) $(GENE2GO) $(MGI_GAF)
go-enrichment: $(ENRICHMENT_BASIC_CT) $(ENRICHMENT_MOUSE_CT)
label-ctrl: $(LABELS_CT)
pseudotime-ctrl: $(PSEUDOTIME_CT)
trajectories-ctrl: $(TRAJECTORIES_CT)
stream-ctrl: trajectories-ctrl
scboolseq-ctrl: $(SCBOOLSEQ_CT)
bdc-ctrl: $(BDC_CT)
specification-ctrl: $(SPECIFICATION_CT)
filter-stage1-ctrl: $(FILTER1_CT)
filter-stage2-ctrl: $(FILTER2_CT)
inference-sub-ctrl: $(INFERENCE_SUB_CT)
inference-min-ctrl: $(INFERENCE_MIN_CT)

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

$(FASTQ_CT):
	$(call section,download fastq file (control data))
	$(CONDA_ACTIVATE) fastq-dump
	mkdir -p $(@D)
	for id in $(SRA_CT)
	do
		parallel-fastq-dump --sra-id $${id} --split-files --readids --origfmt --threads $(JOBS) --outdir $(@D) --gzip

		$(call fastq_naming,$(@D),$${id})
	done
#	cat $(@D)/SRR*.fastq.gz > $@
	$(CONDA_DEACTIVATE)

$(FASTQ_RA):
	$(call section,download fastq file (treated data))
	$(CONDA_ACTIVATE) fastq-dump
	rm -rf $(@D)
	mkdir -p $(@D)
	for id in $(SRA_RA)
	do
		parallel-fastq-dump --sra-id $${id} --threads 8 --outdir $(@D) --gzip
	done
#	cat $(@D)/SRR*.fastq.gz > $@
	$(CONDA_DEACTIVATE)

$(10XGENOMICS_CT):
	$(call section,download 10X genomics data (control data))
	mkdir -p $(@D)
	wget --quiet --show-progress --recursive --no-parent -nd --reject "index.html" \
  		--directory-prefix=$(@D) \
  		ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSM5492nnn/GSM5492245/suppl/
	mv $(@D)/*matrix.mtx.gz $(word 1,$(10XGENOMICS_CT))
	mv $(@D)/*genes.tsv.gz $(word 2,$(10XGENOMICS_CT))
	mv $(@D)/*barcodes.tsv.gz $(word 3,$(10XGENOMICS_CT))

$(10XGENOMICS_RA):
	$(call section,download 10X genomics data (treated data))
	mkdir -p $(@D)
	wget --quiet --show-progress --recursive --no-parent -nd --reject "index.html" \
		--directory-prefix=$(@D) \
		ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSM5492nnn/GSM5492246/suppl/
	mv $(@D)/*matrix.mtx.gz $(word 1,$(10XGENOMICS_RA))
	mv $(@D)/*genes.tsv.gz $(word 2,$(10XGENOMICS_RA))
	mv $(@D)/*barcodes.tsv.gz $(word 3,$(10XGENOMICS_RA))

$(H5AD_CT): $(10XGENOMICS_CT)
	$(call section,conversion (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/load_10X.py $(<D) $@ \
		--sample-info age=adult date=29-09-2020 sample_name=ctrl condition=control
	$(CONDA_DEACTIVATE)

$(H5AD_RA): $(10XGENOMICS_RA)
	$(call section,conversion (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/load_10X.py $(<D) $@ \
		--sample-info age=adult date=29-09-2020 sample_name=ra condition=treated
	$(CONDA_DEACTIVATE)

$(CYCLE_MARKERS):
	$(call section,download cycle phase markers)
	mkdir -p $(@D)
	wget --quiet --show-progress -cO $@ \
		https://github.com/MarioniLab/scran/raw/master/inst/exdata/mouse_cycle_markers.rds

$(FILTER_CT): $(H5AD_CT) $(CYCLE_MARKERS)
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

$(FILTER_RA): $(H5AD_RA) $(CYCLE_MARKERS)
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

$(word 1,$(SIGNATURES)) $(word 2,$(SIGNATURES)):
	$(eval FILENAME := $(basename $(notdir $@)))
	if [ $(FILENAME) = "geiger" ]; then \
		URL=https://doi.org/10.1371/journal.pbio.2003389.s025; \
	else \
		URL=https://ars.els-cdn.com/content/image/1-s2.0-S1934590907002202-mmc3.xls; \
	fi
	$(call section,download $(FILENAME) signatures)
	mkdir -p $(@D)
	wget --quiet --show-progress -cO $@ $$URL
	unset URL

$(lastword $(SIGNATURES)): $(word 1,$(SIGNATURES)) $(word 2,$(SIGNATURES))
	$(call section,convert signatures)
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/load_signatures.py \
		--list-infile $(firstword $^) \
		--table-infile $(lastword $^) \
  		--outfile $@
	$(CONDA_DEACTIVATE)

$(NORMALISATION_CT): $(FILTER_CT)
	$(call section,normalization (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/normalization.py $< $(shell echo $(dir $@) | sed "s/tables\///") \
		--correction G2M_score S_score G1_score \
		--min-cell-expression-proportion 0.001 \
		--jobs $(JOBS)
	$(CONDA_DEACTIVATE)

$(NORMALISATION_RA): $(FILTER_RA)
	$(call section,normalization (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/normalization.py $< $(shell echo $(dir $@) | sed "s/tables\///") \
		--correction G2M_score S_score G1_score \
		--min-cell-expression-proportion 0.001 \
		--jobs $(JOBS)
	$(CONDA_DEACTIVATE)

$(CLUSTER_CT): $(NORMALISATION_CT) $(lastword $(SIGNATURES))
	$(call section,clustering (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/clusters.py $< $(shell echo $(dir $@) | sed "s/tables\///") \
		--hvg --metric euclidean --k-neighbors 20 --resolution 0.45 \
		--dim-pca 50 --dim-clustering 15 --dim-umap 2 \
		--add-legend \
		--seed $(SEED_CLUSTER_CT) --verbose
	$(CONDA_DEACTIVATE)

$(CLUSTER_RA): $(NORMALISATION_RA)
	$(call section,clustering (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/clusters.py $< $(shell echo $(dir $@) | sed "s/tables\///") \
		--hvg --metric euclidean --k-neighbors 20 --resolution 0.4 \
		--dim-pca 50 --dim-clustering 15 --dim-umap 2 \
		--add-legend \
		--seed 1 --verbose
	$(CONDA_DEACTIVATE)

$(MARKERS_CT): $(CLUSTER_CT) $(lastword $(SIGNATURES))
	$(call section,analyse cell types (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/markers.py $^ $(@D) \
  		--group leiden \
  		--logfc-threshold 0.25 \
  		--verbose
	$(CONDA_DEACTIVATE)

$(MARKERS_RA): $(CLUSTER_RA) $(lastword $(SIGNATURES))
	$(call section,analyse cell types (treated data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/markers.py $^ $(@D) \
  		--group leiden \
  		--logfc-threshold 0.25 \
  		--verbose
	$(CONDA_DEACTIVATE)

$(OVER_REPRESENTATION_CT): $(CLUSTER_CT) $(MARKERS_CT)
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

$(ENRICHMENT_BASIC_CT): $(OVER_REPRESENTATION_CT) $(GO_BASIC) $(GENE2GO)
	$(call section,gene ontology enrichment analysis (control data, with go-basic.obo))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/enrichment.py $@ \
    	--population $< \
    	--study $(<D)/cluster*.txt \
    	--go $(word 2,$^) \
    	--gene2go $(lastword $^) \
    	--verbose
	$(CONDA_DEACTIVATE)

$(ENRICHMENT_MOUSE_CT): $(OVER_REPRESENTATION_CT) $(GO_MOUSE) $(GENE2GO)
	$(call section,gene ontology enrichment analysis (control data, with goslim_mouse.obo))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/enrichment.py $@ \
    	--population $< \
    	--study $(<D)/cluster*.txt \
    	--go $(word 2,$^) \
    	--gene2go $(lastword $^) \
    	--verbose
	$(CONDA_DEACTIVATE)

$(OVER_REPRESENTATION_RA): $(CLUSTER_RA) $(MARKERS_RA)
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

$(ENRICHMENT_BASIC_RA): $(OVER_REPRESENTATION_RA) $(GO_BASIC) $(GENE2GO)
	$(call section,gene ontology enrichment analysis (treated data, with go-basic.obo))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/enrichment.py $@ \
    	--population $< \
    	--study $(<D)/cluster*.txt \
    	--go $(word 2,$^) \
    	--gene2go $(lastword $^) \
    	--verbose
	$(CONDA_DEACTIVATE)

$(ENRICHMENT_MOUSE_RA): $(OVER_REPRESENTATION_RA) $(GO_MOUSE) $(GENE2GO)
	$(call section,gene ontology enrichment analysis (treated data, with goslim_mouse.obo))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/enrichment.py $@ \
    	--population $< \
    	--study $(<D)/cluster*.txt \
    	--go $(word 2,$^) \
    	--gene2go $(lastword $^) \
    	--verbose
	$(CONDA_DEACTIVATE)

$(LABELS_CT): $(CLUSTER_CT)
	$(call section,assign cell types (control data))
	$(CONDA_ACTIVATE) preprocess
	python pipeline/preprocess/label_clusters.py $< $@ \
		--column leiden \
		--name 0=Prom2 1=Trans 2=Rep 3=Prom1 4=Prom3 5=Gran
	python figures/plot_embedding.py figures/umap_labels.json \
		--infile $@ --outfile $(shell echo $(dir $@) | sed "s/tables/figures\/umap_labels/")
	$(CONDA_DEACTIVATE)

$(PSEUDOTIME_CT): $(LABELS_CT)
	$(call section,trajectory analysis (stream pseudotime, control data))
	$(CONDA_ACTIVATE) stream
	python pipeline/stream/pseudotime.py $< $(shell echo $(dir $@) | sed "s/tables\///") \
		--extension both --cluster-number 6 --groups leiden \
		--lambda 0.05 --mu 0.03 --alpha 0.03 \
		--extend-leaf-nodes --extend-mode WeigthedCentroid --extend-parameter 0.8 \
		--add-legend --add-graph \
		--jobs $(JOBS)
	$(CONDA_DEACTIVATE)

$(SCBOOLSEQ_CT): $(PSEUDOTIME_CT)
	$(call section,scBoolSeq binarization (control data))
	$(CONDA_ACTIVATE) scboolseq
	python pipeline/binarization/bin_clusters.py $(shell echo $< | sed "s/.pkl//") $(dir $@) \
		--cluster leiden node_clusters --exclude nan \
		--layer log-normalize --hvg \
		--verbose
	$(CONDA DEACTIVATE)

$(BDC_CT): $(SCBOOLSEQ_CT)
	$(call section,Boolean differential calculus (control data))
	$(CONDA_ACTIVATE) scboolseq
	python pipeline/binarization/differential_analysis.py $< $(@D) --verbose
	$(CONDA DEACTIVATE)

$(TRAJECTORIES_CT): $(PSEUDOTIME_CT)
	$(call section,trajectory analysis (stream trajectories, control data))
	@echo -e '$(BOLDGREEN)Warning: root can be modified depending on previous Boolean differential calculus analysis$(NC)'
	$(CONDA_ACTIVATE) stream
	python pipeline/stream/trajectories.py $< $(@D) --root $(ROOT) \
		--groups leiden kmeans node_clusters \
		--add-legend --add-graph \
		--ignore-nodes $(IGNORED_NODES)
	$(CONDA DEACTIVATE)

$(SPECIFICATION_CT): $(TRAJECTORIES_CT)
	$(call section,Bonesis model specification (control data))
	mkdir -p $(@D)
	python3 pipeline/bonesis/design_bo.py $< > $@

$(FILTER1_CT): $(SPECIFICATION_CT) $(SCBOOLSEQ_CT)
	$(call section,Bonesis filtering (control data, stage 1))
	$(CONDA_ACTIVATE) bonesis
	mkdir -p $(@D)
	python pipeline/bonesis/infer_bo.py filter_stage1 $(dir $<) \
		--organism $(ORGANISM) \
		--bin-metastates $(lastword $^) \
  		--model-specification $(firstword $^) > $@
	$(CONDA_DEACTIVATE)

$(FILTER2_CT): $(FILTER1_CT) $(SPECIFICATION_CT) $(SCBOOLSEQ_CT)
	$(call section,Bonesis filtering (control data, stage 2))
	$(CONDA_ACTIVATE) bonesis
	python pipeline/bonesis/infer_bo.py filter_stage2 $(dir $<) \
		--organism $(ORGANISM) \
		--bin-metastates $(lastword $^) \
  		--model-specification $(word 2, $^) \
  		--filter-grn $(firstword $^) > $@
	$(CONDA_DEACTIVATE)

$(INFERENCE_SUB_CT): $(FILTER2_CT) $(SPECIFICATION_CT) $(SCBOOLSEQ_CT)
	$(call section,Bonesis inference (control data, one-sub))
	$(CONDA_ACTIVATE) bonesis
	mkdir -p $(@D)
	python pipeline/bonesis/infer_bo.py one-sub $(dir $<) \
		--organism $(ORGANISM) \
		--bin-metastates $(lastword $^) \
  		--model-specification $(word 2, $^) \
		--filter-grn $(firstword $^)
	$(CONDA_DEACTIVATE)

$(INFERENCE_MIN_CT): $(FILTER2_CT) $(SPECIFICATION_CT) $(SCBOOLSEQ_CT)
	$(call section,Bonesis inference (control data, one-min))
	$(CONDA_ACTIVATE) bonesis
	mkdir -p $(@D)
	python pipeline/bonesis/infer_bo.py one-min $(dir $<) \
		--bin-metastates $(lastword $^) \
		--model-specification $(word 2, $^) \
		--filter-grn $(firstword $^)
	$(CONDA_DEACTIVATE)


### INTEGRATION ###

$(INTEGRATION): $(NORMALISATION_CT) $(NORMALISATION_RA)
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

