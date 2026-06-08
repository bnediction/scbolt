__check_externals__ ?= true
HELP ?= false

launch_dir := $(CURDIR)
lib_dir := $(scbolt_root)/lib
scripts_dir := $(scbolt_root)/scripts
fig_dir := $(scbolt_root)/fig
public_dir := $(scbolt_root)/public

strip_trailing_slash = $(if $(filter /,$(strip $(1))),/,$(patsubst %/,%,$(strip $(1))))
is_absolute_path = $(filter /%,$(strip $(1)))
resolve_path_from = $(call strip_trailing_slash,\
	$(if $(call is_absolute_path,$(1)),$(1),$(abspath $(strip $(2))/$(strip $(1)))))
resolve_optional_path_from = $(if $(strip $(1)),$(call resolve_path_from,$(1),$(2)))

include $(scbolt_root)/default_params.mk

params_base := $(if $(filter command line,$(origin PARAMS)),$(launch_dir),$(scbolt_root))
override PARAMS := $(call resolve_path_from,$(PARAMS),$(params_base))
params_dir := $(call strip_trailing_slash,$(dir $(PARAMS)))

include $(PARAMS)

path_origin_base = $(if $(filter command line,$(origin $(1))),$(launch_dir),$(params_dir))
resolve_user_path_var = $(eval override $(1) := \
	$(call resolve_optional_path_from,$($(1)),$(call path_origin_base,$(1))))
clingo_named_configs := auto frumpy jumpy tweety handy crafty trendy many
clingo_config_vars := \
	CLINGO_CONFIG_SOFT CLINGO_CONFIG_CONSTS CLINGO_CONFIG_RELAXED \
	CLINGO_CONFIG_SEED CLINGO_CONFIG_LOCK
resolve_clingo_config = $(if $(strip $($(1))),\
	$(if $(filter $(strip $($(1))),$(clingo_named_configs)),,$(call resolve_user_path_var,$(1))))

$(call resolve_user_path_var,RESULTS)
$(call resolve_user_path_var,SPEC_FILE)
$(call resolve_user_path_var,BINARIZATION_FILE)
$(call resolve_user_path_var,MACROSTATE_FILE)
$(if $(filter $(strip $(PRIOR_KNOWLEDGE)),collectri dorothea),,$(call resolve_user_path_var,PRIOR_KNOWLEDGE))
$(call resolve_user_path_var,STAR_WHITELIST)
$(foreach var,$(clingo_config_vars),$(call resolve_clingo_config,$(var)))

_lower2upper = a:A b:B c:C d:D e:E f:F g:G h:H i:I j:J k:K l:L m:M n:N o:O p:P q:Q r:R s:S t:T u:U v:V w:W x:X y:Y z:Z
_lower = $(word 1, $(subst :, ,$(word 1,$(1))))
_upper = $(word 2, $(subst :, ,$(word 1,$(1))))
translate_case = $(eval _=$1)$(strip $(foreach pair,$(_lower2upper),\
	$(eval _=$(subst $(call $(2),$(pair)),$(call $(3),$(pair)),$_))))$_
toupper = $(call translate_case,$1,_lower,_upper)
tolower = $(call translate_case,$1,_upper,_lower)

comma := ,
empty :=
space := $(empty) $(empty)

ifndef CONDITIONS
$(error parameter CONDITIONS not defined)
endif

diagnostic_mode := $(filter check show-config progress module-help,$(MAKECMDGOALS))$(__check_mode)\
	$(if $(filter true,$(HELP)),help)

is_positive_integer = $(shell printf '%s\n' "$(strip $(1))" \
	| grep -Eq '^[1-9][0-9]*$$' && echo true || echo false)
is_creatable_path = $(shell { test -n "$(strip $(1))" && mkdir -p "$(strip $(1))"; } \
	>/dev/null 2>&1 && echo true || echo false)

conditions := $(call tolower, $(CONDITIONS))
references_default := $(conditions) $(if $(filter-out 1,$(words $(conditions))),integrated)
REFERENCES ?= $(references_default)
running_references := $(strip $(REFERENCES))
running_conditions := $(filter-out integrated,$(running_references))
invalid_references = $(strip $(filter-out $(conditions) integrated,$(running_references)))

results := $(patsubst %/,%,$(RESULTS))

