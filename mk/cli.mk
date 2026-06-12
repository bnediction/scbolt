## BEGIN UTILITY VARIABLES ##

SHOW_CONFIG_RAW ?= false
PROGRESS_ALL ?= false
config_print_var = $(if $(filter undefined,$(origin $(1))),,$(info $(1)=$($(1))))
help_command = $(if $(filter true,$(SCBOLT_CLI)),scbolt,make)
help_module_usage = $(if $(filter true,$(SCBOLT_CLI)),<module...>,$(green)<module...>$(nc))
help_params_option = $(if $(filter true,$(SCBOLT_CLI)), [--params=<file>])
help_references_option = $(if $(filter true,$(SCBOLT_CLI)),\
	 [--references=<condition...>], [REFERENCES=<condition...>])
help_reset_option = $(if $(filter true,$(SCBOLT_CLI)),\
	 [--reset-target=<module...>], [RESET_TARGET=<module...>])
help_trust_option = $(if $(filter true,$(SCBOLT_CLI)),\
	 [--trust-target=<module...>], [TRUST_TARGET=<module...>])
help_old_file_option = $(if $(filter true,$(SCBOLT_CLI)),\
	 [--old-file=<file>...], [OLD_FILES=<file...>])
help_logging_option = $(if $(filter true,$(SCBOLT_CLI)), [--logging=<bool>], [LOGGING=<bool>])
help_override_option = $(if $(filter true,$(SCBOLT_CLI)),\
	 [--<parameter>=<value>...], [<PARAMETER>=<value>...])
help_usage_width = $(shell \
	cols=$$(tput cols 2>/dev/null || printf '80'); \
	width=$$((cols - 2)); \
	if [ "$${width}" -lt 50 ]; then width=50; fi; \
	if [ "$${width}" -gt 80 ]; then width=80; fi; \
	printf '%s\n' "$${width}")
help_text_width = $(shell \
	cols=$$(tput cols 2>/dev/null || printf '88'); \
	width=$$((cols - 2)); \
	if [ "$${width}" -lt 30 ]; then width=30; fi; \
	if [ "$${width}" -gt 80 ]; then width=80; fi; \
	printf '%s\n' "$${width}")

define config_print_section
$(info )
$(info [$(1)])
$(foreach var,$(strip $(2)),$(call config_print_var,$(var)))
endef

define config_print_global
$(eval config_modules := $(if $(TARGET),\
	$(call target_dry_run_modules,$(TARGET)),\
	$(config_default_modules)))
$(eval config_params := $(call uniq,$(config_base_params) $(call config_params_from_modules,$(config_modules))))
$(call config_print_section,PROJECT PARAMETERS,$(call config_project_params,$(config_params)))
$(call config_print_section,CORE PARAMETERS,$(call config_core_params,$(config_params)))
$(call config_print_section,METHOD PARAMETERS,$(call config_method_params,$(config_params)))
$(call config_print_section,EXTERNAL RESOURCE PARAMETERS,$(call config_external_resource_params,$(config_params)))
@:
endef

progress_default_targets = bn-min bn-submin bn-diverse
progress_targets = $(strip $(if $(TARGET),$(TARGET),$(progress_default_targets)))
progress_modules = $(call uniq,\
	$(foreach target,$(progress_targets),$(call target_dry_run_modules,$(target))))
progress_scan_modules = $(if $(filter true,$(PROGRESS_ALL)),\
	$(reset_stages),$(filter $(reset_stages),$(progress_modules)))
progress_unknown_targets = $(filter-out $(reset_stages),$(progress_targets))
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

module_help_target = $(strip $(TARGET))
module_help_unknown_targets = $(filter-out $(reset_stages),$(module_help_target))
module_help_params = $(call uniq,$(target_params_$(module_help_target)))
module_help_deps = $(call uniq,$(progress_deps_$(module_help_target)))
module_help_targets = $(RESET_TARGET_$(module_help_target))
module_help_has_bin_hvg = $(filter BIN_HVG_TOP,$(module_help_params))
module_help_solution_note = $(if $(filter-out 0,$(strip $(INFER_LIMIT))),\
	up to $(INFER_LIMIT) solutions,\
	$(if $(strip $(INFER_LIMIT)),\
		up to all satisfiable solutions,\
		up to all satisfiable solutions))
module_help_outputs_bn-submin = \
	$(bn_submin_dir)/*/model.bnet \
	$(bn_submin_dir)/*/state.cfg \
	$(bn_submin_dir)/ensemble.pdf
module_help_outputs_bn-diverse = \
	$(bn_diverse_dir)/*/model.bnet \
	$(bn_diverse_dir)/*/state.cfg \
	$(bn_diverse_dir)/ensemble.pdf
module_help_output_note_bn-submin = $(module_help_solution_note)
module_help_output_note_bn-diverse = $(module_help_solution_note)
module_help_outputs = $(strip $(if $(module_help_outputs_$(module_help_target)),\
	$(module_help_outputs_$(module_help_target)),\
	$(module_help_targets)))
module_help_output_note = $(strip $(module_help_output_note_$(module_help_target)))
relative_to_launch = $(shell realpath --relative-to="$(launch_dir)" "$(1)" 2>/dev/null || printf '%s' "$(1)")

show_config_target = $(if $(TARGET),$(TARGET),all)
show_config_modules = $(if $(TARGET),$(call target_dry_run_modules,$(TARGET)),$(config_default_modules))
show_config_params_file = $(call relative_to_launch,$(PARAMS))
show_config_results = $(call relative_to_launch,$(results))
show_config_public_dir = $(call relative_to_launch,$(public_dir))
show_config_old_files = $(foreach path,$(OLD_FILES),$(call relative_to_launch,$(path)))
show_config_logging = $(if $(filter true,$(LOGGING)),enabled,$(if $(filter false,$(LOGGING)),disabled,$(LOGGING)))
show_config_integration = $(if $(filter-out 1,$(words $(conditions))),$(INTEGRATION),none)
show_config_embedding_label_X_umap = $(call toupper,$(embedding_method_X_umap))
show_config_embedding_label_X_tsne = t-SNE
show_config_embedding_label_X_se = spectral embedding
show_config_embedding_label_X_pca = PCA
show_config_embedding_label_X_largevis = LargeVis
show_config_embedding_label_X_diffmap = diffusion map
show_config_embedding_label_X_phate = PHATE
show_config_embedding_label_X_trimap = TriMap
show_config_embedding_label_X_pacmap = PaCMAP
show_config_embedding_label = $(strip $(if $(show_config_embedding_label_$(1)),\
	$(show_config_embedding_label_$(1)),\
	$(patsubst X_%,%,$(1))))
