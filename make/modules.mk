## BEGIN PATHS ##

omics_dir := $(results)/omics
bin_dir := $(results)/bin
infer_dir := $(results)/$(inference_subdir)

fastq_dir = $(omics_dir)/fastq/$(call condition_path,$(1))
count_dir = $(omics_dir)/count/$(call condition_path,$(1))
filter_dir = $(omics_dir)/prep/$(call condition_path,$(1))filter/
norm_dir = $(omics_dir)/prep/$(call condition_path,$(1))norm/
clust_dir = $(omics_dir)/clust/$(call condition_path,$(1))
annot_dir = $(omics_dir)/annot/$(call condition_path,$(1))
dea_dir = $(omics_dir)/dea/$(call condition_path,$(1))
scoring_dir = $(omics_dir)/scoring/$(call condition_path,$(1))
goea_dir = $(omics_dir)/goea/$(call condition_path,$(1))
velocity_dir = $(omics_dir)/trajectories/velocity/$(call condition_path,$(1))
potency_dir = $(omics_dir)/trajectories/potency/$(call condition_path,$(1))
mstates_dir = $(omics_dir)/mstates/$(1)/$(call condition_path,$(2))

h5ads_for_conditions = $(foreach condition,$(running_conditions),$($(1)_$(condition)))
default_bin_input_h5ads = $(if $(multi_condition),$(annotation_integrated),$(annotation_$(conditions)))
macrostate_h5ad = $(if $(MACROSTATE_FILES),$(tmpdir)/bin/macrostates.h5ad)
macrostate_h5ads = $(if $(filter 1,$(words $(MACROSTATE_FILES))),\
	$(macrostate_h5ad),\
	$(foreach condition,$(conditions),$(macrostate_h5ad_$(condition))))
bin_input_h5ads = $(if $(MACROSTATE_FILES),$(macrostate_h5ad),$(default_bin_input_h5ads))

clustering_integrated = $(call clust_dir,integrated)clust.h5ad
annotation_integrated = $(call annot_dir,integrated)annot.h5ad

cc_markers  = $(resources_dir)/cycle/mouse_cycle_markers.rds
signatures  = $(resources_dir)/signatures/geiger.xls \
              $(resources_dir)/signatures/chambers.xls \
              $(resources_dir)/signatures/sig.json
go_basic    = $(resources_dir)/go/go_basic.obo
go_organism = $(resources_dir)/go/goslim_$(ORGANISM).obo
gene2go     = $(resources_dir)/go/gene2go.gz
gene2go_done = $(resources_dir)/go/gene2go.gz.done
repeat_msk_table = $(resources_dir)/ref/rmsk.txt.gz
repeat_msk  = $(resources_dir)/ref/repeat_msk.gtf.gz
geneinfo_organism = $(subst -,_,$(ORGANISM))
geneinfo_latest = $(tmpdir)/ncbi/$(geneinfo_organism)_gene_info_latest.tsv.gz

genome_ref_name = $(if $(strip $(genome_url)),$(notdir $(genome_url)),missing-genome-url)
genome_ref_archive = $(resources_dir)/ref/$(genome_ref_name)
$(eval genome_ref := $(tmpdir)/ref/$(genome_ref_name))
genome_ref := $(genome_ref:.tar.gz=)
star_index = $(genome_ref)/star/Genome

define find_paths_for_conditions

fastq_$(1) =                    $(patsubst %/,%,$(call fastq_dir,$(1)))
count_file_$(1) =               $(call file_for_condition,$(1),$(COUNT_FILES))
load_matrix_$(1) =              $(call count_dir,$(1))counts.h5ad
cellranger_$(1) =               $(call count_dir,$(1))cellranger/$(call condition_name,$(1)).mri.tgz
star_$(1) =                     $(call count_dir,$(1))star/Aligned.sortedByCoord.out.bam \
                                $(call count_dir,$(1))star/Solo.out/matrix.mtx \
                                $(call count_dir,$(1))star/Solo.out/barcodes.tsv
qc_$(1) =                       $(call count_dir,$(1))star/star.velocyto.bam
velocyto_$(1) =                 $(call count_dir,$(1))counts.h5ad
filtering_$(1) =                $(call filter_dir,$(1))counts.h5ad
normalization_$(1) =            $(call norm_dir,$(1))counts.h5ad
velocity_$(1) =                 $(call velocity_dir,$(1))velocity.h5ad
potency_$(1) =                  $(call potency_dir,$(1))potency.csv
cotan_$(1) =                    $(call mstates_dir,cotan,$(1))mstates.h5ad \
                                $(call mstates_dir,cotan,$(1))mstates.csv
cellrank_$(1) =                 $(call mstates_dir,cellrank,$(1))mstates.h5ad \
                                $(call mstates_dir,cellrank,$(1))mstates.csv
stream_$(1) =                   $(call mstates_dir,stream,$(1))mstates.h5ad \
                                $(call mstates_dir,stream,$(1))mstates.csv
knnsc_$(1) =                    $(call mstates_dir,knnsc,$(1))mstates.h5ad \
                                $(call mstates_dir,knnsc,$(1))mstates.csv

ifeq ($(MACROSTATE_METHOD),cotan)
macrostates_$(1) =              $$(cotan_$(1))
else ifeq ($(MACROSTATE_METHOD),cellrank)
macrostates_$(1) =              $$(cellrank_$(1))
else ifeq ($(MACROSTATE_METHOD),stream)
macrostates_$(1) =              $$(stream_$(1))
else ifeq ($(MACROSTATE_METHOD),knnsc)
macrostates_$(1) =              $$(knnsc_$(1))
else
macrostates_$(1) =              $(call mstates_dir,invalid-method,$(1)).error
endif

ifeq ($(ALIGNMENT_TOOL),cellranger)
alignment_$(1) =                $$(cellranger_$(1))
else ifeq ($(ALIGNMENT_TOOL),star)
alignment_$(1) =                $$(star_$(1))
else
alignment_$(1) =                $(call count_dir,$(1))invalid-alignment/.error
endif

macrostate_file_$(1) =          $(call file_for_condition,$(1),$(MACROSTATE_FILES))
macrostate_h5ad_$(1) =          $(tmpdir)/$(1)/bin/macrostates.h5ad
count_input_$(1) =              $(if $(filter true,$(count_files_mode)),$$(count_file_$(1)),\
                                $(if $(filter true,$(matrix_mode)),$$(load_matrix_$(1)),$$(velocyto_$(1))))

endef

define find_paths_for_references

clustering_$(1) =               $(call clust_dir,$(1))clust.h5ad
dea_$(1) =                      $(call dea_dir,$(1))markers.csv \
                                $(call dea_dir,$(1))genes.xlsx
scoring_$(1) =                  $(call scoring_dir,$(1))signature_pvals.csv \
                                $(call scoring_dir,$(1))signature_pvals_adj.csv \
                                $(call scoring_dir,$(1))signature_fold_enrichment.csv \
                                $(call scoring_dir,$(1))ora_results.xlsx
goea_basic_$(1) =               $(call goea_dir,$(1))basic.xlsx
goea_organism_$(1) =            $(call goea_dir,$(1))$(ORGANISM).xlsx
annotation_$(1) =               $(call annot_dir,$(1))annot.h5ad