log_target := $(patsubst __%,%,$(or $(firstword $(MAKECMDGOALS)),default))
LOGFILE := $(results)/logs/$(shell date '+%Y%m%d_%H%M%S')_$(log_target).log
log_dir := $(patsubst %/,%,$(dir $(LOGFILE)))
export tmpdir := $(shell mktemp -d -t scbolt-XXXXXXXXXX)
$(shell { trap 'rm -rf $(tmpdir);' EXIT; tail --pid=$$PPID -f /dev/null; } </dev/null >/dev/null 2>/dev/null &)

## BEGIN URLS ##

cycle_url := https://github.com/MarioniLab/scran/raw/master/inst/exdata/mouse_cycle_markers.rds
go_basic_url := http://purl.obolibrary.org/obo/go/go-basic.obo
geiger_url := https://doi.org/10.1371/journal.pbio.2003389.s025
chambers_url := https://ars.els-cdn.com/content/image/1-s2.0-S1934590907002202-mmc3.xls
gene2go_url := ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/gene2go.gz

## END URLS ##

## BEGIN TERMINAL OUTPUT ##

interactive_output := $(if $(MAKE_TERMOUT),true,false)

ifeq ($(interactive_output),true)
nc        = \033[0m
green     = \033[0;32m
red       = \033[0;31m
yellow    = \033[0;33m
bold      = \033[1m
success_label = $(green)✓ SUCCESS$(nc)
warning_label = $(yellow)⚠ WARNING$(nc)
failure_label = $(red)✗ FAIL$(nc)
else
nc        =
green     =
red       =
yellow    =
bold      =
success_label = SUCCESS
warning_label = WARNING
failure_label = FAIL
endif

## END TERMINAL OUTPUT ##

## BEGIN FUNCTIONS ##

log = printf '%s - %s - %s\n' "`date '+%Y-%m-%d %H:%M:%S.%3N'`" "$(1)" "$(2)"

print_rule    = $(call log,RULE,$(1)$(if $(2), (reference: $(2))))
print_task    = $(call log,TASK,$(1))
print_info    = $(call log,INFO,$(1))
print_warning = $(call log,WARNING,$(1))
print_debug   = $(call log,DEBUG,$(1))
print_result  = $(call log,RESULT,$(1))
print_error   = $(call log,ERROR,$(1)); exit 1

define finalize_velocyto_h5ad
$(call conda_run,scbolt-core) python -c '\
import sys; \
import anndata as ad; \
adata = ad.read_h5ad(sys.argv[1]); \
adata.layers["counts"] = adata.X.copy(); \
adata.write_h5ad(filename=sys.argv[2], compression="gzip"); \
spliced = float(adata.layers["spliced"].sum()); \
unspliced = float(adata.layers["unspliced"].sum()); \
ambiguous = float(adata.layers["ambiguous"].sum()); \
counts = float(adata.layers["counts"].sum()); \
print(f"reads: spliced={spliced:.0f}, unspliced={unspliced:.0f}, ambiguous={ambiguous:.0f}"); \
print(f"reads: spliced+unspliced+ambiguous={spliced + unspliced + ambiguous:.0f}, counts={counts:.0f}")' \
$(1) $(2) | while IFS= read -r line; do $(call print_result,$$$$line); done
endef

define check_file
[ -n "$(1)" ] || { $(call print_error,required file parameter not defined: $(2)); }; \
[ -f "$(1)" ] || { $(call print_error,required file not found: $(1)); }
endef

check_command = command -v $(1) >/dev/null 2>&1 || { $(call print_error,required command not found: $(1)); }
check_conda_env = conda env list | awk '{print $$1}' | grep -qx "$(1)" \
	|| { $(call print_error,required conda environment not found: $(1)); }
check_parameter = [ -n "$(strip $(1))" ] || { $(call print_error,required parameter not defined: $(2)); }

define require_parameter
[ -n "$(strip $($(1)))" ] || { \
	$(call print_error,required parameter not defined: $(1)$(if $(2), \(needed by target '$(2)'\))); \
}
endef

define require_choice
case "$(strip $($(1)))" in \
	$(subst $(space),|,$(strip $(2)))) ;; \
	"") $(call print_error,required parameter not defined: $(1)$(if $(3), \(needed by target '$(3)'\)));; \
	*) $(call print_error,unsupported value for parameter $(1) \
		(supported values: $(subst $(space),$(comma) ,$(strip $(2)))));; \
esac
endef

require_bool = $(call require_choice,$(1),true false,$(2))

define require_positive_integer
case "$(strip $($(1)))" in \
	''|*[!0-9]*|0) $(call print_error,required positive integer for parameter $(1) \(current: $(strip $($(1)))\));; \
esac
endef

define require_optional_positive_integer
if [ -n "$(strip $($(1)))" ]; then \
	$(call require_positive_integer,$(1)); \
fi
endef

define require_float
if ! printf '%s\n' "$(strip $($(1)))" \
		| grep -Eq '^[-+]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][-+]?[0-9]+)?$$$$'; then \
	$(call print_error,required numeric value for parameter $(1) \(current: $(strip $($(1)))\)); \
fi
endef

define require_optional_hvg_method
case "$(strip $($(1)))" in \
	""|seurat|cell_ranger|seurat_v3) ;; \
	*) $(call print_error,unsupported value for parameter $(1) (supported values: seurat, cell_ranger, seurat_v3));; \