show_config_embedding = $(if $(filter knnsc,$(MACROSTATE_METHOD)),$(KNNSC_EMBEDDING),$(USE_REP))
show_config_macrostate_embedding = $(call show_config_embedding_label,$(show_config_embedding))
show_config_analytic_modules = \
	velocity potency cotan cellrank stream knnsc \
	bin-cells bin-macrostates bin-dea bin-consensus binarization spec \
	max-nodes-soft max-consts-soft max-nodes-relaxed max-nodes-seed max-nodes-lock \
	bn-min bn-submin bn-diverse
show_config_param_modules = $(call uniq,$(strip \
	$(filter $(show_config_analytic_modules),$(show_config_modules)) \
	$(if $(filter macrostates,$(show_config_modules)),$(MACROSTATE_METHOD))))
show_config_inference_modules = \
	spec max-nodes-soft max-consts-soft max-nodes-relaxed max-nodes-seed max-nodes-lock \
	bn-min bn-submin bn-diverse
show_config_has_inference = $(filter $(show_config_inference_modules),$(show_config_param_modules))
show_config_inference_params = \
	PRIOR_KNOWLEDGE OMNIPATH_VERSION HCOP_VERSION \
	DOROTHEA_API DOROTHEA_COMPATIBILITY DOROTHEA_LEVELS MAX_CLAUSE
show_config_has_analysis_hvg = $(filter clustering,$(show_config_modules))
show_config_binarization_hvg_modules = bin-cells bin-dea bin-consensus spec
show_config_has_binarization_hvg = \
	$(filter $(show_config_binarization_hvg_modules),$(show_config_param_modules))
show_config_has_hvg = $(strip $(show_config_has_analysis_hvg) $(show_config_has_binarization_hvg))
show_config_hvg_params = \
	ANALYSIS_HVG_FLAVOR ANALYSIS_HVG_TOP ANALYSIS_HVG_SPAN ANALYSIS_HVG_BINS \
	BIN_HVG_FLAVOR BIN_HVG_TOP BIN_HVG_SPAN BIN_HVG_BINS
show_config_var_value = $(if $(filter REFERENCES,$(1)),$(running_references),$($(1)))
show_config_var_label = $(call tolower,$(subst _, ,$(1)))
show_config_label_width = $(shell printf '%s\n' \
	$(foreach var,$(strip $(1)),'$(call show_config_var_label,$(var))') \
	| awk '{ if (length > max) max = length } \
		END { width = max + 1; if (width < 20) width = 20; print width }')
show_config_var_command = printf '%-$(2)s: %s\n' \
	'$(call show_config_var_label,$(1))' "$(call show_config_var_value,$(1))";
show_config_print_vars = $(foreach var,$(strip $(1)),$(call show_config_var_command,$(var),$(2)))
show_config_section_title = $(1) parameters
show_config_module_params = $(call uniq,\
	$(filter-out $(show_config_inference_params) $(show_config_hvg_params),$(target_params_$(1))))
show_config_module_label_width = $(call show_config_label_width,$(call show_config_module_params,$(1)))

define command_help_header
	@printf 'usage: %s\n\n' '$(strip $(1))'
	@printf '%s\n\n' '$(strip $(2))'
endef

define show_config_help
	$(call command_help_header,\
		$(if $(filter true,$(SCBOLT_CLI)),\
			scbolt show-config [<module>] [options],\
			make show-config [TARGET=<module>] [SHOW_CONFIG_RAW=true] [HELP=true]),\
		Display the effective scBOLT configuration without running the pipeline.)
	@printf '%s\n' 'By default, show-config prints a readable summary.'
	@printf '%s\n\n' 'Use the raw view to print the underlying Make parameter listing.'
	@printf '$(bold)Parameters$(nc)\n'
	@if [ "$(SCBOLT_CLI)" = "true" ]; then \
		printf '  %-31s %s\n' '<module>' 'select module to summarize'; \
		printf '  %-31s %s\n' '--help' 'display this help'; \
		printf '  %-31s %s\n' '--params=<file>' 'select the parameter file'; \
		printf '  %-31s %s\n' '--raw' 'display raw show-config listing'; \
		printf '  %-31s %s\n' '--references=<condition...>' 'restrict the run to selected references'; \
		printf '  %-31s %s\n' '--reset-target=<module...>' 'preview configuration with forced rebuild context'; \
		printf '  %-31s %s\n' '--trust-target=<module...>' 'preview configuration while trusting selected outputs'; \
		printf '  %-31s %s\n' '--old-file=<file>' 'trust one existing DAG file'; \
		printf '  %-31s %s\n' '--<parameter>=<value>' 'override any Make parameter'; \
	else \
		printf '  %-31s %s\n' 'TARGET=<module>' 'select module to summarize'; \
		printf '  %-31s %s\n' 'HELP=true' 'display this help'; \
		printf '  %-31s %s\n' 'SHOW_CONFIG_RAW=true' 'display raw show-config listing'; \
		printf '  %-31s %s\n' 'REFERENCES=<condition...>' 'restrict the run to selected references'; \
		printf '  %-31s %s\n' 'RESET_TARGET=<module...>' 'preview configuration with forced rebuild context'; \
		printf '  %-31s %s\n' 'TRUST_TARGET=<module...>' 'preview configuration while trusting selected outputs'; \
		printf '  %-31s %s\n' 'OLD_FILES=<file...>' 'trust existing DAG files'; \
		printf '  %-31s %s\n' '<PARAMETER>=<value>' 'override any Make parameter'; \
	fi
endef