endef

bin_cells =                     $(bin_dir)/scboolseq/cell/cells_bin.h5ad \
                                $(bin_dir)/scboolseq/cell/cells_stats.csv
bin_hvg =                       $(tmpdir)/bin/top_genes.txt
bin_mstates =                   $(bin_dir)/scboolseq/macro/$(MACROSTATE_METHOD)/mstates_bin.csv
bin_dea =                       $(bin_dir)/dea/$(MACROSTATE_METHOD)/mstates_bin.csv
bin_consensus =                 $(bin_dir)/consensus/$(MACROSTATE_METHOD)/mstates_bin.csv

bonesis_model =                 $(infer_dir)/spec/model.bo \
                                $(infer_dir)/spec/mstates.csv \
                                $(infer_dir)/spec/important.txt \
                                $(infer_dir)/spec/mandatory.txt \
                                $(infer_dir)/spec/forbidden.txt
max_nodes_soft =                $(infer_dir)/genes/soft/comps.txt
max_nodes_soft_solution =       $(max_nodes_soft)
max_nodes_soft_domain_size =    $(tmpdir)/max-nodes-soft-domain.count
max_consts_soft =               $(infer_dir)/genes/consts/comps.txt
max_nodes_relaxed =             $(infer_dir)/genes/relaxed/comps.txt
max_nodes_relaxed_witness =     $(infer_dir)/genes/relaxed/witness.lp
max_nodes_seed =                $(infer_dir)/genes/seed/comps.txt \
                                $(infer_dir)/genes/seed/witness.lp
max_nodes_lock =                $(infer_dir)/genes/lock/comps.txt
max_nodes_lock_witness =        $(infer_dir)/genes/lock/witness.lp
bn_min =                        $(infer_dir)/bn/min/model.bnet

bn_submin_dir = $(infer_dir)/bn/submin
bn_submin = $(bn_submin_dir)/influence_graph/aggregate.pdf
bn_submin_metadata = $(bn_submin_dir)

bn_diverse_dir = $(infer_dir)/bn/diverse
bn_diverse = $(bn_diverse_dir)/influence_graph/aggregate.pdf
bn_diverse_metadata = $(bn_diverse_dir)

$(foreach condition,$(conditions),$(eval $(call find_paths_for_conditions,$(condition))))
$(foreach reference,$(references_default),$(eval $(call find_paths_for_references,$(reference))))

## END PATHS ##

## BEGIN TARGETS ##

fastq_target :=
load_matrix_target :=
alignment_target :=
cellranger_target :=
star_target :=
qc_target :=
velocyto_target :=
filtering_target :=
normalization_target :=
clustering_target :=
dea_target :=
scoring_target :=
goea_target :=
annotation_target :=
velocity_target :=
potency_target :=
macrostates_target :=
stream_target :=
cellrank_target :=
knnsc_target :=
cotan_target :=

define find_targets_for_conditions

$(eval fastq_target := $(fastq_target) $(if $(filter true,$(matrix_mode)),,$(fastq_$(1))))
$(eval load_matrix_target := $(load_matrix_target) $(if $(filter true,$(matrix_mode)),$(load_matrix_$(1))))
$(eval alignment_target := $(alignment_target) $(alignment_$(1)))
$(eval cellranger_target := $(cellranger_target) $(cellranger_$(1)))
$(eval star_target := $(star_target) $(star_$(1)))
$(eval qc_target := $(qc_target) $(qc_$(1)))
$(eval velocyto_target := $(velocyto_target) $(if $(filter true,$(count_files_mode) $(matrix_mode)),,$(velocyto_$(1))))
$(eval filtering_target := $(filtering_target) $(filtering_$(1)))
$(eval normalization_target := $(normalization_target) $(normalization_$(1)))
$(eval velocity_target := $(velocity_target) $(velocity_$(1)))
$(eval potency_target := $(potency_target) $(potency_$(1)))
$(eval cotan_target := $(cotan_target) $(cotan_$(1)))
$(eval cellrank_target := $(cellrank_target) $(cellrank_$(1)))
$(eval stream_target := $(stream_target) $(stream_$(1)))
$(eval knnsc_target := $(knnsc_target) $(knnsc_$(1)))
$(eval macrostates_target := $(macrostates_target) $(macrostates_$(1)))

endef

define find_targets_for_references

$(eval clustering_target := $(clustering_target) $(clustering_$(1)))
$(eval dea_target := $(dea_target) $(dea_$(1)))
$(eval scoring_target := $(scoring_target) $(scoring_$(1)))
$(eval goea_target := $(goea_target) $(goea_basic_$(1)) $(goea_organism_$(1)))
$(eval annotation_target := $(annotation_target) $(annotation_$(1)))

endef

$(foreach condition,$(target_conditions),$(eval $(call find_targets_for_conditions,$(condition))))
$(foreach reference,$(running_references),$(eval $(call find_targets_for_references,$(reference))))

ifneq ($(strip $(MACROSTATE_FILES)),)
macrostates_target := $(macrostate_h5ad)
endif

## END TARGETS ##

ifeq ($(words $(conditions)),1)
batch =
else
batch = --batch condition
endif

## BEGIN PARAMETERS ##

TRUST_EXISTING ?= false

ifeq ($(diagnostic_mode),)
ifneq ($(memory_valid),true)
$(error parameter MEMORY must be a positive memory size (current: $(MEMORY)))
endif
ifneq ($(call is_positive_integer,$(JOBS)),true)
$(error parameter JOBS must be a positive integer (current: $(JOBS)))
endif
ifneq ($(call is_positive_integer,$(SEED)),true)
$(error parameter SEED must be a positive integer (current: $(SEED)))
endif
ifneq ($(filter $(LOGGING),true false),$(LOGGING))
$(error unsupported value for parameter LOGGING (supported values: true, false))
endif
ifneq ($(filter $(TRUST_EXISTING),true false),$(TRUST_EXISTING))
$(error unsupported value for parameter TRUST_EXISTING (supported values: true, false))
endif
ifneq ($(call is_creatable_path,$(PROJECT_DIR)),true)
$(error parameter PROJECT_DIR must be a valid output path (current: $(PROJECT_DIR)))
endif
ifneq ($(inference_dir_valid),true)
$(error parameter INFERENCE_DIR must be a relative subdirectory of PROJECT_DIR (current: $(INFERENCE_DIR)))
endif
ifneq ($(call is_creatable_path,$(RESOURCES_DIR)),true)
$(error parameter RESOURCES_DIR must be a valid output path (current: $(RESOURCES_DIR)))
endif
ifeq ($(strip $(REFERENCES)),)
$(error parameter REFERENCES not defined)
endif
ifneq ($(invalid_references),)
$(error unsupported value for parameter REFERENCES: $(invalid_references) \
	(supported values: $(subst $(space),$(comma) ,$(display_supported_references_label))))
endif
ifeq ($(words $(conditions)),1)
ifneq ($(filter integrated,$(running_references)),)
$(error unsupported value for parameter REFERENCES: integrated is not supported \
	for mono-condition projects)
endif
endif
endif

