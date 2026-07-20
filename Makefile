#!/usr/bin/env make

.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c

SHELL := /bin/bash
MAKEFLAGS += --silent --no-builtin-rules

makefile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
scbolt_root := $(patsubst %/,%,$(dir $(makefile_path)))

include $(scbolt_root)/mk/config.mk
include $(scbolt_root)/mk/modules.mk
include $(scbolt_root)/mk/parameter_help.mk
include $(scbolt_root)/mk/cli.mk
include $(scbolt_root)/mk/check.mk
include $(scbolt_root)/mk/clean.mk

## preserve target even if make is killed or interrupted
.PRECIOUS: $(max_nodes_soft_solution)
.PRECIOUS: $(max_consts_soft)
.PRECIOUS: $(max_nodes_relaxed)
.PRECIOUS: $(max_nodes_seed)
.PRECIOUS: $(max_nodes_lock)
.PRECIOUS: $(dir $(bn_submin))
.PRECIOUS: $(dir $(bn_diverse))

$(bin_cells)&: export OPENBLAS_NUM_THREADS = $(scboolseq_openblas_threads)
$(bin_cells)&: export OMP_NUM_THREADS = $(scboolseq_omp_threads)

## BEGIN RULES ##

$(genome_ref_archive):
	$(call print_rule,load-genome)
ifeq ($(strip $(genome_url)),)
	$(call print_error,no default genome_url for ORGANISM=$(ORGANISM). Set genome_url in your parameter file)
else
	mkdir -p $(@D)
	$(call wget_download,-cO $@.tmp $(genome_url))
	mv $@.tmp $@
endif

$(genome_ref): $(genome_ref_archive)
	$(call print_rule,load-genome)
	$(call print_task,extracting reference genome)
	rm -rf $@
	mkdir -p $(@D)
	$(call system_tool,tar) -zxf $< -C $(@D)
	if [ ! -d $@ ]; then \
		$(call print_error,reference archive did not extract expected directory: $@); \
	fi
	if [ -f $@/genes/genes.gtf.gz ]; then \
		$(call print_debug,decompressing reference gene annotation); \
		$(call system_tool,gzip) -cd $@/genes/genes.gtf.gz > $@/genes/genes.gtf.tmp; \
		mv $@/genes/genes.gtf.tmp $@/genes/genes.gtf; \
	fi

$(repeat_msk_table):
	$(call print_rule,load-genome,repeat_msk)
ifeq ($(strip $(repeat_msk_url)),)
	$(call print_error,no default repeat_msk_url for ORGANISM=$(ORGANISM). Set repeat_msk_url in your parameter file)
else
	mkdir -p $(@D)
	$(call wget_download,-cO $@.tmp $(repeat_msk_url))
	mv $@.tmp $@
endif

$(repeat_msk): $(repeat_msk_table)
	$(call print_rule,load-genome,repeat_msk)
	$(call print_task,converting RepeatMasker table to GTF)
	$(call system_tool,gzip) -cd $< \
		| $(call system_tool,awk) -F '\t' 'BEGIN { OFS = "\t" } \
			NF >= 17 { \
				id = $$6 ":" ($$7 + 1) "-" $$8 ":" $$10 ":" $$17; \
				gsub(/\\/, "\\\\", id); gsub(/"/, "\\\"", id); \
				name = $$11; gsub(/\\/, "\\\\", name); gsub(/"/, "\\\"", name); \
				class = $$12; gsub(/\\/, "\\\\", class); gsub(/"/, "\\\"", class); \
				family = $$13; gsub(/\\/, "\\\\", family); gsub(/"/, "\\\"", family); \
				print $$6, "UCSC_rmsk", "repeat_region", $$7 + 1, $$8, $$2, $$10, ".", \
					"gene_id \"" id "\"; transcript_id \"" id "\"; repeat_name \"" name \
					"\"; repeat_class \"" class "\"; repeat_family \"" family "\";" \
			}' \
		| $(call system_tool,gzip) -c > $@.tmp
	mv $@.tmp $@

$(star_index): | $(genome_ref)
	$(call check_file,$@,STAR genome index)

$(cc_markers):
	$(call print_rule,load-cc)
	mkdir -p $(@D)
	$(call wget_download,-cO $@ $(cycle_url))

$(geneinfo_latest):
	$(call print_rule,load-geneinfo,$(ORGANISM))
	if [ -z "$(geneinfo_url)" ]; then \
		$(call print_error,no default gene_info URL for ORGANISM=$(ORGANISM)); \
	fi
	mkdir -p $(@D)
	$(call wget_download,-cO $@.tmp $(geneinfo_url))
	mv $@.tmp $@

$(word 1,$(signatures)) $(word 2,$(signatures)):
	$(eval FILENAME := $(basename $(notdir $@)))
	$(call print_rule,load-signatures,$(FILENAME))
	mkdir -p $(@D)
	if [ $(FILENAME) = "geiger" ]; then \
		$(call wget_download,-cO $@ $(geiger_url)); \
	else \
		$(call wget_download,-cO $@ $(chambers_url)); \
	fi

$(lastword $(signatures)): $(word 1,$(signatures)) $(word 2,$(signatures)) $(if $(geneinfo_dependency),| $(geneinfo_dependency))
	$(call print_rule,load-signatures,conversion)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/load_signatures.py \
		--list-infile $(firstword $^) \
		--table-infile $(lastword $^) \
		--outfile $@ --organism $(ORGANISM) $(geneinfo_version_arg)

$(go_basic):
	$(call print_rule,load-go,go_basic)
	mkdir -p $(@D)
	$(call wget_download,-cO $@ $(go_basic_url))

$(go_organism):
	$(call print_rule,load-go,go_$(ORGANISM))
	mkdir -p $(@D)
	$(call wget_download,-cO $@ $(go_organism_url))

$(gene2go):
	$(call print_rule,load-go,gene2go)
	mkdir -p $(@D)
	rm -f $@.tmp
	for attempt in 1 2 3; do \
		rm -f $@.tmp; \
		$(call wget_download_label,loading gene-to-GO associations,-O $@.tmp $(gene2go_url)); \
		if $(call system_tool,gzip) -t $@.tmp; then \
			break; \
		fi; \
		if [ "$${attempt}" -eq 3 ]; then \
			exit 1; \
		fi; \
		$(call print_warning,invalid gene2go archive: retrying download); \
	done
	mv $@.tmp $@

$(gene2go_done): $(gene2go)
	mkdir -p $(@D)
	if ! $(call system_tool,gzip) -t $< >/dev/null 2>&1; then \
		$(call print_warning,corrupted gene2go archive: redownloading); \
		rm -f $< $@ $<.tmp; \
		for attempt in 1 2 3; do \
			rm -f $<.tmp; \
			$(call wget_download_label,loading gene-to-GO associations,-O $<.tmp $(gene2go_url)); \
			if $(call system_tool,gzip) -t $<.tmp; then \
				break; \
			fi; \
			if [ "$${attempt}" -eq 3 ]; then \
				exit 1; \
			fi; \
			$(call print_warning,invalid gene2go archive: retrying download); \
		done; \
		mv $<.tmp $<; \
	fi
	$(call system_tool,touch) $@

$(omics_dir)/count/%/invalid-alignment/.error:
	$(call print_rule,alignment,$*)
	$(call require_choice,ALIGNMENT_TOOL,cellranger star,alignment)

$(omics_dir)/count/invalid-alignment/.error:
	$(call print_rule,alignment)
	$(call require_choice,ALIGNMENT_TOOL,cellranger star,alignment)

$(omics_dir)/mstates/invalid-method/%/.error:
	$(call print_rule,macrostates,$*)
	$(call require_choice,MACROSTATE_METHOD,cotan cellrank stream knnsc,macrostates)