define dry_run_help
	$(call command_help_header,\
		$(if $(filter true,$(SCBOLT_CLI)),\
			scbolt dry-run <module> [options],\
			make dry-run TARGET=<module> [HELP=true]),\
		Display recipes required to build a module without executing them.)
	@printf '$(bold)Parameters$(nc)\n'
	@if [ "$(SCBOLT_CLI)" = "true" ]; then \
		printf '  %-31s %s\n' '<module>' 'select module to preview'; \
		printf '  %-31s %s\n' '--help' 'display this help'; \
		printf '  %-31s %s\n' '--params=<file>' 'select the parameter file'; \
		printf '  %-31s %s\n' '--references=<condition...>' 'restrict the preview to selected references'; \
		printf '  %-31s %s\n' '--reset-target=<module...>' 'preview rebuild from these modules'; \
		printf '  %-31s %s\n' '--trust-target=<module...>' 'preview while trusting selected module outputs'; \
		printf '  %-31s %s\n' '--old-file=<file>' 'preview while trusting one existing DAG file'; \
		printf '  %-31s %s\n' '--<parameter>=<value>' 'override any Make parameter'; \
	else \
		printf '  %-31s %s\n' 'TARGET=<module>' 'select module to preview'; \
		printf '  %-31s %s\n' 'HELP=true' 'display this help'; \
		printf '  %-31s %s\n' 'REFERENCES=<condition...>' 'restrict the preview to selected references'; \
		printf '  %-31s %s\n' 'RESET_TARGET=<module...>' 'preview rebuild from these modules'; \
		printf '  %-31s %s\n' 'TRUST_TARGET=<module...>' 'preview while trusting selected module outputs'; \
		printf '  %-31s %s\n' 'OLD_FILES=<file...>' 'preview while trusting existing DAG files'; \
		printf '  %-31s %s\n' '<PARAMETER>=<value>' 'override any Make parameter'; \
	fi
endef

define progress_help
	$(call command_help_header,\
		$(if $(filter true,$(SCBOLT_CLI)),\
			scbolt progress [<module...>] [options],\
			make progress [TARGET=<module...>] [PROGRESS_ALL=true] [HELP=true]),\
		Display which workflow modules are already built.)
	@if [ "$(SCBOLT_CLI)" = "true" ]; then \
		printf '%s\n' 'Without modules, progress summarizes the workflows ending at bn-min, bn-submin, and bn-diverse.'; \
		printf '%s\n\n' 'Use --all to also display extra completed and skipped modules.'; \
	else \
		printf '%s\n' 'Without TARGET, progress summarizes the workflows ending at bn-min, bn-submin, and bn-diverse.'; \
		printf '%s\n\n' 'Use PROGRESS_ALL=true to also display extra completed and skipped modules.'; \
	fi
	@printf '$(bold)States$(nc)\n'
	@printf '  %-31s %s\n' 'DONE' 'output exists and matches current metadata'
	@printf '  %-31s %s\n' 'STALE' 'output exists but metadata or upstream state is outdated'
	@printf '  %-31s %s\n' 'UNTRACKED' 'output exists but metadata is missing'
	@printf '  %-31s %s\n' 'PENDING' 'output is missing or will be rebuilt'
	@printf '  %-31s %s\n' 'EXTRA COMPLETED' 'output exists outside the current workflow (--all)'
	@printf '  %-31s %s\n' 'EXTRA STALE' 'output exists outside the current workflow and is stale (--all)'
	@printf '  %-31s %s\n' 'EXTRA UNTRACKED' 'output exists outside the current workflow and is untracked (--all)'
	@printf '  %-31s %s\n' 'SKIPPED' 'output is outside the current workflow (--all)'
	@printf '\n'
	@printf '$(bold)Parameters$(nc)\n'
	@if [ "$(SCBOLT_CLI)" = "true" ]; then \
		printf '  %-31s %s\n' '<module...>' 'final modules to inspect'; \
		printf '  %-31s %s\n' '--all' 'include extra completed and skipped modules'; \
		printf '  %-31s %s\n' '--help' 'display this help'; \
		printf '  %-31s %s\n' '--params=<file>' 'select the parameter file'; \
		printf '  %-31s %s\n' '--references=<condition...>' 'select references'; \
		printf '  %-31s %s\n' '--reset-target=<module...>' 'inspect progress with forced rebuild context'; \
		printf '  %-31s %s\n' '--trust-target=<module...>' 'inspect progress while trusting selected outputs'; \
		printf '  %-31s %s\n' '--old-file=<file>' 'inspect progress while trusting one existing DAG file'; \
		printf '  %-31s %s\n' '--<parameter>=<value>' 'override any Make parameter'; \
	else \
		printf '  %-31s %s\n' 'TARGET=<module...>' 'final modules to inspect'; \
		printf '  %-31s %s\n' 'PROGRESS_ALL=true' 'include extra completed and skipped modules'; \
		printf '  %-31s %s\n' 'HELP=true' 'display this help'; \
		printf '  %-31s %s\n' 'REFERENCES=<condition...>' 'select references'; \
		printf '  %-31s %s\n' 'RESET_TARGET=<module...>' 'inspect progress with forced rebuild context'; \
		printf '  %-31s %s\n' 'TRUST_TARGET=<module...>' 'inspect progress while trusting selected outputs'; \
		printf '  %-31s %s\n' 'OLD_FILES=<file...>' 'inspect progress while trusting existing DAG files'; \
		printf '  %-31s %s\n' '<PARAMETER>=<value>' 'override any Make parameter'; \
	fi
endef

define show_config_print_param_section
$(if $(strip $(target_params_$(1))),\
printf '\n%s\n' '$(call show_config_section_title,$(1))'
printf '%s\n' '$(call show_config_section_title,$(1))' | sed 's/./-/g'
$(call show_config_print_vars,\
	$(call show_config_module_params,$(1)),\
	$(call show_config_module_label_width,$(1))))
endef

define show_config_print_pipeline
$(if $(strip $(show_config_param_modules)),\
@printf '\nExecution pipeline\n'
@printf '%s\n' '------------------'
@printf '%s\n' $(foreach module,$(show_config_param_modules),'- $(module)'))
endef

define show_config_print_old_files
$(if $(strip $(OLD_FILES)),\
@printf '\nTrusted old files\n'
@printf '%s\n' '-----------------'
@printf '%s\n' $(foreach path,$(show_config_old_files),'- $(path)'))
endef

define show_config_print_inference
$(if $(strip $(show_config_has_inference)),\
@printf '\nInference\n'
@printf '%s\n' '---------'
@printf '%-16s : %s\n' 'Prior knowledge' "$(PRIOR_KNOWLEDGE)"
$(if $(filter collectri dorothea,$(PRIOR_KNOWLEDGE)),@printf '%-16s : %s\n' 'OmniPath' "$(OMNIPATH_VERSION)")
$(if $(filter collectri dorothea,$(PRIOR_KNOWLEDGE)),@printf '%-16s : %s\n' 'HCOP' "$(HCOP_VERSION)")
$(if $(filter dorothea,$(PRIOR_KNOWLEDGE)),@printf '%-16s : %s\n' 'DoRothEA API' "$(DOROTHEA_API)")
$(if $(filter dorothea,$(PRIOR_KNOWLEDGE)),@printf '%-16s : %s\n' 'Compatibility' "$(DOROTHEA_COMPATIBILITY)")
$(if $(and $(filter dorothea,$(PRIOR_KNOWLEDGE)),$(filter current,$(DOROTHEA_API))),@printf '%-16s : %s\n' 'Levels' "$(DOROTHEA_LEVELS)")
@printf '%-16s : %s\n' 'Max clause' "$(MAX_CLAUSE)")
endef