esac; \
if [ "$(strip $($(1)))" = "seurat_v3" ] && [ -z "$(strip $($(2)))" ]; then \
	$(call print_error,parameter $(2) is required when parameter $(1) is equal to seurat_v3); \
fi
endef

define require_hvg_method
$(call require_choice,$(1),seurat cell_ranger seurat_v3,$(3)); \
if [ "$(strip $($(1)))" = "seurat_v3" ] && [ -z "$(strip $($(2)))" ]; then \
	$(call print_error,parameter $(2) is required when parameter $(1) is equal to seurat_v3); \
fi
endef

define require_prior_knowledge
$(call require_parameter,PRIOR_KNOWLEDGE,$(1)); \
[ -n "$(strip $(prior_knowledge))" ] || { \
	$(call print_error,unsupported value for parameter PRIOR_KNOWLEDGE \
		(supported values: $(subst $(space),$(comma) ,$(strip $(known_prior_knowledge))) \
		or an existing file path)); \
}
endef

define require_dorothea_api
if [ "$(strip $(PRIOR_KNOWLEDGE))" = "dorothea" ]; then \
	$(call require_choice,DOROTHEA_API,$(dorothea_apis),$(1)); \
fi
endef

define require_dorothea_levels
for level in $(DOROTHEA_LEVELS); do \
	case "$${level}" in \
		$(subst $(space),|,$(dorothea_levels))) ;; \
		*) $(call print_error,unsupported value for parameter DOROTHEA_LEVELS \
			(supported values: $(subst $(space),$(comma) ,$(dorothea_levels))));; \
	esac; \
done
endef

define require_cc_correction
$(call require_bool,CC_CORRECTION,$(1)); \
if [ "$(CC_CORRECTION)" = "true" ] && [ "$(ORGANISM)" != "mouse" ]; then \
	$(call print_error,CC_CORRECTION=true is only supported for mouse \(current: $(ORGANISM)\)); \
fi
endef

define require_filtering_parameters
$(call require_bool,NORM_MAD,filtering)
endef

define require_clustering_parameters
$(call require_choice,USE_REP,X_umap X_tsne,clustering); \
$(call require_choice,ANALYSIS_HVG_FLAVOR,seurat cell_ranger seurat_v3,clustering); \
$(call require_optional_positive_integer,ANALYSIS_HVG_TOP); \
$(call require_float,ANALYSIS_HVG_SPAN); \
$(call require_positive_integer,ANALYSIS_HVG_BINS); \
$(call require_positive_integer,DIM_PCA); \
$(call require_positive_integer,DIM_CLUSTERING); \
$(call require_positive_integer,DIM_EMBEDDING); \
$(call require_bool,PCA_ONLY_HVG,clustering); \
$(call require_positive_integer,NEIGHBORS); \
$(call require_float,RESOLUTION); \
$(call require_float,MIN_DIST); \
$(call require_float,SPREAD)
endef

define require_velocity_parameters
$(call require_positive_integer,DIM_MOMENT); \
$(call require_bool,VELOCITY_ONLY_HVG,velocity)
endef

define require_cellrank_parameters
$(call require_positive_integer,INITIAL_STATES); \
$(call require_positive_integer,TERMINAL_STATES); \
$(call require_float,CELLRANK_STABILITY); \
$(call require_float,CELLRANK_ALPHA)
endef

