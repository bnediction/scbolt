#!/usr/bin/env make

.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c

SHELL := /bin/bash
MAKEFLAGS += --silent
__check_externals__ ?= true

launch_dir := $(CURDIR)
makefile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
scbolt_root := $(patsubst %/,%,$(dir $(makefile_path)))
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
$(call resolve_user_path_var,YAML_MODEL)
$(call resolve_user_path_var,BINARIZATION_FILE)
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

diagnostic_mode := $(filter check config,$(MAKECMDGOALS))$(__check_mode)

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
export tmpdir := $(shell mktemp -d -t scbolt-XXXXXXXXXX)
$(shell { trap 'rm -rf $(tmpdir);' EXIT; tail --pid=$$PPID -f /dev/null; } </dev/null >/dev/null 2>/dev/null &)

## BEGIN URLS ##

cycle_url := https://github.com/MarioniLab/scran/raw/master/inst/exdata/mouse_cycle_markers.rds
go_basic_url := http://purl.obolibrary.org/obo/go/go-basic.obo
geiger_url := https://doi.org/10.1371/journal.pbio.2003389.s025
chambers_url := https://ars.els-cdn.com/content/image/1-s2.0-S1934590907002202-mmc3.xls
gene2go_url := ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/gene2go.gz

## END URLS ##

## BEGIN COLORS ##

nc        = \033[0m
green     = \033[0;32m
red       = \033[0;31m
bold      = \033[1m

## END COLORS ##

## BEGIN FUNCTIONS ##

log = printf '%s - %s - %s\n' "`date '+%Y-%m-%d %H:%M:%S.%3N'`" "$(1)" "$(2)"

print_rule    = $(call log,RULE,$(1)$(if $(2), (reference: $(2))))
print_task    = $(call log,TASK,$(1))
print_info    = $(call log,INFO,$(1))
print_warning = $(call log,WARNING,$(1))
print_debug   = $(call log,DEBUG,$(1))
print_error   = $(call log,ERROR,$(1)); exit 1

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
$(call require_bool,NORM_MAD,filtering); \
$(call require_bool,FILTER_NON_HVG,filtering)
endef
define require_clustering_parameters
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
$(call require_choice,KNNBS_EMBEDDING,pca umap,knnbs); \
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
$(call require_float,UNIMODAL_QUANTILE); \
$(call require_bool,ZEROES_ARE_ZEROES,bin-cells)
endef
define require_bin_macrostates_parameters
$(call require_float,NANS_THRESHOLD); \
$(call require_float,BIMODAL_THRESHOLD); \
$(call require_float,ZEROINF_THRESHOLD); \
$(call require_float,UNIMODAL_THRESHOLD)
endef
define require_bin_dea_parameters
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
check_success = check_success "$(1)"
check_failure = check_failure "$(1)"
report_check_error = missing=1; $(call check_failure,$(1))
print_check_reports = cat "$${project_checks}" "$${core_checks}" "$${method_checks}" \
	"$${external_resource_checks}" "$${file_checks}" "$${conda_checks}" \
	"$${command_checks}" "$${other_checks}"
parameter_label = $(strip $(if $(3),$(3) )parameter)
parameter_name = $(firstword $(strip $(1)))
parameter_assignment = $(strip $(call parameter_name,$(2))=$(strip $(1)) \
	$(strip $(patsubst $(call parameter_name,$(2))%,%,$(strip $(2)))))
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
define check_conda_env_diagnostic
if conda env list | awk '{print $$1}' | grep -qx "$(1)"; then \
	$(call check_success,conda environment found: $(1)); \
else \
	$(call report_check_error,required conda environment not found: $(1)); \
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
		$(call parameter_label,$(1),$(2),$(3)) $(2) (current: $(strip $(1))));; \
	*) $(call check_success,$(call parameter_label,$(1),$(2),$(3)) valid: $(2)=$(strip $(1)));; \
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
	$(call check_success,$(call parameter_label,$(1),$(2),$(3)) valid: $(2)=$(strip $(1))); \
else \
	$(call report_check_error,required numeric value for \
		$(call parameter_label,$(1),$(2),$(3)) $(2) (current: $(strip $(1)))); \
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
		$(call check_success,$(call parameter_label,$(1),$(3),$(4)) valid: $(3)=$(strip $(1)));; \
	"") $(call report_check_error,required $(call parameter_label,$(1),$(3),$(4)) not defined: $(3));; \
	*) $(call report_check_error,unsupported value for \
		$(call parameter_label,$(1),$(3),$(4)) $(3) \
		(supported values: $(subst $(space),$(comma) ,$(strip $(2)))));; \
esac
endef
check_bool_diagnostic = $(call check_choice_diagnostic,$(1),true false,$(2),$(3))
define check_optional_hvg_method_diagnostic
case "$(strip $(1))" in \
	""|seurat|cell_ranger|seurat_v3) \
		$(call check_success,$(call parameter_label,$(1),$(3),$(5)) valid: \
			$(strip $(3))=$(strip $(1)));; \
	*) $(call report_check_error,unsupported value for \
		$(call parameter_label,$(1),$(3),$(5)) $(strip $(3)) \
		(supported values: seurat, cell_ranger, seurat_v3));; \