$(if $(filter true,$(call is_creatable_path,$(PROJECT_DIR))),$(shell $(call system_tool,mkdir) -p "$(results)"))
$(if $(filter true,$(call is_creatable_path,$(RESOURCES_DIR))),$(shell $(call system_tool,mkdir) -p "$(resources_dir)"))

check_mode := $(filter check,$(MAKECMDGOALS))$(__check_mode)

ifneq ($(check_mode),)
$(if $(strip $(JOBS)),,$(eval override JOBS := 1))
endif

ifndef JOBS
scboolseq_native_threads := 1
else ifneq ($(call is_positive_integer,$(JOBS)),true)
scboolseq_native_threads := 1
else
try_scboolseq_native_threads := $(shell echo $$(($(JOBS) / 2)))
scboolseq_native_threads := $(if $(findstring $(try_scboolseq_native_threads),0),1,$(try_scboolseq_native_threads))
endif

ifeq ($(filter auto,$(SCBOOLSEQ_OPENBLAS_THREADS)),auto)
override SCBOOLSEQ_OPENBLAS_THREADS := $(scboolseq_native_threads)
endif
ifeq ($(filter auto,$(SCBOOLSEQ_OMP_THREADS)),auto)
override SCBOOLSEQ_OMP_THREADS := $(scboolseq_native_threads)
endif

scboolseq_openblas_threads := $(SCBOOLSEQ_OPENBLAS_THREADS)
scboolseq_omp_threads := $(SCBOOLSEQ_OMP_THREADS)

consistent_mad = $(if $(filter true,$(CONSISTENT_MAD)),--consistent-mad)
cc_correction = $(if $(filter true,$(CC_CORRECTION)),--correction G2M_score S_score G1_score)
pca_only_hvg = $(if $(filter true,$(PCA_ONLY_HVG)),--only-hvg)
centered_pca = $(if $(filter true,$(CENTERED_PCA)),--centered-pca)
embedding_method_X_umap = umap
embedding_method_X_tsne = tsne
embedding_method_X_se = spectral
embedding_method = $(embedding_method_$(1))
embedding = $(call embedding_method,$(REPRESENTATION))

label_ids = $(if $(LABEL),$(shell $(call system_tool,seq) 0 1 $$(($(words $(LABEL))-1))))
label_map = $(join $(label_ids),$(addprefix :,$(LABEL)))

velocity_only_hvg = $(if $(filter true,$(VELOCITY_ONLY_HVG)),--only-hvg)
cotan_only_hvg = $(if $(filter true,$(COTAN_ONLY_HVG)),--only-hvg)
extend_epg = $(if $(filter true,$(EXTEND_EPG)),--extend-epg)
prune_epg = $(if $(filter true,$(PRUNE_EPG)),--prune-epg)

ifeq ($(KNNSC_DIMENSION),)
knnsc_dimension=
else
knnsc_dimension=--dimension $(KNNSC_DIMENSION)
endif

hvg_layer_name = $(if $(filter loess,$(1)),counts,log-norm)
hvg_layer = --expression $(call hvg_layer_name,$(1))
bin_hvg_layer = $(if $(filter loess binning,$(BIN_HVG_METHOD)),\
	$(call hvg_layer,$(BIN_HVG_METHOD)))
bin_scboolseq_hvg = $(if $(filter true,$(BIN_SCBOOLSEQ_ONLY_HVG)),--filter-genes $(bin_hvg))
bin_dea_hvg = $(if $(filter true,$(BIN_DEA_ONLY_HVG)),--filter-genes $(bin_hvg))
zeroes_are_zeroes = $(if $(filter true,$(ZEROES_ARE_ZEROES)),--zeroes-are-zeroes)
bin_method_error = $(bin_dir)/invalid-method/.error
default_bin = $(if $(filter scboolseq,$(BIN_METHOD)),$(bin_mstates),\
	$(if $(filter dea,$(BIN_METHOD)),$(bin_dea),\
	$(if $(filter consensus,$(BIN_METHOD)),$(bin_consensus),$(bin_method_error))))
bin = $(if $(BINARIZATION_FILE),$(BINARIZATION_FILE),$(default_bin))

known_prior_knowledge = collectri dorothea
dorothea_apis = modern legacy
dorothea_levels = A B C D

# Resolve the user-facing prior knowledge parameter to the actual domain passed
# to BoNesis scripts.
ifeq ($(PRIOR_KNOWLEDGE),collectri)
prior_knowledge = collectri
else ifeq ($(PRIOR_KNOWLEDGE),dorothea)
prior_knowledge = dorothea
else ifneq ($(wildcard $(PRIOR_KNOWLEDGE)),)
prior_knowledge = $(PRIOR_KNOWLEDGE)
endif
dorothea_levels_arg = $(if $(filter dorothea,$(prior_knowledge)),\
	$(if $(strip $(DOROTHEA_LEVELS)),--dorothea-levels $(DOROTHEA_LEVELS)))
dorothea_api_arg = $(if $(filter dorothea,$(prior_knowledge)),\
	--dorothea-api $(DOROTHEA_API))
dorothea_compatibility_arg = $(if $(filter dorothea,$(prior_knowledge)),\
	--dorothea-compatibility $(DOROTHEA_COMPATIBILITY))
geneinfo_version = $(if $(filter latest,$(GENEINFO_VERSION)),$(geneinfo_latest),$(GENEINFO_VERSION))
geneinfo_version_arg = --geneinfo-version $(geneinfo_version)
geneinfo_dependency = $(if $(filter latest,$(GENEINFO_VERSION)),$(geneinfo_latest))
omnipath_version_arg = $(if $(filter collectri dorothea,$(prior_knowledge)),\
	--omnipath-version $(OMNIPATH_VERSION))
hcop_version_arg = $(if $(filter collectri dorothea,$(prior_knowledge)),\
	--hcop-version $(HCOP_VERSION))
prior_knowledge_args = \
	$(geneinfo_version_arg) \
	$(omnipath_version_arg) \
	$(hcop_version_arg) \
	$(dorothea_api_arg) \
	$(dorothea_compatibility_arg) \
	$(dorothea_levels_arg)
prior_knowledge_params = PRIOR_KNOWLEDGE \
	GENEINFO_VERSION \
	$(if $(filter collectri dorothea,$(PRIOR_KNOWLEDGE)),OMNIPATH_VERSION HCOP_VERSION) \
	$(if $(filter dorothea,$(PRIOR_KNOWLEDGE)),\
	DOROTHEA_API DOROTHEA_COMPATIBILITY DOROTHEA_LEVELS)

min_self_loop_consts = $(if $(filter true,$(MIN_SELF_LOOP_CONSTS)),--minimize-self-loops)
min_self_loop_infer = $(if $(filter true,$(MIN_SELF_LOOP_INFER)),--minimize-self-loops)
clause_continuation_params = \
	CLAUSE_CONTINUATION_SOFT CLAUSE_CONTINUATION_RELAXED \
	CLAUSE_CONTINUATION_SEED CLAUSE_CONTINUATION_LOCK
clause_bound_patience_params = PATIENCE_CLAUSE_BOUND
clause_continuation = $(if $(filter true,$($(1))),--clause-continuation)
domain_continuation_params = \
	DOMAIN_CONTINUATION_SOFT DOMAIN_CONTINUATION_RELAXED \
	DOMAIN_CONTINUATION_SEED DOMAIN_CONTINUATION_LOCK
