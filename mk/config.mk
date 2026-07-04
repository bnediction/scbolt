__check_externals__ ?= true
HELP ?= false
DEFAULT_CONFIG ?= false
params_optional_mode := $(filter help,$(MAKECMDGOALS))$(if $(filter true,$(HELP)),help)

launch_dir := $(CURDIR)
lib_dir := $(scbolt_root)/lib
scripts_dir := $(scbolt_root)/scripts
fig_dir := $(scbolt_root)/scripts/fig
scbolt_tool := $(scbolt_root)/bin/scbolt-tool
conda_command = $(if $(and $(filter conda,$(backend)),$(CONDA_EXE)),$(CONDA_EXE),$(backend))
SCBOLT_SYSTEM_ENV ?= scbolt-system
SCBOLT_LOGGING_TO_FILE ?= false
conda_base_from_exe = $(patsubst %/condabin/conda,%,$(patsubst %/bin/conda,%,$(1)))
conda_base = $(if $(and $(filter conda,$(backend)),$(CONDA_EXE)),$(call conda_base_from_exe,$(CONDA_EXE)))
python ?= $(if $(and $(conda_base),$(wildcard $(conda_base)/bin/python)),$(conda_base)/bin/python,python3)
scbolt_system_bin = $(if $(conda_base),$(conda_base)/envs/$(SCBOLT_SYSTEM_ENV)/bin)
system_tool = $(if $(wildcard $(scbolt_system_bin)/$(1)),$(scbolt_system_bin)/$(1),$(1))
define wget_download
if [ "$(SCBOLT_LOGGING_TO_FILE)" = "true" ]; then \
	if [ -w /dev/tty ]; then \
		$(call system_tool,wget) --quiet --show-progress --progress=bar:force:noscroll $(1) 2>/dev/tty; \
	else \
		$(call system_tool,wget) --no-verbose $(1); \
	fi; \
elif [ -t 2 ]; then \
	$(call system_tool,wget) --quiet --show-progress --progress=bar:force:noscroll $(1); \
else \
	$(call system_tool,wget) --no-verbose $(1); \
fi
endef
define wget_download_label
if [ -w /dev/tty ]; then \
	$(call system_tool,wget) --quiet --show-progress --progress=bar:force:noscroll $(2) \
		2> >($(call system_tool,awk) -v label="$(1)" 'BEGIN { RS = "\r"; ORS = "\r" } { sub(/^.*[[:space:]]+([0-9]+%)/, label " \\1"); print } END { printf "\n" }' > /dev/tty); \
elif [ "$(SCBOLT_LOGGING_TO_FILE)" = "true" ]; then \
	$(call system_tool,wget) --no-verbose $(2); \
elif [ -t 2 ]; then \
	$(call system_tool,wget) --quiet --show-progress --progress=bar:force:noscroll $(2); \
else \
	$(call system_tool,wget) --no-verbose $(2); \
fi
endef
ifneq ($(wildcard $(scbolt_system_bin)),)
override PATH := $(scbolt_system_bin):$(PATH)
export PATH
endif
define system_shell_functions
command -v awk >/dev/null 2>&1 || awk() { "$(scbolt_tool)" awk "$$@"; }; \
command -v cat >/dev/null 2>&1 || cat() { "$(scbolt_tool)" cat "$$@"; }; \
command -v cp >/dev/null 2>&1 || cp() { "$(scbolt_tool)" cp "$$@"; }; \
command -v du >/dev/null 2>&1 || du() { "$(scbolt_tool)" du "$$@"; }; \
command -v find >/dev/null 2>&1 || find() { "$(scbolt_tool)" find "$$@"; }; \
command -v grep >/dev/null 2>&1 || grep() { "$(scbolt_tool)" grep "$$@"; }; \
command -v realpath >/dev/null 2>&1 || realpath() { "$(scbolt_tool)" realpath "$$@"; }; \
command -v sed >/dev/null 2>&1 || sed() { "$(scbolt_tool)" sed "$$@"; }; \
command -v sort >/dev/null 2>&1 || sort() { "$(scbolt_tool)" sort "$$@"; }; \
command -v timeout >/dev/null 2>&1 || timeout() { "$(scbolt_tool)" timeout "$$@"; }; \
command -v touch >/dev/null 2>&1 || touch() { "$(scbolt_tool)" touch "$$@"; }; \
command -v tr >/dev/null 2>&1 || tr() { "$(scbolt_tool)" tr "$$@"; }; \
command -v wc >/dev/null 2>&1 || wc() { "$(scbolt_tool)" wc "$$@"; };
endef

strip_trailing_slash = $(if $(filter /,$(strip $(1))),/,$(patsubst %/,%,$(strip $(1))))
is_absolute_path = $(filter /%,$(strip $(1)))
resolve_path_from = $(call strip_trailing_slash,\
	$(if $(call is_absolute_path,$(1)),$(1),$(abspath $(strip $(2))/$(strip $(1)))))
resolve_optional_path_from = $(if $(strip $(1)),$(call resolve_path_from,$(1),$(2)))
resolve_path_list_from = $(strip \
	$(foreach path,$(strip $(1)),$(call resolve_path_from,$(path),$(2))))
resolve_user_path_list_var = $(eval override $(1) := \
	$(call resolve_path_list_from,$($(1)),$(call path_origin_base,$(1))))
uniq = $(if $(1),$(firstword $(1)) $(call uniq,$(filter-out $(firstword $(1)),$(1))))

include $(scbolt_root)/mk/default_params.mk

ifeq ($(DEFAULT_CONFIG),true)
override PARAMS := (defaults)
params_dir := $(launch_dir)
else
params_base := $(if $(filter command line,$(origin PARAMS)),$(launch_dir),$(scbolt_root))
override PARAMS := $(call resolve_path_from,$(PARAMS),$(params_base))
params_dir := $(call strip_trailing_slash,$(dir $(PARAMS)))

ifneq ($(params_optional_mode),)
-include $(PARAMS)
else
ifeq ($(wildcard $(PARAMS)),)
$(error parameter file not found: $(PARAMS))
endif
include $(PARAMS)
endif
endif

ifneq ($(origin RUNTIME_BACKEND),undefined)
$(error unsupported RUNTIME_BACKEND; use BACKEND instead)
endif

backend := $(strip $(BACKEND))
ifneq ($(filter $(backend),conda mamba micromamba docker),$(backend))
$(error unsupported BACKEND=$(BACKEND) \(supported values: conda, mamba, micromamba, docker\))
endif

backend_defined_in_params = $(and $(filter-out true,$(DEFAULT_CONFIG)),$(shell \
	if [ -f "$(PARAMS)" ] && grep -Eq '^[[:space:]]*(override[[:space:]]+)?BACKEND[[:space:]]*[:?+!]?=' "$(PARAMS)"; then \
		printf true; \
	fi))
backend_source = $(strip \
	$(if $(filter command line,$(origin BACKEND)),cli,\
	$(if $(backend_defined_in_params),params,\
	$(if $(strip $(SCBOLT_DEFAULT_BACKEND)),$(if $(strip $(SCBOLT_DEFAULT_BACKEND_SOURCE)),$(SCBOLT_DEFAULT_BACKEND_SOURCE),install),default_params.mk))))
backend_version = $(strip $(shell $(backend) --version 2>/dev/null \
	| $(call system_tool,head) -n 1 \
	| $(call system_tool,sed) 's/^[^0-9]*//; s/[[:space:]].*//' || true))
backend_label = $(backend)$(if $(backend_version), ($(backend_version)))
make_label = GNU Make $(MAKE_VERSION)

