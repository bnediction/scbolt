data = ../../data

all: bootstrap_filter_grn_stage2.txt

bootstrap_filter_grn_stage1.txt:
	python infer_bo.py filter_stage1 \
		--bin-metastates ${data}/rna/binarization/cluster_bin_node_clusters.csv \
  		--model-specification plzf_rara_model.txt \
  		--gene-synonyms mus_musculus_gene_info.tsv \
  		--quiet > bootstrap_filter_grn_stage1.txt
bootstrap_filter_grn_stage2.txt: bootstrap_filter_grn_stage1.txt
	python infer_bo.py filter_stage2 \
		--bin-metastates ${data}/rna/binarization/cluster_bin_node_clusters.csv \
  		--model-specification plzf_rara_model.txt \
  		--gene-synonyms mus_musculus_gene_info.tsv \
  		--filter-grn bootstrap_filter_grn_stage1.txt \
		--quiet > bootstrap_filter_grn_stage2.txt
