MAKEFLAGS += --silent
BONESIS_PATH = data/rna/bonesis

NC = \033[0m
LIGHT_RED = \033[91m

all: $(BONESIS_PATH)/min_1.bn

filter1: $(BONESIS_PATH)/bootstrap_filter_grn_stage1.txt
$(BONESIS_PATH)/bootstrap_filter_grn_stage1.txt:
	echo "$(LIGHT_RED)> stage-1 filtering...$(NC)"
	python pipeline/bonesis/infer_bo.py filter_stage1 $(BONESIS_PATH) \
		--bin-metastates data/rna/binarization/cluster_bin_node_clusters.csv \
  		--model-specification pipeline/bonesis/plzf_rara_model.txt \
  		--quiet > $(BONESIS_PATH)/bootstrap_filter_grn_stage1.txt

filter2: $(BONESIS_PATH)/bootstrap_filter_grn_stage2.txt 
$(BONESIS_PATH)/bootstrap_filter_grn_stage2.txt: $(BONESIS_PATH)/bootstrap_filter_grn_stage1.txt
	echo "$(LIGHT_RED)> stage-2 filtering...$(NC)"
	python pipeline/bonesis/infer_bo.py filter_stage2 data/rna/bonesis \
		--bin-metastates data/rna/binarization/cluster_bin_node_clusters.csv \
  		--model-specification pipeline/bonesis/plzf_rara_model.txt \
  		--filter-grn $(BONESIS_PATH)/bootstrap_filter_grn_stage1.txt \
		--quiet > $(BONESIS_PATH)/bootstrap_filter_grn_stage2.txt

sub1: $(BONESIS_PATH)/sub_1.bn
$(BONESIS_PATH)/sub_1.bn: $(BONESIS_PATH)/bootstrap_filter_grn_stage2.txt
	echo "$(LIGHT_RED)> one-sub inference...$(NC)"
	python pipeline/bonesis/infer_bo.py one-sub data/rna/bonesis \
		--bin-metastates data/rna/binarization/cluster_bin_node_clusters.csv \
		--model-specification pipeline/bonesis/plzf_rara_model.txt \
		--filter-grn $(BONESIS_PATH)/bootstrap_filter_grn_stage2.txt \
		--quiet

min1: $(BONESIS_PATH)/min_1.bn 
$(BONESIS_PATH)/min_1.bn: $(BONESIS_PATH)/bootstrap_filter_grn_stage2.txt
	echo "$(LIGHT_RED)> one-min inference...$(NC)"
	python pipeline/bonesis/infer_bo.py one-min data/rna/bonesis \
		--bin-metastates data/rna/binarization/cluster_bin_node_clusters.csv \
		--model-specification pipeline/bonesis/plzf_rara_model.txt \
		--filter-grn $(BONESIS_PATH)/bootstrap_filter_grn_stage2.txt \
		--quiet

clean:
	rm -rf $(BONESIS_PATH)/*