ifeq ($(strip $(genome_url)),)
ifeq ($(ORGANISM),mouse)
override genome_url := https://cf.10xgenomics.com/supp/cell-exp/refdata-gex-GRCm39-2024-A.tar.gz
else ifeq ($(ORGANISM),human)
override genome_url := https://cf.10xgenomics.com/supp/cell-exp/refdata-gex-GRCh38-2024-A.tar.gz
else
override genome_url :=
endif
endif
ifeq ($(strip $(repeat_msk_url)),)
ifeq ($(ORGANISM),mouse)
override repeat_msk_url := https://hgdownload.soe.ucsc.edu/goldenPath/mm39/database/rmsk.txt.gz
else ifeq ($(ORGANISM),human)
override repeat_msk_url := https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/rmsk.txt.gz
else
override repeat_msk_url :=
endif
endif

path_origin_base = $(if $(filter command line,$(origin $(1))),$(launch_dir),$(params_dir))
resolve_user_path_var = $(eval override $(1) := \
	$(call resolve_optional_path_from,$($(1)),$(call path_origin_base,$(1))))
SCBOLT_PROJECT_ROOT ?=
resolved_scbolt_project_root := $(call resolve_optional_path_from,$(SCBOLT_PROJECT_ROOT),$(launch_dir))
resources_dir_base := $(if $(filter command line,$(origin RESOURCES_DIR)),$(launch_dir),\
	$(if $(strip $(resolved_scbolt_project_root)),$(resolved_scbolt_project_root),$(params_dir)))
override RESOURCES_DIR := $(call resolve_optional_path_from,$(RESOURCES_DIR),$(resources_dir_base))
clingo_named_configs := auto frumpy jumpy tweety handy crafty trendy many
clingo_config_vars := \
	CLINGO_CONFIG_SOFT CLINGO_CONFIG_CONSTS CLINGO_CONFIG_RELAXED \
	CLINGO_CONFIG_SEED CLINGO_CONFIG_LOCK
resolve_clingo_config = $(if $(strip $($(1))),\
	$(if $(filter $(strip $($(1))),$(clingo_named_configs)),,$(call resolve_user_path_var,$(1))))

$(call resolve_user_path_var,PROJECT_DIR)
$(call resolve_user_path_var,SPEC_FILE)
$(call resolve_user_path_var,BINARIZATION_FILE)
$(call resolve_user_path_list_var,COUNT_FILES)
$(call resolve_user_path_list_var,MACROSTATE_FILES)
$(if $(filter $(strip $(PRIOR_KNOWLEDGE)),collectri dorothea),,$(call resolve_user_path_var,PRIOR_KNOWLEDGE))
$(if $(filter $(strip $(GENEINFO_VERSION)),bundled latest),,$(call resolve_user_path_var,GENEINFO_VERSION))
$(call resolve_user_path_var,STAR_WHITELIST)
$(foreach var,$(clingo_config_vars),$(call resolve_clingo_config,$(var)))
old_files_from_params := $(call resolve_path_list_from,$(OLD_FILES),$(call path_origin_base,OLD_FILES))
old_files_from_cli := $(call resolve_path_list_from,$(CLI_OLD_FILES),$(launch_dir))
override OLD_FILES := $(strip $(call uniq,$(old_files_from_params) $(old_files_from_cli)))

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

diagnostic_mode := $(strip \
	$(filter help check config progress dry-run clean module-help __reference-context,$(MAKECMDGOALS)) \
	$(filter __%,$(MAKECMDGOALS)) \
	$(__check_mode) \
	$(if $(filter true,$(HELP)),help))

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

is_positive_integer = $(shell printf '%s\n' "$(strip $(1))" \
	| $(call system_tool,grep) -Eq '^[1-9][0-9]*$$' && echo true || echo false)
define memory_conversion_values
$(strip $(shell $(call system_tool,awk) -v memory="$(strip $(1))" -v jobs="$(strip $(2))" '\
function ceil(value, integer) { \
	integer = int(value); \
	return value > integer ? integer + 1 : integer; \
} \
function unit_label(unit) { \
	if (unit == "kib") return "KiB"; \
	if (unit == "mib") return "MiB"; \
	if (unit == "gib") return "GiB"; \
	if (unit == "tib") return "TiB"; \
	return toupper(unit); \
} \
function unit_multiplier(unit) { \
	if (unit == "kb") return 1000; \
	if (unit == "mb") return 1000000; \
	if (unit == "gb") return 1000000000; \
	if (unit == "tb") return 1000000000000; \
	if (unit == "kib") return 1024; \
	if (unit == "mib") return 1048576; \
	if (unit == "gib") return 1073741824; \
	if (unit == "tib") return 1099511627776; \
	return 0; \
} \
BEGIN { \
	value = memory; \
	gsub(/[[:space:]]/, "", value); \
	lower = tolower(value); \
	if (value == "") exit 1; \
	split("kib mib gib tib kb mb gb tb", units, " "); \
	for (i = 1; i <= 8; i++) { \
		suffix = units[i]; \
		if (lower ~ suffix "$$") { \
			unit = suffix; \
			number = substr(value, 1, length(value) - length(suffix)); \
			break; \
		} \
	} \
	if (unit == "") { \
		unit = "gb"; \
		number = value; \
		bare = 1; \
	} \
	if (number !~ /^[0-9]+([.][0-9]+)?$$/) exit 1; \
	if (number + 0 <= 0) exit 1; \
	if (bare && number !~ /^[0-9]+$$/) exit 1; \
	bytes = (number + 0) * unit_multiplier(unit); \
	canonical = bare ? int(number) "GB" : number unit_label(unit); \
	gb = ceil(bytes / 1000000000); \
	mb = ceil(bytes / 1000000); \
	mb_per_job = ""; \
	if (jobs ~ /^[1-9][0-9]*$$/) { \
		mb_per_job = int(bytes / ((jobs + 0) * 1000000)); \
		if (mb_per_job < 1) mb_per_job = 1; \
	} \
	print canonical, gb, mb, mb_per_job; \
}' 2>/dev/null))
endef
memory_values := $(call memory_conversion_values,$(MEMORY),$(JOBS))
memory_bonesistools := $(word 1,$(memory_values))
memory_gb := $(word 2,$(memory_values))
memory_mb := $(word 3,$(memory_values))
memory_velocyto := $(word 4,$(memory_values))
memory_valid := $(if $(memory_bonesistools),true,false)
is_memory_size = $(if $(call memory_conversion_values,$(1),1),true,false)
is_creatable_path = $(shell { test -n "$(strip $(1))" && $(call system_tool,mkdir) -p "$(strip $(1))"; } \
	>/dev/null 2>&1 && echo true || echo false)

raw_conditions := $(strip $(call tolower, $(CONDITIONS)))
unnamed_condition := $(if $(raw_conditions),false,true)
conditions := $(if $(raw_conditions),$(raw_conditions),unique)
condition_indices := $(shell $(call system_tool,seq) 1 $(words $(conditions)))
$(foreach i,$(condition_indices),$(eval condition_index_$(word $(i),$(conditions)) := $(i)))
file_for_condition = $(word $(condition_index_$(1)),$(strip $(2)))
condition_path = $(if $(filter true,$(unnamed_condition)),,$(1)/)
condition_name = $(if $(filter true,$(unnamed_condition)),sample,$(1))
display_reference = $(strip $(if $(filter true,$(unnamed_condition)),\
	$(patsubst %/unique,%,$(filter-out unique,$(1))),\
	$(1)))
