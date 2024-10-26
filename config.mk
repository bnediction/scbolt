# computing resources
SHELL = /bin/bash
MEMORY = 50
JOBS = 16

# functions
define section
	@echo -e '$(GREEN)===== $(1) =====$(NC)'
endef

# metadata
METADATA_CTRL = age=adult date=29-09-2020 sample_name=ctrl condition=control			# Must contains condition
METADATA_TREATED = age=adult date=29-09-2020 sample_name=treated condition=treated		# Must contains condition

# url
GENOME_URL = ftp://ftp.ensembl.org/pub/release-112/fasta/mus_musculus/dna/Mus_musculus.GRCm39.dna.primary_assembly.fa.gz
TRANSCRIPTOME_URL = https://cf.10xgenomics.com/supp/cell-exp/refdata-gex-GRCm39-2024-A.tar.gz
CELL_CYCLE_URL = https://github.com/MarioniLab/scran/raw/master/inst/exdata/mouse_cycle_markers.rds
GO_BASIC_URL = http://purl.obolibrary.org/obo/go/go-basic.obo
GO_MOUSE_URL = https://current.geneontology.org/ontology/subsets/goslim_mouse.obo

# sample ids
SRA_CTRL = SRR15305311 SRR15305312 SRR15305313 SRR15305314
SRA_TREATED = SRR15305315 SRR15305316 SRR15305317 SRR15305318

# directories
PUBLIC = data/public
RNA = data/rna
RNA_CTRL = data/rna/ctrl
RNA_TREATED = data/rna/treated
RNA_INTEGRATED = data/rna/integrated

CYCLE_MARKERS = $(PUBLIC)/cycle_phases/mouse_cycle_markers.rds
SIGNATURES = $(PUBLIC)/signatures/geiger.xls $(PUBLIC)/signatures/chambers.xls $(PUBLIC)/signatures/signatures.json
GO_BASIC = $(PUBLIC)/enrichment/go-basic.obo
GO_MOUSE = $(PUBLIC)/enrichment/goslim.obo
GENE2GO = $(PUBLIC)/enrichment/gene2go

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
CLUSTER_INTEGRATED = $(RNA_INTEGRATED)/cluster/tables/integrated.h5ad		# Must contain the parent directory tables/

MARKERS_CTRL = $(RNA_CTRL)/markers/genes/background.txt
MARKERS_TREATED = $(RNA_TREATED)/markers/genes/background.txt
MARKERS_INTEGRATED = $(RNA_INTEGRATED)/markers/genes/background.txt

GOEA_BASIC_CTRL = $(RNA_CTRL)/enrichment/goea_basic.xlsx
GOEA_MOUSE_CTRL = $(RNA_CTRL)/enrichment/goea_mouse.xlsx
GOEA_BASIC_TREATED = $(RNA_TREATED)/enrichment/goea_basic.xlsx
GOEA_MOUSE_TREATED = $(RNA_TREATED)/enrichment/goea_mouse.xlsx
GOEA_BASIC_INTEGRATED = $(RNA_INTEGRATED)/enrichment/goea_basic.xlsx
GOEA_MOUSE_INTEGRATED = $(RNA_INTEGRATED)/enrichment/goea_mouse.xlsx

LABELS_CTRL = $(dir $(CLUSTER_CTRL))/counts_labels.h5ad
LABELS_TREATED = $(dir $(CLUSTER_TREATED))/counts_labels.h5ad

SCVELO_CTRL = $(RNA_CTRL)/scvelo/tables/scvelo.h5ad							# Must contain the parent directory tables/
SCVELO_TREATED = $(RNA_TREATED)/scvelo/tables/scvelo.h5ad					# Must contain the parent directory tables/

PSEUDOTIME_STREAM_CTRL = $(RNA_CTRL)/stream/pseudotime/tables/stream.h5ad.pkl			# Must contain the parent directory tables/
PSEUDOTIME_STREAM_TREATED = $(RNA_TREATED)/stream/pseudotime/tables/stream.h5ad.pkl		# Must contain the parent directory tables/

TRAJECTORIES_STREAM_CTRL = $(RNA_CTRL)/stream/trajectories/branches.txt
TRAJECTORIES_STREAM_TREATED = $(RNA_TREATED)/stream/trajectories/branches.txt