define show_config_print_hvg
$(if $(strip $(show_config_has_hvg)),\
@printf '\nhighly variable genes\n'
@printf '%s\n' 'highly variable genes' | sed 's/./-/g')
$(if $(strip $(show_config_has_analysis_hvg)),\
@printf 'analysis:\n'
@printf '  - %-6s : %s\n' 'flavor' "$(ANALYSIS_HVG_FLAVOR)"
@printf '  - %-6s : %s\n' 'top' "$(ANALYSIS_HVG_TOP)"
@printf '  - %-6s : %s\n' 'span' "$(ANALYSIS_HVG_SPAN)"
@printf '  - %-6s : %s\n' 'bins' "$(ANALYSIS_HVG_BINS)")
$(if $(strip $(show_config_has_binarization_hvg)),\
$(if $(strip $(show_config_has_analysis_hvg)),@printf '\n')
@printf 'binarization:\n'
@printf '  - %-6s : %s\n' 'flavor' "$(BIN_HVG_FLAVOR)"
@printf '  - %-6s : %s\n' 'top' "$(BIN_HVG_TOP)"
@printf '  - %-6s : %s\n' 'span' "$(BIN_HVG_SPAN)"
@printf '  - %-6s : %s\n' 'bins' "$(BIN_HVG_BINS)")
endef

define show_config_print
@printf 'Target: %s\n\n' "$(show_config_target)"
@printf 'Project\n'
@printf '%s\n' '-------'
@printf '%-13s : %s\n' 'Params file' "$(show_config_params_file)"
@printf '%-13s : %s\n' 'Organism' "$(ORGANISM)"
@printf '%-13s : %s\n' 'Conditions' "$(conditions)"
@printf '%-13s : %s\n' 'Public dir' "$(show_config_public_dir)"
@printf '%-13s : %s\n\n' 'Results' "$(show_config_results)"
@printf 'Workflow\n'
@printf '%s\n' '--------'
@printf '%-14s : %s\n' 'Representation' "$(USE_REP)"
@printf '%-14s : %s\n\n' 'Label column' "$(LABEL_COL)"
@printf 'Methods\n'
@printf '%s\n' '-------'
@printf '%-14s : %s\n' 'Embedding' "$(show_config_macrostate_embedding)"
@printf '%-14s : %s\n' 'Integration' "$(show_config_integration)"
@printf '%-14s : %s\n' 'Macrostate' "$(MACROSTATE_METHOD)"
@printf '%-14s : %s\n' 'Binarization' "$(BIN_METHOD)"
$(if $(filter knnsc,$(MACROSTATE_METHOD)),@printf '%-14s : %s\n' 'Neighbors' "$(KNNSC_NEIGHBORS)")
$(if $(filter knnsc,$(MACROSTATE_METHOD)),@printf '%-14s : %s\n' 'Min cluster' "$(KNNSC_MIN_CLUSTER_SIZE)")
@printf '\n'
@printf 'Execution\n'
@printf '%s\n' '---------'
@printf '%-12s : %s\n' 'Jobs' "$(JOBS)"
@printf '%-12s : %s GB\n' 'Memory' "$(MEMORY)"
@printf '%-12s : %s\n' 'Seed' "$(SEED)"
@printf '%-12s : %s\n' 'Logging' "$(show_config_logging)"
$(show_config_print_hvg)
$(show_config_print_inference)
$(show_config_print_old_files)
$(show_config_print_pipeline)
$(foreach module,$(show_config_param_modules),$(call show_config_print_param_section,$(module)))
endef

## END UTILITY VARIABLES ##

## BEGIN HELP ##

##@ Utilities