display_list = $(strip $(foreach item,$(strip $(1)),$(call display_reference,$(item))))
multi_condition := $(filter-out 1,$(words $(conditions)))
references_default := $(strip $(conditions) $(if $(multi_condition),integrated))
REFERENCES ?= $(references_default)
running_references := $(strip $(REFERENCES))
running_conditions := $(filter-out integrated,$(running_references))
invalid_references = $(strip $(filter-out $(conditions) integrated,$(running_references)))
target_conditions := $(call uniq,$(running_conditions) \
	$(if $(filter integrated,$(running_references)),$(conditions)))
supported_references := $(strip $(conditions) $(if $(multi_condition),integrated))
display_conditions := $(call display_list,$(conditions))
display_conditions_label := $(if $(display_conditions),$(display_conditions),unnamed)
display_references := $(call display_list,$(running_references))
display_references_label := $(if $(display_references),$(display_references),unnamed)
display_references_default := $(call display_list,$(references_default))
display_references_default_label := $(if $(display_references_default),$(display_references_default),unnamed)
display_supported_references := $(call display_list,$(supported_references))
display_supported_references_label := $(if $(display_supported_references),$(display_supported_references),unnamed)
gsm_var = $(if $(filter true,$(unnamed_condition)),GSM,GSM_$(call toupper,$(1)))
sra_var = $(if $(filter true,$(unnamed_condition)),SRA,SRA_$(call toupper,$(1)))
gsm_value = $(strip $($(call gsm_var,$(1))))
sra_value = $(strip $($(call sra_var,$(1))))
condition_param_var = $(if $(filter true,$(unnamed_condition)),$(1),$(1)_$(call toupper,$(2)))
gsm_conditions := $(strip $(foreach condition,$(conditions),\
	$(if $(call gsm_value,$(condition)),$(condition))))
sra_conditions := $(strip $(foreach condition,$(conditions),\
	$(if $(call sra_value,$(condition)),$(condition))))
count_files_mode := $(if $(COUNT_FILES),true,false)
input_route_parameters := $(strip $(sra_conditions) $(gsm_conditions) \
	$(COUNT_FILES) $(MACROSTATE_FILES) $(BINARIZATION_FILE))
input_route_variables := $(strip \
	$(if $(sra_conditions),$(if $(filter true,$(unnamed_condition)),SRA,SRA_*)) \
	$(if $(gsm_conditions),$(if $(filter true,$(unnamed_condition)),GSM,GSM_*)) \
	$(if $(COUNT_FILES),COUNT_FILES) \
	$(if $(MACROSTATE_FILES),MACROSTATE_FILES) \
	$(if $(BINARIZATION_FILE),BINARIZATION_FILE))
input_routes := $(strip \
	$(if $(sra_conditions),$(if $(filter true,$(unnamed_condition)),SRA,SRA_<CONDITION>)) \
	$(if $(gsm_conditions),$(if $(filter true,$(unnamed_condition)),GSM,GSM_<CONDITION>)) \
	$(if $(COUNT_FILES),COUNT_FILES) \
	$(if $(MACROSTATE_FILES),MACROSTATE_FILES) \
	$(if $(BINARIZATION_FILE),BINARIZATION_FILE))
input_route_choices = SRA, GSM, SRA_<CONDITION>, GSM_<CONDITION>, COUNT_FILES, MACROSTATE_FILES, BINARIZATION_FILE
input_route_conflict = variable conflict: input routes are mutually exclusive \
	(specified: $(subst $(space),$(comma) ,$(strip $(input_route_variables))))
matrix_mode := $(if $(COUNT_FILES),false,$(if $(gsm_conditions),true,false))
count_input_module := $(if $(filter true,$(count_files_mode)),,\
	$(if $(filter true,$(matrix_mode)),load-matrix,velocyto))

resources_dir := $(patsubst %/,%,$(RESOURCES_DIR))
results := $(patsubst %/,%,$(PROJECT_DIR))

log_target := $(patsubst __%,%,$(or $(firstword $(MAKECMDGOALS)),default))
LOGFILE := $(results)/logs/$(shell $(call system_tool,date) '+%Y%m%d_%H%M%S')_$(log_target).log
log_dir := $(patsubst %/,%,$(dir $(LOGFILE)))
export tmpdir := $(shell $(call system_tool,mktemp) -d -t scbolt-XXXXXXXXXX)
$(shell { trap '$(call system_tool,rm) -rf $(tmpdir);' EXIT; $(call system_tool,tail) --pid=$$PPID -f /dev/null; } </dev/null >/dev/null 2>/dev/null &)

ifeq ($(diagnostic_mode),)
ifneq ($(words $(input_routes)),0)
ifneq ($(words $(input_routes)),1)
$(error $(failure_label) $(input_route_conflict))
endif
endif
ifneq ($(strip $(COUNT_FILES)),)
ifneq ($(words $(COUNT_FILES)),$(words $(conditions)))
$(error COUNT_FILES must contain one file per condition \(conditions: $(display_conditions_label)\))
endif
endif
ifneq ($(strip $(MACROSTATE_FILES)),)
ifneq ($(words $(MACROSTATE_FILES)),1)
ifneq ($(words $(MACROSTATE_FILES)),$(words $(conditions)))
$(error MACROSTATE_FILES must contain either one multi-condition file or one file per condition \(conditions: $(display_conditions_label)\))
endif
endif
endif
endif

## BEGIN URLS ##

cycle_url := https://github.com/MarioniLab/scran/raw/master/inst/exdata/mouse_cycle_markers.rds
go_basic_url := http://purl.obolibrary.org/obo/go/go-basic.obo
geiger_url := https://doi.org/10.1371/journal.pbio.2003389.s025
chambers_url := https://ars.els-cdn.com/content/image/1-s2.0-S1934590907002202-mmc3.xls
gene2go_url := https://ftp.ncbi.nlm.nih.gov/gene/DATA/gene2go.gz
geneinfo_url = $(strip \
	$(if $(filter human,$(ORGANISM)),ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz,\
	$(if $(filter mouse,$(ORGANISM)),ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Mus_musculus.gene_info.gz,\
	$(if $(filter escherichia-coli,$(ORGANISM)),ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Bacteria/Escherichia_coli_str._K-12_substr._MG1655.gene_info.gz))))

## END URLS ##

## BEGIN FUNCTIONS ##

log = printf '%s - %s - %s\n' "`date '+%Y-%m-%d %H:%M:%S.%3N'`" "$(1)" "$(2)"

print_rule    = $(call log,RULE,$(1)$(if $(call display_reference,$(2)), (reference: $(call display_reference,$(2)))))
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
import std; \
adata = ad.read_h5ad(sys.argv[1]); \
adata.layers["counts"] = adata.X.copy(); \
std.write_h5ad(adata, filename=sys.argv[2], compression="gzip"); \
spliced = float(adata.layers["spliced"].sum()); \
unspliced = float(adata.layers["unspliced"].sum()); \
ambiguous = float(adata.layers["ambiguous"].sum()); \
counts = float(adata.layers["counts"].sum()); \
print(f"reads: spliced={spliced:.0f}, unspliced={unspliced:.0f}, ambiguous={ambiguous:.0f}"); \
print(f"reads: spliced+unspliced+ambiguous={spliced + unspliced + ambiguous:.0f}, counts={counts:.0f}")' \
$(1) $(2) | while IFS= read -r line; do $(call print_result,$$$$line); done
endef

define plot_embeddings_command
$(call conda_run,scbolt-core) python $(fig_dir)/plot_embedding.py $(1) \
	--infile $(2) --outfile "$$outfile" \
	$(4)
endef