define require_dea_parameters
$(call require_float,LOGFC)
endef

define require_stream_parameters
$(call require_positive_integer,CLUSTER_NUMBER); \
$(call require_float,ALPHA_EPG); \
$(call require_float,MU_EPG); \
$(call require_float,LAMBDA_EPG); \
$(call require_bool,EXTEND_EPG,stream); \
$(call require_float,EXTEND_PARAMETER); \
$(call require_bool,PRUNE_EPG,stream); \
$(call require_bool,COLLAPSE_PARAMETER,stream)
endef

define require_knnbs_parameters
$(call require_parameter,KNNBS_EMBEDDING,knnbs); \
$(call require_positive_integer,KNNBS_NEIGHBORS)
endef

define require_star_barcode_filter_parameters
$(call require_choice,STAR_BARCODE_FILTER,auto threshold top,$(1)); \
$(call require_optional_positive_integer,STAR_MIN_UMI); \
$(call require_optional_positive_integer,STAR_TOP_BARCODES); \
if [ "$(STAR_BARCODE_FILTER)" = "threshold" ] && [ -z "$(strip $(STAR_MIN_UMI))" ]; then \
	$(call print_error,required parameter not defined: STAR_MIN_UMI \(needed by target '$(1)'\)); \
fi; \
if [ "$(STAR_BARCODE_FILTER)" = "top" ] && [ -z "$(strip $(STAR_TOP_BARCODES))" ]; then \
	$(call print_error,required parameter not defined: STAR_TOP_BARCODES \(needed by target '$(1)'\)); \
fi; \
if [ "$(STAR_BARCODE_FILTER)" = "auto" ] && [ -n "$(strip $(STAR_MIN_UMI)$(STAR_TOP_BARCODES))" ]; then \
	$(call print_error,STAR_MIN_UMI and STAR_TOP_BARCODES require STAR_BARCODE_FILTER=threshold or top); \
fi
endef

define require_bin_cells_parameters
$(call require_bool,BIN_SCBOOLSEQ_ONLY_HVG,bin-cells); \
$(call require_float,UNIMODAL_QUANTILE); \
$(call require_bool,ZEROES_ARE_ZEROES,bin-cells)
endef

define require_bin_hvg_parameters
$(call require_hvg_method,BIN_HVG_FLAVOR,BIN_HVG_TOP,$(1)); \
$(call require_float,BIN_HVG_SPAN); \
$(call require_positive_integer,BIN_HVG_BINS)
endef

define require_bin_mstates_parameters
$(call require_float,NANS_THRESHOLD); \
$(call require_float,BIMODAL_THRESHOLD); \
$(call require_float,ZEROINF_THRESHOLD); \
$(call require_float,UNIMODAL_THRESHOLD)
endef

define require_bin_dea_parameters
$(call require_bool,BIN_DEA_ONLY_HVG,bin-dea); \
$(call require_float,BIN_LOGFC); \
$(call require_float,BIN_ALPHA)
endef

require_binarization_parameters = $(call require_choice,BIN_METHOD,scboolseq dea consensus,binarization)

define require_prior_parameters
$(call require_prior_knowledge,$(1)); \
$(call require_dorothea_api,$(1)); \
$(call require_dorothea_levels)
endef

define require_bonesis_filter_parameters
$(call require_prior_parameters,$(1)); \
$(call require_bool,CANONIC_FILTER,$(1))
endef

define require_bonesis_infer_parameters
$(call require_prior_parameters,$(1)); \
$(call require_bool,CANONIC_INFER,$(1))
endef

ifneq ($(__dry_run_output),)
require_parameter =
require_choice =
require_bool =
require_positive_integer =
require_optional_positive_integer =
require_float =
require_optional_hvg_method =
require_hvg_method =
require_prior_knowledge =
require_dorothea_api =
require_dorothea_levels =
require_cc_correction =
require_filtering_parameters =
require_clustering_parameters =
require_velocity_parameters =
require_cellrank_parameters =
require_dea_parameters =
require_stream_parameters =
require_knnbs_parameters =
require_star_barcode_filter_parameters =
require_bin_cells_parameters =
require_bin_hvg_parameters =
require_bin_mstates_parameters =
require_bin_dea_parameters =
require_binarization_parameters =
require_prior_parameters =
require_bonesis_filter_parameters =
require_bonesis_infer_parameters =
endif