.PHONY: help
help: ## display help
	@awk 'function hanging(text, width, indent,    line, n, words, i) { \
			n = split(text, words, " "); \
			line = ""; \
			for (i = 1; i <= n; i++) { \
				if (line == "") { \
					line = words[i]; \
				} else if (length(line) + 1 + length(words[i]) <= width) { \
					line = line " " words[i]; \
				} else { \
					print line; \
					line = indent words[i]; \
				} \
			} \
			if (line != "") { print line; } \
		} \
		function paragraph(text, width,    line, n, words, i) { \
			n = split(text, words, " "); \
			line = ""; \
			for (i = 1; i <= n; i++) { \
				if (line == "") { \
					line = words[i]; \
				} else if (length(line) + 1 + length(words[i]) <= width) { \
					line = line " " words[i]; \
				} else { \
					print line; \
					line = words[i]; \
				} \
			} \
			if (line != "") { print line; } \
			print ""; \
		} \
		BEGIN {FS = ":.*##"; \
			hanging("usage: $(help_command) $(help_module_usage)$(help_params_option)" \
				"$(help_references_option)$(help_reset_option)$(help_trust_option)" \
				"$(help_old_file_option)$(help_logging_option)$(help_override_option)", \
				$(help_usage_width), "       "); \
			printf "\n"; \
			paragraph("scBOLT is a software framework for Boolean network inference " \
				"from multi-condition single-cell transcriptomes. Built upon the BoNesis engine, " \
				"it provides a reproducible workflow for transforming transcriptomic observations " \
				"into executable Boolean models through state abstractions, " \
				"dynamical constraint engineering, and exact logical model inference.", \
				$(help_text_width)); \
			printf "$(bold)Special parameters$(nc)\n"; \
				if ("$(SCBOLT_CLI)" == "true") { \
					printf "  %-31s %s\n", "--params=<file>", "select parameter file"; \
					printf "  %-31s %s\n", "--public-dir=<dir>", "select public resource directory"; \
					printf "  %-31s %s\n", "--references=<condition...>", "select references"; \
					printf "  %-31s %s\n", "", "default: $(running_references)"; \
					printf "  %-31s %s\n", "--reset-target=<module...>", "rebuild from modules"; \
					printf "  %-31s %s\n", "--trust-target=<module...>", "skip rebuilding modules"; \
					printf "  %-31s %s\n", "--old-file=<file>", "trust existing DAG file"; \
					printf "  %-31s %s\n", "--logging=<bool>", "enable logging"; \
					printf "  %-31s %s\n", "--help", "display command help"; \
					printf "  %-31s %s\n", "--<parameter>=<value>", "override Make parameter"; \
			} else { \
					printf "  %-31s %s\n", "REFERENCES=<condition...>", "select references"; \
					printf "  %-31s %s\n", "", "default: $(running_references)"; \
					printf "  %-31s %s\n", "PUBLIC_DIR=<dir>", "select public resource directory"; \
					printf "  %-31s %s\n", "RESET_TARGET=<module...>", "rebuild from modules"; \
					printf "  %-31s %s\n", "TRUST_TARGET=<module...>", "skip rebuilding modules"; \
					printf "  %-31s %s\n", "OLD_FILES=<file...>", "trust existing DAG files"; \
					printf "  %-31s %s\n", "LOGGING=<bool>", "enable logging"; \
					printf "  %-31s %s\n", "SHOW_CONFIG_RAW=true", "display raw show-config listing"; \
					printf "  %-31s %s\n", "HELP=true", "display command help"; \
					printf "  %-31s %s\n", "<PARAMETER>=<value>", "override Make parameter"; \
				}} \
			/^[a-zA-Z_-]+:.*?##/ { \
				if (section == "Utilities" && \
						($$1 == "help" || $$1 == "show-config" || $$1 == "progress" || \
						 $$1 == "check" || $$1 == "dry-run" || $$1 == "clean")) { \
					next; \
				} \
				printf "  $(green)%-22s$(nc) %s\n", $$1, $$2; \
			} \
			/^##@/ { \
				section = substr($$0, 5); \
				printf "\n$(bold)%s$(nc)\n", section; \
				if ("$(SCBOLT_CLI)" == "true" && section == "Utilities") { \
					printf "  $(green)%-22s$(nc)  %s\n", "init", "initialize a project"; \
				} \
				if (section == "Utilities") { \
					printf "  $(green)%-22s$(nc)  %s\n", "help", "display help"; \
					printf "  $(green)%-22s$(nc)  %s\n", "show-config", "display the effective configuration"; \
					printf "  $(green)%-22s$(nc)  %s\n", "progress", "display module progress"; \
					printf "  $(green)%-22s$(nc)  %s\n", "check", "validate module requirements"; \
					printf "  $(green)%-22s$(nc)  %s\n", "dry-run", "preview build dependencies"; \
					printf "  $(green)%-22s$(nc)  %s\n", "clean", "clean cache, logs and selected outputs"; \
				} \
			} ' $(MAKEFILE_LIST)

.PHONY: module-help
module-help:
ifeq ($(module_help_target),)
	$(call print_error,missing TARGET \(usage: make module-help TARGET=<module>\))
else ifneq ($(words $(module_help_target)),1)
	$(call print_error,module help expects one TARGET \(current: $(module_help_target)\))
else ifneq ($(module_help_unknown_targets),)
	$(call print_error,unknown TARGET=$(module_help_unknown_targets); supported values: $(reset_stages))