define plot_composition_command
$(call conda_run,scbolt-core) python $(fig_dir)/plot_composition.py $(1) \
	--infile $(2) --outfile "$$outfile" \
	$(4)
endef

define plot_embeddings
outfile="$(3)"
display_file="$$(realpath --relative-to="$(launch_dir)" "$$outfile" 2>/dev/null \
	|| printf '%s' "$$outfile")"
$(call print_task,plotting embeddings (file=$$display_file))
$(call plot_embeddings_command,$(1),$(2),$(3),$(4))
endef

define plot_composition
outfile="$(3)"
display_file="$$(realpath --relative-to="$(launch_dir)" "$$outfile" 2>/dev/null \
	|| printf '%s' "$$outfile")"
$(call print_task,plotting composition (file=$$display_file))
$(call plot_composition_command,$(1),$(2),$(3),$(4))
endef

define check_file
[ -n "$(1)" ] || { $(call print_error,required file parameter not defined: $(2)); }; \
[ -f "$(1)" ] || { $(call print_error,required file not found: $(1)); }
endef

check_command = command -v $(1) >/dev/null 2>&1 || { $(call print_error,required command not found: $(1)); }
check_conda_env = $(conda_command) env list | $(call system_tool,awk) '{print $$1}' | $(call system_tool,grep) -qx "$(1)" \
	|| { $(call print_error,required conda environment not found: $(1)); }
check_parameter = [ -n "$(strip $(1))" ] || { $(call print_error,required parameter not defined: $(2)); }

define require_parameter
[ -n "$(strip $($(1)))" ] || { \
	$(call print_error,required parameter not defined: $(1)$(if $(2), \(needed by target '$(2)'\))); \
}
endef

define require_gsm_condition
[ -n "$(call gsm_value,$(1))" ] || { \
	$(call print_error,required parameter not defined: $(call gsm_var,$(1)) \(needed by target 'load-matrix'\)); \
}; \
if [ -n "$(call sra_value,$(1))" ]; then \
	$(call print_error,incompatible input sources$(if $(call display_reference,$(1)), for condition '$(1)'): \
		both $(call sra_var,$(1)) and $(call gsm_var,$(1)) are defined); \
fi
endef

define require_sra_condition
[ -n "$(call sra_value,$(1))" ] || { \
	$(call print_error,required parameter not defined: $(call sra_var,$(1)) \(needed by target 'load-fastq'\)); \
}; \
if [ -n "$(call gsm_value,$(1))" ]; then \
	$(call print_error,incompatible input sources$(if $(call display_reference,$(1)), for condition '$(1)'): \
		both $(call sra_var,$(1)) and $(call gsm_var,$(1)) are defined); \
fi
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
	''|*[!0-9]*|0) $(call print_error,required positive integer for parameter $(1) (current: $(strip $($(1)))));; \
esac
endef

define require_nonnegative_integer
case "$(strip $($(1)))" in \
	''|*[!0-9]*) $(call print_error,required non-negative integer for parameter $(1) (current: $(strip $($(1)))));; \
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
	$(call print_error,required numeric value for parameter $(1) (current: $(strip $($(1))))); \
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

define require_hcop_version
if [ "$(strip $(prior_knowledge))" = "collectri" ] || [ "$(strip $(prior_knowledge))" = "dorothea" ]; then \
	$(call require_parameter,HCOP_VERSION,$(1)); \
fi
endef

define require_dorothea_compatibility
if [ "$(strip $(PRIOR_KNOWLEDGE))" = "dorothea" ]; then \
	$(call require_bool,DOROTHEA_COMPATIBILITY,$(1)); \
fi
endef

define require_dorothea_levels
if [ "$(strip $(PRIOR_KNOWLEDGE))" = "dorothea" ]; then \
for level in $(DOROTHEA_LEVELS); do \
	case "$${level}" in \
		$(subst $(space),|,$(dorothea_levels))) ;; \
		*) $(call print_error,unsupported value for parameter DOROTHEA_LEVELS \
			(supported values: $(subst $(space),$(comma) ,$(dorothea_levels))));; \
	esac; \
done; \
fi
endef

define require_cc_correction
$(call require_bool,CC_CORRECTION,$(1)); \
if [ "$(CC_CORRECTION)" = "true" ] && [ "$(ORGANISM)" != "mouse" ]; then \
	$(call print_error,CC_CORRECTION=true is only supported for mouse \(current: $(ORGANISM)\)); \
fi
endef

define require_filtering_parameters
$(call require_bool,CONSISTENT_MAD,filtering)
endef

define require_clustering_parameters
$(call require_choice,ANALYSIS_HVG_FLAVOR,seurat cell_ranger seurat_v3,clustering); \
$(call require_optional_positive_integer,ANALYSIS_HVG_TOP); \
$(call require_float,ANALYSIS_HVG_SPAN); \
$(call require_positive_integer,ANALYSIS_HVG_BINS); \
$(call require_positive_integer,DIM_PCA); \
$(call require_positive_integer,DIM_EMBEDDING); \
$(call require_bool,CENTERED_PCA,clustering); \
$(call require_bool,PCA_ONLY_HVG,clustering); \
$(call require_positive_integer,NEIGHBORS); \
$(call require_float,RESOLUTION); \
$(call require_float,MIN_DIST); \
$(call require_float,SPREAD); \
$(call require_positive_integer,EMBEDDING_N_ITER)
endef

define require_velocity_parameters
$(call require_choice,REPRESENTATION,X_umap X_tsne,velocity); \
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
$(call require_choice,DEA_METHOD,wilcoxon welch welch_overestimate,dea); \
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

define require_knnsc_parameters
$(call require_parameter,KNNSC_EMBEDDING,knnsc); \
$(call require_positive_integer,KNNSC_NEIGHBORS); \
$(call require_nonnegative_integer,KNNSC_MIN_CLUSTER_SIZE)
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
$(call require_positive_integer,SCBOOLSEQ_OPENBLAS_THREADS); \
$(call require_positive_integer,SCBOOLSEQ_OMP_THREADS); \
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
$(call require_hcop_version,$(1)); \
$(call require_dorothea_api,$(1)); \
$(call require_dorothea_compatibility,$(1)); \
$(call require_dorothea_levels)
endef

define require_bonesis_filter_parameters
$(call require_prior_parameters,$(1)); \
$(call require_bool,CANONICAL_FILTER,$(1))
endef

define require_bonesis_infer_parameters
$(call require_prior_parameters,$(1)); \
$(call require_bool,CANONICAL_INFER,$(1))
endef

ifneq ($(__dry_run_output),)
require_parameter =
require_gsm_condition =
require_sra_condition =
require_choice =
require_bool =
require_positive_integer =
require_nonnegative_integer =
require_optional_positive_integer =
require_float =
require_optional_hvg_method =
require_hvg_method =
require_prior_knowledge =
require_dorothea_api =
require_hcop_version =
require_dorothea_compatibility =
require_dorothea_levels =
require_cc_correction =
require_filtering_parameters =
require_clustering_parameters =
require_velocity_parameters =
require_cellrank_parameters =
require_dea_parameters =
require_stream_parameters =
require_knnsc_parameters =
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

define check_knnsc_seed_diagnostic
if [ -n "$(strip $(1))" ] || [ -n "$(strip $(2))" ]; then \
	if [ -n "$(strip $(1))" ]; then \
		$(call check_success,method parameter valid: \
			$(call knnsc_centrality_var,$(3))=$(strip $(1)) (needed by target 'knnsc')); \
	fi; \
	if [ -n "$(strip $(2))" ]; then \
		$(call check_success,method parameter valid: \
			$(call knnsc_periphery_var,$(3))=$(strip $(2)) (needed by target 'knnsc')); \
	fi; \
