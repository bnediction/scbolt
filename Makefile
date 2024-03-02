MAKEFLAGS += --silent

NC = \033[0m
LIGHT_RED = \033[91m

all: pipeline/bonesis/bootstrap_filter_grn_stage2.txt

pipeline/bonesis/bootstrap_filter_grn_stage1.txt:
	echo "${LIGHT_RED}> filter stage 1...${NC}"
	python pipeline/bonesis/infer_bo.py filter_stage1 \
		--bin-metastates data/rna/binarization/cluster_bin_node_clusters.csv \
  		--model-specification pipeline/bonesis/plzf_rara_model.txt \
  		--quiet > pipeline/bonesis/bootstrap_filter_grn_stage1.txt
pipeline/bonesis/bootstrap_filter_grn_stage2.txt: pipeline/bonesis/bootstrap_filter_grn_stage1.txt
	echo "${LIGHT_RED}> filter stage 1...${NC}"
	python pipeline/bonesis/infer_bo.py filter_stage2 \
		--bin-metastates data/rna/binarization/cluster_bin_node_clusters.csv \
  		--model-specification pipeline/bonesis/plzf_rara_model.txt \
  		--filter-grn pipeline/bonesis/bootstrap_filter_grn_stage1.txt \
		--quiet > pipeline/bonesis/bootstrap_filter_grn_stage2.txt