check_success = check_success "$(1)"
check_failure = check_failure "$(1)"
report_check_error = missing=1; $(call check_failure,$(1))
print_check_reports = cat "$${project_checks}" "$${core_checks}" "$${method_checks}" \
	"$${external_resource_checks}" "$${file_checks}" "$${conda_checks}" \
	"$${command_checks}" "$${other_checks}"
parameter_label = $(strip $(if $(3),$(3) )parameter)
parameter_name = $(firstword $(strip $(1)))
parameter_context = $(strip $(patsubst $(call parameter_name,$(1))%,%,$(strip $(1))))
parameter_description = $(strip $(call parameter_label,$(1),$(2),$(3)) \
	$(call parameter_name,$(2)) $(call parameter_context,$(2)))
parameter_assignment = $(strip $(call parameter_name,$(2))=$(strip $(1)) \
	$(strip $(patsubst $(call parameter_name,$(2))%,%,$(strip $(2)))))
needed_by = $(1) (needed by target '$(2)')

define check_file_diagnostic
if [ -z "$(1)" ]; then \
	$(call report_check_error,required file parameter not defined: $(2)); \
elif [ ! -f "$(1)" ]; then \
	$(call report_check_error,required file not found: $(1)); \
elif [ -n "$(strip $(3))" ]; then \
	$(call check_success,$(call parameter_label,$(1),$(2),$(3)) valid: $(call parameter_assignment,$(1),$(2))); \
else \
	$(call check_success,file found: $(2) ($(1))); \
fi
endef

define check_command_diagnostic
if command -v $(1) >/dev/null 2>&1; then \
	$(call check_success,command found: $(1)); \
else \
	$(call report_check_error,required command not found: $(1)); \
fi
endef

define check_parameter_diagnostic
if [ -n "$(strip $(1))" ]; then \
	$(if $(strip $(3)),\
		$(call check_success,$(call parameter_label,$(1),$(2),$(3)) valid: $(call parameter_assignment,$(1),$(2))),\
		$(call check_success,parameter defined: $(strip $(2)))); \
else \
	$(call report_check_error,required $(call parameter_label,$(1),$(2),$(3)) not defined: $(strip $(2))); \
fi
endef

define check_knnbs_seed_diagnostic
if [ -n "$(strip $(1))" ] || [ -n "$(strip $(2))" ]; then \
	if [ -n "$(strip $(1))" ]; then \
		$(call check_success,method parameter valid: \
			KNNBS_CENTRALITY_$(call toupper,$(3))=$(strip $(1)) (needed by target 'knnbs')); \
	fi; \
	if [ -n "$(strip $(2))" ]; then \
		$(call check_success,method parameter valid: \
			KNNBS_PERIPHERY_$(call toupper,$(3))=$(strip $(2)) (needed by target 'knnbs')); \
	fi; \
else \
	$(call report_check_error,required method parameter not defined: \
		KNNBS_CENTRALITY_$(call toupper,$(3)) or \
		KNNBS_PERIPHERY_$(call toupper,$(3)) (needed by target 'knnbs')); \
fi
endef

define check_positive_integer_diagnostic
case "$(strip $(1))" in \
	''|*[!0-9]*|0) $(call report_check_error,required positive integer for \
		$(call parameter_description,$(1),$(2),$(3)) (current: $(strip $(1))));; \
	*) $(call check_success,$(call parameter_label,$(1),$(2),$(3)) valid: \
		$(call parameter_assignment,$(1),$(2)));; \
esac
endef

define check_optional_positive_integer_diagnostic
if [ -n "$(strip $(1))" ]; then \
	$(call check_positive_integer_diagnostic,$(1),$(2),$(3)); \
fi
endef

define check_float_diagnostic
if printf '%s\n' "$(strip $(1))" \
		| grep -Eq '^[-+]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][-+]?[0-9]+)?$$$$'; then \
	$(call check_success,$(call parameter_label,$(1),$(2),$(3)) valid: \
		$(call parameter_assignment,$(1),$(2))); \
else \
	$(call report_check_error,required numeric value for \
		$(call parameter_description,$(1),$(2),$(3)) (current: $(strip $(1)))); \
fi
endef

define check_path_diagnostic
if [ -z "$(strip $(1))" ]; then \
	$(call report_check_error,required path $(call parameter_label,$(1),$(2),$(3)) not defined: $(2)); \