else \
	$(call report_check_error,required method parameter not defined: \
		$(call knnsc_centrality_var,$(3)) or \
		$(call knnsc_periphery_var,$(3)) (needed by target 'knnsc')); \
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

define check_memory_diagnostic
if [ "$(memory_valid)" = "true" ]; then \
	$(call check_success,$(call parameter_label,$(1),$(2),$(3)) valid: \
		$(call parameter_assignment,$(1),$(2))); \
else \
	$(call report_check_error,required positive memory size for \
		$(call parameter_description,$(1),$(2),$(3)) (current: $(strip $(1)))); \
fi
endef

define check_nonnegative_integer_diagnostic
case "$(strip $(1))" in \
	''|*[!0-9]*) $(call report_check_error,required non-negative integer for \
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
			(supported values: $(subst $(space),$(comma) ,$(display_supported_references_label)))); \
		references_ok=0; \
	fi; \
	if [ "$(words $(conditions))" -eq 1 ] && [ -n "$(filter integrated,$(running_references))" ]; then \
		$(call report_check_error,unsupported value for core parameter REFERENCES: integrated is not supported \
			for mono-condition projects); \
		references_ok=0; \
	fi; \
	if [ "$${references_ok}" -eq 1 ]; then \
		$(call check_success,core parameter valid: REFERENCES=$(display_references_label)); \
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

knnsc_centrality_var = $(call condition_param_var,KNNSC_CENTRALITY,$(1))
knnsc_periphery_var = $(call condition_param_var,KNNSC_PERIPHERY,$(1))
knnsc_centrality = $($(call knnsc_centrality_var,$(1)))
knnsc_periphery = $($(call knnsc_periphery_var,$(1)))
log_parameters = $(foreach var,$(strip $(1)),printf '%s=%s\n' '$(var)' "$($(var))"; )
metadata_target_args = $(foreach target,$(strip $(RESET_TARGET_$(1))),--target "$(target)")
metadata_custom_target_args = $(foreach target,$(strip $(2)),--target "$(target)")
metadata_param_args = $(foreach param,$(strip $(sensitive_params_$(1))),--param '$(param)=$($(param))')
metadata_extra_param_args = $(foreach param,$(strip $(1)),--param "$(param)")
metadata_runtime_env_args = $(foreach env,$(strip $(runtime_envs_$(1))),--runtime-env "$(env)")
metadata_backend_args = \
	--backend "$(BACKEND)" \
	--container-engine "$(SCBOLT_CONTAINER_ENGINE)" \
	--container-image "$(SCBOLT_IMAGE)"
metadata_old_file_args = $(foreach path,$(strip $(OLD_FILES)),--old-file "$(path)")
metadata_git_hash = $$(git -C "$(scbolt_root)" rev-parse HEAD 2>/dev/null || echo unknown)
metadata_state = $(python) $(scripts_dir)/utils/scbolt_metadata.py state \
	--module "$(1)" \
	$(call metadata_target_args,$(1)) \
	$(metadata_old_file_args) \
	$(call metadata_param_args,$(1)) \
	$(call metadata_runtime_env_args,$(1)) \
	$(metadata_backend_args)
metadata_state_field = $(call metadata_state,$(1)) --field "$(2)"
metadata_state_make = $(nested_make) LOGGING=false __reset_disabled=metadata \
	__metadata-state METADATA_MODULE="$(1)" METADATA_FIELD="$(2)" \
	PARAMS="$(PARAMS)" OLD_FILES="$(OLD_FILES)"

.PHONY: __metadata-state
__metadata-state:
	@$(call metadata_state_field,$(METADATA_MODULE),$(or $(METADATA_FIELD),all))

define warn_stale_outputs
$(foreach path,$(unknown_old_files),\
	$(call print_warning,old file is not a known scBOLT target: $(path));) \
$(system_shell_functions) \
selected_modules=" $(call target_dry_run_modules,$(1)) "; \
running_modules=" $(reset_modules) "; \
rebuilding_modules=" "; \
pending_modules=" "; \
stale_modules=" "; \
untracked_modules=" "; \
is_running() { \
	case "$${running_modules}" in *" $$1 "*) return 0 ;; *) return 1 ;; esac; \
}; \
is_rebuilding() { \
	case "$${rebuilding_modules}" in *" $$1 "*) return 0 ;; *) return 1 ;; esac; \
}; \
is_pending() { \
	case "$${pending_modules}" in *" $$1 "*) return 0 ;; *) return 1 ;; esac; \
}; \
is_stale() { \
	case "$${stale_modules}" in *" $$1 "*) return 0 ;; *) return 1 ;; esac; \
}; \
is_untracked() { \
	case "$${untracked_modules}" in *" $$1 "*) return 0 ;; *) return 1 ;; esac; \
}; \
metadata_manifest="$$(mktemp)"; \
metadata_report_dir="$$(mktemp -d)"; \
$(nested_make) LOGGING=false __reset_disabled=metadata \
	__check-metadata-manifest CHECK_METADATA_MODULES="$${selected_modules}" \
	PARAMS="$(PARAMS)" OLD_FILES="$(OLD_FILES)" > "$${metadata_manifest}"; \
if [ -s "$${metadata_manifest}" ]; then \
	$(python) "$(scripts_dir)/utils/scbolt_metadata.py" batch-progress \
		--manifest "$${metadata_manifest}" \
		$(metadata_backend_args) \
		$(metadata_old_file_args) \
		| while IFS="	" read -r report_module report_field report_value; do \
			printf '%s\t%s\n' "$${report_field}" "$${report_value}" \
				>> "$${metadata_report_dir}/$${report_module}"; \
		done; \