SCBOOLSEQ_CTRL = $(RNA_CTRL)/binarization/cluster_bin_node_clusters.csv
SCBOOLSEQ_TREATED = $(RNA_TREATED)/binarization/cluster_bin_node_clusters.csv

BDC_CTRL = $(RNA_CTRL)/binarization/pairwise_predecessor_scores.csv
BDC_TREATED = $(RNA_TREATED)/binarization/pairwise_predecessor_scores.csv

MODEL_SPECIFICATION_CTRL = $(RNA_CTRL)/bonesis/specification_model.txt
MODEL_SPECIFICATION_TREATED = $(RNA_TREATED)/bonesis/specification_model.txt

FILTER1_CTRL = $(RNA_CTRL)/bonesis/ct/bootstrap_filter_grn_stage1.txt
FILTER2_CTRL = $(RNA_CTRL)/bonesis/ct/bootstrap_filter_grn_stage2.txt
INFERENCE_SUB_CTRL = $(RNA_CTRL)/bonesis/ct/sub.bn
INFERENCE_MIN_CTRL = $(RNA_CTRL)/bonesis/ct/min.bn
MARKERS_ALL = $(RNA)/markers/all/markers.csv

# cluster parameters
$(eval K_NEIGHBORS_CTRL := 20)					# K-closest neighbors
$(eval RESOLUTION_LEIDEN_CTRL := 0.45)			# coarseness of the clustering when using Leiden algorithm
$(eval DIM_PCA_CTRL := 50)						# number of principal components
$(eval DIM_CLUSTERING_CTRL := 15)				# number of principal components taken into account for clustering
$(eval DIM_UMAP_CTRL := 2)						# number of embedding dimensions
SEED_CLUSTER_CTRL = 0

$(eval K_NEIGHBORS_TREATED := 20)				# K-closest neighbors
$(eval RESOLUTION_LEIDEN_TREATED := 0.4)		# coarseness of the clustering when using Leiden algorithm
$(eval DIM_PCA_TREATED := 50)					# number of principal components
$(eval DIM_CLUSTERING_TREATED := 15)			# number of principal components taken into account for clustering
$(eval DIM_UMAP_TREATED := 2)					# number of embedding dimensions
SEED_CLUSTER_TREATED = 1

# integration parameters
INTEGRATION_METHOD = bbknn
$(eval K_NEIGHBORS_INTEGRATED := 20)			# K-closest neighbors
$(eval RESOLUTION_LEIDEN_INTEGRATED := 0.4)		# coarseness of the clustering when using Leiden algorithm
$(eval DIM_PCA_INTEGRATED := 50)				# number of principal components
$(eval DIM_CLUSTERING_INTEGRATED := 15)			# number of principal components taken into account for clustering
$(eval DIM_UMAP_INTEGRATED := 2)				# number of embedding dimensions
SEED_CLUSTER_INTEGRATED = 1

# cluster labels
$(eval CLUSTER_LABEL_CTRL := 0=Prom1 1=Prom2 2=Trans 3=Rep 4=Prom3 5=Gran)			# depends on the marker, signature and goea analysis if not well-characterized
$(eval CLUSTER_LABEL_TREATED := 0=Trans 1=Prom1 2=Unknown 3=Rep 4=Gran 5=Rep)		# depends on the marker, signature and goea analysis if not well-characterized

# scvelo parameters
$(eval SCVELO_K_NEIGHBORS_CTRL := 20)			# K-closest neighbors
$(eval SCVELO_DIM_CLUSTERING_CTRL := 15)		# number of principal components taken into account for clustering
$(eval SMM_MODE_CTRL := stochastic)				# mode used to estimate the steady-state model								

$(eval SCVELO_K_NEIGHBORS_TREATED := 20)		# K-closest neighbors
$(eval SCVELO_DIM_CLUSTERING_TREATED := 15)		# number of principal components taken into account for clustering
$(eval SMM_MODE_TREATED := stochastic)			# mode used to estimate the steady-state model								

# stream parameters
LAMBDA_CTRL := 0.05
MU_CTRL := 0.05
ALPHA_CTRL := 0.03
EXTEND_CTRL := 0.8
ROOT_CTRL := 0
IGNORED_NODES_CTRL := 5

LAMBDA_TREATED := 0.05
MU_TREATED := 0.03
ALPHA_TREATED := 0.03
EXTEND_TREATED := 0.8
ROOT_TREATED := 0
IGNORED_NODES_TREATED := 
