# computing resources
SHELL = /bin/bash
MEMORY = 64
JOBS = 16

# colors
NC = \033[0m
RED = \033[0;31m
BOLDGREEN = \033[1;32m

# functions
define section
	@echo -e '$(RED)===== $(1) =====$(NC)'
endef

clean:
	rm -rf $(RNA)

mrproper:
	clean
	rm -rf $(PUBLIC)/genome

# metadata
ORGANISM = mouse

# url
GENOME_URL = ftp://ftp.ensembl.org/pub/release-112/fasta/mus_musculus/dna/Mus_musculus.GRCm39.dna.primary_assembly.fa.gz
ANNOTATIONS_URL = ftp://ftp.ensembl.org/pub/release-112/gtf/mus_musculus/Mus_musculus.GRCm39.112.chr.gtf.gz
TRANSCRIPTOME_URL = https://cf.10xgenomics.com/supp/cell-exp/refdata-gex-GRCm39-2024-A.tar.gz

# sample ids
SRA_CTRL = SRR15305311 SRR15305312 SRR15305313 SRR15305314
SRA_TREATED = SRR15305315 SRR15305316 SRR15305317 SRR15305318

# directories
RNA = data/rna
PUBLIC = data/public
$(eval GENOME := $(PUBLIC)/genome/$(basename $(notdir $(GENOME_URL))))
$(eval ANNOTATIONS := $(PUBLIC)/genome/$(basename $(notdir $(ANNOTATIONS_URL))))
$(eval TRANSCRIPTOME := $(PUBLIC)/genome/$(notdir $(TRANSCRIPTOME_URL)))
TRANSCRIPTOME := $(TRANSCRIPTOME:.tar.gz=)
FASTQ_CTRL = $(RNA)/fastq/ct
FASTQ_TREATED = $(RNA)/fastq/ra
CELLRANGER_CTRL = $(RNA)/cellranger/ct/ctrl.mri.tgz
CELLRANGER_TREATED = $(RNA)/cellranger/ra/treated.mri.tgz
VELOCYTO_CTRL = $(RNA)/cellranger/ct/velocyto/ct.loom
VELOCYTO_TREATED = $(RNA)/cellranger/ra/velocyto/ra.loom
10XGENOMICS_CTRL = $(RNA)/raw/ct/matrix.mtx.gz $(RNA)/raw/ct/features.tsv.gz $(RNA)/raw/ct/barcodes.tsv.gz
10XGENOMICS_TREATED = $(RNA)/raw/ra/matrix.mtx.gz $(RNA)/raw/ra/features.tsv.gz $(RNA)/raw/ra/barcodes.tsv.gz
H5AD_CTRL = $(RNA)/raw/ct/ct.h5ad
H5AD_TREATED = $(RNA)/raw/ra/ra.h5ad
CYCLE_MARKERS = $(PUBLIC)/cycle_phases/mouse_cycle_markers.rds
FILTER_CTRL = $(RNA)/cell_filtering/ct/tables/counts.h5ad
FILTER_TREATED = $(RNA)/cell_filtering/ra/tables/counts.h5ad
SIGNATURES = $(PUBLIC)/signatures/geiger.xls $(PUBLIC)/signatures/chambers.xls $(PUBLIC)/signatures/signatures.json
NORMALISATION_CTRL = $(RNA)/normalization/ct/tables/corrected.h5ad
NORMALISATION_TREATED = $(RNA)/normalization/ra/tables/corrected.h5ad
CLUSTER_CTRL = $(RNA)/cluster/ct/tables/counts.h5ad
CLUSTER_TREATED = $(RNA)/cluster/ra/tables/counts.h5ad
MARKERS_CTRL = $(RNA)/markers/ct/markers.csv
MARKERS_TREATED = $(RNA)/markers/ra/markers.csv
GO_BASIC = $(PUBLIC)/enrichment/go-basic.obo
GO_MOUSE = $(PUBLIC)/enrichment/goslim_mouse.obo
GENE2GO = $(PUBLIC)/enrichment/gene2go
MGI_GAF = $(PUBLIC)/enrichment/mgi.gaf
OVER_REPRESENTATION_CTRL = $(RNA)/enrichment/ct/background.txt
ENRICHMENT_BASIC_CTRL = $(RNA)/enrichment/ct/goea_basic.xlsx
ENRICHMENT_MOUSE_CTRL = $(RNA)/enrichment/ct/goea_mouse.xlsx
ENRICHMENT_BASIC_TREATED = $(RNA)/enrichment/ra/goea_basic.xlsx
ENRICHMENT_MOUSE_TREATED = $(RNA)/enrichment/ra/goea_mouse.xlsx
LABELS_CTRL = $(dir $(CLUSTER_CTRL))/counts_labels.h5ad
PSEUDOTIME_CTRL = $(RNA)/stream/pseudotime/ct/tables/stream.h5ad.pkl
TRAJECTORIES_CTRL = $(RNA)/stream/trajectories/ct/branches.txt
SCBOOLSEQ_CTRL = $(RNA)/binarization/ct/cluster_bin_node_clusters.csv
BDC_CTRL = $(RNA)/binarization/ct/pairwise_predecessor_scores.csv
SPECIFICATION_CTRL = $(RNA)/bonesis/ct/plzf_TREATEDra_model.txt
FILTER1_CTRL = $(RNA)/bonesis/ct/bootstrap_filter_grn_stage1.txt
FILTER2_CTRL = $(RNA)/bonesis/ct/bootstrap_filter_grn_stage2.txt
INFERENCE_SUB_CTRL = $(RNA)/bonesis/ct/sub.bn
INFERENCE_MIN_CTRL = $(RNA)/bonesis/ct/min.bn

# algorithm parameters
INTEGRATION_METHOD = bbknn
SEED_CLUSTER_CTRL = 0
ROOT = 3
IGNORED_NODES = 4
