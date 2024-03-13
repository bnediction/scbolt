MAKEFLAGS += --silent

NC = \033[0m
LIGHT_RED = \033[91m

all: pipeline/bonesis/min_1.bn

pipeline/bonesis/bootstrap_filter_grn_stage1.txt:
	echo "${LIGHT_RED}> stage-1 filtering...${NC}"
	python pipeline/bonesis/infer_bo.py filter_stage1 \
		--bin-metastates data/rna/binarization/cluster_bin_node_clusters.csv \
  		--model-specification pipeline/bonesis/plzf_rara_model.txt \
  		--quiet > pipeline/bonesis/bootstrap_filter_grn_stage1.txt
pipeline/bonesis/bootstrap_filter_grn_stage2.txt: pipeline/bonesis/bootstrap_filter_grn_stage1.txt
	echo "${LIGHT_RED}> stage-2 filtering...${NC}"
	python pipeline/bonesis/infer_bo.py filter_stage2 \
		--bin-metastates data/rna/binarization/cluster_bin_node_clusters.csv \
  		--model-specification pipeline/bonesis/plzf_rara_model.txt \
  		--filter-grn pipeline/bonesis/bootstrap_filter_grn_stage1.txt \
		--quiet > pipeline/bonesis/bootstrap_filter_grn_stage2.txt
pipeline/bonesis/sub_1.bn: pipeline/bonesis/bootstrap_filter_grn_stage2.txt
	echo "${LIGHT_RED}> one-sub inference...${NC}"
	python pipeline/bonesis/infer_bo.py one-sub \
		--bin-metastates data/rna/binarization/cluster_bin_node_clusters.csv \
		--model-specification pipeline/bonesis/plzf_rara_model.txt \
		--filter-grn pipeline/bonesis/bootstrap_filter_grn_stage2.txt \
		--quiet
pipeline/bonesis/min_1.bn: pipeline/bonesis/bootstrap_filter_grn_stage2.txt
	echo "${LIGHT_RED}> one-min inference...${NC}"
	python pipeline/bonesis/infer_bo.py one-min \
		--bin-metastates data/rna/binarization/cluster_bin_node_clusters.csv \
		--model-specification pipeline/bonesis/plzf_rara_model.txt \
		--filter-grn pipeline/bonesis/bootstrap_filter_grn_stage2.txt \
		--quiet