fi; \
$(foreach module,$(reset_stages),\
	module_deps="$(strip $(progress_deps_$(module)))"; \
	module_rebuilding=0; \
	if is_running "$(module)"; then \
		module_rebuilding=1; \
	else \
		for dependency in $${module_deps}; do \
			if is_rebuilding "$${dependency}"; then \
				module_rebuilding=1; \
				break; \
			fi; \
		done; \
	fi; \
	if [ "$${module_rebuilding}" -eq 1 ]; then \
		rebuilding_modules="$${rebuilding_modules}$(module) "; \
	fi; \
	if [[ "$${selected_modules}" == *" $(module) "* ]]; then \
		module_report="$${metadata_report_dir}/$(module)"; \
		module_status="$$(awk -F '\t' '$$1 == "status" { print $$2; exit }' "$${module_report}")"; \
		module_message="$$(awk -F '\t' '$$1 == "message" { print $$2; exit }' "$${module_report}")"; \
		module_deps="$$(awk -F '\t' '$$1 == "deps" { print $$2; exit }' "$${module_report}")"; \
		module_details=""; \
		module_pending=0; \
		module_stale=0; \
		module_untracked=0; \
		if [ "$${module_status}" = "pending" ]; then \
			module_pending=1; \
		elif [ "$${module_status}" = "stale" ]; then \
			module_stale=1; \
		elif [ "$${module_status}" = "untracked" ]; then \
			module_untracked=1; \
		elif [ "$${module_status}" = "done" ]; then \
			for dependency in $${module_deps}; do \
				if is_stale "$${dependency}"; then \
					module_message="$(module) (depends on module '$${dependency}')"; \
					module_stale=1; \
					break; \
				elif is_untracked "$${dependency}"; then \
					module_message="$(module) (depends on module '$${dependency}')"; \
					module_untracked=1; \
					break; \
				elif is_pending "$${dependency}"; then \
					module_message="$(module) (depends on module '$${dependency}')"; \
					module_stale=1; \
					break; \
				fi; \
			done; \
		fi; \
		if [ "$${module_rebuilding}" -eq 1 ]; then \
			:; \
		elif [ "$${module_pending}" -eq 1 ]; then \
			:; \
		elif [ "$${module_stale}" -eq 1 ]; then \
			if [[ "$${module_status}" = "stale" && "$${module_message}" == "$(module) ("*")" ]]; then \
				module_details="$${module_message#$(module) (}"; \
				module_details="$${module_details%)}"; \
				module_message="$(module)"; \
			fi; \
			$(call print_warning,stale module output: $${module_message}); \
			if [ -n "$${module_details}" ]; then \
				printf '%s\n' "$${module_details}" \
					| tr ';' '\n' \
					| sed 's/^[[:space:]]*/    - /'; \
			fi; \
			stale_modules="$${stale_modules}$(module) "; \
		elif [ "$${module_untracked}" -eq 1 ]; then \
			if ! is_running "$(module)"; then \
				if [[ "$${module_message}" == "$(module) ("*")" ]]; then \
					module_details="$${module_message#$(module) (}"; \
					module_details="$${module_details%)}"; \
					module_message="$(module)"; \
				fi; \
				if [ "$${module_status}" = "untracked" ]; then \
					$(call print_warning,missing module metadata: $${module_message} (untracked output)); \
				else \
					$(call print_warning,untracked module output: $${module_message}); \
				fi; \
				if [ -n "$${module_details}" ]; then \
					printf '%s\n' "$${module_details}" \
						| sed 's/, /;/g' \
						| tr ';' '\n' \
						| sed 's/^[[:space:]]*/    - /'; \
				fi; \
				untracked_modules="$${untracked_modules}$(module) "; \
			fi; \
		fi; \
	fi;)
rm -f "$${metadata_manifest}"; \
rm -rf "$${metadata_report_dir}";
endef

define write_scbolt_metadata_command
$(python) $(scripts_dir)/utils/scbolt_metadata.py write \
	--module "$(1)" \
	$(call metadata_custom_target_args,$(1),$(2)) \
	--params-file "$(PARAMS)" \
	--git-hash "$(metadata_git_hash)" \
	$(call metadata_param_args,$(1)) \
	$(call metadata_extra_param_args,$(3)) \
	$(4) \
	$(call metadata_runtime_env_args,$(1)) \
	$(metadata_backend_args)
endef

define write_scbolt_metadata
$(if $(strip $(sensitive_params_$(1)) $(runtime_envs_$(1))),\
$(if $(filter true,$(__dry_run_output)),,\
$(call write_scbolt_metadata_command,$(1),$(2),$(3),$(4))))
endef

PYTHONUNBUFFERED ?= 1
TQDM_DISABLE ?= 0
TQDM_TO_TTY ?= 0
LOKY_MAX_CPU_COUNT ?= $(JOBS)

conda_runtime_env = \
	LOKY_MAX_CPU_COUNT="$(LOKY_MAX_CPU_COUNT)" \
	PYTHONPATH="$(lib_dir)$(if $(PYTHONPATH),:$(PYTHONPATH))" \
	PYTHONUNBUFFERED="$(PYTHONUNBUFFERED)"
container_mount_roots = $(call uniq,\
	$(scbolt_root) \
	$(launch_dir) \
	$(params_dir) \
	$(patsubst %/,%,$(dir $(results))) \
	$(patsubst %/,%,$(dir $(resources_dir))) \
	$(tmpdir) \
	$(SCBOLT_CONTAINER_MOUNTS))
container_mount_args = $(foreach path,$(strip $(container_mount_roots)),-v "$(path):$(path)")
container_base = $(SCBOLT_CONTAINER_ENGINE) run --rm \
	$(container_mount_args) \
	-w "$(launch_dir)" \
	$(SCBOLT_CONTAINER_ARGS)
container_runtime_env = \
	-e LOKY_MAX_CPU_COUNT="$(LOKY_MAX_CPU_COUNT)" \
	-e PYTHONPATH="$(lib_dir)$(if $(PYTHONPATH),:$(PYTHONPATH))" \
	-e PYTHONUNBUFFERED="$(PYTHONUNBUFFERED)" \
	-e HOME="$(tmpdir)" \
	-e MPLCONFIGDIR="$(tmpdir)/matplotlib"
container_cellrank_env = $(container_runtime_env) \
	-e OMPI_MCA_btl="^smcuda"
container_inference_env = $(container_runtime_env) \
	-e TQDM_DISABLE="$(TQDM_DISABLE)" \
	-e TQDM_TO_TTY="$(TQDM_TO_TTY)" \
	-e PYTHONHASHSEED="$(SEED)"

ifeq ($(backend),docker)
ifeq ($(SCBOLT_IN_DOCKER),true)
conda_run = $(conda_runtime_env) micromamba run -n $(1)
conda_run_cellrank = $(conda_runtime_env) \
	OMPI_MCA_btl="^smcuda" \
	micromamba run -n $(1)
conda_inference_env = $(conda_runtime_env) \
	TQDM_DISABLE="$(TQDM_DISABLE)" \
	TQDM_TO_TTY="$(TQDM_TO_TTY)" \
	PYTHONHASHSEED="$(SEED)"
conda_run_inference = $(conda_inference_env) \
	micromamba run -n $(1)
conda_run_inference_timeout = $(conda_inference_env) \
	$(call inference_timeout,$(2)) \
	micromamba run -n $(1)
else
conda_run = $(container_base) $(container_runtime_env) --entrypoint micromamba "$(SCBOLT_IMAGE)" \
	run -n $(1)
conda_run_cellrank = $(container_base) $(container_cellrank_env) --entrypoint micromamba "$(SCBOLT_IMAGE)" \
	run -n $(1)
conda_run_inference = $(container_base) $(container_inference_env) --entrypoint micromamba "$(SCBOLT_IMAGE)" \
	run -n $(1)
conda_run_inference_timeout = $(call inference_timeout,$(2)) \
	$(container_base) $(container_inference_env) --entrypoint micromamba "$(SCBOLT_IMAGE)" \
	run -n $(1)
endif
else
conda_run_option = $(if $(filter conda,$(backend)),--no-capture-output)
conda_run = $(conda_runtime_env) $(conda_command) run $(conda_run_option) -n $(1)
conda_run_cellrank = $(conda_runtime_env) \
	OMPI_MCA_btl="^smcuda" \
	$(conda_command) run $(conda_run_option) -n $(1)
conda_inference_env = $(conda_runtime_env) \
	TQDM_DISABLE="$(TQDM_DISABLE)" \
	TQDM_TO_TTY="$(TQDM_TO_TTY)" \
	PYTHONHASHSEED="$(SEED)"
conda_run_inference = $(conda_inference_env) \
	$(conda_command) run $(conda_run_option) -n $(1)
conda_run_inference_timeout = $(conda_inference_env) \
	$(call inference_timeout,$(2)) \
	$(conda_command) run $(conda_run_option) -n $(1)
endif
nested_make = \
	$(if $(PYTHONPATH),PYTHONPATH="$(PYTHONPATH)") \
	PYTHONUNBUFFERED="$(PYTHONUNBUFFERED)" \
	TQDM_DISABLE="$(TQDM_DISABLE)" \
	TQDM_TO_TTY="$(TQDM_TO_TTY)" \
	$(MAKE) --no-print-directory -f "$(makefile_path)" $(trust_make_options)
