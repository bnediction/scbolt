# computing resources
SHELL = /bin/bash
MEMORY = 50
JOBS = 16

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
$(eval CLUSTER_LABEL_INTEGRATED := 0=Prom2 1=Rep 2=Prom1 3=Gran 4=Prom3)		 	# depends on the marker, signature and goea analysis if not well-characterized
$(eval LABELING_FROM_INTEGRATION := true)		# true or false

# scvelo parameters
$(eval SCVELO_K_NEIGHBORS_CTRL := 20)			# K-closest neighbors
$(eval SCVELO_DIM_CLUSTERING_CTRL := 15)		# number of principal components taken into account for clustering
$(eval SMM_MODE_CTRL := dynamical)				# mode used to estimate the steady-state model (deterministic, stochastic or dynamical)								

$(eval SCVELO_K_NEIGHBORS_TREATED := 20)		# K-closest neighbors
$(eval SCVELO_DIM_CLUSTERING_TREATED := 15)		# number of principal components taken into account for clustering
$(eval SMM_MODE_TREATED := dynamical)			# mode used to estimate the steady-state model (deterministic, stochastic or dynamical)

# macrostates parameters
$(eval MACROSTATES_FROM_CELLRANK := false)		# true or false
$(eval MACROSTATE_SIZE := 100)

$(eval CENTER_CTRL := Prom2)
$(eval EXTREMITY_CTRL := Rep Prom3)
$(eval EXCLUDE_CTRL := false)
$(eval CENTER_TREATED := Prom2)
$(eval EXTREMITY_TREATED := Prom1 Gran)
$(eval EXCLUDE_TREATED := true)

$(eval CELLRANK_METHOD := stability)			# stability, top_n, eigengap or eigengap_coarse
$(eval INITIAL_STATES_CTRL := 1)				# number of initial states with cellrank
$(eval TERMINAL_STATES_CTRL := 4)				# number of terminal states with cellrank
$(eval INITIAL_STATES_TREATED := 1)				# number of initial states with cellrank
$(eval TERMINAL_STATES_TREATED := 4)			# number of terminal states with cellrank

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
