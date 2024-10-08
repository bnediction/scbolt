# computing resources
SHELL = /bin/bash
MEMORY = 50
JOBS = 16

# functions
define section
	@echo -e '$(RED)===== $(1) =====$(NC)'
endef

# metadata
METADATA_CTRL = age=adult date=29-09-2020 sample_name=ctrl condition=control
METADATA_TREATED = age=adult date=29-09-2020 sample_name=treated condition=treated

# url
GENOME_URL = ftp://ftp.ensembl.org/pub/release-112/fasta/mus_musculus/dna/Mus_musculus.GRCm39.dna.primary_assembly.fa.gz
ANNOTATIONS_URL = ftp://ftp.ensembl.org/pub/release-112/gtf/mus_musculus/Mus_musculus.GRCm39.112.chr.gtf.gz
TRANSCRIPTOME_URL = https://cf.10xgenomics.com/supp/cell-exp/refdata-gex-GRCm39-2024-A.tar.gz
CELL_CYCLE_URL = https://github.com/MarioniLab/scran/raw/master/inst/exdata/mouse_cycle_markers.rds
GEIGER_URL = https://doi.org/10.1371/journal.pbio.2003389.s025
CHAMBERS_URL=https://ars.els-cdn.com/content/image/1-s2.0-S1934590907002202-mmc3.xls

# sample ids
SRA_CTRL = SRR15305311 SRR15305312 SRR15305313 SRR15305314
SRA_TREATED = SRR15305315 SRR15305316 SRR15305317 SRR15305318

# directories
PUBLIC = data/public
RNA = data/rna
RNA_CTRL = data/rna/ctrl
RNA_TREATED = data/rna/treated
RNA_INTEGRATED = data/rna/integrated

SIGNATURES = $(PUBLIC)/signatures/geiger.xls $(PUBLIC)/signatures/chambers.xls $(PUBLIC)/signatures/signatures.json
GO_BASIC = $(PUBLIC)/enrichment/go-basic.obo
GO_MOUSE = $(PUBLIC)/enrichment/goslim.obo
GENE2GO = $(PUBLIC)/enrichment/gene2go
MGI_GAF = $(PUBLIC)/enrichment/mgi.gaf
CYCLE_MARKERS = $(PUBLIC)/cycle_phases/mouse_cycle_markers.rds

$(eval GENOME := $(PUBLIC)/genome/$(basename $(notdir $(GENOME_URL))))
$(eval ANNOTATIONS := $(PUBLIC)/genome/$(basename $(notdir $(ANNOTATIONS_URL))))
$(eval TRANSCRIPTOME := $(PUBLIC)/genome/$(notdir $(TRANSCRIPTOME_URL)))
TRANSCRIPTOME := $(TRANSCRIPTOME:.tar.gz=)

FASTQ_CTRL = $(RNA_CTRL)/fastq
FASTQ_TREATED = $(RNA_TREATED)/fastq

CELLRANGER_CTRL = $(RNA_CTRL)/cellranger/ctrl.mri.tgz
CELLRANGER_TREATED = $(RNA_TREATED)/cellranger/treated.mri.tgz

VELOCYTO_CTRL = $(RNA_CTRL)/velocyto/ctrl.loom
VELOCYTO_TREATED = $(RNA_TREATED)/velocyto/treated.loom

H5AD_CTRL = $(RNA_CTRL)/raw/ctrl.h5ad
H5AD_TREATED = $(RNA_TREATED)/raw/treated.h5ad

FILTER_CTRL = $(RNA_CTRL)/cell_filtering/tables/counts.h5ad					# Must contain the parent directory tables/
FILTER_TREATED = $(RNA_TREATED)/cell_filtering/tables/counts.h5ad			# Must contain the parent directory tables/

NORMALISATION_CTRL = $(RNA_CTRL)/normalization/tables/corrected.h5ad		# Must contain the parent directory tables/
NORMALISATION_TREATED = $(RNA_TREATED)/normalization/tables/corrected.h5ad	# Must contain the parent directory tables/

CLUSTER_CTRL = $(RNA_CTRL)/cluster/tables/counts.h5ad						# Must contain the parent directory tables/
CLUSTER_TREATED = $(RNA_TREATED)/cluster/tables/counts.h5ad					# Must contain the parent directory tables/

MARKERS_CTRL = $(RNA_CTRL)/markers/markers.csv
MARKERS_TREATED = $(RNA_TREATED)/markers/markers.csv

OVER_REPRESENTATION_CTRL = $(RNA_CTRL)/enrichment/background.txt

ENRICHMENT_BASIC_CTRL = $(RNA_CTRL)/enrichment/goea_basic.xlsx
ENRICHMENT_MOUSE_CTRL = $(RNA_CTRL)/enrichment/goea_mouse.xlsx
ENRICHMENT_BASIC_TREATED = $(RNA_TREATED)/enrichment/goea_basic.xlsx
ENRICHMENT_MOUSE_TREATED = $(RNA_TREATED)/enrichment/goea_mouse.xlsx

10XGENOMICS_CTRL = $(RNA_CTRL)/raw/matrix.mtx.gz $(RNA_CTRL)/raw/features.tsv.gz $(RNA_CTRL)/raw/barcodes.tsv.gz
10XGENOMICS_TREATED = $(RNA_TREATED)/raw/ra/matrix.mtx.gz $(RNA_TREATED)/raw/ra/features.tsv.gz $(RNA_TREATED)/raw/ra/barcodes.tsv.gz
LABELS_CTRL = $(dir $(CLUSTER_CTRL))/counts_labels.h5ad
PSEUDOTIME_CTRL = $(RNA_CTRL)/stream/pseudotime/ct/tables/stream.h5ad.pkl
TRAJECTORIES_CTRL = $(RNA_CTRL)/stream/trajectories/ct/branches.txt
SCBOOLSEQ_CTRL = $(RNA_CTRL)/binarization/ct/cluster_bin_node_clusters.csv
BDC_CTRL = $(RNA_CTRL)/binarization/ct/pairwise_predecessor_scores.csv
SPECIFICATION_CTRL = $(RNA_CTRL)/bonesis/ct/plzf_TREATEDra_model.txt
FILTER1_CTRL = $(RNA_CTRL)/bonesis/ct/bootstrap_filter_grn_stage1.txt
FILTER2_CTRL = $(RNA_CTRL)/bonesis/ct/bootstrap_filter_grn_stage2.txt
INFERENCE_SUB_CTRL = $(RNA_CTRL)/bonesis/ct/sub.bn
INFERENCE_MIN_CTRL = $(RNA_CTRL)/bonesis/ct/min.bn
INTEGRATION = $(foreach METHOD,$(INTEGRATION_METHOD),$(RNA)/integration/tables/$(METHOD).h5ad) # Must contain the parent directory tables/
MARKERS_ALL = $(RNA)/markers/all/markers.csv

# algorithm parameters
INTEGRATION_METHOD = bbknn
SEED_CLUSTER_CTRL = 0
ROOT = 3
IGNORED_NODES = 4