esac; \
if [ "$(strip $(1))" = "seurat_v3" ] && [ -z "$(strip $(2))" ]; then \
	$(call report_check_error,$(call parameter_label,$(1),$(4),$(5)) $(strip $(4)) \
		is required when $(call parameter_label,$(1),$(3),$(5)) $(strip $(3)) \
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
conda_run_inference = $(conda_runtime_env) \
	TQDM_DISABLE="$(TQDM_DISABLE)" \
	TQDM_TO_TTY="$(TQDM_TO_TTY)" \
	PYTHONHASHSEED="$(SEED)" \
	conda run --no-capture-output -n $(1)
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
	mkdir -p $(dir $(LOGFILE)); \
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

## BEGIN PATHS ##

cc_markers  = $(public_dir)/cycle/mouse_cycle_markers.rds
signatures  = $(public_dir)/signatures/geiger.xls \
              $(public_dir)/signatures/chambers.xls \
              $(public_dir)/signatures/sig.json
go_basic    = $(public_dir)/go/go_basic.obo
go_organism = $(public_dir)/go/goslim_$(ORGANISM).obo
gene2go     = $(public_dir)/go/gene2go
dorothea_legacy = $(public_dir)/omnipath/dorothea_legacy_$(ORGANISM).csv

$(eval genome_ref := $(public_dir)/ref/$(notdir $(genome_url)))
genome_ref := $(genome_ref:.tar.gz=)
star_index = $(genome_ref)/star/Genome

define find_paths_for_conditions

fastq_$(1) =                    $(results)/$(1)/fastq
cellranger_$(1) =               $(results)/$(1)/count/cellranger/$(1).mri.tgz
star_$(1) =                     $(results)/$(1)/count/star/Aligned.sortedByCoord.out.bam \
                                $(results)/$(1)/count/star/Solo.out/matrix.mtx \
                                $(results)/$(1)/count/star/Solo.out/barcodes.tsv
qc_$(1) =                       $(results)/$(1)/count/star/star.velocyto.bam
velocyto_$(1) =                 $(results)/$(1)/count/counts.h5ad
filtering_$(1) =                $(results)/$(1)/prep/filter/counts.h5ad
normalization_$(1) =            $(results)/$(1)/prep/norm/counts.h5ad
velocity_$(1) =                 $(results)/$(1)/trajectories/velocity/velocity.h5ad
potency_$(1) =                  $(results)/$(1)/trajectories/potency/potency.csv
cotan_$(1) =                    $(results)/$(1)/mstates/cotan/mstates.h5ad \
                                $(results)/$(1)/mstates/cotan/mstates.csv
cellrank_$(1) =                 $(results)/$(1)/mstates/cellrank/mstates.h5ad \
                                $(results)/$(1)/mstates/cellrank/mstates.csv
stream_$(1) =                   $(results)/$(1)/mstates/stream/mstates.h5ad \
                                $(results)/$(1)/mstates/stream/mstates.csv
knnbs_$(1) =                    $(results)/$(1)/mstates/knnbs/mstates.h5ad \
                                $(results)/$(1)/mstates/knnbs/mstates.csv

ifeq ($(MACROSTATE_METHOD),cotan)
macrostates_$(1) =              $$(cotan_$(1))
else ifeq ($(MACROSTATE_METHOD),cellrank)
macrostates_$(1) =              $$(cellrank_$(1))
else ifeq ($(MACROSTATE_METHOD),stream)
macrostates_$(1) =              $$(stream_$(1))
else ifeq ($(MACROSTATE_METHOD),knnbs)
macrostates_$(1) =              $$(knnbs_$(1))
else
macrostates_$(1) =              $(results)/$(1)/mstates/invalid-method/.error
endif

ifeq ($(ALIGNMENT_TOOL),cellranger)
alignment_$(1) =                $$(cellranger_$(1))
else ifeq ($(ALIGNMENT_TOOL),star)
alignment_$(1) =                $$(star_$(1))
else
alignment_$(1) =                $(results)/$(1)/count/invalid-alignment/.error
endif

endef

define find_paths_for_references

clustering_$(1) =               $(results)/$(1)/clust/clust.h5ad
dea_$(1) =                      $(results)/$(1)/clust/dea/markers.csv \
                                $(results)/$(1)/clust/dea/genes.xlsx
scoring_$(1) =                  $(results)/$(1)/clust/sig.csv
goea_basic_$(1) =               $(results)/$(1)/clust/goea/basic.xlsx
goea_organism_$(1) =            $(results)/$(1)/clust/goea/$(ORGANISM).xlsx
annotation_$(1) =               $(results)/$(1)/clust/annot.h5ad

endef

bin_cells =                     $(results)/bin/scboolseq/cell/cells_bin.h5ad \
                                $(results)/bin/scboolseq/cell/cells_stats.csv
bin_macrostates =               $(results)/bin/scboolseq/macro/$(MACROSTATE_METHOD)/mstates_bin.csv
bin_dea =                       $(results)/bin/dea/$(MACROSTATE_METHOD)/mstates_bin.csv
bin_consensus =                 $(results)/bin/consensus/$(MACROSTATE_METHOD)/mstates_bin.csv

bonesis_model =                 $(results)/infer/spec/model.bo \
                                $(results)/infer/spec/mstates.csv \
                                $(results)/infer/spec/important.txt \
                                $(results)/infer/spec/mandatory.txt
max_nodes_soft =                $(results)/infer/genes/soft/comps.txt
max_consts_soft =               $(results)/infer/genes/consts/comps.txt
max_nodes_relaxed =             $(results)/infer/genes/relaxed/comps.txt
max_nodes_seed =                $(results)/infer/genes/seed/comps.txt
max_nodes_lock =                $(results)/infer/genes/lock/comps.txt
bn_min =                        $(results)/infer/bn/min/model.bnet

bn_submin_dir = $(results)/infer/bn/submin
bn_files = $(foreach i,$(1),$(2)/$(i)/model.bnet $(2)/$(i)/state.cfg)
ifneq ($(filter-out 0,$(strip $(INFER_LIMIT))),)
bn_submin_indices := $(shell seq 0 $$(($(INFER_LIMIT)-1)))
bn_submin = $(call bn_files,$(bn_submin_indices),$(bn_submin_dir))
else
bn_submin = $(bn_submin_dir)/ensemble.pdf
endif

bn_diverse_dir = $(results)/infer/bn/diverse
ifneq ($(filter-out 0,$(strip $(INFER_LIMIT))),)
bn_diverse_indices := $(shell seq 0 $$(($(INFER_LIMIT)-1)))
bn_diverse = $(call bn_files,$(bn_diverse_indices),$(bn_diverse_dir))
else
bn_diverse = $(bn_diverse_dir)/ensemble.pdf
endif

$(foreach condition,$(conditions),$(eval $(call find_paths_for_conditions,$(condition))))
$(foreach reference,$(references),$(eval $(call find_paths_for_references,$(reference))))

## END PATHS ##

## BEGIN TARGETS ##

fastq_target :=
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
knnbs_target :=
cotan_target :=

define find_targets_for_conditions

$(eval fastq_target := $(fastq_target) $(fastq_$(1)))
$(eval alignment_target := $(alignment_target) $(alignment_$(1)))
$(eval cellranger_target := $(cellranger_target) $(cellranger_$(1)))
$(eval star_target := $(star_target) $(star_$(1)))
$(eval qc_target := $(qc_target) $(qc_$(1)))
$(eval velocyto_target := $(velocyto_target) $(velocyto_$(1)))
$(eval filtering_target := $(filtering_target) $(filtering_$(1)))
$(eval normalization_target := $(normalization_target) $(normalization_$(1)))
$(eval velocity_target := $(velocity_target) $(velocity_$(1)))
$(eval potency_target := $(potency_target) $(potency_$(1)))
$(eval cotan_target := $(cotan_target) $(cotan_$(1)))
$(eval cellrank_target := $(cellrank_target) $(cellrank_$(1)))
$(eval stream_target := $(stream_target) $(stream_$(1)))
$(eval knnbs_target := $(knnbs_target) $(knnbs_$(1)))
$(eval macrostates_target := $(macrostates_target) $(macrostates_$(1)))

endef

define find_targets_for_references

$(eval clustering_target := $(clustering_target) $(clustering_$(1)))
$(eval dea_target := $(dea_target) $(dea_$(1)))
$(eval scoring_target := $(scoring_target) $(scoring_$(1)))
$(eval goea_target := $(goea_target) $(goea_basic_$(1)) $(goea_organism_$(1)))
$(eval annotation_target := $(annotation_target) $(annotation_$(1)))

endef

$(foreach condition,$(running_conditions),$(eval $(call find_targets_for_conditions,$(condition))))
$(foreach reference,$(running_references),$(eval $(call find_targets_for_references,$(reference))))

## END TARGETS ##

ifeq ($(words $(CONDITIONS)),1)
batch =
else
batch = --batch condition
endif

## BEGIN PARAMETERS ##

ifeq ($(diagnostic_mode),)
ifneq ($(call is_positive_integer,$(MEMORY)),true)
$(error parameter MEMORY must be a positive integer (current: $(MEMORY)))
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
ifneq ($(call is_creatable_path,$(RESULTS)),true)
$(error parameter RESULTS must be a valid output path (current: $(RESULTS)))
endif
ifeq ($(strip $(REFERENCES)),)
$(error parameter REFERENCES not defined)
endif
ifneq ($(invalid_references),)
$(error unsupported value for parameter REFERENCES: $(invalid_references) \
	(supported values: $(subst $(space),$(comma) ,$(conditions) integrated)))
endif
ifeq ($(words $(conditions)),1)
ifneq ($(filter integrated,$(running_references)),)
$(error unsupported value for parameter REFERENCES: integrated is not supported \
	for mono-condition projects)
endif
endif
endif

$(if $(filter true,$(call is_creatable_path,$(RESULTS))),$(shell mkdir -p "$(results)"))

check_mode := $(filter check,$(MAKECMDGOALS))$(__check_mode)
check_required_config_params = MEMORY JOBS SEED LOGGING RESULTS USE_REP LABEL_COL
check_missing_config_params := $(strip \
	$(foreach var,$(check_required_config_params),\
		$(if $(strip $($(var))),,$(var))))
check_simple_config_params = USE_REP LABEL_COL
check_present_config_params := $(filter-out \
	$(check_missing_config_params),$(check_simple_config_params))

ifneq ($(check_mode),)
$(if $(strip $(JOBS)),,$(eval override JOBS := 1))
endif

ifndef JOBS
open_allocated_cpu := 1
else ifneq ($(call is_positive_integer,$(JOBS)),true)
open_allocated_cpu := 1
else
try_open_allocated_cpu := $(shell echo $$(($(JOBS) / 2)))
open_allocated_cpu := $(if $(findstring $(try_open_allocated_cpu),0),1,$(try_open_allocated_cpu))
endif

norm_mad = $(if $(filter true,$(NORM_MAD)),--consistent-mad)
filter_non_hvg = $(if $(filter true,$(FILTER_NON_HVG)),--filter-non-hvg)
correction = $(if $(filter true,$(CC_CORRECTION)),--correction G2M_score S_score G1_score)
pca_only_hvg = $(if $(filter true,$(PCA_ONLY_HVG)),--only-hvg)

label_ids = $(if $(LABEL),$(shell seq 0 1 $$(($(words $(LABEL))-1))))
label_map = $(join $(label_ids),$(addprefix :,$(LABEL)))

velocity_only_hvg = $(if $(filter true,$(VELOCITY_ONLY_HVG)),--only-hvg)
cotan_only_hvg = $(if $(filter true,$(COTAN_ONLY_HVG)),--only-hvg)
extend_epg = $(if $(filter true,$(EXTEND_EPG)),--extend-epg)
prune_epg = $(if $(filter true,$(PRUNE_EPG)),--prune-epg)

ifeq ($(KNNBS_DIMENSION),)
knnbs_dimension=
else
knnbs_dimension=--dimension $(KNNBS_DIMENSION)
endif

hvg_layer = $(if $(filter seurat_v3,$(1)),--layer counts,--layer log-norm)
scboolseq_layer = $(if $(filter seurat seurat_v3 cell_ranger,$(SCBOOLSEQ_HVG_METHOD)),\
	$(call hvg_layer,$(SCBOOLSEQ_HVG_METHOD)))
zeroes_are_zeroes = $(if $(filter true,$(ZEROES_ARE_ZEROES)),--zeroes-are-zeroes)
dea_layer = $(if $(filter seurat seurat_v3 cell_ranger,$(DEA_HVG_METHOD)),\
	$(call hvg_layer,$(DEA_HVG_METHOD)))
bin_method_error = $(results)/bin/invalid-method/.error
default_bin = $(if $(filter scboolseq,$(BIN_METHOD)),$(bin_macrostates),\
	$(if $(filter dea,$(BIN_METHOD)),$(bin_dea),\
	$(if $(filter consensus,$(BIN_METHOD)),$(bin_consensus),$(bin_method_error))))
bin = $(if $(BINARIZATION_FILE),$(BINARIZATION_FILE),$(default_bin))

known_prior_knowledge = collectri dorothea
dorothea_apis = current legacy
dorothea_levels = A B C D

# Resolve the user-facing prior knowledge parameter to the actual domain passed
# to BoNesis scripts. Only dorothea+legacy is materialized as a custom file,
# because decoupler.get_dorothea lives in the legacy environment.
ifeq ($(PRIOR_KNOWLEDGE),collectri)
prior_knowledge = collectri
else ifeq ($(PRIOR_KNOWLEDGE),dorothea)
ifneq ($(filter $(strip $(DOROTHEA_API)),$(dorothea_apis)),)
ifeq ($(strip $(DOROTHEA_API)),legacy)
prior_knowledge = $(dorothea_legacy)
else
prior_knowledge = dorothea
endif
else
prior_knowledge =
endif
else ifneq ($(wildcard $(PRIOR_KNOWLEDGE)),)
prior_knowledge = $(PRIOR_KNOWLEDGE)
endif
dorothea_levels_arg = $(if $(filter dorothea,$(prior_knowledge)),\
	$(if $(strip $(DOROTHEA_LEVELS)),--dorothea-levels $(DOROTHEA_LEVELS)))
prior_knowledge_params = PRIOR_KNOWLEDGE \
	$(if $(filter dorothea,$(PRIOR_KNOWLEDGE)),\
	DOROTHEA_API $(if $(filter current,$(DOROTHEA_API)),DOROTHEA_LEVELS))

model_layer = $(if $(filter seurat seurat_v3 cell_ranger,$(MODEL_HVG_METHOD)),\
	$(call hvg_layer,$(MODEL_HVG_METHOD)))
min_self_loop_consts = $(if $(filter true,$(MIN_SELF_LOOP_CONSTS)),--minimize-self-loops)
min_self_loop_infer = $(if $(filter true,$(MIN_SELF_LOOP_INFER)),--minimize-self-loops)

reset_stages = \
	load-fastq alignment cellranger star qc velocyto \
	filtering normalization clustering dea scoring goea annotation \
	velocity potency cotan cellrank stream knnbs macrostates \
	bin-cells bin-macrostates bin-dea bin-consensus binarization \
	spec max-nodes-soft max-consts-soft max-nodes-relaxed \
	max-nodes-seed max-nodes-lock bn-min bn-submin bn-diverse
RESET_TARGET_load-fastq = $(fastq_target)
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
RESET_TARGET_knnbs = $(knnbs_target)
RESET_TARGET_macrostates = $(macrostates_target)
RESET_TARGET_bin-cells = $(bin_cells)
RESET_TARGET_bin-macrostates = $(bin_macrostates)
RESET_TARGET_bin-dea = $(bin_dea)
RESET_TARGET_bin-consensus = $(bin_consensus)
RESET_TARGET_binarization = $(bin)
RESET_TARGET_spec = $(bonesis_model)
RESET_TARGET_max-nodes-soft = $(max_nodes_soft)
RESET_TARGET_max-consts-soft = $(max_consts_soft)
RESET_TARGET_max-nodes-relaxed = $(max_nodes_relaxed)
RESET_TARGET_max-nodes-seed = $(max_nodes_seed)
RESET_TARGET_max-nodes-lock = $(max_nodes_lock)
RESET_TARGET_bn-min = $(bn_min)
RESET_TARGET_bn-submin = $(bn_submin)
RESET_TARGET_bn-diverse = $(bn_diverse)

reset_modules := $(strip $(RESET_TARGET))
trust_modules := $(strip $(TRUST_TARGET))
reset_disabled_goals := help
reset_disabled := $(filter $(reset_disabled_goals),$(MAKECMDGOALS))$(__reset_disabled)
ifeq ($(reset_disabled),)
unknown_reset_targets := $(filter-out $(reset_stages),$(reset_modules))
unknown_trust_targets := $(filter-out $(reset_stages),$(trust_modules))
ifneq ($(unknown_reset_targets),)
$(error unknown RESET_TARGET module: $(unknown_reset_targets) \
	(supported values: $(subst $(space),$(comma) ,$(reset_stages))))
endif
ifneq ($(unknown_trust_targets),)
$(error unknown TRUST_TARGET module: $(unknown_trust_targets) \
	(supported values: $(subst $(space),$(comma) ,$(reset_stages))))
endif
reset_targets := $(strip $(foreach module,$(reset_modules),$(RESET_TARGET_$(module))))
trust_targets := $(strip $(foreach module,$(trust_modules),$(RESET_TARGET_$(module))))
ifneq ($(reset_targets),)
.PHONY: $(reset_targets)
endif
trust_make_options := $(foreach target,$(trust_targets),--old-file="$(target)")
endif

target_params_load-dorothea = ORGANISM
target_params_alignment = ALIGNMENT_TOOL MEMORY STAR_CB_LEN STAR_UMI_LEN STAR_WHITELIST
target_params_cellranger = MEMORY
target_params_star = MEMORY STAR_CB_LEN STAR_UMI_LEN STAR_WHITELIST
target_params_qc = STAR_BARCODE_FILTER STAR_MIN_UMI STAR_TOP_BARCODES
target_params_velocyto = ALIGNMENT_TOOL MEMORY STAR_BARCODE_FILTER STAR_MIN_UMI STAR_TOP_BARCODES
target_params_filtering = \
	GENE_DROPOUT GENE_EXPRESSION GENE_COUNTS \
	CELL_DROPOUT CELL_EXPRESSION CELL_READS \
	MAD_DEVIATION NORM_MAD MT HVG FILTER_NON_HVG
target_params_normalization = CC_CORRECTION
target_params_clustering = \
	INTEGRATION DIM_PCA DIM_CLUSTERING DIM_EMBEDDING PCA_ONLY_HVG \
	NEIGHBORS METRIC RESOLUTION MIN_DIST SPREAD
target_params_dea = LOGFC CORRECTION ALPHA
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
target_params_knnbs = MACROSTATE_SIZE KNNBS_EMBEDDING KNNBS_DIMENSION KNNBS_NEIGHBORS
target_params_macrostates = MACROSTATE_METHOD MACROSTATE_SIZE
target_params_bin-cells = SCBOOLSEQ_HVG_METHOD SCBOOLSEQ_TOP_HVG UNIMODAL_QUANTILE ZEROES_ARE_ZEROES
target_params_bin-macrostates = NANS_THRESHOLD BIMODAL_THRESHOLD ZEROINF_THRESHOLD UNIMODAL_THRESHOLD
target_params_bin-dea = DEA_HVG_METHOD DEA_TOP_HVG BIN_LOGFC BIN_CORRECTION BIN_ALPHA
target_params_bin-consensus = \
	NANS_THRESHOLD BIMODAL_THRESHOLD ZEROINF_THRESHOLD UNIMODAL_THRESHOLD \
	DEA_HVG_METHOD DEA_TOP_HVG BIN_LOGFC BIN_CORRECTION BIN_ALPHA
target_params_binarization = BIN_METHOD BINARIZATION_FILE
target_params_spec = YAML_MODEL MODEL_HVG_METHOD MODEL_TOP_HVG $(prior_knowledge_params)
target_params_max-nodes-soft = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_FILTER \
	CLINGO_CONFIG_SOFT CLINGO_OPT_MODE_SOFT CLINGO_OPT_STRATEGY_SOFT \
	JOBS_SOFT TIMEOUT_SOFT
target_params_max-consts-soft = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_FILTER MIN_SELF_LOOP_CONSTS \
	CLINGO_CONFIG_CONSTS CLINGO_OPT_MODE_CONSTS CLINGO_OPT_STRATEGY_CONSTS \
	JOBS_CONSTS TIMEOUT_CONSTS
target_params_max-nodes-relaxed = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_FILTER \
	CLINGO_CONFIG_RELAXED CLINGO_OPT_MODE_RELAXED CLINGO_OPT_STRATEGY_RELAXED \
	JOBS_RELAXED TIMEOUT_RELAXED
target_params_max-nodes-seed = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_FILTER \
	CLINGO_CONFIG_SEED CLINGO_OPT_MODE_SEED CLINGO_OPT_STRATEGY_SEED \
	JOBS_SEED TIMEOUT_SEED
target_params_max-nodes-lock = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_FILTER \
	CLINGO_CONFIG_LOCK CLINGO_OPT_MODE_LOCK CLINGO_OPT_STRATEGY_LOCK \
	JOBS_LOCK TIMEOUT_LOCK
target_params_bn-min = \
	$(prior_knowledge_params) MAX_CLAUSE CANONIC_INFER MIN_SELF_LOOP_INFER \
	CLINGO_OPT_MODE_MIN GRAPH_FORMATS
target_params_bn-submin = $(prior_knowledge_params) MAX_CLAUSE CANONIC_INFER INFER_LIMIT CONFIG_FORMATS GRAPH_FORMATS
target_params_bn-diverse = $(prior_knowledge_params) MAX_CLAUSE CANONIC_INFER INFER_LIMIT CONFIG_FORMATS GRAPH_FORMATS

uniq = $(if $(1),$(firstword $(1)) $(call uniq,$(filter-out $(firstword $(1)),$(1))))

project_config_param_set = \
	ORGANISM CONDITIONS \
	$(foreach condition,$(conditions),SRA_$(call toupper,$(condition))) \
	LABEL YAML_MODEL
core_config_param_set = \
	PARAMS REFERENCES RESULTS MEMORY JOBS SEED LOGGING USE_REP LABEL_COL
method_config_param_set = \
	ALIGNMENT_TOOL STAR_CB_LEN STAR_UMI_LEN \
	STAR_BARCODE_FILTER STAR_MIN_UMI STAR_TOP_BARCODES \
	GENE_DROPOUT GENE_EXPRESSION GENE_COUNTS \
	CELL_DROPOUT CELL_EXPRESSION CELL_READS \
	MAD_DEVIATION NORM_MAD MT HVG FILTER_NON_HVG \
	CC_CORRECTION \
	INTEGRATION DIM_PCA DIM_CLUSTERING DIM_EMBEDDING PCA_ONLY_HVG \
	NEIGHBORS METRIC RESOLUTION MIN_DIST SPREAD \
	LOGFC CORRECTION ALPHA \
	DIM_MOMENT VELOCITY_ONLY_HVG SMM_MODE \
	BATCH_SIZE SMOOTH_BATCH_SIZE \
	MACROSTATE_SIZE MACROSTATE_METHOD \
	COTAN_METHOD COTAN_ONLY_HVG MAX_ITER \
	CELLRANK_METHOD STATES INITIAL_STATES TERMINAL_STATES \
	CELLRANK_STABILITY CELLRANK_ALPHA \
	CLUSTERING_METHOD CLUSTER_NUMBER ALPHA_EPG MU_EPG LAMBDA_EPG \
	EXTEND_EPG EXTEND_MODE EXTEND_PARAMETER PRUNE_EPG COLLAPSE_PARAMETER \
	KNNBS_EMBEDDING KNNBS_DIMENSION KNNBS_NEIGHBORS \
	SCBOOLSEQ_HVG_METHOD SCBOOLSEQ_TOP_HVG UNIMODAL_QUANTILE ZEROES_ARE_ZEROES \
	NANS_THRESHOLD BIMODAL_THRESHOLD ZEROINF_THRESHOLD UNIMODAL_THRESHOLD \
	DEA_HVG_METHOD DEA_TOP_HVG BIN_LOGFC BIN_CORRECTION BIN_ALPHA \
	BIN_METHOD \
	MODEL_HVG_METHOD MODEL_TOP_HVG \
	MAX_CLAUSE DOROTHEA_API DOROTHEA_LEVELS CANONIC_FILTER CANONIC_INFER \
	CLINGO_OPT_MODE_SOFT CLINGO_OPT_STRATEGY_SOFT JOBS_SOFT TIMEOUT_SOFT \
	CLINGO_OPT_MODE_CONSTS CLINGO_OPT_STRATEGY_CONSTS JOBS_CONSTS TIMEOUT_CONSTS \
	CLINGO_OPT_MODE_RELAXED CLINGO_OPT_STRATEGY_RELAXED JOBS_RELAXED TIMEOUT_RELAXED \
	CLINGO_OPT_MODE_SEED CLINGO_OPT_STRATEGY_SEED JOBS_SEED TIMEOUT_SEED \
	CLINGO_OPT_MODE_LOCK CLINGO_OPT_STRATEGY_LOCK JOBS_LOCK TIMEOUT_LOCK \
	CLINGO_OPT_MODE_MIN CONFIG_FORMATS GRAPH_FORMATS MIN_SELF_LOOP_CONSTS \
	MIN_SELF_LOOP_INFER INFER_LIMIT
external_resource_config_param_set = \
	STAR_WHITELIST BINARIZATION_FILE PRIOR_KNOWLEDGE \
	CLINGO_CONFIG_SOFT CLINGO_CONFIG_CONSTS CLINGO_CONFIG_RELAXED \
	CLINGO_CONFIG_SEED CLINGO_CONFIG_LOCK
config_default_modules = \
	load-fastq load-dorothea alignment cellranger star qc velocyto \
	filtering normalization clustering dea annotation velocity potency \
	macrostates cotan cellrank stream knnbs bin-cells bin-macrostates \
	bin-dea bin-consensus binarization spec max-nodes-soft max-consts-soft \
	max-nodes-relaxed max-nodes-seed max-nodes-lock bn-min bn-submin bn-diverse
config_base_params = \
	ORGANISM CONDITIONS $(foreach condition,$(conditions),SRA_$(call toupper,$(condition))) \
	PARAMS REFERENCES RESULTS MEMORY JOBS SEED LOGGING USE_REP LABEL_COL
config_params_from_modules = $(strip $(foreach module,$(1),$(target_params_$(module))))
config_project_params = $(call uniq,$(filter $(project_config_param_set),$(1)))
config_core_params = $(call uniq,$(filter $(core_config_param_set),$(1)))
config_method_params = $(call uniq,$(filter $(method_config_param_set),$(1)))
config_external_resource_params = $(call uniq,$(filter $(external_resource_config_param_set),$(1)))

config_print_var = $(if $(filter undefined,$(origin $(1))),,$(info $(1)=$($(1))))
define config_print_section
$(info )
$(info [$(1)])
$(foreach var,$(strip $(2)),$(call config_print_var,$(var)))
endef

## END PARAMETERS ##

## BEGIN HELP ##

##@ Utilities

.PHONY: help
help: ## display this help and exit
	@awk 'BEGIN {FS = ":.*##"; \
		printf "usage: make $(green)<module>$(nc) [REFERENCES=<condition...>] "; \
		printf "[RESET_TARGET=<module...>] "; \
		printf "[TRUST_TARGET=<module...>]\n"; \
		printf "(default value for REFERENCES: $(running_references))\n\n"; \
		printf "scBOLT is a semi-automated pipeline for Boolean network inference "; \
		printf "from multi-condition single-cell transcriptomes. "; \
		printf "The workflow includes: alignment and preprocessing, integration and clustering, "; \
		printf "cell annotation, trajectory inference, macrostate characterization, "; \
		printf "macrostate binarization, Boolean constraint specification, gene selection, "; \
		printf "and Boolean network inference.\n\n"; \
		printf "$(bold)Special parameters$(nc)\n"; \
		printf "  %-25s %s\n", "REFERENCES=<condition...>", "restrict the run to selected references"; \
		printf "  %-25s %s\n", "RESET_TARGET=<module...>", "rebuild from these modules; successful recipes replace outputs"; \
		printf "  %-25s %s\n", "TRUST_TARGET=<module...>", "trust these module outputs and skip rebuilding them"; \
		printf "  %-25s %s\n", "TARGET=<module>", "select module for check, config, and dry-run"} \
		/^[a-zA-Z_-]+:.*?##/ { printf "  $(green)%-22s$(nc) %s\n", $$1, $$2 } \
		/^##@/ { printf "\n$(bold)%s$(nc)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.PHONY: config
config: ## display effective configuration and exit
	$(eval config_modules := $(if $(TARGET),\
		$(shell $(nested_make) --always-make --dry-run LOGGING=false \
			__check_mode=true __$(TARGET) LOGFILE="$(LOGFILE)" 2>/dev/null \
			| sed -n '/"RULE"/{s/.*"RULE" "//;s/ .*//;s/"//g;p;}' \
			| awk '!seen[$$0]++'),\
		$(config_default_modules)))
	$(eval config_params := $(call uniq,$(config_base_params) $(call config_params_from_modules,$(config_modules))))
	$(call config_print_section,PROJECT PARAMETERS,$(call config_project_params,$(config_params)))
	$(call config_print_section,CORE PARAMETERS,$(call config_core_params,$(config_params)))
	$(call config_print_section,METHOD PARAMETERS,$(call config_method_params,$(config_params)))
	$(call config_print_section,EXTERNAL RESOURCE PARAMETERS,$(call config_external_resource_params,$(config_params)))
	@:

.PHONY: check
check: ## check Make-level dependencies, configuration and external tools required to build TARGET
	@if [ -z "$(TARGET)" ]; then \
		printf '$(red)FAIL$(nc) %s\n' "missing TARGET (usage: make check TARGET=<module>)"; \
		exit 1; \
	fi
	@dry_run="$$(mktemp)"; \
	check_report_dir="$$(mktemp -d)"; \
	project_checks="$${check_report_dir}/01_project"; \
	core_checks="$${check_report_dir}/02_core"; \
	method_checks="$${check_report_dir}/03_method"; \
	external_resource_checks="$${check_report_dir}/04_external_resource"; \
	file_checks="$${check_report_dir}/05_files"; \
	conda_checks="$${check_report_dir}/06_conda"; \
	command_checks="$${check_report_dir}/07_commands"; \
	other_checks="$${check_report_dir}/08_other"; \
	touch "$${project_checks}" "$${core_checks}" "$${method_checks}" \
		"$${external_resource_checks}" "$${file_checks}" "$${conda_checks}" \
		"$${command_checks}" "$${other_checks}"; \
	trap 'rm -f "$${dry_run}"; rm -rf "$${check_report_dir}"' EXIT; \
	route_check_report() { \
		case "$$1" in \
			project\ parameter*|*project\ parameter*) printf '%s\n' "$${project_checks}";; \
			core\ parameter*|*core\ parameter*) printf '%s\n' "$${core_checks}";; \
			method\ parameter*|*method\ parameter*) printf '%s\n' "$${method_checks}";; \
			external\ resource\ parameter*|*external\ resource\ parameter*) \
				printf '%s\n' "$${external_resource_checks}";; \
			file\ found*|*file*) printf '%s\n' "$${file_checks}";; \
			conda\ environment*|command\ found:\ conda|*conda*) printf '%s\n' "$${conda_checks}";; \
			command\ found*|*command*) printf '%s\n' "$${command_checks}";; \
			*) printf '%s\n' "$${other_checks}";; \
		esac; \
	}; \
	check_success() { printf '$(green)SUCCESS$(nc) %s\n' "$$1" >> "$$(route_check_report "$$1")"; }; \
	check_failure() { printf '$(red)FAIL$(nc) %s\n' "$$1" >> "$$(route_check_report "$$1")"; }; \
	missing=0; \
	$(nested_make) --dry-run LOGGING=false \
		__check_mode=true __$(TARGET) LOGFILE="$(LOGFILE)" > "$${dry_run}"; \
	$(foreach var,$(check_missing_config_params),$(call report_check_error,required core parameter not defined: $(var));) \
	if [ -n "$(MEMORY)" ]; then \
		$(call check_positive_integer_diagnostic,$(MEMORY),MEMORY,core); \
	fi; \
	if [ -n "$(JOBS)" ]; then \
		$(call check_positive_integer_diagnostic,$(JOBS),JOBS,core); \
	fi; \
	if [ -n "$(SEED)" ]; then \
		$(call check_positive_integer_diagnostic,$(SEED),SEED,core); \
	fi; \
	if [ -n "$(LOGGING)" ]; then \
		$(call check_bool_diagnostic,$(LOGGING),LOGGING,core); \
	fi; \
	if [ -n "$(RESULTS)" ]; then \
		$(call check_path_diagnostic,$(RESULTS),RESULTS,core); \
	fi; \
	$(call check_references_diagnostic); \
	$(foreach var,$(check_present_config_params),$(call check_success,core parameter valid: $(var)=$($(var)));) \
	if [ ! -s "$${dry_run}" ]; then \
		if [ "$${missing}" -eq 0 ]; then \
			$(call check_success,target already up to date: '$(TARGET)'); \
			$(print_check_reports); \
			exit 0; \
		fi; \
	fi; \
	if grep -qE '(^|[[:space:]])STAR([[:space:]]|$$)' "$${dry_run}"; then \
		$(call check_positive_integer_diagnostic,$(STAR_CB_LEN),STAR_CB_LEN,method); \
		$(call check_positive_integer_diagnostic,$(STAR_UMI_LEN),STAR_UMI_LEN,method); \
		if [ -n "$(STAR_WHITELIST)" ]; then \
		$(call check_file_diagnostic,$(STAR_WHITELIST),STAR_WHITELIST,external resource); \
		fi; \
	fi; \
	if grep -q 'scripts/alignment/filter_barcodes.py' "$${dry_run}"; then \
		$(call check_choice_diagnostic,$(STAR_BARCODE_FILTER),auto threshold top,STAR_BARCODE_FILTER,method); \
		$(call check_optional_positive_integer_diagnostic,$(STAR_MIN_UMI),STAR_MIN_UMI,method); \
		$(call check_optional_positive_integer_diagnostic,$(STAR_TOP_BARCODES),STAR_TOP_BARCODES,method); \
		if [ "$(STAR_BARCODE_FILTER)" = "threshold" ] && [ -z "$(STAR_MIN_UMI)" ]; then \
			$(call report_check_error,required method parameter not defined: \
				STAR_MIN_UMI (needed by target '$(TARGET)')); \
		fi; \
		if [ "$(STAR_BARCODE_FILTER)" = "top" ] && [ -z "$(STAR_TOP_BARCODES)" ]; then \
			$(call report_check_error,required method parameter not defined: \
				STAR_TOP_BARCODES (needed by target '$(TARGET)')); \
		fi; \
		if [ "$(STAR_BARCODE_FILTER)" = "auto" ] \
				&& { [ -n "$(STAR_MIN_UMI)" ] || [ -n "$(STAR_TOP_BARCODES)" ]; }; then \
			$(call report_check_error,method parameters STAR_MIN_UMI and STAR_TOP_BARCODES \
				require STAR_BARCODE_FILTER=threshold or top); \
		fi; \
	fi; \
	if grep -q 'ALIGNMENT_TOOL' "$${dry_run}"; then \
		$(call check_choice_diagnostic,$(ALIGNMENT_TOOL),cellranger star,ALIGNMENT_TOOL,method); \
	fi; \
	if grep -q 'MACROSTATE_METHOD' "$${dry_run}"; then \
		$(call check_choice_diagnostic,$(MACROSTATE_METHOD),cotan cellrank stream knnbs,MACROSTATE_METHOD,method); \
	fi; \
	if grep -q 'BIN_METHOD' "$${dry_run}"; then \
		$(call check_choice_diagnostic,$(BIN_METHOD),scboolseq dea consensus,BIN_METHOD,method); \
	fi; \
	if grep -q 'scripts/preprocessing/filtering.py' "$${dry_run}"; then \
		$(call check_bool_diagnostic,$(NORM_MAD),NORM_MAD,method); \
		$(call check_bool_diagnostic,$(FILTER_NON_HVG),FILTER_NON_HVG,method); \
	fi; \
	if grep -q 'scripts/preprocessing/normalization.py' "$${dry_run}"; then \
		$(call check_bool_diagnostic,$(CC_CORRECTION),CC_CORRECTION,method); \
		if [ "$(CC_CORRECTION)" = "true" ] && [ "$(ORGANISM)" != "mouse" ]; then \
			$(call report_check_error,method parameter CC_CORRECTION=true is only supported \
				for ORGANISM=mouse (current: $(ORGANISM))); \
		fi; \
	fi; \
	if grep -qE 'scripts/clustering/(clustering|integration).py' "$${dry_run}"; then \
		$(call check_positive_integer_diagnostic,$(DIM_PCA),DIM_PCA,method); \
		$(call check_positive_integer_diagnostic,$(DIM_CLUSTERING),DIM_CLUSTERING,method); \
		$(call check_positive_integer_diagnostic,$(DIM_EMBEDDING),DIM_EMBEDDING,method); \
		$(call check_bool_diagnostic,$(PCA_ONLY_HVG),PCA_ONLY_HVG,method); \
		$(call check_positive_integer_diagnostic,$(NEIGHBORS),NEIGHBORS,method); \
		$(call check_float_diagnostic,$(RESOLUTION),RESOLUTION,method); \
		$(call check_float_diagnostic,$(MIN_DIST),MIN_DIST,method); \
		$(call check_float_diagnostic,$(SPREAD),SPREAD,method); \
	fi; \
	if grep -q 'scripts/trajectories/velocity.py' "$${dry_run}"; then \
		$(call check_positive_integer_diagnostic,$(DIM_MOMENT),DIM_MOMENT,method); \
		$(call check_bool_diagnostic,$(VELOCITY_ONLY_HVG),VELOCITY_ONLY_HVG,method); \
	fi; \
	if grep -q 'scripts/macrostates/cellrank_macrostates.py' "$${dry_run}"; then \
		$(call check_positive_integer_diagnostic,$(INITIAL_STATES),INITIAL_STATES,method); \
		$(call check_positive_integer_diagnostic,$(TERMINAL_STATES),TERMINAL_STATES,method); \
		$(call check_float_diagnostic,$(CELLRANK_STABILITY),CELLRANK_STABILITY,method); \
		$(call check_float_diagnostic,$(CELLRANK_ALPHA),CELLRANK_ALPHA,method); \
	fi; \
	if grep -q 'scripts/macrostates/cotan_macrostates.R' "$${dry_run}"; then \
		$(call check_bool_diagnostic,$(COTAN_ONLY_HVG),COTAN_ONLY_HVG,method); \
	fi; \
	if grep -q 'scripts/macrostates/stream_macrostates.py' "$${dry_run}"; then \
		$(call check_positive_integer_diagnostic,$(CLUSTER_NUMBER),CLUSTER_NUMBER,method); \
		$(call check_float_diagnostic,$(ALPHA_EPG),ALPHA_EPG,method); \
		$(call check_float_diagnostic,$(MU_EPG),MU_EPG,method); \
		$(call check_float_diagnostic,$(LAMBDA_EPG),LAMBDA_EPG,method); \
		$(call check_bool_diagnostic,$(EXTEND_EPG),EXTEND_EPG,method); \
		$(call check_float_diagnostic,$(EXTEND_PARAMETER),EXTEND_PARAMETER,method); \
		$(call check_bool_diagnostic,$(PRUNE_EPG),PRUNE_EPG,method); \
		$(call check_bool_diagnostic,$(COLLAPSE_PARAMETER),COLLAPSE_PARAMETER,method); \
	fi; \
	if grep -q 'scripts/macrostates/knnbs_macrostates.py' "$${dry_run}"; then \
		$(call check_choice_diagnostic,$(KNNBS_EMBEDDING),pca umap,KNNBS_EMBEDDING,method); \
		$(call check_positive_integer_diagnostic,$(KNNBS_NEIGHBORS),KNNBS_NEIGHBORS,method); \
	fi; \
	if grep -q 'scripts/binarization/bin_cells_scboolseq.py' "$${dry_run}"; then \
		$(call check_optional_hvg_method_diagnostic,\
			$(SCBOOLSEQ_HVG_METHOD),$(SCBOOLSEQ_TOP_HVG),\
			SCBOOLSEQ_HVG_METHOD,SCBOOLSEQ_TOP_HVG,method); \
		$(call check_float_diagnostic,$(UNIMODAL_QUANTILE),UNIMODAL_QUANTILE,method); \
		$(call check_bool_diagnostic,$(ZEROES_ARE_ZEROES),ZEROES_ARE_ZEROES,method); \
	fi; \
	if grep -q 'scripts/binarization/bin_clusters_scboolseq.py' "$${dry_run}"; then \
		$(call check_float_diagnostic,$(NANS_THRESHOLD),NANS_THRESHOLD,method); \
		$(call check_float_diagnostic,$(BIMODAL_THRESHOLD),BIMODAL_THRESHOLD,method); \
		$(call check_float_diagnostic,$(ZEROINF_THRESHOLD),ZEROINF_THRESHOLD,method); \
		$(call check_float_diagnostic,$(UNIMODAL_THRESHOLD),UNIMODAL_THRESHOLD,method); \
	fi; \
	if grep -q 'scripts/binarization/bin_dea.py' "$${dry_run}"; then \
		$(call check_optional_hvg_method_diagnostic,$(DEA_HVG_METHOD),$(DEA_TOP_HVG),DEA_HVG_METHOD,DEA_TOP_HVG,method); \
		$(call check_float_diagnostic,$(BIN_LOGFC),BIN_LOGFC,method); \
		$(call check_float_diagnostic,$(BIN_ALPHA),BIN_ALPHA,method); \
	fi; \
	if grep -q 'scripts/clustering/markers.py' "$${dry_run}"; then \
		$(call check_float_diagnostic,$(LOGFC),LOGFC,method); \
	fi; \
	if grep -q 'scripts/inference/specification.py' "$${dry_run}"; then \
		$(call check_file_diagnostic,$(YAML_MODEL),YAML_MODEL,project); \
		$(call check_optional_hvg_method_diagnostic,\
			$(MODEL_HVG_METHOD),$(MODEL_TOP_HVG),\
			MODEL_HVG_METHOD,MODEL_TOP_HVG,method); \
	fi; \
	if grep -q 'PRIOR_KNOWLEDGE' "$${dry_run}"; then \
		$(call check_parameter_diagnostic,$(PRIOR_KNOWLEDGE),PRIOR_KNOWLEDGE,external resource); \
		if [ -n "$(PRIOR_KNOWLEDGE)" ] && [ -z "$(prior_knowledge)" ]; then \
			$(call report_check_error,unsupported value for external resource parameter PRIOR_KNOWLEDGE \
				(supported values: collectri, dorothea or an existing file path)); \
		fi; \
	fi; \
	if grep -q 'DOROTHEA_API' "$${dry_run}" && [ "$(PRIOR_KNOWLEDGE)" = "dorothea" ]; then \
		$(call check_choice_diagnostic,$(DOROTHEA_API),$(dorothea_apis),DOROTHEA_API,method); \
	fi; \
	if grep -q 'DOROTHEA_LEVELS' "$${dry_run}"; then \
		invalid_dorothea_levels=0; \
		for level in $(DOROTHEA_LEVELS); do \
			case "$${level}" in \
				$(subst $(space),|,$(dorothea_levels))) ;; \
				*) $(call report_check_error,unsupported value for method parameter DOROTHEA_LEVELS \
					(supported values: $(subst $(space),$(comma) ,$(dorothea_levels)))); \
					invalid_dorothea_levels=1;; \
			esac; \
		done; \
		if [ -n "$(DOROTHEA_LEVELS)" ] && [ "$${invalid_dorothea_levels}" -eq 0 ]; then \
			$(call check_success,method parameter valid: DOROTHEA_LEVELS=$(DOROTHEA_LEVELS)); \
		fi; \
	fi; \
	if grep -q 'CANONIC_FILTER' "$${dry_run}"; then \
		$(call check_bool_diagnostic,$(CANONIC_FILTER),CANONIC_FILTER,method); \
	fi; \
	if grep -q 'CANONIC_INFER' "$${dry_run}"; then \
		$(call check_bool_diagnostic,$(CANONIC_INFER),CANONIC_INFER,method); \
	fi; \
	if grep -q 'MIN_SELF_LOOP_CONSTS' "$${dry_run}"; then \
		$(call check_bool_diagnostic,$(MIN_SELF_LOOP_CONSTS),MIN_SELF_LOOP_CONSTS,method); \
	fi; \
	if grep -q 'MIN_SELF_LOOP_INFER' "$${dry_run}"; then \
		$(call check_bool_diagnostic,$(MIN_SELF_LOOP_INFER),MIN_SELF_LOOP_INFER,method); \
	fi; \
	if grep -q -- '--solution $(max_nodes_seed)' "$${dry_run}"; then \
		$(call check_parameter_diagnostic,$(TIMEOUT_SEED),TIMEOUT_SEED (needed by target 'max-nodes-seed'),method); \
	fi; \
	if grep -q 'parallel-fastq-dump' "$${dry_run}"; then \
		:; \
		$(foreach condition,$(running_conditions),\
			$(call check_parameter_diagnostic,\
				$(SRA_$(call toupper,$(condition))),\
				SRA_$(call toupper,$(condition)) \
					(needed by target 'load-fastq'),project);) \
	fi; \
	if grep -q 'scripts/clustering/annotation.py' "$${dry_run}"; then \
		$(call check_parameter_diagnostic,$(LABEL),LABEL (needed by target 'annotation'),project); \
	fi; \
	if grep -q 'scripts/macrostates/knnbs_macrostates.py' "$${dry_run}" \
			|| grep -q 'KNNBS_CENTRALITY_' "$${dry_run}"; then \
		:; \
		$(foreach condition,$(running_conditions),\
			$(call check_knnbs_seed_diagnostic,\
				$(call knnbs_centrality,$(condition)),\
				$(call knnbs_periphery,$(condition)),$(condition));) \
	fi; \
	if [ "$(__check_externals__)" = "true" ]; then \
		if grep -q 'repeat_msk.gtf' "$${dry_run}"; then \
			$(call check_file_diagnostic,$(public_dir)/transcriptome/repeat_msk.gtf,repeat masker annotation); \
		fi; \
		$(call check_command_diagnostic,conda); \
		for env in $$({ \
			grep -oE 'conda run[^;|&]* -n [^ ]+' "$${dry_run}" || true; \
		} | awk '{print $$NF}' | sort -u); do \
			$(call check_conda_env_diagnostic,$${env}); \
		done; \
		if grep -qE '(^|[[:space:]])cellranger count([[:space:]]|$$)' "$${dry_run}"; then \
			$(call check_command_diagnostic,cellranger); \
		fi; \
		if grep -q -- '--graph-formats' "$${dry_run}"; then \
			$(call check_command_diagnostic,dot); \
		fi; \
	fi; \
	if [ "$${missing}" -ne 0 ]; then \
		$(call check_failure,check failed for target '$(TARGET)'); \
		$(print_check_reports); \
		exit 1; \
	fi; \
	$(call check_success,check passed for target '$(TARGET)'); \
	$(print_check_reports)