domain_wave_patience_params = PATIENCE_DOMAIN_WAVE PATIENCE_DOMAIN_WAVE_LOCK
domain_continuation_policy_params = MIN_DOMAIN_YIELD MAX_DOMAIN_REFRESHES
domain_continuation = $(if $(filter true,$($(1))),--domain-continuation)
clingo_threads_params = CLINGO_THREADS

reset_stages = \
	load-fastq load-matrix alignment cellranger star qc velocyto \
	filtering normalization clustering dea scoring goea annotation \
	velocity potency cotan cellrank stream knnsc macrostates \
	bin-cells bin-macrostates bin-dea bin-consensus binarization \
	spec max-nodes-soft max-consts-soft max-nodes-relaxed \
	max-nodes-seed max-nodes-lock bn-min bn-submin bn-diverse

progress_deps_load-matrix =
progress_deps_alignment = $(ALIGNMENT_TOOL)
progress_deps_cellranger = load-fastq
progress_deps_star = load-fastq
progress_deps_qc = star
progress_deps_velocyto = $(if $(filter star,$(ALIGNMENT_TOOL)),qc,cellranger)
progress_deps_filtering = $(count_input_module)
progress_deps_normalization = filtering
progress_deps_clustering = normalization
progress_deps_dea = clustering
progress_deps_scoring = clustering
progress_deps_goea = dea
progress_deps_annotation = clustering
progress_deps_velocity = annotation
progress_deps_potency = annotation
progress_deps_cotan = annotation
progress_deps_cellrank = velocity potency
progress_deps_stream = annotation
progress_deps_knnsc = annotation
progress_deps_macrostates = $(if $(MACROSTATE_FILES),,$(MACROSTATE_METHOD))
progress_deps_bin-cells = $(if $(MACROSTATE_FILES),,annotation)
progress_deps_bin-macrostates = \
	bin-cells $(if $(MACROSTATE_FILES),,macrostates)
progress_deps_bin-dea = $(if $(MACROSTATE_FILES),,annotation macrostates)
progress_deps_bin-consensus = bin-macrostates bin-cells bin-dea
progress_deps_binarization = $(if $(BINARIZATION_FILE),,\
	$(if $(filter scboolseq,$(BIN_METHOD)),bin-macrostates,\
	$(if $(filter dea,$(BIN_METHOD)),bin-dea,\
	$(if $(filter consensus,$(BIN_METHOD)),bin-consensus))))
progress_deps_spec = $(if $(BINARIZATION_FILE),,binarization)
progress_deps_max-nodes-soft = spec
progress_deps_max-consts-soft = spec max-nodes-soft
progress_deps_max-nodes-relaxed = spec max-consts-soft
progress_deps_max-nodes-seed = spec max-nodes-relaxed
progress_deps_max-nodes-lock = spec max-nodes-relaxed max-nodes-seed
progress_deps_bn-min = spec max-nodes-lock
progress_deps_bn-submin = spec max-nodes-lock
progress_deps_bn-diverse = spec max-nodes-lock

RESET_TARGET_load-fastq = $(fastq_target)
RESET_TARGET_load-matrix = $(load_matrix_target)
RESET_TARGET_alignment = $(alignment_target)
RESET_TARGET_cellranger = $(cellranger_target)
RESET_TARGET_star = $(star_target)
RESET_TARGET_qc = $(qc_target)
RESET_TARGET_velocyto = $(velocyto_target)
RESET_TARGET_filtering = $(filtering_target)
RESET_TARGET_normalization = $(normalization_target)
RESET_TARGET_clustering = $(clustering_target)
RESET_TARGET_dea = $(dea_target)
RESET_TARGET_scoring = $(scoring_target)
RESET_TARGET_goea = $(goea_target)
RESET_TARGET_annotation = $(annotation_target)
RESET_TARGET_velocity = $(velocity_target)
RESET_TARGET_potency = $(potency_target)
RESET_TARGET_cotan = $(cotan_target)
RESET_TARGET_cellrank = $(cellrank_target)
RESET_TARGET_stream = $(stream_target)
RESET_TARGET_knnsc = $(knnsc_target)
RESET_TARGET_macrostates = $(macrostates_target)
RESET_TARGET_bin-cells = $(bin_cells)
RESET_TARGET_bin-macrostates = $(bin_mstates)
RESET_TARGET_bin-dea = $(bin_dea)
RESET_TARGET_bin-consensus = $(bin_consensus)
RESET_TARGET_binarization = $(bin)
RESET_TARGET_spec = $(bonesis_model)
RESET_TARGET_max-nodes-soft = $(max_nodes_soft)
RESET_TARGET_max-consts-soft = $(max_consts_soft)
RESET_TARGET_max-nodes-relaxed = $(max_nodes_relaxed) $(max_nodes_relaxed_witness)
RESET_TARGET_max-nodes-seed = $(max_nodes_seed)
RESET_TARGET_max-nodes-lock = $(max_nodes_lock) $(max_nodes_lock_witness)
RESET_TARGET_bn-min = $(bn_min)
RESET_TARGET_bn-submin = $(bn_submin_metadata)
RESET_TARGET_bn-diverse = $(bn_diverse_metadata)
RESET_BUILD_TARGET_bn-submin = $(bn_submin)
RESET_BUILD_TARGET_bn-diverse = $(bn_diverse)

reset_modules := $(strip $(RESET_TARGET) $(CLI_RESET_TARGETS) $(RESET_FROM))
trust_modules := $(strip $(TRUST_TARGET) $(CLI_TRUST_TARGETS))
raw_clean_modules := $(strip $(CLEAN_TARGET))
clean_all := $(filter all,$(raw_clean_modules))
clean_modules := $(if $(filter all,$(raw_clean_modules)),$(reset_stages),$(raw_clean_modules))
reset_disabled_goals := help
reset_disabled := $(strip \
	$(filter $(reset_disabled_goals),$(MAKECMDGOALS)) \
	$(__reset_disabled) \
	$(if $(filter true,$(HELP)),help))
ifeq ($(reset_disabled),)
unknown_reset_targets := $(filter-out $(reset_stages),$(reset_modules))
unknown_trust_targets := $(filter-out $(reset_stages),$(trust_modules))
unknown_clean_targets := $(filter-out $(reset_stages) all,$(raw_clean_modules))
ifneq ($(clean_all),)
ifneq ($(filter-out all,$(raw_clean_modules)),)
$(error CLEAN_TARGET=all cannot be combined with modules: $(filter-out all,$(raw_clean_modules)))
endif
endif
ifneq ($(unknown_reset_targets),)
$(error unknown RESET_TARGET/RESET_FROM module: $(unknown_reset_targets) \
	(supported values: $(subst $(space),$(comma) ,$(reset_stages))))
endif
ifneq ($(unknown_trust_targets),)
$(error unknown TRUST_TARGET module: $(unknown_trust_targets) \
	(supported values: $(subst $(space),$(comma) ,$(reset_stages))))
endif
ifneq ($(unknown_clean_targets),)
$(error unknown CLEAN_TARGET module: $(unknown_clean_targets) \
	(supported values: $(subst $(space),$(comma) ,$(reset_stages))))