else
	@description="$$(awk -F ':.*##' -v target="$(module_help_target)" \
		'$$1 == target { sub(/^[[:space:]]+/, "", $$2); print $$2; exit }' \
		$(MAKEFILE_LIST))"; \
	[ -n "$${description}" ] || description="No description available."; \
	relpath() { \
		if command -v realpath >/dev/null 2>&1; then \
			realpath -m --relative-to="$(launch_dir)" "$$1" 2>/dev/null \
				|| printf '%s\n' "$$1"; \
		else \
			printf '%s\n' "$$1"; \
		fi; \
	}; \
	format_value() { \
		case "$$1" in \
			/*) relpath "$$1" ;; \
			*) printf '%s\n' "$$1" ;; \
		esac; \
	}; \
	print_parameter_help() { \
		name="$$1"; \
		value="$$2"; \
		hint="$$3"; \
		description="$$4"; \
		note="$$5"; \
		note2="$$6"; \
		note3="$$7"; \
		if [ -n "$${value}" ] && [ -n "$${hint}" ]; then \
			printf '  %-26s %s (%s)\n' "$${name}" "$${value}" "$${hint}"; \
		elif [ -n "$${value}" ]; then \
			printf '  %-26s %s\n' "$${name}" "$${value}"; \
		elif [ -n "$${hint}" ]; then \
			printf '  %-26s (%s)\n' "$${name}" "$${hint}"; \
		else \
			printf '  %s\n' "$${name}"; \
		fi; \
		if [ -n "$${description}" ]; then \
			printf '    %s\n' "$${description}"; \
		fi; \
		if [ -n "$${note}" ]; then \
			printf '    %s\n' "$${note}"; \
		fi; \
		if [ -n "$${note2}" ]; then \
			printf '    %s\n' "$${note2}"; \
		fi; \
		if [ -n "$${note3}" ]; then \
			printf '    %s\n' "$${note3}"; \
		fi; \
	}; \
	if [ "$(SCBOLT_CLI)" = "true" ]; then \
		printf 'usage: scbolt %s [options]\n\n' "$(module_help_target)"; \
	else \
		printf 'usage: make %s [PARAMS=<file>] [REFERENCES=<condition...>] [OLD_FILES=<file...>]\n\n' \
			"$(module_help_target)"; \
	fi; \
	printf '%s\n' 'Description'; \
	printf '%s\n' '-----------'; \
	printf '%s\n\n' "$${description}"; \
	printf '%s\n' 'Outputs'; \
	printf '%s\n' '-------'; \
	outputs=( $(foreach output,$(module_help_outputs),"$(output)") ); \
	if [ "$${#outputs[@]}" -eq 0 ]; then \
		printf '  none\n'; \
	else \
		shown=0; \
		max_outputs=12; \
		for output in "$${outputs[@]}"; do \
			if [ "$${shown}" -ge "$${max_outputs}" ]; then \
				break; \
			fi; \
			printf '  - %s\n' "$$(relpath "$${output}")"; \
			shown=$$((shown + 1)); \
		done; \
		if [ "$${#outputs[@]}" -gt "$${max_outputs}" ]; then \
			printf '  - ... (%s more outputs)\n' "$$(($${#outputs[@]} - max_outputs))"; \
		fi; \
		if [ -n "$(module_help_output_note)" ]; then \
			printf '\n  (%s)\n' "$(module_help_output_note)"; \
		fi; \
	fi; \
	printf '\n%s\n' 'Dependencies'; \
	printf '%s\n' '------------'; \
	dependency_count=0; \
	$(foreach dep,$(module_help_deps),\
		$(foreach target,$(RESET_TARGET_$(dep)),\
			printf '  - %s (%s$(if $(filter $(target),$(OLD_FILES)),$(comma) old file))\n' \
				"$$(relpath '$(target)')" '$(dep)'; \
			dependency_count=$$((dependency_count + 1));)) \
	if [ "$${dependency_count}" -eq 0 ]; then \
		printf '  none\n'; \
	fi; \
	printf '\n%s\n' 'Parameters'; \
	printf '%s\n' '----------'; \
	params=( $(foreach param,$(module_help_params),"$(param)") ); \
	if [ "$${#params[@]}" -eq 0 ]; then \
		printf '  none\n'; \
	else \
		:; \
		$(foreach param,$(module_help_params),\
			print_parameter_help \
				'$(param)' "$$(format_value "$($(param))")" \
				'$(parameter_help_hint_$(param))' \
				'$(parameter_help_description_$(param))' \
				'$(parameter_help_note_$(param))' \
				'$(parameter_help_note2_$(param))' \
				'$(parameter_help_note3_$(param))';) \
	fi; \
	if [ -n "$(module_help_has_bin_hvg)" ]; then \
		printf '\n'; \
		printf '%s\n' 'Notes'; \
		printf '%s\n' '-----'; \
		printf '%s\n' 'Empty top HVG count means automatic estimation.'; \
		printf '%s\n' 'For the seurat_v3 HVG method it must be set explicitly.'; \
	fi
endif

.PHONY: show-config
show-config: ## display the effective configuration
ifeq ($(HELP),true)
	$(show_config_help)
else ifeq ($(HELP),false)
ifneq ($(TARGET),)
ifeq ($(filter $(TARGET),$(reset_stages)),)
	$(call print_error,unknown TARGET=$(TARGET); supported values: $(reset_stages))
endif
endif
ifeq ($(SHOW_CONFIG_RAW),true)
	$(config_print_global)
else ifeq ($(SHOW_CONFIG_RAW),false)
	$(show_config_print)
else
	$(call print_error,unsupported SHOW_CONFIG_RAW=$(SHOW_CONFIG_RAW) \(supported values: true, false\))
endif
else
	$(call print_error,unsupported HELP=$(HELP) \(supported values: true, false\))
endif

.PHONY: __progress-module
__progress-module:
	@$(call metadata_state_field,$(PROGRESS_MODULE),progress); \
	printf 'deps\t%s\n' "$(strip $(progress_deps_$(PROGRESS_MODULE)))"

.PHONY: __reference-context
__reference-context:
	@printf 'REFERENCES=%s\n' "$(running_references)"
	@printf 'REFERENCES_DEFAULT=%s\n' "$(references_default)"

.PHONY: progress
progress: ## display module progress
ifeq ($(HELP),true)
	$(progress_help)
else ifeq ($(HELP),false)
ifneq ($(progress_unknown_targets),)
	$(call print_error,unknown TARGET=$(progress_unknown_targets); supported values: $(reset_stages))
endif
ifneq ($(filter $(PROGRESS_ALL),true false),$(PROGRESS_ALL))
	$(call print_error,unsupported PROGRESS_ALL=$(PROGRESS_ALL) \(supported values: true, false\))
endif
	@done_file="$$(mktemp)"; \
	stale_file="$$(mktemp)"; \
	untracked_file="$$(mktemp)"; \
	pending_file="$$(mktemp)"; \
	extra_done_file="$$(mktemp)"; \
	extra_stale_file="$$(mktemp)"; \
	extra_untracked_file="$$(mktemp)"; \
	skipped_file="$$(mktemp)"; \
	progress_manifest="$$(mktemp)"; \
	progress_report_dir="$$(mktemp -d)"; \
	trap 'rm -f "$${done_file}" "$${stale_file}" "$${untracked_file}" "$${pending_file}" \
		"$${extra_done_file}" "$${extra_stale_file}" "$${extra_untracked_file}" \
		"$${skipped_file}" "$${progress_manifest}"; rm -rf "$${progress_report_dir}"' EXIT; \
	for path in $(OLD_FILES); do \
		if [ ! -e "$${path}" ] && [ ! -L "$${path}" ]; then \
			printf '$(failure_label) %s\n' "old file not found: $${path}"; \
			exit 1; \
		fi; \
	done; \
	for path in $(unknown_old_files); do \
		printf '$(warning_label) %s\n' "old file is not a known scBOLT target: $${path}"; \
	done; \
	selected_modules=" $(progress_modules) "; \
	pending_modules=" "; \
	stale_modules=" "; \
	untracked_modules=" "; \
	workflow_total=0; \
	workflow_done=0; \
	is_pending() { \
		case "$${pending_modules}" in *" $$1 "*) return 0 ;; *) return 1 ;; esac; \
	}; \
	is_stale() { \
		case "$${stale_modules}" in *" $$1 "*) return 0 ;; *) return 1 ;; esac; \
	}; \
	is_untracked() { \
		case "$${untracked_modules}" in *" $$1 "*) return 0 ;; *) return 1 ;; esac; \
	}; \
	print_list() { \
		if [ -s "$$1" ]; then \
			sed 's/^/  /' "$$1"; \
		else \
			printf '  (none)\n'; \
		fi; \
	}; \
	$(foreach module,$(progress_scan_modules),\
		{ \
			printf 'module\t%s\n' "$(module)"; \
			$(foreach target,$(strip $(RESET_TARGET_$(module))),\
				printf 'target\t%s\n' "$(target)";) \
			$(foreach param,$(strip $(sensitive_params_$(module))),\
				printf 'param\t%s=%s\n' '$(param)' "$($(param))";) \
			printf 'deps\t%s\n' "$(strip $(progress_deps_$(module)))"; \
			printf 'end\n'; \
		} >> "$${progress_manifest}";) \
	python3 "$(scripts_dir)/utils/scbolt_metadata.py" batch-progress \
		--manifest "$${progress_manifest}" \
		$(metadata_old_file_args) \
		| while IFS="	" read -r report_module report_field report_value; do \
			printf '%s\t%s\n' "$${report_field}" "$${report_value}" \
				>> "$${progress_report_dir}/$${report_module}"; \
		done; \
	for module in $(progress_scan_modules); do \
		module_report="$${progress_report_dir}/$${module}"; \
		module_status="$$(awk -F '\t' '$$1 == "status" { print $$2; exit }' "$${module_report}")"; \
		module_message="$$(awk -F '\t' '$$1 == "message" { print $$2; exit }' "$${module_report}")"; \
		module_done_label="$$(awk -F '\t' '$$1 == "done-label" { print $$2; exit }' "$${module_report}")"; \
		module_stale_label="$$(awk -F '\t' '$$1 == "stale-label" { print $$2; exit }' "$${module_report}")"; \
		module_pending_message="$$(awk -F '\t' '$$1 == "pending-message" { print $$2; exit }' "$${module_report}")"; \
		module_pending_label="$$(awk -F '\t' '$$1 == "pending-label" { print $$2; exit }' "$${module_report}")"; \
		module_deps="$$(awk -F '\t' '$$1 == "deps" { print $$2; exit }' "$${module_report}")"; \
		if [[ "$${selected_modules}" == *" $${module} "* ]]; then \
			module_label="$${module}"; \
			if [[ "$${module_message}" == *"(old file"* ]]; then \
				module_label="$${module} (old file)"; \
			fi; \
				module_pending=0; \
				module_stale=0; \
				module_untracked=0; \
				if [ "$${module_status}" = "pending" ]; then \
					module_pending=1; \
				elif [ "$${module_status}" = "stale" ]; then \
					module_stale=1; \
				elif [ "$${module_status}" = "untracked" ]; then \
					module_untracked=1; \
				else \
					for dependency in $${module_deps}; do \
						if is_pending "$${dependency}" || is_stale "$${dependency}"; then \
							module_message="$${module} (depends on module '$${dependency}')"; \
							module_stale=1; \
							break; \
						elif is_untracked "$${dependency}"; then \
							module_message="$${module} (depends on module '$${dependency}')"; \
							module_untracked=1; \
							break; \
						fi; \
					done; \
				fi; \
			workflow_total=$$((workflow_total + 1)); \
			if [ "$${module_pending}" -eq 1 ]; then \
				if [ -n "$${module_done_label}" ]; then \
					printf '%s\n' "- $${module_done_label}" >> "$${done_file}"; \
				fi; \
				printf '%s\n' "- $${module_pending_label:-$${module}}" >> "$${pending_file}"; \
				pending_modules="$${pending_modules}$${module} "; \
				elif [ "$${module_stale}" -eq 1 ]; then \
					if [ -n "$${module_done_label}" ]; then \
						printf '%s\n' "- $${module_done_label}" >> "$${done_file}"; \
					fi; \
					printf '%s\n' "- $${module_stale_label:-$${module_message}}" >> "$${stale_file}"; \
					stale_modules="$${stale_modules}$${module} "; \
					if [ -n "$${module_pending_label}" ]; then \
						printf '%s\n' "- $${module_pending_label}" >> "$${pending_file}"; \
						pending_modules="$${pending_modules}$${module} "; \
					fi; \
				elif [ "$${module_untracked}" -eq 1 ]; then \
					workflow_done=$$((workflow_done + 1)); \
					if [ -n "$${module_done_label}" ]; then \
						printf '%s\n' "- $${module_done_label}" >> "$${done_file}"; \
					fi; \
					printf '%s\n' "- $${module_message}" >> "$${untracked_file}"; \
					untracked_modules="$${untracked_modules}$${module} "; \
					if [ -n "$${module_pending_label}" ]; then \
						printf '%s\n' "- $${module_pending_label}" >> "$${pending_file}"; \
						pending_modules="$${pending_modules}$${module} "; \
					fi; \
				else \
					workflow_done=$$((workflow_done + 1)); \
					printf '%s\n' "- $${module_label}" >> "$${done_file}"; \
			fi; \
		elif [ "$(PROGRESS_ALL)" = "true" ]; then \
				if [ "$${module_status}" = "done" ]; then \
					printf '%s\n' "- $${module}" >> "$${extra_done_file}"; \
				elif [ "$${module_status}" = "stale" ]; then \
					if [ -n "$${module_done_label}" ]; then \
						printf '%s\n' "- $${module_done_label}" >> "$${extra_done_file}"; \
					fi; \
					printf '%s\n' "- $${module_stale_label:-$${module_message}}" >> "$${extra_stale_file}"; \
				elif [ "$${module_status}" = "untracked" ]; then \
					if [ -n "$${module_done_label}" ]; then \
						printf '%s\n' "- $${module_done_label}" >> "$${extra_done_file}"; \
					fi; \
					printf '%s\n' "- $${module_message}" >> "$${extra_untracked_file}"; \
				else \
					if [ -n "$${module_done_label}" ]; then \
						printf '%s\n' "- $${module_done_label}" >> "$${extra_done_file}"; \
					fi; \
					printf '%s\n' "- $${module}" >> "$${skipped_file}"; \
				fi; \
		fi; \
	done; \
	printf 'PROGRESS\n'; \
	printf '  final modules: %s\n' "$(progress_targets)"; \
	printf '  completed modules: %s/%s\n' "$${workflow_done}" "$${workflow_total}"; \
	printf '\nDONE\n'; \
	print_list "$${done_file}"; \
		if [ -s "$${stale_file}" ]; then \
			printf '\nSTALE\n'; \
			print_list "$${stale_file}"; \
		fi; \
		if [ -s "$${untracked_file}" ]; then \
			printf '\nUNTRACKED\n'; \
			print_list "$${untracked_file}"; \
		fi; \
		printf '\nPENDING\n'; \
		print_list "$${pending_file}"; \
	if [ "$(PROGRESS_ALL)" = "true" ]; then \
		printf '\nEXTRA COMPLETED\n'; \
		print_list "$${extra_done_file}"; \
			if [ -s "$${extra_stale_file}" ]; then \
				printf '\nEXTRA STALE\n'; \
				print_list "$${extra_stale_file}"; \
			fi; \
			if [ -s "$${extra_untracked_file}" ]; then \
				printf '\nEXTRA UNTRACKED\n'; \
				print_list "$${extra_untracked_file}"; \
			fi; \
			printf '\nSKIPPED\n'; \
		print_list "$${skipped_file}"; \
	fi
else
	$(call print_error,unsupported HELP=$(HELP) \(supported values: true, false\))
endif

.PHONY: dry-run
dry-run: ## preview build dependencies
ifeq ($(HELP),true)
	$(dry_run_help)
else ifeq ($(HELP),false)
	@if [ -z "$(TARGET)" ]; then \
		$(call print_error,missing TARGET \(usage: make dry-run TARGET=<module>\)); \
	fi
	$(nested_make) --dry-run LOGGING=false __dry_run_output=true __$(TARGET) LOGFILE="$(LOGFILE)" \
		| sed -e 's#$(launch_dir)/##g' \
			-e 's#$(launch_dir)#.#g' \
			-e '/^[[:space:]]*$$/d'
else
	$(call print_error,unsupported HELP=$(HELP) \(supported values: true, false\))
endif

##@ Download

.PHONY: load-genome __load-genome
load-genome: ## download the reference genome
	$(call run_logged,load-genome)
__load-genome: $(genome_ref)

.PHONY: load-fastq __load-fastq
load-fastq: ## download FASTQ files
	$(call run_logged,load-fastq)
__load-fastq: $(fastq_target)

.PHONY: load-matrix __load-matrix
load-matrix: ## download public count matrices
	$(call run_logged,load-matrix)
__load-matrix: $(load_matrix_target)
ifneq ($(matrix_mode),true)
	$(call print_error,load-matrix requires GSM_<CONDITION> parameters)
	exit 1
endif

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

##@ Alignment/Counting

.PHONY: alignment __alignment
alignment: ## run the selected alignment/counting workflow
	$(call run_logged,alignment)
__alignment: $(alignment_target)

.PHONY: cellranger __cellranger
cellranger: ## perform alignment and counting with Cell Ranger
	$(call run_logged,cellranger)
__cellranger: $(cellranger_target)

.PHONY: star __star
star: ## perform alignment and counting with STAR
	$(call run_logged,star)
__star: $(star_target)

.PHONY: qc __qc
qc: ## perform alignment quality control
	$(call run_logged,qc)
__qc: $(qc_target)

.PHONY: velocyto __velocyto
velocyto: ## generate spliced and unspliced counts
	$(call run_logged,velocyto)
__velocyto: $(velocyto_target)

##@ Preprocessing

.PHONY: filtering __filtering
filtering: ## filter low-quality cells and genes
	$(call run_logged,filtering)
__filtering: $(filtering_target)

.PHONY: normalization __normalization
normalization: ## normalize transcript counts
	$(call run_logged,normalization)
__normalization: $(normalization_target)

##@ Clustering

.PHONY: clustering __clustering
clustering: ## identify cell populations
	$(call run_logged,clustering)
__clustering: $(clustering_target)

.PHONY: dea __dea
dea: ## identify cluster-specific upregulated genes
	$(call run_logged,dea)
__dea: $(dea_target)

.PHONY: scoring __scoring
scoring: ## score phenotype-related signatures
	$(call run_logged,scoring)
__scoring: $(scoring_target)

.PHONY: goea __goea
goea: ## identify enriched Gene Ontology terms
	$(call run_logged,goea)
__goea: $(goea_target)

.PHONY: annotation __annotation
annotation: ## assign names to cell clusters
	$(call run_logged,annotation)
__annotation: $(annotation_target)

##@ Trajectory inference

.PHONY: velocity __velocity
velocity: ## estimate RNA velocity
	$(call run_logged,velocity)
__velocity: $(velocity_target)

.PHONY: potency __potency
potency: ## estimate cell differentiation potential
	$(call run_logged,potency)
__potency: $(potency_target)

##@ Macrostate characterization

.PHONY: cotan __cotan
cotan: ## estimate macrostates with COTAN
	$(call run_logged,cotan)
__cotan: $(cotan_target)

.PHONY: cellrank __cellrank
cellrank: ## estimate macrostates with CellRank
	$(call run_logged,cellrank)
__cellrank: $(cellrank_target)

.PHONY: stream __stream
stream: ## estimate macrostates with STREAM
	$(call run_logged,stream)
__stream: $(stream_target)

.PHONY: knnsc __knnsc
knnsc: ## estimate macrostates with KNNSC
	$(call run_logged,knnsc)
__knnsc: $(knnsc_target)

.PHONY: macrostates __macrostates
macrostates: ## estimate macrostates with MACROSTATE_METHOD
	$(call run_logged,macrostates)
__macrostates: $(macrostates_target)

##@ Binarization

.PHONY: bin-cells __bin-cells
bin-cells: ## binarize cells with scBoolSeq
	$(call run_logged,bin-cells)
__bin-cells: $(bin_cells)

.PHONY: bin-macrostates __bin-macrostates
bin-macrostates: ## binarize macrostates by voting rules
	$(call run_logged,bin-macrostates)
__bin-macrostates: $(bin_mstates)

.PHONY: bin-dea __bin-dea
bin-dea: ## binarize macrostates by differential expression
	$(call run_logged,bin-dea)
__bin-dea: $(bin_dea)

.PHONY: bin-consensus __bin-consensus
bin-consensus: ## combine scBoolSeq and DEA binarizations
	$(call run_logged,bin-consensus)
__bin-consensus: $(bin_consensus)

.PHONY: binarization __binarization
binarization: ## convert macrostates into Boolean abstractions with BIN_METHOD
	$(call run_logged,binarization)
__binarization: $(bin)

##@ Boolean network inference

.PHONY: spec __spec
spec: ## build the BoNesis model specification
	$(call run_logged,spec)
__spec: $(bonesis_model)

.PHONY: max-nodes-soft __max-nodes-soft
max-nodes-soft: ## maximise nodes (soft constraints)
	$(call run_logged,max-nodes-soft)
__max-nodes-soft: $(max_nodes_soft)

.PHONY: max-consts-soft __max-consts-soft
max-consts-soft: ## maximise strong constants (soft constraints)
	$(call run_logged,max-consts-soft)
__max-consts-soft: $(max_consts_soft)

.PHONY: max-nodes-relaxed __max-nodes-relaxed
max-nodes-relaxed: ## maximise nodes (relaxed constraints)
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
bn-min: ## infer one minimum-edge BN
	$(call run_logged,bn-min)
__bn-min: $(bn_min)

.PHONY: bn-submin __bn-submin
bn-submin: ## enumerate subset-minimal BNs
	$(call run_logged,bn-submin)
__bn-submin: $(bn_submin)

.PHONY: bn-diverse __bn-diverse
bn-diverse: ## sample diverse sparsest BNs
	$(call run_logged,bn-diverse)
__bn-diverse: $(bn_diverse)

## END HELP ##