.PHONY: dry-run
dry-run: ## display modules required to build TARGET without executing them
	@if [ -z "$(TARGET)" ]; then \
		$(call print_error,missing TARGET \(usage: make dry-run TARGET=<module>\)); \
	fi
	$(nested_make) --dry-run LOGGING=false __$(TARGET) LOGFILE="$(LOGFILE)"

##@ Clean

.PHONY: clean
clean: ## clear cache
	find . -name "\*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf "{}" \;
	find . -type d -name "cache" -exec rm -rf "{}" \;

.PHONY: mrproper
mrproper: ## clear cache and public/private data
	find . -name "\*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf "{}" \;
	find . -type d -name "cache" -exec rm -rf "{}" \;
	test -n "$(results)" && test "$(results)" != "/"
	rm -rf $(results)
	mkdir -p $(results)
	[ ! -d $(public_dir)/transcriptome ] || find $(public_dir)/transcriptome \
		! -name "repeat_msk.gtf" -type f -exec rm -f "{}" \;

##@ Download

.PHONY: load-genome __load-genome
load-genome: ## download the reference genome
	$(call run_logged,load-genome)
__load-genome: $(genome_ref)

.PHONY: load-fastq __load-fastq
load-fastq: ## download FASTQ files
	$(call run_logged,load-fastq)