endif
reset_targets := $(strip $(foreach module,$(reset_modules),\
	$(if $(RESET_BUILD_TARGET_$(module)),\
		$(RESET_BUILD_TARGET_$(module)),\
		$(RESET_TARGET_$(module)))))
module_rebuilds_after_reset = $(strip $(or \
	$(filter $(1),$(reset_modules)),\
	$(foreach dependency,$(progress_deps_$(1)),\
		$(call module_rebuilds_after_reset,$(dependency)))))
reset_rebuild_modules := $(strip $(foreach module,$(reset_stages),\
	$(if $(call module_rebuilds_after_reset,$(module)),$(module))))
reset_rebuild_targets := $(strip $(foreach module,$(reset_rebuild_modules),\
	$(RESET_TARGET_$(module))))
blocked_trust_targets := $(call uniq,$(reset_targets) $(reset_rebuild_targets))
trust_targets := $(strip $(foreach module,$(trust_modules),$(RESET_TARGET_$(module))))
known_scbolt_targets := $(call uniq,$(foreach module,$(reset_stages),$(RESET_TARGET_$(module))))
existing_scbolt_targets := $(strip $(foreach target,$(known_scbolt_targets),\
	$(if $(wildcard $(target)),$(target))))
trust_existing_candidates := $(if $(filter true,$(TRUST_EXISTING)),\
	$(existing_scbolt_targets))
trust_existing_targets := $(filter-out $(blocked_trust_targets),\
	$(trust_existing_candidates))
trusted_make_targets := $(filter-out $(blocked_trust_targets),\
	$(call uniq,$(trust_targets) $(trust_existing_targets)))
trusted_old_files := $(filter-out $(blocked_trust_targets),$(OLD_FILES))
unknown_old_files := $(filter-out $(known_scbolt_targets),$(OLD_FILES))
missing_old_files := $(strip $(foreach path,$(trusted_old_files),$(if $(wildcard $(path)),,$(path))))
ifneq ($(reset_targets),)
.PHONY: $(reset_targets)
endif
trust_make_options := \
	$(foreach target,$(trusted_make_targets),--old-file="$(target)") \
	$(foreach target,$(trusted_old_files),--old-file="$(target)")
ifeq ($(diagnostic_mode),)
ifneq ($(missing_old_files),)
$(error old file not found: $(missing_old_files))
endif
endif
endif

target_params_load-matrix = $(foreach condition,$(conditions),$(call gsm_var,$(condition)))
target_params_alignment = ALIGNMENT_TOOL MEMORY STAR_CB_LEN STAR_UMI_LEN STAR_WHITELIST
target_params_cellranger = MEMORY
target_params_star = MEMORY STAR_CB_LEN STAR_UMI_LEN STAR_WHITELIST
target_params_qc = STAR_BARCODE_FILTER STAR_MIN_UMI STAR_TOP_BARCODES
target_params_velocyto = ALIGNMENT_TOOL MEMORY STAR_BARCODE_FILTER STAR_MIN_UMI STAR_TOP_BARCODES
target_params_filtering = \
	$(count_file_params) \
	GENEINFO_VERSION \
	GENE_DROPOUT GENE_EXPRESSION GENE_COUNTS \
	CELL_DROPOUT CELL_EXPRESSION CELL_READS \
	MAD_DEVIATION CONSISTENT_MAD MT
target_params_normalization = MEMORY CC_CORRECTION
target_params_clustering = \
	INTEGRATION OMICS_HVG_METHOD OMICS_HVG_TOP OMICS_HVG_SPAN \
	OMICS_HVG_BINS DIM_PCA DIM_EMBEDDING CENTERED_PCA PCA_ONLY_HVG \
	NEIGHBORS METRIC RESOLUTION MIN_DIST SPREAD EMBEDDING_N_ITER
target_params_dea = MEMORY DEA_METHOD LOGFC CORRECTION ALPHA
target_params_goea = GENEINFO_VERSION
target_params_annotation = LABEL
target_params_velocity = DIM_MOMENT VELOCITY_ONLY_HVG SMM_MODE
target_params_potency = BATCH_SIZE SMOOTH_BATCH_SIZE
target_params_cotan = MACROSTATE_SIZE COTAN_METHOD COTAN_ONLY_HVG MAX_ITER
target_params_cellrank = \
	MACROSTATE_SIZE CELLRANK_METHOD STATES INITIAL_STATES TERMINAL_STATES \
	CELLRANK_STABILITY CELLRANK_ALPHA
target_params_stream = \
	MACROSTATE_SIZE CLUSTERING_METHOD CLUSTER_NUMBER \
	ALPHA_EPG MU_EPG LAMBDA_EPG EXTEND_EPG EXTEND_MODE \
	EXTEND_PARAMETER PRUNE_EPG COLLAPSE_PARAMETER
target_params_knnsc = \
	MACROSTATE_SIZE KNNSC_EMBEDDING KNNSC_DIMENSION KNNSC_NEIGHBORS \
	KNNSC_MIN_CLUSTER_SIZE $(knnsc_condition_params)
target_params_macrostates = \
	MACROSTATE_METHOD MACROSTATE_SIZE $(macrostate_file_params)
target_params_bin-cells = \
	$(macrostate_file_params) \
	BIN_SCBOOLSEQ_ONLY_HVG BIN_HVG_METHOD BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	BIN_INCLUDE_NODES \
	SCBOOLSEQ_OPENBLAS_THREADS SCBOOLSEQ_OMP_THREADS \
	UNIMODAL_QUANTILE ZEROES_ARE_ZEROES SEED
target_params_bin-macrostates = \
	$(macrostate_file_params) \
	NANS_THRESHOLD BIMODAL_THRESHOLD ZEROINF_THRESHOLD UNIMODAL_THRESHOLD
target_params_bin-dea = \
	$(macrostate_file_params) \
	BIN_DEA_ONLY_HVG BIN_HVG_METHOD BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	BIN_INCLUDE_NODES \
	MEMORY BIN_LOGFC BIN_CORRECTION BIN_ALPHA
target_params_bin-consensus = \
	$(macrostate_file_params) \
	NANS_THRESHOLD BIMODAL_THRESHOLD ZEROINF_THRESHOLD UNIMODAL_THRESHOLD \
	BIN_DEA_ONLY_HVG BIN_HVG_METHOD BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	BIN_INCLUDE_NODES \
	MEMORY BIN_LOGFC BIN_CORRECTION BIN_ALPHA
target_params_binarization = \
	BIN_METHOD BINARIZATION_FILE $(macrostate_file_params) \
	BIN_HVG_METHOD BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS BIN_INCLUDE_NODES
target_params_spec = \
	SPEC_FILE $(prior_knowledge_params)
target_params_max-nodes-soft = \
	$(prior_knowledge_params) MAX_CLAUSES \
	CLAUSE_CONTINUATION_SOFT PATIENCE_CLAUSE_BOUND \
	DOMAIN_CONTINUATION_SOFT PATIENCE_DOMAIN_WAVE \
	$(domain_continuation_policy_params) \
	$(if $(filter true,$(DOMAIN_CONTINUATION_SOFT)),MEMORY JOBS) \
	CLINGO_CONFIG_SOFT CLINGO_MODE_SOFT CLINGO_STRATEGY_SOFT \
	CLINGO_THREADS TIMEOUT_SOFT