elif mkdir -p "$(strip $(1))" >/dev/null 2>&1; then \
	$(call check_success,$(call parameter_label,$(1),$(2),$(3)) valid: $(2)=$(strip $(1))); \
else \
	$(call report_check_error,invalid path for $(call parameter_label,$(1),$(2),$(3)) $(2): $(strip $(1))); \
fi
endef

define check_references_diagnostic
if [ -z "$(strip $(REFERENCES))" ]; then \
	$(call report_check_error,required core parameter not defined: REFERENCES); \
else \
	references_ok=1; \
	if [ -n "$(invalid_references)" ]; then \
		$(call report_check_error,unsupported value for core parameter REFERENCES: $(invalid_references) \
			(supported values: $(subst $(space),$(comma) ,$(conditions) integrated))); \
		references_ok=0; \
	fi; \
	if [ "$(words $(conditions))" -eq 1 ] && [ -n "$(filter integrated,$(running_references))" ]; then \
		$(call report_check_error,unsupported value for core parameter REFERENCES: integrated is not supported \
			for mono-condition projects); \
		references_ok=0; \
	fi; \
	if [ "$${references_ok}" -eq 1 ]; then \
		$(call check_success,core parameter valid: REFERENCES=$(REFERENCES)); \
	fi; \
fi
endef

define check_choice_diagnostic
case "$(strip $(1))" in \
	$(subst $(space),|,$(strip $(2)))) \
		$(call check_success,$(call parameter_label,$(1),$(3),$(4)) valid: \
			$(call parameter_assignment,$(1),$(3)));; \
	"") $(call report_check_error,required $(call parameter_label,$(1),$(3),$(4)) not defined: \
		$(call parameter_name,$(3)) $(call parameter_context,$(3)));; \
	*) $(call report_check_error,unsupported value for \
		$(call parameter_description,$(1),$(3),$(4)) \
		(supported values: $(subst $(space),$(comma) ,$(strip $(2)))));; \
esac
endef

check_bool_diagnostic = $(call check_choice_diagnostic,$(1),true false,$(2),$(3))

define check_optional_hvg_method_diagnostic
case "$(strip $(1))" in \
	""|seurat|cell_ranger|seurat_v3) \
		$(call check_success,$(call parameter_label,$(1),$(3),$(5)) valid: \
			$(call parameter_assignment,$(1),$(3)));; \
	*) $(call report_check_error,unsupported value for \
		$(call parameter_label,$(1),$(3),$(5)) $(call parameter_name,$(3)) \
		(supported values: seurat, cell_ranger, seurat_v3));; \
esac; \
if [ "$(strip $(1))" = "seurat_v3" ] && [ -z "$(strip $(2))" ]; then \
	$(call report_check_error,$(call parameter_label,$(1),$(4),$(5)) $(call parameter_name,$(4)) \
		is required when $(call parameter_label,$(1),$(3),$(5)) $(call parameter_name,$(3)) \
		is equal to seurat_v3); \
fi
endef

define check_hvg_method_diagnostic
case "$(strip $(1))" in \
	seurat|cell_ranger|seurat_v3) \
		$(call check_success,$(call parameter_label,$(1),$(3),$(5)) valid: \
			$(call parameter_assignment,$(1),$(3)));; \
	"") $(call report_check_error,required $(call parameter_label,$(1),$(3),$(5)) \
		not defined: $(call parameter_name,$(3)));; \
	*) $(call report_check_error,unsupported value for \
		$(call parameter_label,$(1),$(3),$(5)) $(call parameter_name,$(3)) \
		(supported values: seurat, cell_ranger, seurat_v3));; \
esac; \
if [ "$(strip $(1))" = "seurat_v3" ] && [ -z "$(strip $(2))" ]; then \
	$(call report_check_error,$(call parameter_label,$(1),$(4),$(5)) $(call parameter_name,$(4)) \
		is required when $(call parameter_label,$(1),$(3),$(5)) $(call parameter_name,$(3)) \
		is equal to seurat_v3); \
fi
endef

knnbs_centrality = $(KNNBS_CENTRALITY_$(call toupper,$(1)))
knnbs_periphery = $(KNNBS_PERIPHERY_$(call toupper,$(1)))
log_parameters = $(foreach var,$(strip $(1)),printf '%s=%s\n' '$(var)' "$($(var))"; )