__load-fastq: $(fastq_target)

.PHONY: load-signatures __load-signatures
load-signatures: ## download phenotype-related signatures
	$(call run_logged,load-signatures)
__load-signatures: $(lastword $(signatures))

.PHONY: load-cc __load-cc
load-cc: ## download cell-cycle markers
	$(call run_logged,load-cc)
__load-cc: $(cc_markers)

.PHONY: load-go __load-go
load-go: ## download Gene Ontology resources
	$(call run_logged,load-go)
__load-go: $(go_basic) $(go_organism) $(gene2go)

.PHONY: load-dorothea __load-dorothea
load-dorothea: ## download DoRothEA through the legacy decoupler wrapper
	$(call run_logged,load-dorothea)
__load-dorothea: $(dorothea_legacy)

##@ Alignment/Counting

.PHONY: alignment __alignment
alignment: ## run the selected alignment/counting backend
	$(call run_logged,alignment)
__alignment: $(alignment_target)

.PHONY: cellranger __cellranger
cellranger: ## run Cell Ranger for alignment and counting
	$(call run_logged,cellranger)
__cellranger: $(cellranger_target)

.PHONY: star __star
star: ## run STAR for alignment and counting
	$(call run_logged,star)
__star: $(star_target)

.PHONY: qc __qc
qc: ## prepare STAR outputs for downstream spliced/unspliced counting
	$(call run_logged,qc)