target_params_max-consts-soft = \
	$(prior_knowledge_params) MAX_CLAUSES MIN_SELF_LOOP_CONSTS \
	CLINGO_CONFIG_CONSTS CLINGO_MODE_CONSTS CLINGO_STRATEGY_CONSTS \
	CLINGO_THREADS TIMEOUT_CONSTS
target_params_max-nodes-relaxed = \
	$(prior_knowledge_params) MAX_CLAUSES BOUNDED_NONREACH \
	CLAUSE_CONTINUATION_RELAXED PATIENCE_CLAUSE_BOUND \
	DOMAIN_CONTINUATION_RELAXED PATIENCE_DOMAIN_WAVE \
	$(domain_continuation_policy_params) \
	$(if $(filter true,$(DOMAIN_CONTINUATION_RELAXED)),MEMORY JOBS) \
	CLINGO_CONFIG_RELAXED CLINGO_MODE_RELAXED CLINGO_STRATEGY_RELAXED \
	CLINGO_THREADS TIMEOUT_RELAXED
target_params_max-nodes-seed = \
	$(prior_knowledge_params) MAX_CLAUSES BOUNDED_NONREACH \
	CLAUSE_CONTINUATION_SEED PATIENCE_CLAUSE_BOUND \
	DOMAIN_CONTINUATION_SEED PATIENCE_DOMAIN_WAVE \
	$(domain_continuation_policy_params) \
	$(if $(filter true,$(DOMAIN_CONTINUATION_SEED)),MEMORY JOBS) \
	CLINGO_CONFIG_SEED CLINGO_MODE_SEED CLINGO_STRATEGY_SEED \
	CLINGO_THREADS TIMEOUT_SEED
target_params_max-nodes-lock = \
	$(prior_knowledge_params) MAX_CLAUSES BOUNDED_NONREACH \
	CLAUSE_CONTINUATION_LOCK PATIENCE_CLAUSE_BOUND \
	DOMAIN_CONTINUATION_LOCK PATIENCE_DOMAIN_WAVE_LOCK \
	$(domain_continuation_policy_params) \
	$(if $(filter true,$(DOMAIN_CONTINUATION_LOCK)),MEMORY JOBS) \
	CLINGO_CONFIG_LOCK CLINGO_MODE_LOCK CLINGO_STRATEGY_LOCK \
	CLINGO_THREADS TIMEOUT_LOCK
target_params_bn-min = \
	$(prior_knowledge_params) MAX_CLAUSES BOUNDED_NONREACH MIN_SELF_LOOP_INFER \
	CLINGO_MODE_MIN GRAPH_FORMATS
target_params_bn-submin = \
	$(prior_knowledge_params) MAX_CLAUSES BOUNDED_NONREACH \
	MEMORY JOBS INFER_LIMIT CONFIG_FORMATS GRAPH_FORMATS
target_params_bn-diverse = \
	$(prior_knowledge_params) MAX_CLAUSES BOUNDED_NONREACH \
	INFER_LIMIT CONFIG_FORMATS GRAPH_FORMATS

sensitive_params_load-fastq = $(foreach condition,$(conditions),$(call sra_var,$(condition)))
sensitive_params_alignment =
sensitive_params_load-matrix = $(foreach condition,$(conditions),$(call gsm_var,$(condition)))
sensitive_params_cellranger = genome_url
sensitive_params_star = genome_url STAR_CB_LEN STAR_UMI_LEN STAR_WHITELIST
sensitive_params_qc = STAR_BARCODE_FILTER STAR_MIN_UMI STAR_TOP_BARCODES
sensitive_params_velocyto = ALIGNMENT_TOOL genome_url repeat_msk_url STAR_BARCODE_FILTER STAR_MIN_UMI STAR_TOP_BARCODES
sensitive_params_filtering = \
	COUNT_FILES ORGANISM GENEINFO_VERSION \
	GENE_DROPOUT GENE_EXPRESSION GENE_COUNTS \
	CELL_DROPOUT CELL_EXPRESSION CELL_READS \
	MAD_DEVIATION CONSISTENT_MAD MT
sensitive_params_normalization = ORGANISM MEMORY CC_CORRECTION
sensitive_params_clustering = \
	INTEGRATION OMICS_HVG_METHOD OMICS_HVG_TOP OMICS_HVG_SPAN \
	OMICS_HVG_BINS DIM_PCA DIM_EMBEDDING CENTERED_PCA PCA_ONLY_HVG \
	NEIGHBORS METRIC RESOLUTION MIN_DIST SPREAD EMBEDDING_N_ITER SEED
sensitive_params_dea = MEMORY DEA_METHOD LOGFC CORRECTION ALPHA
sensitive_params_scoring = LABEL_COL
sensitive_params_goea = ORGANISM GENEINFO_VERSION
sensitive_params_annotation = LABEL LABEL_COL REPRESENTATION
sensitive_params_velocity = DIM_MOMENT VELOCITY_ONLY_HVG SMM_MODE REPRESENTATION LABEL_COL
sensitive_params_potency = BATCH_SIZE SMOOTH_BATCH_SIZE ORGANISM REPRESENTATION LABEL_COL SEED
sensitive_params_cotan = MACROSTATE_SIZE COTAN_METHOD COTAN_ONLY_HVG MAX_ITER REPRESENTATION LABEL_COL
sensitive_params_cellrank = \
	MACROSTATE_SIZE CELLRANK_METHOD STATES INITIAL_STATES TERMINAL_STATES \
	CELLRANK_STABILITY CELLRANK_ALPHA SEED LABEL_COL
sensitive_params_stream = \
	MACROSTATE_SIZE CLUSTERING_METHOD CLUSTER_NUMBER \
	ALPHA_EPG MU_EPG LAMBDA_EPG EXTEND_EPG EXTEND_MODE \
	EXTEND_PARAMETER PRUNE_EPG COLLAPSE_PARAMETER REPRESENTATION LABEL_COL
sensitive_params_knnsc = \
	MACROSTATE_SIZE KNNSC_EMBEDDING KNNSC_DIMENSION KNNSC_NEIGHBORS \
	KNNSC_MIN_CLUSTER_SIZE $(knnsc_condition_params) METRIC LABEL_COL REPRESENTATION
sensitive_params_macrostates =
sensitive_params_bin-cells = \
	MACROSTATE_FILES REPRESENTATION \
	BIN_SCBOOLSEQ_ONLY_HVG BIN_HVG_METHOD BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	BIN_INCLUDE_NODES \
	SCBOOLSEQ_OPENBLAS_THREADS SCBOOLSEQ_OMP_THREADS \
	UNIMODAL_QUANTILE ZEROES_ARE_ZEROES SEED
sensitive_params_bin-macrostates = \
	MACROSTATE_FILES REPRESENTATION \
	NANS_THRESHOLD BIMODAL_THRESHOLD ZEROINF_THRESHOLD UNIMODAL_THRESHOLD
sensitive_params_bin-dea = \
	MACROSTATE_FILES REPRESENTATION \
	BIN_DEA_ONLY_HVG BIN_HVG_METHOD BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	BIN_INCLUDE_NODES \
	MEMORY BIN_LOGFC BIN_CORRECTION BIN_ALPHA