inference_timeout = $(if $(filter-out 0,$(strip $(1))),$(call system_tool,timeout) --foreground $(strip $(1)),)

ifndef LOGGING
run_logged = \
	$(call warn_stale_outputs,$(1)) \
	$(nested_make) LOGGING=false __$(1) LOGFILE="$(LOGFILE)"
else ifeq ($(LOGGING),true)
run_logged = \
	mkdir -p $(log_dir); \
	{ \
		printf '%s\n' '[RUN]'; \
		printf 'DATE=%s\n' "`date '+%Y-%m-%d %H:%M:%S'`"; \
		printf 'TARGET=%s\n' "$(1)"; \
		printf 'PROJECT DIRECTORY=%s\n' "$(PROJECT_DIR)"; \
		printf 'PARAMETER FILE=%s\n' "$(PARAMS)"; \
		printf 'FILE=%s\n' "$(LOGFILE)"; \
		printf 'SOURCE REVISION=%s\n' "`git rev-parse HEAD 2>/dev/null || echo unknown`"; \
		printf 'BACKEND=%s\n' "$(backend_label)"; \
		printf 'BACKEND_SOURCE=%s\n' "$(backend_source)"; \
		printf 'MAKE_VERSION=%s\n' "$(make_label)"; \
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
	{ \
		$(call warn_stale_outputs,$(1)) \
		$(if $(PYTHONPATH),PYTHONPATH="$(PYTHONPATH)") \
		PYTHONUNBUFFERED="$(PYTHONUNBUFFERED)" \
		TQDM_DISABLE="$(TQDM_DISABLE)" \
		TQDM_TO_TTY="1" \
		SCBOLT_LOGGING_TO_FILE=true \
		$(MAKE) -f "$(makefile_path)" $(trust_make_options) LOGGING=false __$(1) LOGFILE="$(LOGFILE)"; \
	} 2>&1 | $(call system_tool,tee) -a "$(LOGFILE)"
else ifeq ($(LOGGING),false)
run_logged = \
	$(call warn_stale_outputs,$(1)) \
	$(nested_make) LOGGING=false __$(1) LOGFILE="$(LOGFILE)"
else
run_logged = \
	$(call warn_stale_outputs,$(1)) \
	$(nested_make) LOGGING=false __$(1) LOGFILE="$(LOGFILE)"
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

define start_inference_timer
inference_start_seconds="$$SECONDS"; \
format_inference_duration() { \
	duration_seconds="$$1"; \
	duration_days="$$(($${duration_seconds} / 86400))"; \
	duration_seconds="$$(($${duration_seconds} % 86400))"; \
	duration_hours="$$(($${duration_seconds} / 3600))"; \
	duration_seconds="$$(($${duration_seconds} % 3600))"; \
	duration_minutes="$$(($${duration_seconds} / 60))"; \
	duration_seconds="$$(($${duration_seconds} % 60))"; \
	if [ "$${duration_days}" -gt 0 ]; then \
		if [ "$${duration_seconds}" -gt 0 ]; then \
			printf '%dd%02dh%02dm%02ds' "$${duration_days}" "$${duration_hours}" "$${duration_minutes}" "$${duration_seconds}"; \
		elif [ "$${duration_minutes}" -gt 0 ]; then \
			printf '%dd%02dh%02dm' "$${duration_days}" "$${duration_hours}" "$${duration_minutes}"; \
		elif [ "$${duration_hours}" -gt 0 ]; then \
			printf '%dd%02dh' "$${duration_days}" "$${duration_hours}"; \
		else \
			printf '%dd' "$${duration_days}"; \
		fi; \
	elif [ "$${duration_hours}" -gt 0 ]; then \
		if [ "$${duration_seconds}" -gt 0 ]; then \
			printf '%dh%02dm%02ds' "$${duration_hours}" "$${duration_minutes}" "$${duration_seconds}"; \
		elif [ "$${duration_minutes}" -gt 0 ]; then \
			printf '%dh%02dm' "$${duration_hours}" "$${duration_minutes}"; \
		else \
			printf '%dh' "$${duration_hours}"; \
		fi; \
	elif [ "$${duration_minutes}" -gt 0 ]; then \
		if [ "$${duration_seconds}" -gt 0 ]; then \
			printf '%dm%02ds' "$${duration_minutes}" "$${duration_seconds}"; \
		else \
			printf '%dm' "$${duration_minutes}"; \
		fi; \
	else \
		printf '%ds' "$${duration_seconds}"; \
	fi; \
}; \
effective_inference_timeout() { \
	inference_elapsed="$$(($$SECONDS - $${inference_start_seconds}))"; \
	if [ "$${inference_elapsed}" -lt 1 ]; then inference_elapsed=1; fi; \
	format_inference_duration "$${inference_elapsed}"; \
};
endef

define keep_inference_fallback
$(call system_tool,cp) "$(1)" "$@"; \
$(if $(strip $(2)),$(call write_scbolt_metadata,$(2),$@,$(3),$(call solution_metadata_args,partial,$@,$(5)));) \
$(call print_warning,$(4));
endef

count_nonempty_lines = $(call system_tool,awk) 'NF { n++ } END { print n + 0 }' "$(1)"
metadata_solution_field = $(python) $(scripts_dir)/utils/scbolt_metadata.py solution --target "$(1)" --field "$(2)"
solution_metadata_args = \
	$(if $(strip $(1)),--solution-status "$(1)") \
	$(if $(strip $(2)),--solution-kept "$$($(call count_nonempty_lines,$(2)))") \
	$(if $(strip $(3)),--solution-total "$$($(call count_nonempty_lines,$(3)))")
timeout_param_for_module = \
	$(if $(filter max-nodes-soft,$(1)),TIMEOUT_SOFT,\
	$(if $(filter max-consts-soft,$(1)),TIMEOUT_CONSTS,\
	$(if $(filter max-nodes-relaxed,$(1)),TIMEOUT_RELAXED,\
	$(if $(filter max-nodes-seed,$(1)),TIMEOUT_SEED,\
	$(if $(filter max-nodes-lock,$(1)),TIMEOUT_LOCK)))))
interrupted_timeout_param = $(strip \
	$(if $(and $(filter $(INTERRUPTED_TARGET),$(1)),$(strip $(INTERRUPTED_ELAPSED))),\
		$(call timeout_param_for_module,$(1))=$(INTERRUPTED_ELAPSED)))

define report_kept_gene_selection_result
@if [ ! -f "$(4)" ] && [ -s "$(2)" ]; then \
	solution_status="$$($(call metadata_solution_field,$(2),status) 2>/dev/null || true)"; \
	if [ "$${solution_status}" = "partial" ]; then \
		solution_label="$$($(call metadata_solution_field,$(2),label) 2>/dev/null || true)"; \
		if [ -z "$${solution_label}" ]; then \
			kept="$$($(call count_nonempty_lines,$(2)))"; \
			if [ -n "$(3)" ] && [ -s "$(3)" ]; then \
				total="$$($(call count_nonempty_lines,$(3)))"; \
				solution_label="partial ($${kept}/$${total})"; \
			else \
				solution_label="partial ($${kept})"; \
			fi; \
		fi; \
		printf '%s %s\n' "$(1)" "$${solution_label}"; \
		$(call system_tool,touch) "$(4)"; \
	fi; \
fi
endef

define report_intermediate_gene_selection_status
@if [ ! -f "$(4)" ] && [ -s "$(2)" ]; then \
	solution_status="$$($(call metadata_solution_field,$(2),status) 2>/dev/null || true)"; \
	if [ "$${solution_status}" = "partial" ]; then \
		solution_coverage="$$($(call metadata_solution_field,$(2),coverage) 2>/dev/null || true)"; \
		if [ -z "$${solution_coverage}" ]; then \
			kept="$$($(call count_nonempty_lines,$(2)))"; \
			if [ -n "$(3)" ] && [ -s "$(3)" ]; then \
				total="$$($(call count_nonempty_lines,$(3)))"; \
				solution_coverage="$${kept}/$${total}"; \
			else \
				solution_coverage="$${kept}"; \
			fi; \
		fi; \
		printf 'intermediate solution: %s\n' "$${solution_coverage}"; \
		$(call system_tool,touch) "$(4)"; \
	fi; \
fi
endef

define ensure_partial_gene_selection_metadata
@if [ "$(1)" = "$(INTERRUPTED_TARGET)" ] && [ -s "$(2)" ]; then \
	solution_status="$$($(call metadata_solution_field,$(2),status) 2>/dev/null || true)"; \
	if [ -z "$${solution_status}" ]; then \
		$(call write_scbolt_metadata,$(1),$(2),$(call interrupted_timeout_param,$(1)),$(call solution_metadata_args,partial,$(2),$(3))); \
	fi; \
fi
endef

define finalize_interrupted_lock_gene_selection
@if [ ! -s "$(max_nodes_lock)" ] \
		&& [ -s "$(max_nodes_seed)" ] \
		&& [ -s "$(max_nodes_relaxed)" ] \
		&& { [ -f "$(dir $(max_nodes_lock))nodes.sh" ] \
			|| [ -f "$(dir $(max_nodes_lock))mandatory.txt" ]; }; then \
	mkdir -p "$(dir $(max_nodes_lock))"; \
	$(call system_tool,cp) "$(max_nodes_seed)" "$(max_nodes_lock)"; \
	$(call write_scbolt_metadata,max-nodes-lock,$(max_nodes_lock),$(call interrupted_timeout_param,max-nodes-lock),$(call solution_metadata_args,partial,$(max_nodes_lock),$(max_nodes_relaxed))); \
fi
endef

define check_inference_status
	if [ $$exit_status -eq 0 ]; then \
		$(if $(strip $(2)),$(call write_scbolt_metadata,$(2),$@,,$(call solution_metadata_args,global,$@,$(5)));) \
		$(call print_debug,global optimum found); \
	elif [ $$exit_status -eq 124 ]; then \
		echo -e ''; \
		if [ -s $@ ]; then \
			$(if $(strip $(2)),$(call write_scbolt_metadata,$(2),$@,$(if $(strip $(3)),$(3)=$$(effective_inference_timeout)),$(call solution_metadata_args,partial,$@,$(5)));) \
			$(call print_warning,user-defined time limit reached \($(1)\): keeping partial solution); \
		elif [ -n "$(4)" ] && [ -s "$(4)" ]; then \
			$(call keep_inference_fallback,$(4),$(2),$(if $(strip $(3)),$(3)=$$(effective_inference_timeout)),user-defined time limit reached \($(1)\): keeping fallback solution,$(5)) \
		else \
			$(call print_error,user-defined time limit reached \($(1)\): no solution found); \
		fi; \
	elif [ $$exit_status -eq 130 ] || [ $$exit_status -eq 143 ]; then \
		echo -e ''; \
		if [ -s $@ ]; then \
			$(if $(strip $(2)),$(call write_scbolt_metadata,$(2),$@,$(if $(strip $(3)),$(3)=$$(effective_inference_timeout)),$(call solution_metadata_args,partial,$@,$(5)));) \
			$(call print_warning,inference interrupted: keeping partial solutions); \
		elif [ -n "$(4)" ] && [ -s "$(4)" ]; then \
			$(call keep_inference_fallback,$(4),$(2),$(if $(strip $(3)),$(3)=$$(effective_inference_timeout)),inference interrupted: keeping fallback solution,$(5)) \
		else \
			$(call log,ERROR,inference interrupted: no partial solution found); \
		fi; \
		exit $$exit_status; \
	else \
		$(call log,ERROR,inference failed); \
		exit $$exit_status; \
	fi
endef

define trap_inference_interrupt
handle_inference_interrupt() { \
	signal_status="$$1"; \
	echo -e ""; \
	if [ -s $@ ]; then \
		$(if $(strip $(1)),$(call write_scbolt_metadata,$(1),$@,$(if $(strip $(2)),$(2)=$$(effective_inference_timeout)),$(call solution_metadata_args,partial,$@,$(4)));) \
		$(call log,WARNING,inference interrupted: keeping partial solutions); \
	elif [ -n "$(3)" ] && [ -s "$(3)" ]; then \
		$(call keep_inference_fallback,$(3),$(1),$(if $(strip $(2)),$(2)=$$(effective_inference_timeout)),inference interrupted: keeping fallback solution,$(4)) \
	else \
		$(call log,ERROR,inference interrupted: no partial solution found); \
	fi; \
	exit "$${signal_status}"; \
}; \
trap 'handle_inference_interrupt 130' INT; \
trap 'handle_inference_interrupt 143' TERM
endef

define check_bn_outputs
@if [ -d "$(1)" ]; then \
	max_outputs=8; \
	missing_outputs="$$($(call system_tool,mktemp))"; \
	[ -f "$(1)/ensemble.pdf" ] || printf '%s\n' "$(1)/ensemble.pdf" >> "$${missing_outputs}"; \
	$(call system_tool,find) "$(1)" -mindepth 1 -maxdepth 1 -type d \
		| $(call system_tool,sort) -V \
		| while IFS= read -r solution_dir; do \
			solution_name="$${solution_dir##*/}"; \
			case "$${solution_name}" in \
				""|*[!0-9]*) continue;; \
			esac; \
			for file in model.bnet noi.txt \
				$(foreach fmt,$(strip $(3)),state.$(fmt)) \
				$(foreach fmt,$(strip $(4)),ig.$(fmt)); do \
				[ -f "$${solution_dir}/$${file}" ] \
					|| printf '%s\n' "$${solution_dir}/$${file}" >> "$${missing_outputs}"; \
			done; \
		done; \
	missing_count="$$( \
		$(call system_tool,wc) -l < "$${missing_outputs}" \
			| $(call system_tool,tr) -d '[:space:]')"; \
	if [ "$${missing_count}" -eq 0 ]; then \
		rm -f "$${missing_outputs}"; \
		exit 0; \
	fi; \
	echo "" >&2; \
	echo "Detected incomplete outputs for target '$(2)'." >&2; \
	echo "Output directory: $(1)" >&2; \
	echo "" >&2; \
	echo "Missing expected outputs:" >&2; \
	$(call system_tool,sed) -n "1,$${max_outputs}p" "$${missing_outputs}" \
		| $(call system_tool,sed) "s#^$(launch_dir)/##" \
		| $(call system_tool,sed) 's/^[[:space:]]*/    - /' >&2; \
	if [ "$${missing_count}" -gt "$${max_outputs}" ]; then \
		echo "    - $$((missing_count - max_outputs)) more output(s)" >&2; \
	fi; \
	rm -f "$${missing_outputs}"; \
	echo "" >&2; \
	printf "Remove partial outputs and rerun inference? (y/[n]): " >&2; \
	if ! read ans; then ans=; fi; \
	if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ]; then \
		rm -rf "$(1)"; \
		echo "Partial outputs removed." >&2; \
	else \
		echo "Inference aborted." >&2; \
		exit 1; \
	fi; \
fi
endef

## END FUNCTIONS ##