__qc: $(qc_target)

.PHONY: velocyto __velocyto
velocyto: ## run Velocyto for spliced and unspliced counting
	$(call run_logged,velocyto)
__velocyto: $(velocyto_target)

##@ Preprocessing

.PHONY: filtering __filtering
filtering: ## filter low-quality cells and genes, and optionally assign cell-cycle phases
	$(call run_logged,filtering)
__filtering: $(filtering_target)

.PHONY: normalization __normalization
normalization: ## normalize counts and optionally correct for cell-cycle effects
	$(call run_logged,normalization)
__normalization: $(normalization_target)

##@ Clustering

.PHONY: clustering __clustering
clustering: ## cluster cells after dimensionality reduction, with optional integration
	$(call run_logged,clustering)
__clustering: $(clustering_target)

.PHONY: dea __dea
dea: ## identify cluster-specific upregulated genes for marker detection
	$(call run_logged,dea)
__dea: $(dea_target)

.PHONY: scoring __scoring
scoring: ## score phenotype-related signatures to support cluster annotation
	$(call run_logged,scoring)
__scoring: $(scoring_target)

.PHONY: goea __goea
goea: ## perform Gene Ontology enrichment analysis to support cluster annotation
	$(call run_logged,goea)
__goea: $(goea_target)

.PHONY: annotation __annotation
annotation: ## assign names to cell clusters
	$(call run_logged,annotation)
__annotation: $(annotation_target)

##@ Trajectory inference

.PHONY: velocity __velocity
velocity: ## estimate RNA velocity to infer cell-state transitions
	$(call run_logged,velocity)
__velocity: $(velocity_target)

.PHONY: potency __potency
potency: ## estimate cell differentiation potential
	$(call run_logged,potency)
__potency: $(potency_target)

##@ Macrostate characterization

.PHONY: cotan __cotan
cotan: ## estimate macrostates from zero-count co-expression
	$(call run_logged,cotan)
__cotan: $(cotan_target)

.PHONY: cellrank __cellrank
cellrank: ## estimate macrostates using similarity-, potency-, and RNA-velocity-based kernels
	$(call run_logged,cellrank)
__cellrank: $(cellrank_target)

.PHONY: stream __stream
stream: ## estimate macrostates using an elastic principal graph
	$(call run_logged,stream)
__stream: $(stream_target)

.PHONY: knnbs __knnbs
knnbs: ## estimate macrostates using k-nearest-neighbors-based subclustering
	$(call run_logged,knnbs)
__knnbs: $(knnbs_target)

.PHONY: macrostates __macrostates
macrostates: ## define groups of cells sharing similar phenotypic profiles according to MACROSTATE_METHOD
	$(call run_logged,macrostates)
__macrostates: $(macrostates_target)

##@ Binarization

.PHONY: bin-cells __bin-cells
bin-cells: ## binarize cells using gene-specific distributions from ScBoolSeq
	$(call run_logged,bin-cells)
__bin-cells: $(bin_cells)

.PHONY: bin-macrostates __bin-macrostates
bin-macrostates: ## binarize macrostates by aggregating ScBoolSeq-binarized cells using voting rules
	$(call run_logged,bin-macrostates)
__bin-macrostates: $(bin_macrostates)

.PHONY: bin-dea __bin-dea
bin-dea: ## binarize macrostates using differential expression analysis
	$(call run_logged,bin-dea)
__bin-dea: $(bin_dea)

.PHONY: bin-consensus __bin-consensus
bin-consensus: ## binarize macrostates by combining ScBoolSeq and DEA results
	$(call run_logged,bin-consensus)
__bin-consensus: $(bin_consensus)

.PHONY: binarization __binarization
binarization: ## derive partially defined Boolean states from macrostates according to BIN_METHOD
	$(call run_logged,binarization)
__binarization: $(bin)

##@ Boolean network inference

.PHONY: spec __spec
spec: ## specify Boolean constraints using the BoNesis language
	$(call run_logged,spec)
__spec: $(bonesis_model)

.PHONY: max-nodes-soft __max-nodes-soft
max-nodes-soft: ## maximise nodes without non-reachability and universal constraints (soft constraints)
	$(call run_logged,max-nodes-soft)
__max-nodes-soft: $(max_nodes_soft)

.PHONY: max-consts-soft __max-consts-soft
max-consts-soft: ## maximise strong constants without non-reachability and universal constraints (soft constraints)
	$(call run_logged,max-consts-soft)
__max-consts-soft: $(max_consts_soft)

.PHONY: max-nodes-relaxed __max-nodes-relaxed
max-nodes-relaxed: ## maximise nodes without universal constraints (relaxed constraints)
	$(call run_logged,max-nodes-relaxed)
__max-nodes-relaxed: $(max_nodes_relaxed)

.PHONY: max-nodes-seed __max-nodes-seed
max-nodes-seed: ## maximise nodes (hard constraints, stage 1)
	$(call run_logged,max-nodes-seed)
__max-nodes-seed: $(max_nodes_seed)

.PHONY: max-nodes-lock __max-nodes-lock
max-nodes-lock: ## maximise nodes (hard constraints, stage 2)
	$(call run_logged,max-nodes-lock)
__max-nodes-lock: $(max_nodes_lock)

.PHONY: bn-min __bn-min
bn-min: ## infer a minimum-edge Boolean network with BoNesis (one minimal solution)
	$(call run_logged,bn-min)
__bn-min: $(bn_min)

.PHONY: bn-submin __bn-submin
bn-submin: ## enumerate subset-minimal Boolean network solutions
	$(call run_logged,bn-submin)
__bn-submin: $(bn_submin)

.PHONY: bn-diverse __bn-diverse
bn-diverse: ## sampling of diverse sparsest Boolean network solutions
	$(call run_logged,bn-diverse)
__bn-diverse: $(bn_diverse)

## END HELP ##

## preserve target even if make is killed or interrupted
.PRECIOUS: $(max_nodes_soft)
.PRECIOUS: $(max_consts_soft)
.PRECIOUS: $(max_nodes_seed)
.PRECIOUS: $(max_nodes_lock)
.PRECIOUS: $(dir $(bn_submin))
.PRECIOUS: $(dir $(bn_diverse))

$(bin_cells)&: export OPENBLAS_NUM_THREADS = $(open_allocated_cpu)
$(bin_cells)&: export OMP_NUM_THREADS = $(open_allocated_cpu)

## BEGIN RULES ##

$(genome_ref):
	$(call print_rule,load-genome)
	mkdir -p $(@D)
	wget --quiet --show-progress --progress=bar:force:noscroll -cO $@.tar.gz $(genome_url)
	tar -zxvf $@.tar.gz -C $(@D)
	[ -f $@/genes/genes.gtf.gz ] && gunzip $@/genes/genes.gtf.gz

$(star_index): | $(genome_ref)
	$(call check_file,$@,STAR genome index)

$(cc_markers):
	$(call print_rule,load-cc)
	mkdir -p $(@D)
	wget --quiet --show-progress --progress=bar:force:noscroll -cO $@ $(cycle_url)

$(word 1,$(signatures)) $(word 2,$(signatures)):
	$(eval FILENAME := $(basename $(notdir $@)))
	$(call print_rule,load-signatures,$(FILENAME))
	mkdir -p $(@D)
	if [ $(FILENAME) = "geiger" ]; then \
		wget --quiet --show-progress --progress=bar:force:noscroll -cO $@ $(geiger_url); \
	else \
		wget --quiet --show-progress --progress=bar:force:noscroll -cO $@ $(chambers_url); \
	fi

$(lastword $(signatures)): $(word 1,$(signatures)) $(word 2,$(signatures))
	$(call print_rule,load-signatures,conversion)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/load_signatures.py \
		--list-infile $(firstword $^) \
		--table-infile $(lastword $^) \
		--outfile $@

$(go_basic):
	$(call print_rule,load-go,go_basic)
	mkdir -p $(@D)
	wget --quiet --show-progress --progress=bar:force:noscroll -cO $@ $(go_basic_url)

$(go_organism):
	$(call print_rule,load-go,go_$(ORGANISM))
	mkdir -p $(@D)
	wget --quiet --show-progress --progress=bar:force:noscroll -cO $@ $(go_organism_url)

$(gene2go):
	$(call print_rule,load-go,gene2go)
	mkdir -p $(@D)
	wget --quiet --show-progress --progress=bar:force:noscroll --directory-prefix=$(@D) $(gene2go_url)
	[ -f $@.gz ] && gunzip $@.gz

$(dorothea_legacy):
	$(call print_rule,load-dorothea)
	$(call require_prior_parameters,load-dorothea)
	mkdir -p $(@D)
	$(call conda_run,scbolt-decoupler-legacy) python $(scripts_dir)/utils/load_dorothea_legacy.py \
		--organism $(ORGANISM) \
		--outfile $@

$(results)/%/count/invalid-alignment/.error:
	$(call print_rule,alignment,$*)
	$(call require_choice,ALIGNMENT_TOOL,cellranger star,alignment)

$(results)/%/mstates/invalid-method/.error:
	$(call print_rule,macrostates,$*)
	$(call require_choice,MACROSTATE_METHOD,cotan cellrank stream knnbs,macrostates)

$(bin_method_error):
	$(call print_rule,binarization)
	$(call require_binarization_parameters)

define compute_rules_for_conditions

$(fastq_$(1)):
	$(call print_rule,load-fastq,$(1))
	$(call check_parameter,$(SRA_$(call toupper, $(1))),SRA_$(call toupper, $(1)) \(needed by target 'load-fastq'\))
	sample_naming="$(1)"
	lane=0
	rm -rf $(tmpdir)/$(1)/fastq && mkdir -p $(tmpdir)/$(1)/fastq
	for id in $$(SRA_$(call toupper, $(1)))
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