sensitive_params_bin-consensus = \
	MACROSTATE_FILES REPRESENTATION \
	NANS_THRESHOLD BIMODAL_THRESHOLD ZEROINF_THRESHOLD UNIMODAL_THRESHOLD \
	BIN_DEA_ONLY_HVG BIN_HVG_METHOD BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	BIN_INCLUDE_NODES \
	MEMORY BIN_LOGFC BIN_CORRECTION BIN_ALPHA
sensitive_params_binarization =
sensitive_params_spec = \
	SPEC_FILE $(prior_knowledge_params)
sensitive_params_max-nodes-soft = \
	$(prior_knowledge_params) MAX_CLAUSES \
	CLAUSE_CONTINUATION_SOFT PATIENCE_CLAUSE_BOUND \
	DOMAIN_CONTINUATION_SOFT PATIENCE_DOMAIN_WAVE \
	$(if $(filter true,$(DOMAIN_CONTINUATION_SOFT)),\
		$(domain_continuation_policy_params) MEMORY JOBS) \
	CLINGO_CONFIG_SOFT CLINGO_MODE_SOFT CLINGO_STRATEGY_SOFT \
	CLINGO_THREADS TIMEOUT_SOFT SEED
sensitive_params_max-consts-soft = \
	$(prior_knowledge_params) MAX_CLAUSES MIN_SELF_LOOP_CONSTS \
	CLINGO_CONFIG_CONSTS CLINGO_MODE_CONSTS CLINGO_STRATEGY_CONSTS \
	CLINGO_THREADS TIMEOUT_CONSTS SEED
sensitive_params_max-nodes-relaxed = \
	$(prior_knowledge_params) MAX_CLAUSES BOUNDED_NONREACH \
	CLAUSE_CONTINUATION_RELAXED PATIENCE_CLAUSE_BOUND \
	DOMAIN_CONTINUATION_RELAXED PATIENCE_DOMAIN_WAVE \
	$(if $(filter true,$(DOMAIN_CONTINUATION_RELAXED)),\
		$(domain_continuation_policy_params) MEMORY JOBS) \
	CLINGO_CONFIG_RELAXED CLINGO_MODE_RELAXED CLINGO_STRATEGY_RELAXED \
	CLINGO_THREADS TIMEOUT_RELAXED SEED
sensitive_params_max-nodes-seed = \
	$(prior_knowledge_params) MAX_CLAUSES BOUNDED_NONREACH \
	CLAUSE_CONTINUATION_SEED PATIENCE_CLAUSE_BOUND \
	DOMAIN_CONTINUATION_SEED PATIENCE_DOMAIN_WAVE \
	$(if $(filter true,$(DOMAIN_CONTINUATION_SEED)),\
		$(domain_continuation_policy_params) MEMORY JOBS) \
	CLINGO_CONFIG_SEED CLINGO_MODE_SEED CLINGO_STRATEGY_SEED \
	CLINGO_THREADS TIMEOUT_SEED SEED
sensitive_params_max-nodes-lock = \
	$(prior_knowledge_params) MAX_CLAUSES BOUNDED_NONREACH \
	CLAUSE_CONTINUATION_LOCK PATIENCE_CLAUSE_BOUND \
	DOMAIN_CONTINUATION_LOCK PATIENCE_DOMAIN_WAVE_LOCK \
	$(if $(filter true,$(DOMAIN_CONTINUATION_LOCK)),\
		$(domain_continuation_policy_params) MEMORY JOBS) \
	CLINGO_CONFIG_LOCK CLINGO_MODE_LOCK CLINGO_STRATEGY_LOCK \
	CLINGO_THREADS TIMEOUT_LOCK SEED
sensitive_params_bn-min = \
	$(prior_knowledge_params) MAX_CLAUSES BOUNDED_NONREACH MIN_SELF_LOOP_INFER \
	CLINGO_MODE_MIN GRAPH_FORMATS SEED
sensitive_params_bn-submin = \
	$(prior_knowledge_params) MAX_CLAUSES BOUNDED_NONREACH \
	INFER_LIMIT CONFIG_FORMATS GRAPH_FORMATS SEED
sensitive_params_bn-diverse = \
	$(prior_knowledge_params) MAX_CLAUSES BOUNDED_NONREACH \
	INFER_LIMIT CONFIG_FORMATS GRAPH_FORMATS SEED

runtime_envs_load-fastq = scbolt-fastq
runtime_envs_load-matrix = scbolt-core
runtime_envs_star = scbolt-align
runtime_envs_qc = scbolt-core scbolt-velocyto
runtime_envs_velocyto = scbolt-velocyto scbolt-core
runtime_envs_filtering = scbolt-core
runtime_envs_normalization = scbolt-core
runtime_envs_clustering = scbolt-core
runtime_envs_dea = scbolt-core
runtime_envs_scoring = scbolt-core
runtime_envs_goea = scbolt-core
runtime_envs_annotation = scbolt-core
runtime_envs_velocity = scbolt-velocity
runtime_envs_potency = scbolt-potency
runtime_envs_cotan = scbolt-cotan scbolt-core
runtime_envs_cellrank = scbolt-cellrank scbolt-core
runtime_envs_stream = scbolt-stream
runtime_envs_knnsc = scbolt-core
runtime_envs_bin-cells = scbolt-scboolseq scbolt-core
runtime_envs_bin-macrostates = scbolt-core
runtime_envs_bin-dea = scbolt-core
runtime_envs_bin-consensus = scbolt-core
runtime_envs_spec = scbolt-bonesis
runtime_envs_max-nodes-soft = scbolt-bonesis
runtime_envs_max-consts-soft = scbolt-bonesis
runtime_envs_max-nodes-relaxed = scbolt-bonesis
runtime_envs_max-nodes-seed = scbolt-bonesis
runtime_envs_max-nodes-lock = scbolt-bonesis
runtime_envs_bn-min = scbolt-bonesis
runtime_envs_bn-submin = scbolt-bonesis
runtime_envs_bn-diverse = scbolt-bonesis

representation_check_pattern = $(representation_check_pattern_1)$(representation_check_pattern_2)$(representation_check_pattern_3)
representation_check_pattern_1 = scripts/(clust/annotation|utils/pipe_its|traj/potency
representation_check_pattern_2 = |mstates/stream_mstates|bin/(bin_cells_scboolseq
representation_check_pattern_3 = |bin_clust_scboolseq|bin_dea)).py

label_col_check_pattern = $(label_col_check_pattern_1)$(label_col_check_pattern_2)
label_col_check_pattern_1 = scripts/(clust/annotation|utils/pipe_its|traj/velocity
label_col_check_pattern_2 = |traj/potency|mstates/(stream|knnsc)_mstates).py

project_config_param_set = \
	ORGANISM CONDITIONS \
	$(foreach condition,$(conditions),$(call sra_var,$(condition))) \
	$(foreach condition,$(conditions),$(call gsm_var,$(condition))) \
	LABEL SPEC_FILE
core_config_param_set = \
	PARAMS REFERENCES PROJECT_DIR INFERENCE_DIR RESOURCES_DIR MEMORY JOBS SEED \
	BACKEND SCBOLT_IMAGE SCBOLT_CONTAINER_ENGINE SCBOLT_CONTAINER_ARGS \
	SCBOLT_CONTAINER_MOUNTS REPRESENTATION LABEL_COL OLD_FILES