$(omics_dir)/mstates/invalid-method/.error:
	$(call print_rule,macrostates)
	$(call require_choice,MACROSTATE_METHOD,cotan cellrank stream knnsc,macrostates)

$(bin_method_error):
	$(call print_rule,binarization)
	$(call require_binarization_parameters)

ifneq ($(strip $(COUNT_FILES)),)
$(COUNT_FILES):
	$(call print_error,required COUNT_FILES input not found: $@)
endif

define compute_rules_for_conditions

$(fastq_$(1)):
	$(call print_rule,load-fastq,$(1))
	$(call require_sra_condition,$(1))
	sample_naming="$(call condition_name,$(1))"
	lane=0
	rm -rf $(tmpdir)/$(1)/fastq && mkdir -p $(tmpdir)/$(1)/fastq
	for id in $(call sra_value,$(1))
	do
		((++lane))
		$$(call conda_run,scbolt-fastq) parallel-fastq-dump \
			--sra-id $$$${id} \
			--split-files --readids --origfmt --gzip \
			--threads $$(JOBS) \
			--outdir $(tmpdir)/$(1)/fastq
		$$(call fastq_naming,$(tmpdir)/$(1)/fastq,$$$${id},$$$${sample_naming},$$$${lane})
	done
	sleep 3
	mkdir -p $$@
	files=$$$$(shopt -s nullglob dotglob; echo $(tmpdir)/$(1)/fastq/*)
	if (( $$$${#files} )); then \
		mv $$$${files} $$@/; \
		rm -rf $(tmpdir)/$(1)/fastq; \
	else \
		$(call print_error,cannot download fastq files: fastq-dump failed); \
	fi
	unset files
	$$(call write_scbolt_metadata,load-fastq,$$@)

ifeq ($(matrix_mode),true)
$(load_matrix_$(1)):
	$(call print_rule,load-matrix,$(1))
	$(call require_gsm_condition,$(1))
	$(call conda_run,scbolt-core) python $(scripts_dir)/download/load_geo.py \
		$(call gsm_value,$(1)) $$(load_matrix_$(1))
	$$(call write_scbolt_metadata,load-matrix,$$(load_matrix_$(1)))
endif

$(cellranger_$(1)): $(fastq_$(1)) $(genome_ref)
	$(call print_rule,cellranger,$(1))
	mkdir -p $(tmpdir)/cellranger $$(@D)
	(
		cd $(tmpdir)/cellranger
		cellranger count --id=$(call condition_name,$(1)) \
			--fastqs=$$($(call system_tool,realpath) $$(firstword $$^)) \
			--transcriptome=$$($(call system_tool,realpath) $$(lastword $$^)) \
			--create-bam true \
			--localcores=$(JOBS) \
			--localmem=$(memory_gb)
	)
	mv $(tmpdir)/cellranger/$(call condition_name,$(1))/* $$(@D)
	rm -rf $(tmpdir)/cellranger/$(call condition_name,$(1))
	$$(call write_scbolt_metadata,cellranger,$$(cellranger_$(1)))

$(star_$(1))&: $(fastq_$(1)) $(star_index)
	$(call print_rule,star,$(1))
	$(call require_choice,ALIGNMENT_TOOL,cellranger star,star)
	$(call require_positive_integer,STAR_CB_LEN)
	$(call require_positive_integer,STAR_UMI_LEN)
	if [ -n "$(STAR_WHITELIST)" ]; then \
		$(call check_file,$(STAR_WHITELIST),STAR_WHITELIST); \
	fi
	mkdir -p $(tmpdir)/star/$(1) $$(@D)
	fastq_dir="$$($(call system_tool,realpath) $$(firstword $$^))"
	r1_files="$$$$( $(call system_tool,find) "$$$${fastq_dir}" -name '*_R1_001.fastq.gz' | $(call system_tool,sort) | $(call system_tool,paste) -sd, -)"
	r2_files="$$$$( $(call system_tool,find) "$$$${fastq_dir}" -name '*_R2_001.fastq.gz' | $(call system_tool,sort) | $(call system_tool,paste) -sd, -)"
	if [ -z "$$$${r1_files}" ] || [ -z "$$$${r2_files}" ]; then \
		$(call print_error,STAR requires R1 and R2 FASTQ files in $$$${fastq_dir}); \
	fi
	$(call conda_run,scbolt-align) STAR \
		--runThreadN $(JOBS) \
		--genomeDir $(genome_ref)/star \
		--readFilesIn "$$$${r2_files}" "$$$${r1_files}" \
		--readFilesCommand zcat \
		--soloType Droplet \
		--soloCBwhitelist $(if $(strip $(STAR_WHITELIST)),$(STAR_WHITELIST),None) \
		--soloCBstart 1 \
		--soloCBlen $(STAR_CB_LEN) \
		--soloUMIstart 17 \
		--soloUMIlen $(STAR_UMI_LEN) \
		--soloBarcodeReadLength 0 \
		--soloFeatures Gene GeneFull \
		--outSAMattributes NH HI AS nM CR UR \
		--outSAMtype BAM SortedByCoordinate \
		--outFileNamePrefix $(tmpdir)/star/$(1)/
	rm -rf $$(@D)
	mkdir -p $$(@D)
	mv $(tmpdir)/star/$(1)/* $$(@D)/
	$$(call write_scbolt_metadata,star,$$(star_$(1)))

ifneq ($(matrix_mode),true)
ifeq ($(ALIGNMENT_TOOL),cellranger)
$(velocyto_$(1)): $(cellranger_$(1)) $(genome_ref) $(repeat_msk)
	$(call print_rule,velocyto,$(1))
	$(call require_choice,ALIGNMENT_TOOL,cellranger star,velocyto)
	mkdir -p $(tmpdir)/$(1)/velocyto
	repeat_mask="$(tmpdir)/$(1)/velocyto/repeat_msk.gtf"
	$(call print_debug,decompressing RepeatMasker annotation)
	$(call system_tool,gzip) -cd $$(lastword $$^) > "$$$${repeat_mask}"
	$(call conda_run,scbolt-velocyto) velocyto run10x \
		-m "$$$${repeat_mask}" \
		--samtools-threads $(JOBS) --samtools-memory $(memory_velocyto) \
		$$(dir $$(firstword $$^)) $$(word 2,$$^)/genes/genes.gtf
	mkdir -p $$(@D)
	mv $$(<D)/velocyto/cellranger.loom $$(@D)/counts.loom
	rm -rf $$(<D)/velocyto
	$(call print_debug,converting loom to h5ad)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/adata_conversion.py \
		$$(@D)/counts.loom $(tmpdir)/$(1)/velocyto/counts.h5ad --from loom --to h5ad \
		--remove-positions --sort
	$(call finalize_velocyto_h5ad,$(tmpdir)/$(1)/velocyto/counts.h5ad,$$@)
	$$(call write_scbolt_metadata,velocyto,$$(velocyto_$(1)))
else ifeq ($(ALIGNMENT_TOOL),star)
$(qc_$(1)): $(star_$(1))
	$(call print_rule,qc,$(1))
	$(call print_task,filtering STAR barcodes)
	$(call require_star_barcode_filter_parameters,qc)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/align/qc.py \
		$$(<D)/Solo.out/matrix.mtx \
		$$(<D)/Solo.out/barcodes.tsv \
		$$(@D)/filtered_barcodes.tsv \
		--method $(STAR_BARCODE_FILTER) \
		$(if $(STAR_MIN_UMI),--min-umi $(STAR_MIN_UMI),) \
		$(if $(STAR_TOP_BARCODES),--top-barcodes $(STAR_TOP_BARCODES),)
	$(call print_task,preparing STAR BAM for velocyto)
	mkdir -p $$(@D) $(tmpdir)/$(1)/qc
	$(call conda_run,scbolt-velocyto) python $(scripts_dir)/align/retag_bam.py \
		$$(<D)/Aligned.sortedByCoord.out.bam $(tmpdir)/$(1)/qc/star.velocyto.bam \
		--barcodes $$(@D)/filtered_barcodes.tsv \
		--tag CR:CB UR:UB \
		--jobs $(JOBS)
	mv $(tmpdir)/$(1)/qc/star.velocyto.bam $$@
	$$(call write_scbolt_metadata,qc,$$(qc_$(1)))

$(velocyto_$(1)): $(qc_$(1)) $(genome_ref) $(repeat_msk)
	$(call print_rule,velocyto,$(1))
	$(call require_choice,ALIGNMENT_TOOL,cellranger star,velocyto)
	$(call require_star_barcode_filter_parameters,velocyto)
	mkdir -p $(tmpdir)/velocyto/$(1)
	repeat_mask="$(tmpdir)/velocyto/$(1)/repeat_msk.gtf"
	$(call print_debug,decompressing RepeatMasker annotation)
	$(call system_tool,gzip) -cd $$(lastword $$^) > "$$$${repeat_mask}"
	$(call print_task,estimating spliced and unspliced counts with velocyto)
	$(call conda_run,scbolt-velocyto) velocyto run \
		-m "$$$${repeat_mask}" \
		-b $$(<D)/filtered_barcodes.tsv \
		-o $(tmpdir)/velocyto/$(1) \
		-e star \
		--samtools-threads $(JOBS) --samtools-memory $(memory_velocyto) \
		$$(firstword $$^) $$(word 2,$$^)/genes/genes.gtf
	mkdir -p $$(@D)
	mv $(tmpdir)/velocyto/$(1)/star.loom $$(@D)/counts.loom
	rm -rf $(tmpdir)/velocyto/$(1)
	$(call print_debug,converting loom to h5ad)
	mkdir -p $(tmpdir)/$(1)/velocyto
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/adata_conversion.py \
		$$(@D)/counts.loom $(tmpdir)/$(1)/velocyto/counts.h5ad --from loom --to h5ad \
		--remove-positions --sort
	$(call finalize_velocyto_h5ad,$(tmpdir)/$(1)/velocyto/counts.h5ad,$$@)
	$$(call write_scbolt_metadata,velocyto,$$(velocyto_$(1)))
endif
endif

$(filtering_$(1)): $(count_input_$(1)) $(if $(filter true,$(CC_CORRECTION)),$(if $(filter mouse,$(ORGANISM)),$(cc_markers))) $(if $(geneinfo_dependency),| $(geneinfo_dependency))
	$(call print_rule,filtering,$(1))
	$(require_filtering_parameters)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/prep/filter.py \
		$$(firstword $$^) $$@ $(if $(filter true,$(CC_CORRECTION)),$(if $(filter mouse,$(ORGANISM)),--marker $$(lastword $$^))) \
		--expression counts \
		--gene-dropout $(GENE_DROPOUT) --gene-expression $(GENE_EXPRESSION) --gene-counts $(GENE_COUNTS) \
		--cell-dropout $(CELL_DROPOUT) --cell-expression $(CELL_EXPRESSION) --cell-reads $(CELL_READS) \
		--mad-deviation $(MAD_DEVIATION) $(consistent_mad) --mt $(MT) \
		--organism $(ORGANISM) \
		$(geneinfo_version_arg)
	$$(call write_scbolt_metadata,filtering,$$(filtering_$(1)))

$(normalization_$(1)): $(filtering_$(1))
	$(call print_rule,normalization,$(1))
	$(call require_cc_correction,normalization)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/prep/norm.py \
		$$< $$@ $(cc_correction) --expression counts --jobs $(JOBS) --max-memory "$(memory_bonesistools)"
	$$(call write_scbolt_metadata,normalization,$$(normalization_$(1)))

$(clustering_$(1)): $(normalization_$(1))
	$(call print_rule,clustering,$(1))
	$(require_clustering_parameters)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/clust/clustering.py $$< $$@ \
		--expression correct --adjacency knn \
		--pca-dimension $(DIM_PCA) \
		--clustering-dimension $(DIM_PCA) \
		--embedding-dimension $(DIM_EMBEDDING) \
		--method $(ANALYSIS_HVG_METHOD) $(if $(ANALYSIS_HVG_TOP),--top-hvg $(ANALYSIS_HVG_TOP),) \
		--span $(ANALYSIS_HVG_SPAN) --bins $(ANALYSIS_HVG_BINS) $(centered_pca) $(pca_only_hvg) \
		--neighbors $(NEIGHBORS) --metric $(METRIC) \
		--resolution $(RESOLUTION) --min-dist $(MIN_DIST) --spread $(SPREAD) \
		--embedding-n-iter $(EMBEDDING_N_ITER) \
		--seed $(SEED)
	$$(call write_scbolt_metadata,clustering,$$(clustering_$(1)))

ifeq ($(words $(conditions)),1)
$(annotation_$(1)): $(clustering_$(1))
	$(call print_rule,annotation,$(1))
	if [ -z "$(LABEL)" ]; then \
			$(call print_error,required parameter not defined: LABEL \(needed by target 'annotation'\). \
				Review DEA/GOEA/signature outputs and set LABEL in your parameter file); \
	fi
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/clust/annotation.py $$< $$@ \
		--obs cluster --new-obs $(LABEL_COL) --labels $(label_map) \
		--embedding $(REPRESENTATION)
	$$(call write_scbolt_metadata,annotation,$$(annotation_$(1)))
else
$(annotation_$(1)): $(annotation_integrated) $(clustering_$(1))
	$(call print_rule,annotation,$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/pipe_its.py $$^ --outfiles $$@ \
		--labels $(1) --obs-label condition --obs $(LABEL_COL) \
		--var highly_variable highly_variable_rank \
		--plot-obs $(LABEL_COL) --embedding $(REPRESENTATION)
	$$(call write_scbolt_metadata,annotation,$$(annotation_$(1)))
endif

$(velocity_$(1)): $(annotation_$(1))
	$(call print_rule,velocity,$(1))
	$(call require_velocity_parameters)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-velocity) python $(scripts_dir)/traj/velocity.py $$< $$@ \
		--expression counts --cluster $(LABEL_COL) --moment-dimension $(DIM_MOMENT) \
		$(velocity_only_hvg) --mode $(SMM_MODE) --embedding $(embedding) --jobs $(JOBS)
	$$(call write_scbolt_metadata,velocity,$$(velocity_$(1)))

$(potency_$(1)): $(annotation_$(1))
	$(call print_rule,potency,$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-potency) python $(scripts_dir)/traj/potency.py $$< $$(@D) \
		--csv $$(notdir $$@) --h5ad $$(basename $$(notdir $$@)).h5ad \
		--expression counts --cluster $(LABEL_COL) --batch-size $(BATCH_SIZE) --smooth-batch-size $(SMOOTH_BATCH_SIZE) \
		--organism $(ORGANISM) --representation $(REPRESENTATION) --seed $(SEED) --jobs $(JOBS)
	$$(call write_scbolt_metadata,potency,$$(potency_$(1)))

$(cotan_$(1))&: $(annotation_$(1))
	$(call print_rule,cotan,$(1))
	$(call require_bool,COTAN_ONLY_HVG,cotan)
	mkdir -p $$(@D) $(tmpdir)/$(1)/cotan
	$(call print_debug,converting AnnData object to CSV counts)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/adata_conversion.py \
		$$< $(tmpdir)/$(1)/cotan/barcts.csv --from h5ad --to csv \
		--expression counts $(cotan_only_hvg)
	$(call print_debug,transposing count matrix)
	ruby -rcsv -e 'puts CSV.parse(STDIN).transpose.map &:to_csv' \
		< $(tmpdir)/$(1)/cotan/barcts.csv \
		> $(tmpdir)/$(1)/cotan/gencts.csv
	$(call conda_run,scbolt-cotan) Rscript $(scripts_dir)/mstates/cotan_mstates.R \
		--infile $(tmpdir)/$(1)/cotan/gencts.csv --outfile $$(@D)/cotan.RDS --csv $$(lastword $$(cotan_$(1))) \
		--sep , --name $(1) --max-iterations $(MAX_ITER) --method $(COTAN_METHOD) --min-ude 0.3 --jobs $(JOBS)
	$(call print_debug,adding COTAN macrostates to AnnData)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/add_to_anndata.py \
		$$< $$(firstword $$(cotan_$(1))) \
		--csv $$(lastword $$(cotan_$(1))) \
		--axis 0 --sep , --type category \
		--plot-obs macrostate --plot-representation $(REPRESENTATION) \
		--plot-outfile $$(@D)/macrostates.pdf
	$$(call write_scbolt_metadata,cotan,$$(cotan_$(1)))

$(cellrank_$(1))&: $(velocity_$(1)) $(potency_$(1))
	$(call print_rule,cellrank,$(1))
	$(call require_cellrank_parameters)
	mkdir -p $$(@D) $(tmpdir)/$(1)/cellrank
	$(call print_debug,adding potency scores to AnnData)
	$(call system_tool,awk) -F, -v txt="score" 'FNR==1{for(col=1;$$$$col!=txt;col++);next} {print $$$$1 "," $$$$col}' \
		$$(lastword $$^) > $(tmpdir)/$(1)/cellrank/potency_scores.csv
	$(call system_tool,sed) -i '1 i\,cytotrace_score' $(tmpdir)/$(1)/cellrank/potency_scores.csv
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/add_to_anndata.py \
		$$(firstword $$^) $(tmpdir)/$(1)/cellrank/kernels.h5ad \
		--csv $(tmpdir)/$(1)/cellrank/potency_scores.csv \
		--axis 0 --sep , --type float
	$(call conda_run_cellrank,scbolt-cellrank) python $(scripts_dir)/mstates/cellrank_mstates.py \
		$(tmpdir)/$(1)/cellrank/kernels.h5ad $$(firstword $$(cellrank_$(1))) \
		--csv $$(lastword $$(cellrank_$(1))) \
		--obs $(LABEL_COL) --method $(CELLRANK_METHOD) \
		--cytotrace-score cytotrace_score --scvelo-velocity velocity \
		--states $(STATES) --initial-states $(INITIAL_STATES) --terminal-states $(TERMINAL_STATES) \
		--stability $(CELLRANK_STABILITY) --alpha $(CELLRANK_ALPHA) --size $(MACROSTATE_SIZE) --seed $(SEED)
	$$(call write_scbolt_metadata,cellrank,$$(cellrank_$(1)))

$(stream_$(1))&: $(annotation_$(1))
	$(call print_rule,stream,$(1))
	$(call require_stream_parameters)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-stream) python $(scripts_dir)/mstates/stream_mstates.py \
		$$< $$(firstword $$(stream_$(1))) \
		--csv $$(lastword $$(stream_$(1))) \
		--representation $(REPRESENTATION) --obs $(LABEL_COL) \
		--clustering $(CLUSTERING_METHOD) --cluster-number $(CLUSTER_NUMBER) \
		--alpha $(ALPHA_EPG) --mu $(MU_EPG) --lambda $(LAMBDA_EPG) \
		$(extend_epg) \
		$(if $(filter $(EXTEND_EPG),true),--extend-mode $(EXTEND_MODE),) \
		$(if $(filter $(EXTEND_EPG),true),--extend-parameter $(EXTEND_PARAMETER),) \
		$(prune_epg) \
		$(if $(filter $(PRUNE_EPG),true),--collapse-parameter $(COLLAPSE_PARAMETER),) \
		--size $(MACROSTATE_SIZE) --jobs $(JOBS)
	$$(call write_scbolt_metadata,stream,$$(stream_$(1)))

ifeq ($(or $(call knnsc_centrality,$(1)),$(call knnsc_periphery,$(1))),)
$(knnsc_$(1))&: $(annotation_$(1))
	$(call print_error,required parameter not defined: $(call knnsc_centrality_var,$(1)) \
		or $(call knnsc_periphery_var,$(1)) \(needed by target 'knnsc'\))
else
$(knnsc_$(1))&: $(annotation_$(1))
	$(call print_rule,knnsc,$(1))
	$(call require_knnsc_parameters)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/mstates/knnsc_mstates.py \
		$$< $$(firstword $$(knnsc_$(1))) \
		--csv $$(lastword $$(knnsc_$(1))) \
		--obs $(LABEL_COL) --embedding $(KNNSC_EMBEDDING) --neighbors $(KNNSC_NEIGHBORS) \
		$(knnsc_dimension) --metric $(METRIC) --size $(MACROSTATE_SIZE) \
		--min-cluster-size $(KNNSC_MIN_CLUSTER_SIZE) \
		$(if $(call knnsc_centrality,$(1)),--centrality $(call knnsc_centrality,$(1)),) \
		$(if $(call knnsc_periphery,$(1)),--periphery $(call knnsc_periphery,$(1)),) \
		--plot-representation $(REPRESENTATION) \
		--jobs $(JOBS)
	$$(call write_scbolt_metadata,knnsc,$$(knnsc_$(1)))
endif

endef

define compute_rules_for_references

$(dea_$(1))&: $(clustering_$(1))
	$(call print_rule,dea,$(1))
	$(call require_dea_parameters)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/clust/dea.py \
		$$< $(firstword $(dea_$(1))) \
		--xlsx $(lastword $(dea_$(1))) \
		--cluster cluster --expression log-norm --is-log \
		--method $(DEA_METHOD) --logfc $(LOGFC) --alpha $(ALPHA) --correction $(CORRECTION) \
		--max-memory "$(memory_bonesistools)"
	$$(call write_scbolt_metadata,dea,$$(dea_$(1)))

$(scoring_$(1))&: $(clustering_$(1)) $(lastword $(signatures)) $(lastword $(dea_$(1)))
	$(call print_rule,scoring,$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/clust/scoring.py \
		$$^ $(firstword $(scoring_$(1))) --cluster cluster --ignore-sheets background --correction none
	$$(call write_scbolt_metadata,scoring,$$(scoring_$(1)))

$(goea_basic_$(1)): $(lastword $(dea_$(1))) $(go_basic) $(gene2go_done) $(if $(geneinfo_dependency),| $(geneinfo_dependency))
	$(call print_rule,goea,go_basic/$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/clust/goea.py $$< $$@ \
		--background background --go $$(word 2,$$^) --gene2go $(gene2go) \
		--organism $(ORGANISM) $(geneinfo_version_arg)
	$$(call write_scbolt_metadata,goea,$$@)

$(goea_organism_$(1)): $(lastword $(dea_$(1))) $(go_organism) $(gene2go_done) $(if $(geneinfo_dependency),| $(geneinfo_dependency))
	$(call print_rule,goea,go_$(ORGANISM)/$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/clust/goea.py $$< $$@ \
		--background background --go $$(word 2,$$^) --gene2go $(gene2go) \
		--organism $(ORGANISM) $(geneinfo_version_arg)
	$$(call write_scbolt_metadata,goea,$$@)

endef

ifneq ($(multi_condition),)
$(clustering_integrated): $(foreach condition,$(conditions),$(normalization_$(condition)))
	$(call print_rule,clustering,integrated)
	$(require_clustering_parameters)
	mkdir -p $(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/clust/integration.py \
		$^ --outfile $@ --labels $(conditions) \
		--expression correct --adjacency knn --integration $(INTEGRATION) \
		--pca-dimension $(DIM_PCA) --clustering-dimension $(DIM_PCA) --embedding-dimension $(DIM_EMBEDDING) \
		--method $(ANALYSIS_HVG_METHOD) $(if $(ANALYSIS_HVG_TOP),--top-hvg $(ANALYSIS_HVG_TOP),) \
		--span $(ANALYSIS_HVG_SPAN) --bins $(ANALYSIS_HVG_BINS) $(centered_pca) $(pca_only_hvg) \
		--neighbors $(NEIGHBORS) --metric $(METRIC) --resolution $(RESOLUTION) \
		--min-dist $(MIN_DIST) --spread $(SPREAD) \
		--embedding-n-iter $(EMBEDDING_N_ITER) \
		--seed $(SEED) --jobs $(JOBS)
	$(call write_scbolt_metadata,clustering,$@)

$(annotation_integrated): $(clustering_integrated)
	$(call print_rule,annotation,integrated)
	if [ -z "$(LABEL)" ]; then \
			$(call print_error,required parameter not defined: LABEL \(needed by target 'annotation'\). \
				Review DEA/GOEA/signature outputs and set LABEL in your parameter file); \
	fi
	mkdir -p $(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/clust/annotation.py $< $@ \
		--obs cluster --new-obs $(LABEL_COL) --labels $(label_map) \
		--condition-col condition --embedding $(REPRESENTATION)
	$(call write_scbolt_metadata,annotation,$@)
endif

ifneq ($(strip $(MACROSTATE_FILES)),)
ifneq ($(filter-out 1,$(words $(MACROSTATE_FILES))),)
$(macrostate_h5ad_$(1)):
	$(call print_task,preparing macrostate AnnData (reference=$(1)))
	$(call check_file,$$(macrostate_file_$(1)),MACROSTATE_FILES)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/prepare_macrostate_h5ad.py \
		$$(macrostate_file_$(1)) $$@ \
		--macrostate-obs macrostate --condition $(1) --condition-obs condition \
		--prefix-macrostates --representation $(REPRESENTATION)
endif
endif

ifneq ($(strip $(MACROSTATE_FILES)),)
ifeq ($(words $(MACROSTATE_FILES)),1)
$(macrostate_h5ad):
	$(call print_task,preparing macrostate AnnData)
	$(call check_file,$(firstword $(MACROSTATE_FILES)),MACROSTATE_FILES)
	mkdir -p $(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/prepare_macrostate_h5ad.py \
		$(firstword $(MACROSTATE_FILES)) $@ \
		--macrostate-obs macrostate --representation $(REPRESENTATION) \
		$(if $(filter-out 1,$(words $(conditions))),--condition-obs condition --prefix-macrostates)
else
$(macrostate_h5ad): $(macrostate_h5ads)
	$(call print_task,concatenating macrostate AnnData files)
	mkdir -p $(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/concat_h5ad.py \
		$^ --outfile $@
endif
endif

define build_bin_hvg
$(call require_bin_hvg_parameters,$(1))
if [ ! -f "$(bin_hvg)" ]; then
	mkdir -p $(dir $(bin_hvg))
	$(call print_task,estimating top$(if $(BIN_HVG_TOP), $(BIN_HVG_TOP),) \
		highly variable genes with $(BIN_HVG_METHOD))
	$(call conda_run,scbolt-core) python $(scripts_dir)/prep/hvg.py \
		$(lastword $(bin_input_h5ads)) $(bin_hvg) \
		--method $(BIN_HVG_METHOD) \
		$(bin_hvg_layer) \
		$(if $(BIN_HVG_TOP),--hvg $(BIN_HVG_TOP),) \
		--span $(BIN_HVG_SPAN) --bins $(BIN_HVG_BINS) \
		$(batch)
fi
endef

$(bin_hvg): $(bin_input_h5ads)
	$(call build_bin_hvg,binarization)

$(bin_cells)&: $(bin_input_h5ads)
	$(call print_rule,bin-cells)
	$(if $(filter true,$(BIN_SCBOOLSEQ_ONLY_HVG)),$(call require_bin_hvg_parameters,bin-cells))
	$(call require_bin_cells_parameters)
	mkdir -p $(@D)
	$(if $(filter true,$(BIN_SCBOOLSEQ_ONLY_HVG)),$(call build_bin_hvg,bin-cells))
	$(call conda_run,scbolt-scboolseq) python $(scripts_dir)/bin/bin_cells_scboolseq.py \
		$< --outfile $(firstword $(bin_cells)) \
		--statistics $(lastword $(bin_cells)) \
		--expression log-norm \
		--representation $(REPRESENTATION) \
		--quantile $(UNIMODAL_QUANTILE) \
		--seed $(SEED) \
		$(zeroes_are_zeroes) \
		$(bin_scboolseq_hvg)
	$(call write_scbolt_metadata,bin-cells,$(bin_cells))

ifeq ($(strip $(MACROSTATE_FILES)),)
$(bin_mstates): $(firstword $(bin_cells)) \
    $(foreach condition,$(conditions),$(lastword $(macrostates_$(condition))))
	$(call print_rule,bin-macrostates)
	$(call require_bin_mstates_parameters)
	mkdir -p $(@D) $(tmpdir)/integrated/bin/aggr
	$(call print_debug,adding macrostates to AnnData)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/add_to_anndata.py \
		$(firstword $^) $(tmpdir)/integrated/bin/aggr/mcts.h5ad \
		--csv $(filter-out $<, $^) \
		$(if $(multi_condition),--labels $(conditions),) \
		$(if $(multi_condition),--label-column condition,) \
		$(if $(multi_condition),--add-prefix macrostate,) \
		--axis 0 --sep , --type category
	$(call conda_run,scbolt-core) python $(scripts_dir)/bin/bin_clust_scboolseq.py \
		$(tmpdir)/integrated/bin/aggr/mcts.h5ad $@ \
		--counts $(@D)/counts_bin.csv \
		--expression bin --distribution distribution --cluster macrostate \
		--representation $(REPRESENTATION) \
		--nans-threshold $(NANS_THRESHOLD) \
		--bimodal-threshold $(BIMODAL_THRESHOLD) \
		--zeroinf-threshold $(ZEROINF_THRESHOLD) \
		--unimodal-threshold $(UNIMODAL_THRESHOLD)
	$(call write_scbolt_metadata,bin-macrostates,$@)
else
$(bin_mstates): $(firstword $(bin_cells))
	$(call print_rule,bin-macrostates)
	$(call require_bin_mstates_parameters)
	mkdir -p $(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/bin/bin_clust_scboolseq.py \
		$< $@ \
		--counts $(@D)/counts_bin.csv \
		--expression bin --distribution distribution --cluster macrostate \
		--representation $(REPRESENTATION) \
		--nans-threshold $(NANS_THRESHOLD) \
		--bimodal-threshold $(BIMODAL_THRESHOLD) \
		--zeroinf-threshold $(ZEROINF_THRESHOLD) \
		--unimodal-threshold $(UNIMODAL_THRESHOLD)
	$(call write_scbolt_metadata,bin-macrostates,$@)
endif

ifeq ($(strip $(MACROSTATE_FILES)),)
$(bin_dea): \
    $(bin_input_h5ads) \
    $(foreach condition,$(conditions),$(lastword $(macrostates_$(condition))))
	$(call print_rule,bin-dea)
	$(if $(filter true,$(BIN_DEA_ONLY_HVG)),$(call require_bin_hvg_parameters,bin-dea))
	$(call require_bin_dea_parameters)
	mkdir -p $(@D) $(tmpdir)/integrated/bin/dea
	$(if $(filter true,$(BIN_DEA_ONLY_HVG)),$(call build_bin_hvg,bin-dea))
	$(call print_debug,adding macrostates to AnnData)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/add_to_anndata.py \
		$(firstword $^) $(tmpdir)/integrated/bin/dea/mcts.h5ad \
		--csv $(filter-out $<, $^) \
		$(if $(multi_condition),--labels $(conditions),) \
		$(if $(multi_condition),--label-column condition,) \
		$(if $(multi_condition),--add-prefix macrostate,) \
		--axis 0 --sep , --type category
	$(call conda_run,scbolt-core) python $(scripts_dir)/bin/bin_dea.py $(tmpdir)/integrated/bin/dea/mcts.h5ad $@ \
		--cluster macrostate --expression log-norm --is-log --method wilcoxon --representation $(REPRESENTATION) \
		--logfc $(BIN_LOGFC) --alpha $(BIN_ALPHA) --correction $(BIN_CORRECTION) \
		--max-memory "$(memory_bonesistools)" \
		$(bin_dea_hvg)
	$(call write_scbolt_metadata,bin-dea,$@)
else
$(bin_dea): $(bin_input_h5ads)
	$(call print_rule,bin-dea)
	$(if $(filter true,$(BIN_DEA_ONLY_HVG)),$(call require_bin_hvg_parameters,bin-dea))
	$(call require_bin_dea_parameters)
	mkdir -p $(@D)
	$(if $(filter true,$(BIN_DEA_ONLY_HVG)),$(call build_bin_hvg,bin-dea))
	$(call conda_run,scbolt-core) python $(scripts_dir)/bin/bin_dea.py $< $@ \
		--cluster macrostate --expression log-norm --is-log --method wilcoxon --representation $(REPRESENTATION) \
		--logfc $(BIN_LOGFC) --alpha $(BIN_ALPHA) --correction $(BIN_CORRECTION) \
		--max-memory "$(memory_bonesistools)" \
		$(bin_dea_hvg)
	$(call write_scbolt_metadata,bin-dea,$@)
endif

$(bin_consensus): $(bin_mstates) $(lastword $(bin_cells)) $(bin_dea)
	$(call print_rule,bin-consensus)
	mkdir -p $(@D) $(tmpdir)/bin/consensus
	$(call print_debug,extracting scBoolSeq distributions)
	col=`head $(word 2, $^) -n 1 \
		| $(call system_tool,sed) "s/,/\n/g" \
		| $(call system_tool,awk) -F, '{printf("%d %s\n", NR-1, $$0)}' \
		| $(call system_tool,grep) Category \
		| $(call system_tool,awk) '{print $$1}'`
	((col++))
	cut -f 1,$$col -d ',' $(word 2, $^) > $(tmpdir)/bin/consensus/distributions.csv
	unset col
	$(call conda_run,scbolt-core) python $(scripts_dir)/bin/bin_consensus.py \
		--scboolseq $< $(tmpdir)/bin/consensus/distributions.csv --dea $(lastword $^) \
		--outfile $@ --pct-bin $(@D)/pct_bin.csv
	$(call write_scbolt_metadata,bin-consensus,$@)

$(bonesis_model)&: $(bin) $(if $(geneinfo_dependency),| $(geneinfo_dependency))
	$(call print_rule,spec)
	$(call require_prior_parameters,spec)
	$(call check_file,$(SPEC_FILE),SPEC_FILE)
	mkdir -p $(@D)
	$(call conda_run,scbolt-bonesis) python $(scripts_dir)/infer/spec.py $(SPEC_FILE) $< \
		--model $(word 1,$(bonesis_model)) --metastates $(word 2,$(bonesis_model)) \
		--important-nodes $(word 3,$(bonesis_model)) --mandatory-nodes $(word 4,$(bonesis_model)) \
		--forbidden-nodes $(word 5,$(bonesis_model)) \
		--domain $(prior_knowledge) --organism $(ORGANISM) \
		$(prior_knowledge_args)
	$(call system_tool,sort) -u $(word 3,$(bonesis_model)) -o $(word 3,$(bonesis_model))
	$(call system_tool,sort) -u $(word 4,$(bonesis_model)) -o $(word 4,$(bonesis_model))
	$(call system_tool,sort) -u $(word 5,$(bonesis_model)) -o $(word 5,$(bonesis_model))
	$(call write_scbolt_metadata,spec,$(bonesis_model))

$(max_nodes_soft_solution): $(bonesis_model) $(if $(geneinfo_dependency),| $(geneinfo_dependency))
	$(call print_rule,max-nodes-soft)
	$(call require_bonesis_filter_parameters,max-nodes-soft)
	$(call require_bool,CLAUSE_CONTINUATION_SOFT,max-nodes-soft)
	$(call require_bool,DOMAIN_CONTINUATION_SOFT,max-nodes-soft)
	mkdir -p $(@D)
	set +e; \
	$(call start_inference_timer) \
	$(call trap_inference_interrupt,max-nodes-soft,TIMEOUT_SOFT,,$(max_nodes_soft_domain)); \
	$(call conda_run_inference,scbolt-bonesis) python $(scripts_dir)/infer/selection.py filter-nodes \
		$(word 1,$^) $(word 2,$^) \
		--important-nodes $(word 3,$^) --mandatory-nodes $(word 4,$^) \
		--forbidden-nodes $(word 5,$^) \
		--asp $(@D)/nodes.sh --solution $@ \
		--witness $(@D)/witness.lp \
		$(call clause_continuation,CLAUSE_CONTINUATION_SOFT) \
		--clause-continuation-parameter CLAUSE_CONTINUATION_SOFT \
		$(if $(strip $(PATIENCE_CLAUSE_CONTINUATION_SOFT)),--clause-continuation-patience "$(PATIENCE_CLAUSE_CONTINUATION_SOFT)") \
		$(call domain_continuation,DOMAIN_CONTINUATION_SOFT) \
		$(if $(strip $(PATIENCE_DOMAIN_CONTINUATION_SOFT)),--domain-continuation-patience "$(PATIENCE_DOMAIN_CONTINUATION_SOFT)") \
		--domain-continuation-jobs $(JOBS) \
		--domain-continuation-seed $(SEED) \
		--domain-nodes $(max_nodes_soft_domain) \
		--domain $(prior_knowledge) --organism $(ORGANISM) \
		$(prior_knowledge_args) \
		--bonesis-mode soft --max-clause $(MAX_CLAUSE) \
		--canonical $(CANONICAL_FILTER) \
		$(if $(strip $(CLINGO_CONFIG_SOFT)),--clingo-configuration $(CLINGO_CONFIG_SOFT)) \
		--clingo-opt-mode $(CLINGO_OPT_MODE_SOFT) \
		--clingo-opt-strategy $(CLINGO_OPT_STRATEGY_SOFT) \
		--jobs $(JOBS_CLINGO_SOFT) $(if $(strip $(TIMEOUT_SOFT)),--timeout "$(TIMEOUT_SOFT)") \
		--timeout-status-file "$(@D)/.inference-timeout"; \
	$(call capture_inference_exit_status,$(@D)/.inference-timeout) \
	trap - INT TERM; \
	set -e; \
	$(call check_inference_status,$(TIMEOUT_SOFT),max-nodes-soft,TIMEOUT_SOFT,,$(max_nodes_soft_domain))

$(max_consts_soft): $(bonesis_model) $(max_nodes_soft_solution) $(if $(geneinfo_dependency),| $(geneinfo_dependency))
	$(call print_rule,max-consts-soft)
	$(call require_bonesis_filter_parameters,max-consts-soft)
	$(call require_bool,MIN_SELF_LOOP_CONSTS,max-consts-soft)
	mkdir -p $(@D)
	set +e; \
	$(call start_inference_timer) \
	$(call trap_inference_interrupt,max-consts-soft,TIMEOUT_CONSTS,,$(lastword $^)); \
	$(call conda_run_inference,scbolt-bonesis) python $(scripts_dir)/infer/selection.py filter-consts \
		$(word 1,$^) $(word 2,$^) \
		--important-nodes $(word 3,$^) --mandatory-nodes $(word 4,$^) \
		--filter-grn $(lastword $^) \
		--asp $(@D)/nodes.sh --solution $@ \
		--witness $(@D)/witness.lp \
		--domain $(prior_knowledge) --organism $(ORGANISM) \
		$(prior_knowledge_args) \
		--bonesis-mode soft --max-clause $(MAX_CLAUSE) $(min_self_loop_consts) \
		--canonical $(CANONICAL_FILTER) \
		$(if $(strip $(CLINGO_CONFIG_CONSTS)),--clingo-configuration $(CLINGO_CONFIG_CONSTS)) \
		--clingo-opt-mode $(CLINGO_OPT_MODE_CONSTS) \
		--clingo-opt-strategy $(CLINGO_OPT_STRATEGY_CONSTS) \
		--jobs $(JOBS_CLINGO_CONSTS) $(if $(strip $(TIMEOUT_CONSTS)),--timeout "$(TIMEOUT_CONSTS)") \
		--timeout-status-file "$(@D)/.inference-timeout"; \
	$(call capture_inference_exit_status,$(@D)/.inference-timeout) \
	trap - INT TERM; \
	set -e; \
	$(call check_inference_status,$(TIMEOUT_CONSTS),max-consts-soft,TIMEOUT_CONSTS,,$(lastword $^))

$(max_nodes_relaxed): $(bonesis_model) $(max_consts_soft) $(if $(geneinfo_dependency),| $(geneinfo_dependency))
	$(call print_rule,max-nodes-relaxed)
	$(call require_bonesis_filter_parameters,max-nodes-relaxed)
	$(call require_bool,CLAUSE_CONTINUATION_RELAXED,max-nodes-relaxed)
	$(call require_bool,DOMAIN_CONTINUATION_RELAXED,max-nodes-relaxed)
	mkdir -p $(@D)
	set +e; \
	$(call start_inference_timer) \
	$(call trap_inference_interrupt,max-nodes-relaxed,TIMEOUT_RELAXED,,$(lastword $^)); \
	$(call conda_run_inference,scbolt-bonesis) python $(scripts_dir)/infer/selection.py filter-nodes \
		$(word 1,$^) $(word 2,$^) \
		--important-nodes $(word 3,$^) --mandatory-nodes $(word 4,$^) \
		--filter-grn $(lastword $^) --asp $(@D)/nodes.sh \
		--solution $@ --witness $(@D)/witness.lp \
		$(call clause_continuation,CLAUSE_CONTINUATION_RELAXED) \
		--clause-continuation-parameter CLAUSE_CONTINUATION_RELAXED \
		$(if $(strip $(PATIENCE_CLAUSE_CONTINUATION_RELAXED)),--clause-continuation-patience "$(PATIENCE_CLAUSE_CONTINUATION_RELAXED)") \
		$(call domain_continuation,DOMAIN_CONTINUATION_RELAXED) \
		$(if $(strip $(PATIENCE_DOMAIN_CONTINUATION_RELAXED)),--domain-continuation-patience "$(PATIENCE_DOMAIN_CONTINUATION_RELAXED)") \
		--domain-continuation-jobs $(JOBS) \
		--domain-continuation-seed $(SEED) \
		--domain $(prior_knowledge) --organism $(ORGANISM) \
		$(prior_knowledge_args) \
		--bonesis-mode relaxed --max-clause $(MAX_CLAUSE) \
		--canonical $(CANONICAL_FILTER) \
		$(if $(strip $(CLINGO_CONFIG_RELAXED)),--clingo-configuration $(CLINGO_CONFIG_RELAXED)) \
		--clingo-opt-mode $(CLINGO_OPT_MODE_RELAXED) \
		--clingo-opt-strategy $(CLINGO_OPT_STRATEGY_RELAXED) \
		--jobs $(JOBS_CLINGO_RELAXED) $(if $(strip $(TIMEOUT_RELAXED)),--timeout "$(TIMEOUT_RELAXED)") \
		--timeout-status-file "$(@D)/.inference-timeout"; \
	$(call capture_inference_exit_status,$(@D)/.inference-timeout) \
	trap - INT TERM; \
	set -e; \
	$(call check_inference_status,$(TIMEOUT_RELAXED),max-nodes-relaxed,TIMEOUT_RELAXED,,$(lastword $^))

$(max_nodes_seed)&: $(bonesis_model) $(max_nodes_relaxed) $(if $(geneinfo_dependency),| $(geneinfo_dependency))
	$(call print_rule,max-nodes-seed)
	$(call require_bonesis_filter_parameters,max-nodes-seed)
	$(call require_bool,CLAUSE_CONTINUATION_SEED,max-nodes-seed)
	$(call require_bool,DOMAIN_CONTINUATION_SEED,max-nodes-seed)
	$(call check_parameter,$(TIMEOUT_SEED),TIMEOUT_SEED (needed by target 'max-nodes-seed'))
	mkdir -p $(@D)
	set +e; \
	$(call start_inference_timer) \
	$(call trap_inference_interrupt,max-nodes-seed,TIMEOUT_SEED,,$(lastword $^),$(@D)/comps.txt); \
	$(call conda_run_inference,scbolt-bonesis) python $(scripts_dir)/infer/selection.py filter-nodes \
		$(word 1,$^) $(word 2,$^) \
		--important-nodes $(word 3,$^) --mandatory-nodes $(word 4,$^) \
		--filter-grn $(lastword $^) --asp $(@D)/nodes.sh \
		--solution $(@D)/comps.txt --witness $(@D)/witness.lp \
		$(call clause_continuation,CLAUSE_CONTINUATION_SEED) \
		--clause-continuation-parameter CLAUSE_CONTINUATION_SEED \
		$(if $(strip $(PATIENCE_CLAUSE_CONTINUATION_SEED)),--clause-continuation-patience "$(PATIENCE_CLAUSE_CONTINUATION_SEED)") \
		$(call domain_continuation,DOMAIN_CONTINUATION_SEED) \
		$(if $(strip $(PATIENCE_DOMAIN_CONTINUATION_SEED)),--domain-continuation-patience "$(PATIENCE_DOMAIN_CONTINUATION_SEED)") \
		--domain-continuation-jobs $(JOBS) \
		--domain-continuation-seed $(SEED) \
		--domain $(prior_knowledge) --organism $(ORGANISM) \
		$(prior_knowledge_args) \
		--bonesis-mode hard --max-clause $(MAX_CLAUSE) \
		--canonical $(CANONICAL_FILTER) \
		$(if $(strip $(CLINGO_CONFIG_SEED)),--clingo-configuration $(CLINGO_CONFIG_SEED)) \
		--clingo-opt-mode $(CLINGO_OPT_MODE_SEED) \
		--clingo-opt-strategy $(CLINGO_OPT_STRATEGY_SEED) \
		--jobs $(JOBS_CLINGO_SEED) $(if $(strip $(TIMEOUT_SEED)),--timeout "$(TIMEOUT_SEED)") \
		--timeout-status-file "$(@D)/.inference-timeout"; \
	$(call capture_inference_exit_status,$(@D)/.inference-timeout) \
	trap - INT TERM; \
	set -e; \
	$(call check_inference_status,$(TIMEOUT_SEED),max-nodes-seed,TIMEOUT_SEED,,$(lastword $^),$(@D)/comps.txt)

$(max_nodes_lock): $(bonesis_model) $(max_nodes_relaxed) $(max_nodes_seed) $(if $(geneinfo_dependency),| $(geneinfo_dependency))
	$(call print_rule,max-nodes-lock)
	$(call require_bonesis_filter_parameters,max-nodes-lock)
	$(call require_bool,CLAUSE_CONTINUATION_LOCK,max-nodes-lock)
	mkdir -p $(@D)
	if [ "$$($(call metadata_solution_field,$(word 7,$^),status) 2>/dev/null || true)" = "global" ]; then \
		$(call print_debug,solution already globally optimal: skipping lock optimization); \
		$(call system_tool,cp) $(word 7,$^) $@; \
		$(call write_scbolt_metadata,max-nodes-lock,$@,,$(call solution_metadata_args,global,$@,$(word 6,$^))); \
	elif [ "$(strip $(TIMEOUT_LOCK))" = "0" ]; then \
		$(call print_warning,TIMEOUT_LOCK=0: keeping seed solution); \
		$(call system_tool,cp) $(word 7,$^) $@; \
		$(call write_scbolt_metadata,max-nodes-lock,$@,,$(call solution_metadata_args,partial,$@,$(word 6,$^))); \
	else \
		set +e; \
		$(call start_inference_timer) \
		$(call trap_inference_interrupt,max-nodes-lock,TIMEOUT_LOCK,$(word 7,$^),$(word 6,$^)); \
		$(call system_tool,cat) $(word 4,$^) $(word 7,$^) | $(call system_tool,sort) -u > $(@D)/mandatory.txt; \
		$(call conda_run_inference,scbolt-bonesis) python $(scripts_dir)/infer/selection.py filter-nodes \
			$(word 1,$^) $(word 2,$^) \
			--important-nodes $(word 3,$^) --mandatory-nodes $(@D)/mandatory.txt \
			--filter-grn $(word 6,$^) --asp $(@D)/nodes.sh \
			--solution $@ --witness $(@D)/witness.lp \
			--initial-witness $(lastword $^) \
			$(call clause_continuation,CLAUSE_CONTINUATION_LOCK) \
			--clause-continuation-parameter CLAUSE_CONTINUATION_LOCK \
			$(if $(strip $(PATIENCE_CLAUSE_CONTINUATION_LOCK)),--clause-continuation-patience "$(PATIENCE_CLAUSE_CONTINUATION_LOCK)") \
			--domain $(prior_knowledge) --organism $(ORGANISM) \
			$(prior_knowledge_args) \
			--bonesis-mode hard --max-clause $(MAX_CLAUSE) \
			--canonical $(CANONICAL_FILTER) \
			$(if $(strip $(CLINGO_CONFIG_LOCK)),--clingo-configuration $(CLINGO_CONFIG_LOCK)) \
			--clingo-opt-mode $(CLINGO_OPT_MODE_LOCK) \
			--clingo-opt-strategy $(CLINGO_OPT_STRATEGY_LOCK) \
			--jobs $(JOBS_CLINGO_LOCK) $(if $(strip $(TIMEOUT_LOCK)),--timeout "$(TIMEOUT_LOCK)") \
			--timeout-status-file "$(@D)/.inference-timeout"; \
		$(call capture_inference_exit_status,$(@D)/.inference-timeout) \
		trap - INT TERM; \
		set -e; \
		$(call check_inference_status,$(TIMEOUT_LOCK),max-nodes-lock,TIMEOUT_LOCK,$(word 7,$^),$(word 6,$^)); \
	fi

$(bn_min): $(bonesis_model) $(max_nodes_lock) $(if $(geneinfo_dependency),| $(geneinfo_dependency))
	$(call print_rule,bn-min)
	$(call require_bonesis_infer_parameters,bn-min)
	$(call require_bool,MIN_SELF_LOOP_INFER,bn-min)
	mkdir -p $(@D)
	$(call conda_run_inference,scbolt-bonesis) python $(scripts_dir)/infer/infer.py min \
		$(word 1,$^) $(word 2,$^) \
		--filter-grn $(lastword $^) \
		--asp $(@D)/min.sh \
		--solution $(basename $@) \
		--domain $(prior_knowledge) \
		--organism $(ORGANISM) \
		$(prior_knowledge_args) \
		--max-clause $(MAX_CLAUSE) $(min_self_loop_infer) \
		--canonical $(CANONICAL_INFER) \
		--clingo-opt-mode $(CLINGO_OPT_MODE_MIN) --jobs 1 \
		--graph-formats $(GRAPH_FORMATS)
		if command -v dot >/dev/null 2>&1; then
		    for file in $(@D)/*.dot; do
		        [ -e "$${file}" ] || continue
		        dot -Tpdf "$${file}" -o "$${file%.dot}.pdf"
		    done
		fi
	$(call write_scbolt_metadata,bn-min,$@)

.PHONY: __check-bn-submin-outputs __check-bn-diverse-outputs
__check-bn-submin-outputs:
	$(call check_bn_outputs,$(bn_submin_dir),bn-submin,$(CONFIG_FORMATS),$(GRAPH_FORMATS),$(INFER_LIMIT))

__check-bn-diverse-outputs:
	$(call check_bn_outputs,$(bn_diverse_dir),bn-diverse,$(CONFIG_FORMATS),$(GRAPH_FORMATS),$(INFER_LIMIT))

$(bn_submin)&: $(bonesis_model) $(max_nodes_lock) | __check-bn-submin-outputs $(geneinfo_dependency)
	$(call print_rule,bn-submin)
	$(call require_bonesis_infer_parameters,bn-submin)
	rm -rf $(bn_submin_dir)
	mkdir -p $(bn_submin_dir)
	$(call conda_run_inference,scbolt-bonesis) python $(scripts_dir)/infer/infer.py submin \
		$(word 1,$^) $(word 2,$^) \
		--filter-grn $(lastword $^) \
		--asp $(bn_submin_dir)/submin.sh \
		--solution $(bn_submin_dir) \
		--domain $(prior_knowledge) \
		--organism $(ORGANISM) \
		$(prior_knowledge_args) \
		--max-clause $(MAX_CLAUSE) \
		--canonical $(CANONICAL_INFER) \
		--jobs $(JOBS) \
		$(if $(strip $(INFER_LIMIT)),--limit $(INFER_LIMIT)) \
		--config-formats $(CONFIG_FORMATS) \
		--graph-formats $(GRAPH_FORMATS) \
		--remove-isolated-nodes
	$(call write_scbolt_metadata,bn-submin,$(bn_submin_metadata))

$(bn_diverse)&: $(bonesis_model) $(max_nodes_lock) | __check-bn-diverse-outputs $(geneinfo_dependency)
	$(call print_rule,bn-diverse)
	$(call require_bonesis_infer_parameters,bn-diverse)
	rm -rf $(bn_diverse_dir)
	mkdir -p $(bn_diverse_dir)
	$(call conda_run_inference,scbolt-bonesis) python $(scripts_dir)/infer/infer.py diverse \
		$(word 1,$^) $(word 2,$^) \
		--filter-grn $(lastword $^) \
		--asp $(bn_diverse_dir)/diverse.sh \
		--solution $(bn_diverse_dir) \
		--domain $(prior_knowledge) \
		--organism $(ORGANISM) \
		$(prior_knowledge_args) \
		--max-clause $(MAX_CLAUSE) \
		--canonical $(CANONICAL_INFER) \
		--jobs $(JOBS) \
		$(if $(strip $(INFER_LIMIT)),--limit $(INFER_LIMIT)) \
		--config-formats $(CONFIG_FORMATS) \
		--graph-formats $(GRAPH_FORMATS) \
		--remove-isolated-nodes
	$(call write_scbolt_metadata,bn-diverse,$(bn_diverse_metadata))

$(foreach condition,$(conditions),$(eval $(call compute_rules_for_conditions,$(condition))))
$(foreach reference,$(references_default),$(eval $(call compute_rules_for_references,$(reference))))

## END RULES