$(cellranger_$(1)): $(fastq_$(1)) $(genome_ref)
	$(call print_rule,cellranger,$(1))
	mkdir -p $(tmpdir)/cellranger $$(@D)
	(
		cd $(tmpdir)/cellranger
		cellranger count --id=$(1) \
			--fastqs=$$(realpath $$(firstword $$^)) \
			--transcriptome=$$(realpath $$(lastword $$^)) \
			--create-bam true \
			--localcores=$(JOBS) \
			--localmem=$(MEMORY)
	)
	mv $(tmpdir)/cellranger/$(1)/* $$(@D)
	rm -rf $(tmpdir)/cellranger/$(1)

$(star_$(1))&: $(fastq_$(1)) $(star_index)
	$(call print_rule,star,$(1))
	$(call require_choice,ALIGNMENT_TOOL,cellranger star,star)
	$(call require_positive_integer,STAR_CB_LEN)
	$(call require_positive_integer,STAR_UMI_LEN)
	if [ -n "$(STAR_WHITELIST)" ]; then \
		$(call check_file,$(STAR_WHITELIST),STAR_WHITELIST); \
	fi
	mkdir -p $(tmpdir)/star/$(1) $$(@D)
	fastq_dir="$$(realpath $$(firstword $$^))"
	r1_files="$$$$(find "$$$${fastq_dir}" -name '*_R1_001.fastq.gz' | sort | paste -sd, -)"
	r2_files="$$$$(find "$$$${fastq_dir}" -name '*_R2_001.fastq.gz' | sort | paste -sd, -)"
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

ifeq ($(ALIGNMENT_TOOL),cellranger)
$(velocyto_$(1)): $(cellranger_$(1)) $(genome_ref)
	$(call print_rule,velocyto,$(1))
	$(call require_choice,ALIGNMENT_TOOL,cellranger star,velocyto)
	$(call check_file,$(public_dir)/transcriptome/repeat_msk.gtf,repeat_msk.gtf)
	$(call conda_run,scbolt-velocyto) velocyto run10x \
		-m $(public_dir)/transcriptome/repeat_msk.gtf \
		--samtools-threads $(JOBS) --samtools-memory $(MEMORY) \
		$$(dir $$(firstword $$^)) $$(lastword $$^)/genes/genes.gtf
	mkdir -p $$(@D)
	mv $$(<D)/velocyto/cellranger.loom $$(@D)/counts.loom
	rm -rf $$(<D)/velocyto
	$(call print_debug,standardizing gene names and converting loom to h5ad)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/adata_conversion.py \
		$$(@D)/counts.loom $$@ --from loom --to h5ad \
		--remove-positions --sort --standardization
else ifeq ($(ALIGNMENT_TOOL),star)
$(qc_$(1)): $(star_$(1))
	$(call print_rule,qc,$(1))
	$(call print_task,filtering STAR barcodes)
	$(call require_star_barcode_filter_parameters,qc)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/alignment/filter_barcodes.py \
		$$(<D)/Solo.out/matrix.mtx \
		$$(<D)/Solo.out/barcodes.tsv \
		$$(@D)/filtered_barcodes.tsv \
		--method $(STAR_BARCODE_FILTER) \
		$(if $(STAR_MIN_UMI),--min-umi $(STAR_MIN_UMI),) \
		$(if $(STAR_TOP_BARCODES),--top-barcodes $(STAR_TOP_BARCODES),)
	$(call print_task,preparing STAR BAM for velocyto)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-velocyto) python $(scripts_dir)/alignment/retag_bam.py \
		$$(<D)/Aligned.sortedByCoord.out.bam $$@.tmp \
		--barcodes $$(@D)/filtered_barcodes.tsv \
		--tag CR:CB UR:UB \
		--jobs $(JOBS)
	mv $$@.tmp $$@

$(velocyto_$(1)): $(qc_$(1)) $(genome_ref)
	$(call print_rule,velocyto,$(1))
	$(call require_choice,ALIGNMENT_TOOL,cellranger star,velocyto)
	$(call require_star_barcode_filter_parameters,velocyto)
	$(call check_file,$(public_dir)/transcriptome/repeat_msk.gtf,repeat_msk.gtf)
	mkdir -p $(tmpdir)/velocyto/$(1)
	$(call print_task,estimating spliced and unspliced counts with velocyto)
	$(call conda_run,scbolt-velocyto-test) velocyto run \
		-m $(public_dir)/transcriptome/repeat_msk.gtf \
		-b $$(<D)/filtered_barcodes.tsv \
		-o $(tmpdir)/velocyto/$(1) \
		-e star \
		--samtools-threads $(JOBS) --samtools-memory $(MEMORY) \
		$$(firstword $$^) $$(lastword $$^)/genes/genes.gtf
	mkdir -p $$(@D)
	mv $(tmpdir)/velocyto/$(1)/star.loom $$(@D)/counts.loom
	rm -rf $(tmpdir)/velocyto/$(1)
	$(call print_debug,standardizing gene names and converting loom to h5ad)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/adata_conversion.py \
		$$(@D)/counts.loom $$@ --from loom --to h5ad \
		--remove-positions --sort --standardization
endif

$(filtering_$(1)): $(velocyto_$(1)) $(if $(filter mouse,$(ORGANISM)),$(cc_markers))
	$(call print_rule,filtering,$(1))
	$(require_filtering_parameters)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/preprocessing/filtering.py \
		$$(firstword $$^) $$@ $(if $(filter mouse,$(ORGANISM)),--marker $$(lastword $$^)) \
		--gene-dropout $(GENE_DROPOUT) --gene-expression $(GENE_EXPRESSION) --gene-counts $(GENE_COUNTS) \
		--cell-dropout $(CELL_DROPOUT) --cell-expression $(CELL_EXPRESSION) --cell-reads $(CELL_READS) \
		--mad-deviation $(MAD_DEVIATION) $(norm_mad) --mt $(MT) \
		--hvg $(HVG) $(filter_non_hvg)

$(normalization_$(1)): $(filtering_$(1))
	$(call print_rule,normalization,$(1))
	$(call require_cc_correction,normalization)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/preprocessing/normalization.py \
		$$< $$@ $(correction) --jobs $(JOBS)

$(clustering_$(1)): $(normalization_$(1))
	$(call print_rule,clustering,$(1))
	$(require_clustering_parameters)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/clustering/clustering.py $$< $$@ \
		--layer correct --adjacency knn --embedding umap \
		--pca-dimension $(DIM_PCA) \
		--clustering-dimension $(DIM_CLUSTERING) \
		--embedding-dimension $(DIM_EMBEDDING) \
		$(pca_only_hvg) \
		--neighbors $(NEIGHBORS) --metric $(METRIC) \
		--resolution $(RESOLUTION) --min-dist $(MIN_DIST) --spread $(SPREAD) \
		--seed $(SEED)
	$(call print_task,plotting embedding colored by cell-cycle phase)
	$(call conda_run,scbolt-core) python $(fig_dir)/plot_embedding.py $(fig_dir)/cc.json \
		--infile $$@ --outfile $$(@D)/cc.pdf \
		--use-rep $(USE_REP)

$(annotation_$(1)): $(annotation_integrated) $(clustering_$(1))
	$(call print_rule,annotation,$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/pipe_its.py $$^ --outfiles $$@ \
		--labels $(1) --obs-label condition --obs $(LABEL_COL)
	$(call print_task,plotting embedding colored by labels)
	$(call conda_run,scbolt-core) python $(fig_dir)/plot_embedding.py $(fig_dir)/generic.json \
		--infile $$@ --outfile $$(@D)/labels.pdf \
		--obs $(LABEL_COL) --use-rep $(USE_REP)

$(velocity_$(1)): $(annotation_$(1))
	$(call print_rule,velocity,$(1))
	$(call require_velocity_parameters)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-velocity) python $(scripts_dir)/trajectories/velocity.py $$< $$@ \
		--layer counts --cluster label --moment-dimension $(DIM_MOMENT) \
		$(velocity_only_hvg) --mode $(SMM_MODE) --embedding umap --jobs $(JOBS)

$(potency_$(1)): $(annotation_$(1))
	$(call print_rule,potency,$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-potency) python $(scripts_dir)/trajectories/potency.py $$< $$(@D) \
		--csv $$(notdir $$@) --h5ad $$(basename $$(notdir $$@)).h5ad \
		--layer counts --cluster label --batch-size $(BATCH_SIZE) --smooth-batch-size $(SMOOTH_BATCH_SIZE) \
		--organism $(ORGANISM) --embedding umap --seed $(SEED) --jobs $(JOBS)

$(cotan_$(1))&: $(annotation_$(1))
	$(call print_rule,cotan,$(1))
	$(call require_bool,COTAN_ONLY_HVG,cotan)
	mkdir -p $$(@D) $(tmpdir)/$(1)/cotan
	$(call print_debug,loading file $$< \(layer 'matrix'\))
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/adata_conversion.py \
		$$< $(tmpdir)/$(1)/cotan/barcts.csv --from h5ad --to csv \
		--layer matrix $(cotan_only_hvg)
	$(call print_debug,transposing counts matrix)
	ruby -rcsv -e 'puts CSV.parse(STDIN).transpose.map &:to_csv' \
		< $(tmpdir)/$(1)/cotan/barcts.csv \
		> $(tmpdir)/$(1)/cotan/gencts.csv
	$(call conda_run,scbolt-cotan) Rscript $(scripts_dir)/macrostates/cotan_macrostates.R \
		--infile $(tmpdir)/$(1)/cotan/gencts.csv --outfile $$(@D)/cotan.RDS --csv $$(lastword $$(cotan_$(1))) \
		--sep , --name $(1) --max-iterations $(MAX_ITER) --method $(COTAN_METHOD) --min-ude 0.3 --jobs $(JOBS)
	sed -i '1 i\,macrostate' $$(lastword $$(cotan_$(1)))
	$(call print_debug,adding cotan macrostates to AnnData)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/add_to_anndata.py \
		$$< $$(firstword $$(cotan_$(1))) \
		--csv $$(lastword $$(cotan_$(1))) \
		--axis 0 --sep , --type category
	$(call print_task,plotting embedding colored by cotan macrostates)
	$(call conda_run,scbolt-core) python $(fig_dir)/plot_embedding.py $(fig_dir)/macrostates.json \
		--infile $$(firstword $$(cotan_$(1))) \
		--outfile $$(@D)/umap_cotan.pdf \
		--use-rep $(USE_REP)

$(cellrank_$(1))&: $(velocity_$(1)) $(potency_$(1))
	$(call print_rule,cellrank,$(1))
	$(call require_cellrank_parameters)
	mkdir -p $$(@D) $(tmpdir)/$(1)/cellrank
	$(call print_debug,adding potency scores to AnnData)
	awk -F, -v txt="score" 'FNR==1{for(col=1;$$$$col!=txt;col++);next} {print $$$$1 "," $$$$col}' \
		$$(lastword $$^) > $(tmpdir)/$(1)/cellrank/potency_scores.csv
	sed -i '1 i\,cytotrace_score' $(tmpdir)/$(1)/cellrank/potency_scores.csv
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/add_to_anndata.py \
		$$(firstword $$^) $(tmpdir)/$(1)/cellrank/kernels.h5ad \
		--csv $(tmpdir)/$(1)/cellrank/potency_scores.csv \
		--axis 0 --sep , --type float
	$(call conda_run,scbolt-cellrank) python $(scripts_dir)/macrostates/cellrank_macrostates.py \
		$(tmpdir)/$(1)/cellrank/kernels.h5ad $$(firstword $$(cellrank_$(1))) \
		--csv $$(lastword $$(cellrank_$(1))) \
		--obs $(LABEL_COL) --method $(CELLRANK_METHOD) \
		--cytotrace-score cytotrace_score --scvelo-velocity velocity \
		--states $(STATES) --initial-states $(INITIAL_STATES) --terminal-states $(TERMINAL_STATES) \
		--stability $(CELLRANK_STABILITY) --alpha $(CELLRANK_ALPHA) --size $(MACROSTATE_SIZE) --seed $(SEED)

$(stream_$(1))&: $(annotation_$(1))
	$(call print_rule,stream,$(1))
	$(call require_stream_parameters)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-stream) python $(scripts_dir)/macrostates/stream_macrostates.py \
		$$< $$(firstword $$(stream_$(1))) \
		--csv $$(lastword $$(stream_$(1))) \
		--use-rep $(USE_REP) --obs $(LABEL_COL) \
		--clustering $(CLUSTERING_METHOD) --cluster-number $(CLUSTER_NUMBER) \
		--alpha $(ALPHA_EPG) --mu $(MU_EPG) --lambda $(LAMBDA_EPG) \
		$(extend_epg) \
		$(if $(filter $(EXTEND_EPG),true),--extend-mode $(EXTEND_MODE),) \
		$(if $(filter $(EXTEND_EPG),true),--extend-parameter $(EXTEND_PARAMETER),) \
		$(prune_epg) \
		$(if $(filter $(PRUNE_EPG),true),--collapse-parameter $(COLLAPSE_PARAMETER),) \
		--size $(MACROSTATE_SIZE) --jobs $(JOBS)

ifeq ($(or $(call knnbs_centrality,$(1)),$(call knnbs_periphery,$(1))),)
$(knnbs_$(1))&: $(annotation_$(1))
	$(call print_error,required parameter not defined: KNNBS_CENTRALITY_$(call toupper,$(1)) \
		or KNNBS_PERIPHERY_$(call toupper,$(1)) \(needed by target 'knnbs'\))
else
$(knnbs_$(1))&: $(annotation_$(1))
	$(call print_rule,knnbs,$(1))
	$(call require_knnbs_parameters)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/macrostates/knnbs_macrostates.py \
		$$< $$(firstword $$(knnbs_$(1))) \
		--csv $$(lastword $$(knnbs_$(1))) \
		--obs $(LABEL_COL) --embedding $(KNNBS_EMBEDDING) --neighbors $(KNNBS_NEIGHBORS) \
		$(knnbs_dimension) --metric $(METRIC) --size $(MACROSTATE_SIZE) \
		$(if $(call knnbs_centrality,$(1)),--centrality $(call knnbs_centrality,$(1)),) \
		$(if $(call knnbs_periphery,$(1)),--periphery $(call knnbs_periphery,$(1)),) \
		--jobs $(JOBS)
	$(call print_task,plotting embedding colored by knnbs macrostates)
	$(call conda_run,scbolt-core) python $(fig_dir)/plot_embedding.py $(fig_dir)/macrostates.json \
		--infile $$(firstword $$(knnbs_$(1))) \
		--outfile $$(@D)/knnbs.pdf \
		--use-rep $(USE_REP)
endif

endef

define compute_rules_for_references

$(dea_$(1))&: $(clustering_$(1))
	$(call print_rule,dea,$(1))
	$(call require_dea_parameters)
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/clustering/markers.py \
		$$< $(firstword $(dea_$(1))) \
		--xlsx $(lastword $(dea_$(1))) \
		--cluster leiden --layer log-norm --is-log \
		--logfc $(LOGFC) --alpha $(ALPHA) --correction $(CORRECTION)

$(scoring_$(1)): $(clustering_$(1)) $(lastword $(signatures)) $(lastword $(dea_$(1)))
	$(call print_rule,scoring,$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/clustering/scoring.py \
		$$^ $$@ --cluster leiden --ignore-sheets background

$(goea_basic_$(1)): $(lastword $(dea_$(1))) $(go_basic) $(gene2go)
	$(call print_rule,goea,go_basic/$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/clustering/goea.py $$< $$@ \
		--background background --go $$(word 2,$$^) --gene2go $$(lastword $$^)

$(goea_organism_$(1)): $(lastword $(dea_$(1))) $(go_organism) $(gene2go)
	$(call print_rule,goea,go_$(ORGANISM)/$(1))
	mkdir -p $$(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/clustering/goea.py $$< $$@ \
		--background background --go $$(word 2,$$^) --gene2go $$(lastword $$^)

endef

$(clustering_integrated): $(foreach condition,$(conditions),$(normalization_$(condition)))
	$(call print_rule,clustering,integrated)
	$(require_clustering_parameters)
	mkdir -p $(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/clustering/integration.py \
		$^ \
		--outfile $@ --labels $(conditions) \
		--layer correct --adjacency knn --integration $(INTEGRATION) --embedding umap \
		--pca-dimension $(DIM_PCA) --clustering-dimension $(DIM_CLUSTERING) --embedding-dimension $(DIM_EMBEDDING) \
		$(if $(filter $(PCA_ONLY_HVG),true),--hvg $(HVG),) \
		--neighbors $(NEIGHBORS) --metric $(METRIC) --resolution $(RESOLUTION) \
		--min-dist $(MIN_DIST) --spread $(SPREAD) --seed $(SEED) --jobs $(JOBS)

$(annotation_integrated): $(clustering_integrated)
	$(call print_rule,annotation,integrated)
	if [ -z "$(LABEL)" ]; then \
			$(call print_error,required parameter not defined: LABEL \(needed by target 'annotation'\). \
				Review DEA/GOEA/signature outputs and set LABEL in your parameter file); \
	fi
	mkdir -p $(@D)
	$(call conda_run,scbolt-core) python $(scripts_dir)/clustering/annotation.py $< $@ \
		--obs leiden --new-obs $(LABEL_COL) --labels $(label_map)
	$(call print_task,plotting embedding colored by labels)
	$(call conda_run,scbolt-core) python $(fig_dir)/plot_embedding.py $(fig_dir)/generic.json \
		--infile $@ --outfile $(@D)/labels.pdf \
		--obs $(LABEL_COL) --use-rep $(USE_REP)

ifdef SCBOOLSEQ_HVG_METHOD
$(bin_cells)&: \
    $(if $(filter-out $(words $(CONDITIONS)),1),$(annotation_integrated),$(annotation_$(conditions)))
	$(call print_rule,bin-cells)
	$(call require_optional_hvg_method,SCBOOLSEQ_HVG_METHOD,SCBOOLSEQ_TOP_HVG)
	$(call require_bin_cells_parameters)
	mkdir -p $(@D) $(tmpdir)/bin/cell
	$(call print_task,estimating top$(if $(SCBOOLSEQ_TOP_HVG), $(SCBOOLSEQ_TOP_HVG),) \
		highly variable genes with $(SCBOOLSEQ_HVG_METHOD))
	$(call conda_run,scbolt-core) python $(scripts_dir)/preprocessing/hvg.py \
		$(lastword $^) $(tmpdir)/bin/cell/top_genes.txt \
		--method $(SCBOOLSEQ_HVG_METHOD) \
		$(scboolseq_layer) \
		$(if $(SCBOOLSEQ_TOP_HVG),--hvg $(SCBOOLSEQ_TOP_HVG),) \
		$(batch)
	$(call conda_run,scbolt-scboolseq) python $(scripts_dir)/binarization/bin_cells_scboolseq.py \
		$< --outfile $(firstword $(bin_cells)) \
		--bin $(shell echo $@ | sed "s/.h5ad/.csv/") \
		--statistics $(lastword $(bin_cells)) \
		--layer log-norm \
		--quantile $(UNIMODAL_QUANTILE) \
		$(zeroes_are_zeroes) \
		--filter-genes $(tmpdir)/bin/cell/top_genes.txt
	$(call print_task,plotting embedding colored by binarization percentage)
	$(call conda_run,scbolt-core) python $(fig_dir)/plot_embedding.py $(fig_dir)/bin.json \
		--infile $(firstword $(bin_cells)) \
		--outfile $(@D)/pct_bin.pdf \
		--use-rep $(USE_REP)
else
$(bin_cells)&: \
    $(if $(filter-out $(words $(CONDITIONS)),1),$(annotation_integrated),$(annotation_$(conditions)))
	$(call print_rule,bin-cells)
	$(call require_bin_cells_parameters)
	mkdir -p $(@D)
	$(call conda_run,scbolt-scboolseq) python $(scripts_dir)/binarization/bin_cells_scboolseq.py \
		$< --outfile $(firstword $(bin_cells)) \
		--bin $(shell echo $@ | sed "s/.h5ad/.csv/") \
		--statistics $(lastword $(bin_cells)) \
		--layer log-norm \
		--quantile $(UNIMODAL_QUANTILE) \
		$(zeroes_are_zeroes)
	$(call print_task,plotting embedding colored by binarization percentage)
	$(call conda_run,scbolt-core) python $(fig_dir)/plot_embedding.py $(fig_dir)/bin.json \
		--infile $(firstword $(bin_cells)) \
		--outfile $(@D)/pct_bin.pdf \
		--use-rep $(USE_REP)
endif

$(bin_macrostates): $(firstword $(bin_cells)) \
    $(foreach condition,$(conditions),$(lastword $(macrostates_$(condition))))
	$(call print_rule,bin-macrostates)
	$(call require_bin_macrostates_parameters)
	mkdir -p $(@D) $(tmpdir)/integrated/bin/aggr
	$(call print_debug,adding macrostates to AnnData)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/add_to_anndata.py \
		$(firstword $^) $(tmpdir)/integrated/bin/aggr/mcts.h5ad \
		--csv $(filter-out $<, $^) \
		$(if $(filter-out $(words $(CONDITIONS)),1),--labels $(conditions),) \
		$(if $(filter-out $(words $(CONDITIONS)),1),--label-column condition,) \
		$(if $(filter-out $(words $(CONDITIONS)),1),--add-prefix macrostate,) \
		--axis 0 --sep , --type category
	$(call conda_run,scbolt-core) python $(scripts_dir)/binarization/bin_clusters_scboolseq.py \
		$(tmpdir)/integrated/bin/aggr/mcts.h5ad $@ \
		--counts $(@D)/counts_bin.csv \
		--layer bin --distribution distribution --cluster macrostate \
		--use-rep $(USE_REP) \
		--nans-threshold $(NANS_THRESHOLD) \
		--bimodal-threshold $(BIMODAL_THRESHOLD) \
		--zeroinf-threshold $(ZEROINF_THRESHOLD) \
		--unimodal-threshold $(UNIMODAL_THRESHOLD)
	$(call print_task,plotting embedding colored by macrostates)
	$(call conda_run,scbolt-core) python $(fig_dir)/plot_embedding.py $(fig_dir)/macrostates.json \
		--infile $(tmpdir)/integrated/bin/aggr/mcts.h5ad \
		--outfile $(@D)/macrostates.pdf \
		--use-rep $(USE_REP)

ifdef DEA_HVG_METHOD
$(bin_dea): \
    $(if $(filter-out $(words $(CONDITIONS)),1),$(annotation_integrated),$(annotation_$(conditions))) \
    $(foreach condition,$(conditions),$(lastword $(macrostates_$(condition))))
	$(call print_rule,bin-dea)
	$(call require_optional_hvg_method,DEA_HVG_METHOD,DEA_TOP_HVG)
	$(call require_bin_dea_parameters)
	mkdir -p $(@D) $(tmpdir)/integrated/bin/dea
	$(call print_debug,adding macrostates to AnnData)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/add_to_anndata.py \
		$(firstword $^) $(tmpdir)/integrated/bin/dea/mcts.h5ad \
		--csv $(filter-out $<, $^) \
		$(if $(filter-out $(words $(CONDITIONS)),1),--labels $(conditions),) \
		$(if $(filter-out $(words $(CONDITIONS)),1),--label-column condition,) \
		$(if $(filter-out $(words $(CONDITIONS)),1),--add-prefix macrostate,) \
		--axis 0 --sep , --type category
	$(call print_task,estimating top$(if $(DEA_TOP_HVG), $(DEA_TOP_HVG),) highly variable genes with $(DEA_HVG_METHOD))
	$(call conda_run,scbolt-core) python $(scripts_dir)/preprocessing/hvg.py \
		$(firstword $^) $(tmpdir)/bin/dea/top_genes.txt \
		--method $(DEA_HVG_METHOD) \
		$(dea_layer) \
		$(if $(DEA_TOP_HVG),--hvg $(DEA_TOP_HVG),) \
		$(batch)
	$(call conda_run,scbolt-core) python $(scripts_dir)/binarization/bin_dea.py $(tmpdir)/integrated/bin/dea/mcts.h5ad $@ \
		--cluster macrostate --layer log-norm --is-log --method wilcoxon --use-rep $(USE_REP) \
		--logfc $(BIN_LOGFC) --alpha $(BIN_ALPHA) --correction $(BIN_CORRECTION) \
		--filter-genes $(tmpdir)/bin/dea/top_genes.txt
	$(call print_task,plotting embedding colored by macrostates)
	$(call conda_run,scbolt-core) python $(fig_dir)/plot_embedding.py $(fig_dir)/macrostates.json \
		--infile $(tmpdir)/integrated/bin/dea/mcts.h5ad \
		--outfile $(@D)/macrostates.pdf \
		--use-rep $(USE_REP)
else
$(bin_dea): \
    $(if $(filter-out $(words $(CONDITIONS)),1),$(annotation_integrated),$(annotation_$(conditions))) \
    $(foreach condition,$(conditions),$(lastword $(macrostates_$(condition))))
	$(call print_rule,bin-dea)
	$(call require_bin_dea_parameters)
	mkdir -p $(@D) $(tmpdir)/integrated/bin/dea
	$(call print_debug,adding macrostates to AnnData)
	$(call conda_run,scbolt-core) python $(scripts_dir)/utils/add_to_anndata.py \
		$(firstword $^) $(tmpdir)/integrated/bin/dea/mcts.h5ad \
		--csv $(filter-out $<, $^) \
		$(if $(filter-out $(words $(CONDITIONS)),1),--labels $(conditions),) \
		$(if $(filter-out $(words $(CONDITIONS)),1),--label-column condition,) \
		$(if $(filter-out $(words $(CONDITIONS)),1),--add-prefix macrostate,) \
		--axis 0 --sep , --type category
	$(call conda_run,scbolt-core) python $(scripts_dir)/binarization/bin_dea.py \
		$(tmpdir)/integrated/bin/dea/mcts.h5ad $@ \
		--cluster macrostate --layer log-norm --is-log --method wilcoxon --use-rep $(USE_REP) \
		--logfc $(BIN_LOGFC) --alpha $(BIN_ALPHA) --correction $(BIN_CORRECTION)
	$(call print_task,plotting embedding colored by macrostates)
	$(call conda_run,scbolt-core) python $(fig_dir)/plot_embedding.py $(fig_dir)/macrostates.json \
		--infile $(tmpdir)/integrated/bin/dea/mcts.h5ad \
		--outfile $(@D)/macrostates.pdf \
		--use-rep $(USE_REP)
endif

$(bin_consensus): $(bin_macrostates) $(lastword $(bin_cells)) $(bin_dea)
	$(call print_rule,bin-consensus)
	mkdir -p $(@D) $(tmpdir)/bin/consensus
	$(call print_debug,extracting scBoolSeq distributions)
	col=`head $(word 2, $^) -n 1 \
		| sed "s/,/\n/g" \
		| awk -F, '{printf("%d %s\n", NR-1, $$0)}' \
		| grep Category \
		| awk '{print $$1}'`
	((col++))
	cut -f 1,$$col -d ',' $(word 2, $^) > $(tmpdir)/bin/consensus/distributions.csv
	unset col
	$(call conda_run,scbolt-core) python $(scripts_dir)/binarization/bin_consensus.py \
		--scboolseq $< $(tmpdir)/bin/consensus/distributions.csv --dea $(lastword $^) \
		--outfile $@ --pct-bin $(@D)/pct_bin.csv

ifdef MODEL_HVG_METHOD
$(bonesis_model)&: $(bin) \
    $(if $(filter-out $(words $(CONDITIONS)),1),$(annotation_integrated),$(annotation_$(conditions))) \
    | $(if $(filter dorothea,$(PRIOR_KNOWLEDGE)),$(if $(filter legacy,$(DOROTHEA_API)),$(dorothea_legacy)))
	$(call print_rule,spec)
	$(call require_optional_hvg_method,MODEL_HVG_METHOD,MODEL_TOP_HVG)
	$(call require_prior_parameters,spec)
	$(call check_file,$(YAML_MODEL),YAML_MODEL)
	mkdir -p $(tmpdir)/bonesis/hvg $(@D)
	$(call print_task,estimating top$(if $(MODEL_TOP_HVG), $(MODEL_TOP_HVG),) \
		highly variable genes with $(MODEL_HVG_METHOD))
	$(call conda_run,scbolt-core) python $(scripts_dir)/preprocessing/hvg.py \
		$(lastword $^) $(tmpdir)/bonesis/hvg/top_genes.txt \
		--method $(MODEL_HVG_METHOD) \
		$(model_layer) \
		$(if $(MODEL_TOP_HVG),--hvg $(MODEL_TOP_HVG),) \
		$(batch)
	$(call conda_run,scbolt-bonesis) python $(scripts_dir)/inference/specification.py $(YAML_MODEL) $< \
		--model $(word 1,$(bonesis_model)) --metastates $(word 2,$(bonesis_model)) \
		--important-genes $(word 3,$(bonesis_model)) --mandatory-genes $(word 4,$(bonesis_model)) \
		--filter-genes $(tmpdir)/bonesis/hvg/top_genes.txt \
		--domain $(prior_knowledge) --organism $(ORGANISM) $(dorothea_levels_arg)
	sort -u $(word 3,$(bonesis_model)) -o $(word 3,$(bonesis_model))
	sort -u $(word 4,$(bonesis_model)) -o $(word 4,$(bonesis_model))
else
$(bonesis_model)&: $(bin) \
    | $(if $(filter dorothea,$(PRIOR_KNOWLEDGE)),$(if $(filter legacy,$(DOROTHEA_API)),$(dorothea_legacy)))
	$(call print_rule,spec)
	$(call require_prior_parameters,spec)
	$(call check_file,$(YAML_MODEL),YAML_MODEL)
	mkdir -p $(@D)
	$(call conda_run,scbolt-bonesis) python $(scripts_dir)/inference/specification.py $(YAML_MODEL) $< \
		--model $(word 1,$(bonesis_model)) --metastates $(word 2,$(bonesis_model)) \
		--important-genes $(word 3,$(bonesis_model)) --mandatory-genes $(word 4,$(bonesis_model)) \
		--domain $(prior_knowledge) --organism $(ORGANISM) $(dorothea_levels_arg)
	sort -u $(word 3,$(bonesis_model)) -o $(word 3,$(bonesis_model))
	sort -u $(word 4,$(bonesis_model)) -o $(word 4,$(bonesis_model))
endif

$(max_nodes_soft): $(bonesis_model)
	$(call print_rule,max-nodes-soft)
	$(call require_bonesis_filter_parameters,max-nodes-soft)
	mkdir -p $(@D)
	set +e; \
	$(call trap_inference_interrupt); \
	$(call inference_timeout,$(TIMEOUT_SOFT)) \
		$(call conda_run_inference,scbolt-bonesis) python $(scripts_dir)/inference/inference.py filter-nodes \
		$(word 1,$^) $(word 2,$^) \
		--important-genes $(word 3,$^) --mandatory-genes $(word 4,$^) \
		--asp $(@D)/nodes.sh --solution $@ --status $(@D)/__SOLUTION \
		--domain $(prior_knowledge) --organism $(ORGANISM) $(dorothea_levels_arg) \
		--bonesis-mode soft --max-clause $(MAX_CLAUSE) \
		--canonic $(CANONIC_FILTER) \
		$(if $(strip $(CLINGO_CONFIG_SOFT)),--clingo-configuration $(CLINGO_CONFIG_SOFT)) \
		--clingo-opt-mode $(CLINGO_OPT_MODE_SOFT) \
		--clingo-opt-strategy $(CLINGO_OPT_STRATEGY_SOFT) \
		--jobs $(JOBS_SOFT); \
	exit_status=$$?; \
	trap - INT TERM; \
	set -e; \
	$(call check_inference_status, $(TIMEOUT_SOFT))

$(max_consts_soft): $(bonesis_model) $(max_nodes_soft)
	$(call print_rule,max-consts-soft)
	$(call require_bonesis_filter_parameters,max-consts-soft)
	$(call require_bool,MIN_SELF_LOOP_CONSTS,max-consts-soft)
	mkdir -p $(@D)
	set +e; \
	$(call trap_inference_interrupt); \
	$(call inference_timeout,$(TIMEOUT_CONSTS)) \
		$(call conda_run_inference,scbolt-bonesis) python $(scripts_dir)/inference/inference.py filter-consts \
		$(word 1,$^) $(word 2,$^) \
		--mandatory-genes $(word 4,$^) --filter-grn $(lastword $^) \
		--asp $(@D)/nodes.sh --solution $@ --status $(@D)/__SOLUTION \
		--domain $(prior_knowledge) --organism $(ORGANISM) $(dorothea_levels_arg) \
		--bonesis-mode soft --max-clause $(MAX_CLAUSE) $(min_self_loop_consts) \
		--canonic $(CANONIC_FILTER) \
		$(if $(strip $(CLINGO_CONFIG_CONSTS)),--clingo-configuration $(CLINGO_CONFIG_CONSTS)) \
		--clingo-opt-mode $(CLINGO_OPT_MODE_CONSTS) \
		--clingo-opt-strategy $(CLINGO_OPT_STRATEGY_CONSTS) \
		--jobs $(JOBS_CONSTS); \
	exit_status=$$?; \
	trap - INT TERM; \
	set -e; \
	$(call check_inference_status, $(TIMEOUT_CONSTS))

$(max_nodes_relaxed): $(bonesis_model) $(max_consts_soft)
	$(call print_rule,max-nodes-relaxed)
	$(call require_bonesis_filter_parameters,max-nodes-relaxed)
	mkdir -p $(@D)
	set +e; \
	$(call trap_inference_interrupt); \
	$(call inference_timeout,$(TIMEOUT_RELAXED)) \
		$(call conda_run_inference,scbolt-bonesis) python $(scripts_dir)/inference/inference.py filter-nodes \
		$(word 1,$^) $(word 2,$^) \
		--important-genes $(word 3,$^) --mandatory-genes $(word 4,$^) \
		--filter-grn $(lastword $^) --asp $(@D)/nodes.sh \
		--solution $@ --status $(@D)/__SOLUTION \
		--domain $(prior_knowledge) --organism $(ORGANISM) $(dorothea_levels_arg) \
		--bonesis-mode relaxed --max-clause $(MAX_CLAUSE) \
		--canonic $(CANONIC_FILTER) \
		$(if $(strip $(CLINGO_CONFIG_RELAXED)),--clingo-configuration $(CLINGO_CONFIG_RELAXED)) \
		--clingo-opt-mode $(CLINGO_OPT_MODE_RELAXED) \
		--clingo-opt-strategy $(CLINGO_OPT_STRATEGY_RELAXED) \
		--jobs $(JOBS_RELAXED); \
	exit_status=$$?; \
	trap - INT TERM; \
	set -e; \
	$(call check_inference_status, $(TIMEOUT_RELAXED))

$(max_nodes_seed): $(bonesis_model) $(max_nodes_relaxed)
	$(call print_rule,max-nodes-seed)
	$(call require_bonesis_filter_parameters,max-nodes-seed)
	$(call check_parameter,$(TIMEOUT_SEED),TIMEOUT_SEED (needed by target 'max-nodes-seed'))
	mkdir -p $(@D)
	set +e; \
	$(call trap_inference_interrupt); \
	$(call inference_timeout,$(TIMEOUT_SEED)) \
		$(call conda_run_inference,scbolt-bonesis) python $(scripts_dir)/inference/inference.py filter-nodes \
		$(word 1,$^) $(word 2,$^) \
		--important-genes $(word 3,$^) --mandatory-genes $(word 4,$^) \
		--filter-grn $(lastword $^) --asp $(@D)/nodes.sh \
		--solution $@ --status $(@D)/__SOLUTION \
		--domain $(prior_knowledge) --organism $(ORGANISM) $(dorothea_levels_arg) \
		--bonesis-mode hard --max-clause $(MAX_CLAUSE) \
		--canonic $(CANONIC_FILTER) \
		$(if $(strip $(CLINGO_CONFIG_SEED)),--clingo-configuration $(CLINGO_CONFIG_SEED)) \
		--clingo-opt-mode $(CLINGO_OPT_MODE_SEED) \
		--clingo-opt-strategy $(CLINGO_OPT_STRATEGY_SEED) \
		--jobs $(JOBS_SEED); \
	exit_status=$$?; \
	trap - INT TERM; \
	set -e; \
	$(call check_inference_status, $(TIMEOUT_SEED))

$(max_nodes_lock): $(bonesis_model) $(max_nodes_relaxed) $(max_nodes_seed)
	$(call print_rule,max-nodes-lock)
	$(call require_bonesis_filter_parameters,max-nodes-lock)
	mkdir -p $(@D)
	if [ -f $(dir $(lastword $^))__SOLUTION ] && [ "$$(cat $(dir $(lastword $^))__SOLUTION)" = "_GLOBAL_OPTIMUM" ]; then \
		$(call print_debug,solution already globally optimal: skipping lock optimization); \
		cp $(lastword $^) $@; \
		echo "_GLOBAL_OPTIMUM" > $(@D)/__SOLUTION; \
	else \
		set +e; \
		$(call trap_inference_interrupt); \
		cat $(word 4,$^) $(word 6,$^) | sort -u > $(@D)/mandatory.txt; \
		$(call inference_timeout,$(TIMEOUT_LOCK)) \
			$(call conda_run_inference,scbolt-bonesis) python $(scripts_dir)/inference/inference.py filter-nodes \
			$(word 1,$^) $(word 2,$^) \
			--important-genes $(word 3,$^) --mandatory-genes $(@D)/mandatory.txt \
			--filter-grn $(word 5,$^) --asp $(@D)/nodes.sh \
			--solution $@ --status $(@D)/__SOLUTION \
			--domain $(prior_knowledge) --organism $(ORGANISM) $(dorothea_levels_arg) \
			--bonesis-mode hard --max-clause $(MAX_CLAUSE) \
			--canonic $(CANONIC_FILTER) \
			$(if $(strip $(CLINGO_CONFIG_LOCK)),--clingo-configuration $(CLINGO_CONFIG_LOCK)) \
			--clingo-opt-mode $(CLINGO_OPT_MODE_LOCK) \
			--clingo-opt-strategy $(CLINGO_OPT_STRATEGY_LOCK) \
			--jobs $(JOBS_LOCK); \
		exit_status=$$?; \
		trap - INT TERM; \
		set -e; \
		$(call check_inference_status,$(TIMEOUT_LOCK)); \
	fi

$(bn_min): $(bonesis_model) $(max_nodes_lock)
	$(call print_rule,bn-min)
	$(call require_bonesis_infer_parameters,bn-min)
	$(call require_bool,MIN_SELF_LOOP_INFER,bn-min)
	mkdir -p $(@D)
	$(call conda_run_inference,scbolt-bonesis) python $(scripts_dir)/inference/inference.py min \
		$(word 1,$^) $(word 2,$^) \
		--filter-grn $(lastword $^) \
		--asp $(@D)/min.sh \
		--solution $(basename $@) \
		--domain $(prior_knowledge) \
		--organism $(ORGANISM) $(dorothea_levels_arg) \
		--max-clause $(MAX_CLAUSE) $(min_self_loop_infer) \
		--canonic $(CANONIC_INFER) \
		--clingo-opt-mode $(CLINGO_OPT_MODE_MIN) --jobs 1 \
		--graph-formats $(GRAPH_FORMATS)
		if command -v dot >/dev/null 2>&1; then
		    for file in $(@D)/*.dot; do
		        [ -e "$${file}" ] || continue
		        dot -Tpdf "$${file}" -o "$${file%.dot}.pdf"
		    done
		fi

$(bn_submin)&: $(bonesis_model) $(max_nodes_lock)
	$(call print_rule,bn-submin)
	$(call require_bonesis_infer_parameters,bn-submin)
	$(call check_partial_bn_outputs,$(bn_submin_dir),bn-submin,$@)
	mkdir -p $(bn_submin_dir)
	$(call conda_run_inference,scbolt-bonesis) python $(scripts_dir)/inference/inference.py submin \
		$(word 1,$^) $(word 2,$^) \
		--filter-grn $(lastword $^) \
		--asp $(bn_submin_dir)/submin.sh \
		--solution $(bn_submin_dir) \
		--domain $(prior_knowledge) \
		--organism $(ORGANISM) \
		$(dorothea_levels_arg) \
		--max-clause $(MAX_CLAUSE) \
		--canonic $(CANONIC_INFER) \
		--jobs $(JOBS) \
		$(if $(strip $(INFER_LIMIT)),--limit $(INFER_LIMIT)) \
		--config-formats $(CONFIG_FORMATS) \
		--graph-formats $(GRAPH_FORMATS) \
		--remove-isolated-nodes

$(bn_diverse)&: $(bonesis_model) $(max_nodes_lock)
	$(call print_rule,bn-diverse)
	$(call require_bonesis_infer_parameters,bn-diverse)
	$(call check_partial_bn_outputs,$(bn_diverse_dir),bn-diverse,$@)
	mkdir -p $(bn_diverse_dir)
	$(call conda_run_inference,scbolt-bonesis) python $(scripts_dir)/inference/inference.py diverse \
		$(word 1,$^) $(word 2,$^) \
		--filter-grn $(lastword $^) \
		--asp $(bn_diverse_dir)/diverse.sh \
		--solution $(bn_diverse_dir) \
		--domain $(prior_knowledge) \
		--organism $(ORGANISM) \
		$(dorothea_levels_arg) \
		--max-clause $(MAX_CLAUSE) \
		--canonic $(CANONIC_INFER) \
		--jobs $(JOBS) \
		$(if $(strip $(INFER_LIMIT)),--limit $(INFER_LIMIT)) \
		--config-formats $(CONFIG_FORMATS) \
		--graph-formats $(GRAPH_FORMATS) \
		--remove-isolated-nodes

$(foreach condition,$(conditions),$(eval $(call compute_rules_for_conditions,$(condition))))
$(foreach reference,$(references),$(eval $(call compute_rules_for_references,$(reference))))

## END RULES