PYTHONUNBUFFERED ?= 1
TQDM_DISABLE ?= 0
TQDM_TO_TTY ?= 0

conda_runtime_env = env \
	PYTHONPATH="$(lib_dir)$(if $(PYTHONPATH),:$(PYTHONPATH))" \
	PYTHONUNBUFFERED="$(PYTHONUNBUFFERED)"
conda_run = $(conda_runtime_env) conda run --no-capture-output -n $(1)
conda_run_cellrank = $(conda_runtime_env) \
	OMPI_MCA_btl="^smcuda" \
	conda run --no-capture-output -n $(1)
conda_run_inference = $(conda_runtime_env) \
	TQDM_DISABLE="$(TQDM_DISABLE)" \
	TQDM_TO_TTY="$(TQDM_TO_TTY)" \
	PYTHONHASHSEED="$(SEED)" \
	conda run --no-capture-output -n $(1)
BONESIS_HASH ?= 24c4f9c91a4496b9777043e17e504ecc31312d87
SCVELO_HASH ?= b2f31b345641efdccd39fbcb8c0beaa0014b4b88
nested_make = env \
	$(if $(PYTHONPATH),PYTHONPATH="$(PYTHONPATH)") \
	PYTHONUNBUFFERED="$(PYTHONUNBUFFERED)" \
	TQDM_DISABLE="$(TQDM_DISABLE)" \
	TQDM_TO_TTY="$(TQDM_TO_TTY)" \
	$(MAKE) -f "$(makefile_path)" $(trust_make_options)
inference_timeout = $(if $(filter-out 0,$(strip $(1))),timeout --foreground $(strip $(1)),)

ifndef LOGGING
run_logged = $(nested_make) LOGGING=false __$(1) LOGFILE="$(LOGFILE)"
else ifeq ($(LOGGING),true)
run_logged = \
	mkdir -p $(log_dir); \
	{ \
		printf '%s\n' '[RUN]'; \
		printf 'DATE=%s\n' "`date '+%Y-%m-%d %H:%M:%S'`"; \
		printf 'TARGET=%s\n' "$(1)"; \
		printf 'RESULTS=%s\n' "$(RESULTS)"; \
		printf 'PARAMS=%s\n' "$(PARAMS)"; \
		printf 'LOGFILE=%s\n' "$(LOGFILE)"; \
		printf 'GIT_HASH=%s\n' "`git rev-parse HEAD 2>/dev/null || echo unknown`"; \
		printf '\n'; \
		printf '%s\n' '[CONTEXT]'; \
		printf 'SEED=%s\n' "$(SEED)"; \
		printf 'JOBS=%s\n' "$(JOBS)"; \
		printf 'CONDITIONS=%s\n' "$(CONDITIONS)"; \
		printf 'REFERENCES=%s\n' "$(REFERENCES)"; \
		printf '\n'; \
		$(if $(strip $(target_params_$(1))),\
			printf '%s\n' '[CONFIGURATION]'; \
			$(call log_parameters,$(strip $(target_params_$(1)))) \
			printf '\n';) \
		printf '%s\n' '[OUTPUT]'; \
	} >> "$(LOGFILE)"; \
	env \
		$(if $(PYTHONPATH),PYTHONPATH="$(PYTHONPATH)") \
		PYTHONUNBUFFERED="$(PYTHONUNBUFFERED)" \
		TQDM_DISABLE="$(TQDM_DISABLE)" \
		TQDM_TO_TTY="1" \
		$(MAKE) -f "$(makefile_path)" LOGGING=false __$(1) LOGFILE="$(LOGFILE)" 2>&1 \
		| tee -a "$(LOGFILE)"
else ifeq ($(LOGGING),false)
run_logged = $(nested_make) LOGGING=false __$(1) LOGFILE="$(LOGFILE)"
else
run_logged = $(nested_make) LOGGING=false __$(1) LOGFILE="$(LOGFILE)"
endif