method_config_param_set = \
	ALIGNMENT_TOOL STAR_CB_LEN STAR_UMI_LEN \
	STAR_BARCODE_FILTER STAR_MIN_UMI STAR_TOP_BARCODES \
	GENE_DROPOUT GENE_EXPRESSION GENE_COUNTS \
	CELL_DROPOUT CELL_EXPRESSION CELL_READS \
	MAD_DEVIATION CONSISTENT_MAD MT \
	CC_CORRECTION \
	INTEGRATION OMICS_HVG_METHOD OMICS_HVG_TOP OMICS_HVG_SPAN \
	OMICS_HVG_BINS DIM_PCA DIM_EMBEDDING CENTERED_PCA PCA_ONLY_HVG \
	NEIGHBORS METRIC RESOLUTION MIN_DIST SPREAD EMBEDDING_N_ITER \
	DEA_METHOD LOGFC CORRECTION ALPHA \
	DIM_MOMENT VELOCITY_ONLY_HVG SMM_MODE \
	BATCH_SIZE SMOOTH_BATCH_SIZE \
	MACROSTATE_SIZE MACROSTATE_METHOD \
	COTAN_METHOD COTAN_ONLY_HVG MAX_ITER \
	CELLRANK_METHOD STATES INITIAL_STATES TERMINAL_STATES \
	CELLRANK_STABILITY CELLRANK_ALPHA \
	CLUSTERING_METHOD CLUSTER_NUMBER ALPHA_EPG MU_EPG LAMBDA_EPG \
	EXTEND_EPG EXTEND_MODE EXTEND_PARAMETER PRUNE_EPG COLLAPSE_PARAMETER \
	KNNSC_EMBEDDING KNNSC_DIMENSION KNNSC_NEIGHBORS KNNSC_MIN_CLUSTER_SIZE \
	$(knnsc_condition_params) \
	BIN_SCBOOLSEQ_ONLY_HVG BIN_HVG_METHOD BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	BIN_INCLUDE_NODES \
	UNIMODAL_QUANTILE ZEROES_ARE_ZEROES \
	NANS_THRESHOLD BIMODAL_THRESHOLD ZEROINF_THRESHOLD UNIMODAL_THRESHOLD \
	BIN_DEA_ONLY_HVG BIN_HVG_METHOD BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS \
	BIN_LOGFC BIN_CORRECTION BIN_ALPHA \
	BIN_METHOD \
	MAX_CLAUSES BOUNDED_NONREACH \
	DOROTHEA_API DOROTHEA_COMPATIBILITY DOROTHEA_LEVELS \
	$(clause_continuation_params) \
	$(clause_bound_patience_params) \
	$(domain_continuation_params) \
	$(domain_wave_patience_params) \
	$(domain_continuation_policy_params) \
	CLINGO_THREADS \
	CLINGO_MODE_SOFT CLINGO_STRATEGY_SOFT TIMEOUT_SOFT \
	CLINGO_MODE_CONSTS CLINGO_STRATEGY_CONSTS TIMEOUT_CONSTS \
	CLINGO_MODE_RELAXED CLINGO_STRATEGY_RELAXED TIMEOUT_RELAXED \
	CLINGO_MODE_SEED CLINGO_STRATEGY_SEED TIMEOUT_SEED \
	CLINGO_MODE_LOCK CLINGO_STRATEGY_LOCK TIMEOUT_LOCK \
	CLINGO_MODE_MIN CONFIG_FORMATS GRAPH_FORMATS MIN_SELF_LOOP_CONSTS \
	MIN_SELF_LOOP_INFER INFER_LIMIT
external_resource_config_param_set = \
	STAR_WHITELIST COUNT_FILES $(count_file_params) BINARIZATION_FILE \
	MACROSTATE_FILES $(macrostate_file_params) PRIOR_KNOWLEDGE \
	GENEINFO_VERSION OMNIPATH_VERSION HCOP_VERSION \
	CLINGO_CONFIG_SOFT CLINGO_CONFIG_CONSTS CLINGO_CONFIG_RELAXED \
	CLINGO_CONFIG_SEED CLINGO_CONFIG_LOCK
config_all_modules = \
	load-genome load-fastq load-matrix load-signatures load-cc load-go \
	alignment cellranger star qc velocyto \
	filtering normalization clustering dea scoring goea annotation \
	velocity potency cotan cellrank stream knnsc macrostates \
	bin-cells bin-macrostates bin-dea bin-consensus binarization \
	spec max-nodes-soft max-consts-soft max-nodes-relaxed \
	max-nodes-seed max-nodes-lock bn-min bn-submin bn-diverse
config_workflow_modules = \
	load-fastq load-matrix alignment cellranger star qc velocyto \
	filtering normalization clustering dea annotation velocity potency \
	macrostates cotan cellrank stream knnsc bin-cells bin-macrostates \
	bin-dea bin-consensus binarization spec max-nodes-soft max-consts-soft \
	max-nodes-relaxed max-nodes-seed max-nodes-lock bn-min bn-submin bn-diverse
config_default_modules = $(if $(strip $(input_routes)),$(config_workflow_modules),$(config_all_modules))
config_base_params = \
	ORGANISM CONDITIONS \
	$(foreach condition,$(conditions),$(call sra_var,$(condition))) \
	$(foreach condition,$(conditions),$(call gsm_var,$(condition))) \
	PARAMS REFERENCES PROJECT_DIR INFERENCE_DIR RESOURCES_DIR MEMORY JOBS SEED \
	BACKEND SCBOLT_IMAGE SCBOLT_CONTAINER_ENGINE SCBOLT_CONTAINER_ARGS \
	SCBOLT_CONTAINER_MOUNTS REPRESENTATION LABEL_COL OLD_FILES
config_params_from_modules = $(strip $(foreach module,$(1),$(target_params_$(module))))
config_project_params = $(call uniq,$(filter $(project_config_param_set),$(1)))
config_core_params = $(call uniq,$(filter $(core_config_param_set),$(1)))
config_method_params = $(call uniq,$(filter $(method_config_param_set),$(1)))
config_external_resource_params = $(call uniq,$(filter $(external_resource_config_param_set),$(1)))
target_dry_run_modules = $(shell $(nested_make) --always-make --dry-run LOGGING=false \
	__check_mode=true __$(1) PARAMS="$(PARAMS)" LOGFILE="$(LOGFILE)" 2>/dev/null \
	| $(call system_tool,sed) -n '/"RULE"/{s/.*"RULE" "//;s/ .*//;s/"//g;p;}' \
	| $(call system_tool,awk) '$$0 != "bin-hvg" && !seen[$$0]++')
target_run_modules = $(shell $(nested_make) --dry-run LOGGING=false \
	__check_mode=true __$(1) PARAMS="$(PARAMS)" LOGFILE="$(LOGFILE)" 2>/dev/null \
	| $(call system_tool,sed) -n '/"RULE"/{s/.*"RULE" "//;s/ .*//;s/"//g;p;}' \
	| $(call system_tool,awk) '$$0 != "bin-hvg" && !seen[$$0]++')

## END PARAMETERS ##