define fastq_naming
	n_fastq="$$(find $(1) -name "$(2)_[1-4].fastq.gz" -printf '.' | wc -m)"
	if [ $${n_fastq} -eq 0 ]; then \
		$(call print_error,fastq downloading failed);\
	
	elif [ $${n_fastq} -eq 1 ]; then \
		mv $(1)/$(2)_1.fastq.gz $(1)/$(3)_S1_L00$(4)_R1_001.fastq.gz;\
	
	elif [ $${n_fastq} -eq 2 ]; then \
		mv $(1)/$(2)_1.fastq.gz $(1)/$(3)_S1_L00$(4)_R1_001.fastq.gz
		mv $(1)/$(2)_2.fastq.gz $(1)/$(3)_S1_L00$(4)_R2_001.fastq.gz;\
	
	elif [ $${n_fastq} -eq 3 ]; then \
		mv $(1)/$(2)_1.fastq.gz $(1)/$(3)_S1_L00$(4)_I1_001.fastq.gz
		mv $(1)/$(2)_2.fastq.gz $(1)/$(3)_S1_L00$(4)_R1_001.fastq.gz
		mv $(1)/$(2)_3.fastq.gz $(1)/$(3)_S1_L00$(4)_R2_001.fastq.gz;\

	elif [ $${n_fastq} -eq 4 ]; then \
		mv $(1)/$(2)_1.fastq.gz $(1)/$(3)_S1_L00$(4)_I1_001.fastq.gz
		mv $(1)/$(2)_2.fastq.gz $(1)/$(3)_S1_L00$(4)_I2_001.fastq.gz
		mv $(1)/$(2)_3.fastq.gz $(1)/$(3)_S1_L00$(4)_R1_001.fastq.gz
		mv $(1)/$(2)_4.fastq.gz $(1)/$(3)_S1_L00$(4)_R2_001.fastq.gz;\

	else \
		$(call print_error,number of downloaded fastq exceeds 4);\

	fi
endef

define check_inference_status
	if [ $$exit_status -eq 0 ]; then \
		echo "_GLOBAL_OPTIMUM" > $(@D)/__SOLUTION; \
		$(call print_debug,global optimum found); \
	elif [ $$exit_status -eq 124 ]; then \
		echo -e ''; \
		if [ -s $@ ]; then \
			echo "_LOCAL_OPTIMUM" > $(@D)/__SOLUTION; \
			$(call print_warning,user-defined time limit reached \($(1)\): local optimum found); \
		else \
			echo "_FAILURE" > $(@D)/__SOLUTION; \
			$(call print_error,user-defined time limit reached \($(1)\): no solution found); \
		fi; \
	elif [ $$exit_status -eq 130 ] || [ $$exit_status -eq 143 ]; then \
		echo -e ''; \
		if [ -s $@ ]; then \
			echo "_PARTIAL_SOLUTIONS" > $(@D)/__SOLUTION; \
			$(call print_warning,inference interrupted: keeping partial solutions); \
		else \
			echo "_FAILURE" > $(@D)/__SOLUTION; \
			$(call log,ERROR,inference interrupted: no partial solution found); \
		fi; \
		exit $$exit_status; \
	else \
		echo "_FAILURE" > $(@D)/__SOLUTION; \
		$(call log,ERROR,inference failed); \
		exit $$exit_status; \
	fi
endef

define trap_inference_interrupt
handle_inference_interrupt() { \
	signal_status="$$1"; \
	echo -e ""; \
	if [ -s $@ ]; then \
		echo "_PARTIAL_SOLUTIONS" > $(@D)/__SOLUTION; \
		$(call log,WARNING,inference interrupted: keeping partial solutions); \
	else \
		echo "_FAILURE" > $(@D)/__SOLUTION; \
		$(call log,ERROR,inference interrupted: no partial solution found); \
	fi; \
	exit "$${signal_status}"; \
}; \
trap 'handle_inference_interrupt 130' INT; \
trap 'handle_inference_interrupt 143' TERM
endef

define check_partial_bn_outputs
@if [ -d "$(1)" ] && [ ! -f "$(3)" ]; then \
	echo "" > /dev/tty; \
	echo "Detected incomplete outputs for target '$(2)'." > /dev/tty; \
	echo "Output directory: $(1)" > /dev/tty; \
	echo "" > /dev/tty; \
	printf "Remove partial outputs and rerun inference? [y/N] " > /dev/tty; \
	read ans; \
	if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ]; then \
		rm -rf "$(1)"; \
		echo "Partial outputs removed." > /dev/tty; \
	else \
		echo "Inference aborted." > /dev/tty; \
		exit 1; \
	fi; \
fi
endef

## END FUNCTIONS ##
