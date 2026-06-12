## BEGIN CHECK ##

check_default_targets = $(progress_default_targets)
check_targets = $(strip $(if $(TARGET),$(TARGET),$(check_default_targets)))
check_unknown_targets = $(filter-out $(reset_stages),$(check_targets))
check_target_label = $(if $(filter 1,$(words $(check_targets))),target '$(check_targets)',targets '$(check_targets)')

define check_help
	$(call command_help_header,\
		$(if $(filter true,$(SCBOLT_CLI)),\
			scbolt check [<module>] [options],\
			make check [TARGET=<module>] [HELP=true]),\
		Check the inputs required before running a workflow.)
	@if [ "$(SCBOLT_CLI)" = "true" ]; then \
		printf '%s\n' 'Without a module, check validates the workflows ending at bn-min, bn-submin, and bn-diverse.'; \
	else \
		printf '%s\n' 'Without TARGET, check validates the workflows ending at bn-min, bn-submin, and bn-diverse.'; \
	fi
	@printf '\n'
	@printf '$(bold)Parameters$(nc)\n'
	@if [ "$(SCBOLT_CLI)" = "true" ]; then \
		printf '  %-31s %s\n' '<module>' 'final module to validate'; \
		printf '  %-31s %s\n' '--help' 'display this help'; \
		printf '  %-31s %s\n' '--params=<file>' 'select the parameter file'; \
		printf '  %-31s %s\n' '--references=<condition...>' 'restrict checks to selected references'; \
		printf '  %-31s %s\n' '--reset-target=<module...>' 'check what would be required after rebuilding from these modules'; \
		printf '  %-31s %s\n' '--trust-target=<module...>' 'check while trusting selected module outputs'; \
		printf '  %-31s %s\n' '--old-file=<file>' 'check while trusting one existing DAG file'; \
		printf '  %-31s %s\n' '--<parameter>=<value>' 'override any Make parameter'; \
	else \
		printf '  %-31s %s\n' 'TARGET=<module>' 'final module to validate'; \
		printf '  %-31s %s\n' 'HELP=true' 'display this help'; \
		printf '  %-31s %s\n' 'REFERENCES=<condition...>' 'restrict checks to selected references'; \
		printf '  %-31s %s\n' 'RESET_TARGET=<module...>' 'check what would be required after rebuilding from these modules'; \
		printf '  %-31s %s\n' 'TRUST_TARGET=<module...>' 'check while trusting selected module outputs'; \
		printf '  %-31s %s\n' '__check_externals__=false' 'skip external command and conda environment checks'; \
		printf '  %-31s %s\n' '<PARAMETER>=<value>' 'override any Make parameter'; \
	fi
endef

.PHONY: __check-metadata-manifest
__check-metadata-manifest:
	@$(foreach module,$(CHECK_METADATA_MODULES),\
		{ \
			printf 'module\t%s\n' "$(module)"; \
			$(foreach target,$(strip $(RESET_TARGET_$(module))),\
				printf 'target\t%s\n' "$(target)";) \
			$(foreach param,$(strip $(sensitive_params_$(module))),\
				printf 'param\t%s=%s\n' '$(param)' "$($(param))";) \
			printf 'deps\t%s\n' "$(strip $(progress_deps_$(module)))"; \
			printf 'end\n'; \
		};)

.PHONY: check
check:
ifeq ($(HELP),true)
	$(check_help)
else ifeq ($(HELP),false)
	@if [ -n "$(check_unknown_targets)" ]; then \
		printf '$(failure_label) %s\n' "unknown TARGET=$(check_unknown_targets); supported values: $(reset_stages)"; \
		exit 1; \
	fi
	@workflow_dry_run="$$(mktemp)"; \
	target_dry_run="$$(mktemp)"; \
	dry_run="$$(mktemp)"; \
	check_report_dir="$$(mktemp -d)"; \
	project_checks="$${check_report_dir}/01_project"; \
	core_checks="$${check_report_dir}/02_core"; \
	method_checks="$${check_report_dir}/03_method"; \
	external_resource_checks="$${check_report_dir}/04_external_resource"; \
	file_checks="$${check_report_dir}/05_files"; \
	conda_checks="$${check_report_dir}/06_conda"; \
	command_checks="$${check_report_dir}/07_commands"; \
	other_checks="$${check_report_dir}/08_other"; \
	metadata_manifest="$$(mktemp)"; \
	metadata_report_dir="$$(mktemp -d)"; \
	conda_report_dir="$$(mktemp -d)"; \
	touch "$${project_checks}" "$${core_checks}" "$${method_checks}" \
		"$${external_resource_checks}" "$${file_checks}" "$${conda_checks}" \
		"$${command_checks}" "$${other_checks}"; \
	trap 'rm -f "$${workflow_dry_run}" "$${target_dry_run}" "$${dry_run}" \
		"$${metadata_manifest}"; \
		rm -rf "$${check_report_dir}" "$${metadata_report_dir}" "$${conda_report_dir}"' EXIT; \
	route_check_report() { \
		case "$$1" in \
			project\ parameter*|*project\ parameter*) printf '%s\n' "$${project_checks}";; \
			input\ route*|*input\ route*) printf '%s\n' "$${project_checks}";; \
			core\ parameter*|*core\ parameter*) printf '%s\n' "$${core_checks}";; \
			method\ parameter*|*method\ parameter*) printf '%s\n' "$${method_checks}";; \
			external\ resource\ parameter*|*external\ resource\ parameter*) \
				printf '%s\n' "$${external_resource_checks}";; \
			stale\ module\ output*|missing\ module\ metadata*|untracked\ module\ output*) \
				printf '%s\n' "$${file_checks}";; \
			old\ file*) printf '%s\n' "$${file_checks}";; \
			h5ad\ metadata*|*h5ad\ metadata*) printf '%s\n' "$${file_checks}";; \
			file\ found*|*file*) printf '%s\n' "$${file_checks}";; \
			conda\ environment*|command\ found:\ conda|*conda*) printf '%s\n' "$${conda_checks}";; \
			command\ found*|*command*) printf '%s\n' "$${command_checks}";; \
			*) printf '%s\n' "$${other_checks}";; \
		esac; \
	}; \
	check_success() { printf '$(success_label) %s\n' "$$1" >> "$$(route_check_report "$$1")"; }; \
	check_warning() { printf '$(warning_label) %s\n' "$$1" >> "$$(route_check_report "$$1")"; }; \
	check_failure() { printf '$(failure_label) %s\n' "$$1" >> "$$(route_check_report "$$1")"; }; \
	flush_check_reports() { \
		for report in "$$@"; do \
			cat "$${report}"; \
			: > "$${report}"; \
		done; \
	}; \
	missing=0; \
	$(foreach path,$(OLD_FILES),\
		if [ -e "$(path)" ] || [ -L "$(path)" ]; then \
			check_success "old file found: $(path)"; \
		else \
			check_failure "old file not found: $(path)"; \
			missing=1; \
		fi; \
		$(if $(filter $(path),$(known_scbolt_targets)),,\
			check_warning "old file is not a known scBOLT target: $(path)";)) \
	if [ -n "$(filter load-matrix,$(check_targets))" ]; then \
		:; \
		$(foreach condition,$(running_conditions),\
			$(call check_parameter_diagnostic,\
				$(GSM_$(call toupper,$(condition))),\
				GSM_$(call toupper,$(condition)) \
					(needed by target 'load-matrix'),project);) \
	fi; \
	: > "$${workflow_dry_run}"; \
	: > "$${target_dry_run}"; \
	$(foreach target,$(check_targets),\
		$(nested_make) --always-make --dry-run LOGGING=false \
			__check_mode=true __$(target) LOGFILE="$(LOGFILE)" >> "$${workflow_dry_run}";) \
	$(foreach target,$(check_targets),\
		$(nested_make) --dry-run LOGGING=false \
			__check_mode=true __$(target) LOGFILE="$(LOGFILE)" >> "$${target_dry_run}";) \
	selected_modules=" $$(sed -n '/"RULE"/{s/.*"RULE" "//;s/ .*//;s/"//g;p;}' "$${workflow_dry_run}" \
		| awk '$$0 != "bin-hvg" && !seen[$$0]++') "; \
	running_modules=" $$(sed -n '/"RULE"/{s/.*"RULE" "//;s/ .*//;s/"//g;p;}' "$${target_dry_run}" \
		| awk '$$0 != "bin-hvg" && !seen[$$0]++') $(reset_modules) "; \
	pending_modules=" "; \
	stale_modules=" "; \
	untracked_modules=" "; \
	is_running() { \
		case "$${running_modules}" in *" $$1 "*) return 0 ;; *) return 1 ;; esac; \
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
	$(nested_make) LOGGING=false __reset_disabled=metadata \
		__check-metadata-manifest CHECK_METADATA_MODULES="$${selected_modules}" \
		PARAMS="$(PARAMS)" OLD_FILES="$(OLD_FILES)" > "$${metadata_manifest}"; \
	python3 "$(scripts_dir)/utils/scbolt_metadata.py" batch-progress \
		--manifest "$${metadata_manifest}" \
		$(metadata_old_file_args) \
		| while IFS="	" read -r report_module report_field report_value; do \
			printf '%s\t%s\n' "$${report_field}" "$${report_value}" \
				>> "$${metadata_report_dir}/$${report_module}"; \
		done; \
	for module in $${selected_modules}; do \
		module_report="$${metadata_report_dir}/$${module}"; \
		module_status="$$(awk -F '\t' '$$1 == "status" { print $$2; exit }' "$${module_report}")"; \
		module_message="$$(awk -F '\t' '$$1 == "message" { print $$2; exit }' "$${module_report}")"; \
		module_deps="$$(awk -F '\t' '$$1 == "deps" { print $$2; exit }' "$${module_report}")"; \
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
					module_message="$${module} (depends on module '$${dependency}')"; \
					module_stale=1; \
					break; \
				elif is_untracked "$${dependency}"; then \
					module_message="$${module} (depends on module '$${dependency}')"; \
					module_untracked=1; \
					break; \
				elif is_pending "$${dependency}"; then \
					module_message="$${module} (depends on module '$${dependency}')"; \
					module_stale=1; \
					break; \
				fi; \
			done; \
		fi; \
		if [ "$${module_pending}" -eq 1 ]; then \
			if ! is_running "$${module}"; then \
				pending_modules="$${pending_modules}$${module} "; \
			fi; \
		elif [ "$${module_stale}" -eq 1 ]; then \
			if ! is_running "$${module}"; then \
				check_warning "stale module output: $${module_message}"; \
				stale_modules="$${stale_modules}$${module} "; \
			fi; \
		elif [ "$${module_untracked}" -eq 1 ]; then \
			if ! is_running "$${module}"; then \
				if [ "$${module_status}" = "untracked" ]; then \
					check_warning "missing module metadata: $${module_message} (untracked output)"; \
				else \
					check_warning "untracked module output: $${module_message}"; \
				fi; \
				untracked_modules="$${untracked_modules}$${module} "; \
			fi; \
		fi; \
	done; \
	if [ "$(matrix_mode)" = "true" ]; then \
		:; \
		$(foreach condition,$(running_conditions),\
			if [ -f "$(load_matrix_$(condition))" ] && ! is_running "load-matrix"; then \
				matrix_h5ad_report="$$(mktemp)"; \
				if $(call conda_run,scbolt-core) python $(scripts_dir)/utils/check_h5ad.py \
						$(load_matrix_$(condition)) --layers counts --non-empty \
						> /dev/null 2> "$${matrix_h5ad_report}"; then \
					check_success "h5ad metadata: matrix input valid (reference: $(condition))"; \
				else \
					check_failure "h5ad metadata: matrix input invalid \
						(reference: $(condition), file=$(load_matrix_$(condition)))"; \
					missing=1; \
				fi; \
				rm -f "$${matrix_h5ad_report}"; \
			fi;) \
	fi; \
	if [ ! -s "$${target_dry_run}" ]; then \
		if [ "$${missing}" -ne 0 ]; then \
			$(call check_failure,check failed for $(check_target_label)); \
			$(print_check_reports); \
			exit 1; \
		fi; \
		$(call check_success,$(check_target_label) already up to date); \
		$(call check_success,check passed for $(check_target_label)); \
		$(print_check_reports); \
		exit 0; \
	fi; \
	cp "$${target_dry_run}" "$${dry_run}"; \
	$(call check_parameter_diagnostic,$(CONDITIONS),CONDITIONS,project); \
	$(call check_parameter_diagnostic,$(ORGANISM),ORGANISM,project); \
	if [ -z "$(input_route_parameters)" ]; then \
		$(call report_check_error,required input route not defined: define SRA_<CONDITION> or GSM_<CONDITION> or COUNT_FILES or MACROSTATE_FILES or BINARIZATION_FILE); \
	fi; \
	if [ "$(words $(input_routes))" -gt 1 ]; then \
		$(call report_check_error,$(input_route_conflict)); \
	fi; \
	if [ -n "$(COUNT_FILES)" ]; then \
		if [ "$(words $(COUNT_FILES))" -ne "$(words $(conditions))" ]; then \
			$(call report_check_error,COUNT_FILES must contain one file per condition \(conditions: $(conditions)\)); \
		else \
			:; \
			$(foreach condition,$(conditions),\
				$(call check_file_diagnostic,$(count_file_$(condition)),COUNT_FILES,external resource);) \
		fi; \
	fi; \
	if [ -n "$(MACROSTATE_FILES)" ]; then \
		if [ "$(words $(MACROSTATE_FILES))" -ne 1 ] \
				&& [ "$(words $(MACROSTATE_FILES))" -ne "$(words $(conditions))" ]; then \
			$(call report_check_error,MACROSTATE_FILES must contain either one multi-condition file or one file per condition \(conditions: $(conditions)\)); \
		else \
			:; \
			$(foreach path,$(MACROSTATE_FILES),\
				$(call check_file_diagnostic,$(path),MACROSTATE_FILES,external resource);) \
		fi; \
	fi; \
	$(call check_path_diagnostic,$(PUBLIC_DIR),PUBLIC_DIR,core); \
	if grep -qE -- '--samtools-memory|--localmem|--memory' "$${dry_run}"; then \
		$(call check_positive_integer_diagnostic,$(MEMORY),MEMORY,core); \
	fi; \
	if grep -qE -- '--threads|--jobs|--runThreadN|--samtools-threads|--localcores' "$${dry_run}"; then \
		$(call check_positive_integer_diagnostic,$(JOBS),JOBS,core); \
	fi; \
	if grep -qE -- '--seed|PYTHONHASHSEED' "$${dry_run}"; then \
		$(call check_positive_integer_diagnostic,$(SEED),SEED,core); \
	fi; \
	if grep -qE '$(use_rep_check_pattern)' "$${dry_run}" \
			|| grep -q 'scripts/mstates/knnbs_mstates.py' "$${dry_run}" \
			|| grep -q '/cotan/barcts.csv' "$${dry_run}"; then \
		if ! grep -qE 'scripts/clust/(clustering|integration).py' "$${dry_run}"; then \
			$(call check_parameter_diagnostic,$(USE_REP),USE_REP,core); \
		fi; \
	fi; \
	if grep -qE '$(label_col_check_pattern)' "$${dry_run}"; then \
		$(call check_parameter_diagnostic,$(LABEL_COL),LABEL_COL,core); \
	fi; \
	if grep -qE '(^|[[:space:]])STAR([[:space:]]|$$)' "$${dry_run}"; then \
		$(call check_positive_integer_diagnostic,$(STAR_CB_LEN),$(call needed_by,STAR_CB_LEN,star),method); \
		$(call check_positive_integer_diagnostic,$(STAR_UMI_LEN),$(call needed_by,STAR_UMI_LEN,star),method); \
		if [ -n "$(STAR_WHITELIST)" ]; then \
		$(call check_file_diagnostic,$(STAR_WHITELIST),$(call needed_by,STAR_WHITELIST,star),external resource); \
		fi; \
	fi; \
	if grep -q 'scripts/align/qc.py' "$${dry_run}"; then \
		$(call check_choice_diagnostic,\
			$(STAR_BARCODE_FILTER),auto threshold top,$(call needed_by,STAR_BARCODE_FILTER,qc),method); \
		$(call check_optional_positive_integer_diagnostic,\
			$(STAR_MIN_UMI),$(call needed_by,STAR_MIN_UMI,qc),method); \
		$(call check_optional_positive_integer_diagnostic,\
			$(STAR_TOP_BARCODES),$(call needed_by,STAR_TOP_BARCODES,qc),method); \
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
		$(call check_choice_diagnostic,\
			$(MACROSTATE_METHOD),cotan cellrank stream knnbs,$(call needed_by,MACROSTATE_METHOD,macrostates),method); \
	fi; \
	if grep -q 'BIN_METHOD' "$${dry_run}"; then \
		$(call check_choice_diagnostic,\
			$(BIN_METHOD),scboolseq dea consensus,$(call needed_by,BIN_METHOD,binarization),method); \
	fi; \
	if grep -q 'scripts/utils/prepare_macrostate_h5ad.py' "$${dry_run}"; then \
		$(call check_parameter_diagnostic,\
			$(MACROSTATE_FILES),$(call needed_by,MACROSTATE_FILES,$(check_targets)),external resource); \
	fi; \
	if grep -q 'scripts/prep/filter.py' "$${dry_run}"; then \
		$(call check_bool_diagnostic,$(NORM_MAD),$(call needed_by,NORM_MAD,filtering),method); \
	fi; \
	if grep -q 'scripts/prep/norm.py' "$${dry_run}"; then \
		$(call check_bool_diagnostic,$(CC_CORRECTION),$(call needed_by,CC_CORRECTION,normalization),method); \
		if [ "$(CC_CORRECTION)" = "true" ] && [ "$(ORGANISM)" != "mouse" ]; then \
			$(call report_check_error,method parameter CC_CORRECTION=true is only supported \
				for ORGANISM=mouse (current: $(ORGANISM))); \
		fi; \
	fi; \
	if grep -qE 'scripts/clust/(clustering|integration).py' "$${dry_run}"; then \
		$(call check_choice_diagnostic,$(USE_REP),X_umap X_tsne,USE_REP,core); \
		$(call check_choice_diagnostic,\
			$(ANALYSIS_HVG_FLAVOR),seurat cell_ranger seurat_v3,\
			$(call needed_by,ANALYSIS_HVG_FLAVOR,clustering),method); \
		$(call check_optional_positive_integer_diagnostic,\
			$(ANALYSIS_HVG_TOP),$(call needed_by,ANALYSIS_HVG_TOP,clustering),method); \
		$(call check_float_diagnostic,\
			$(ANALYSIS_HVG_SPAN),$(call needed_by,ANALYSIS_HVG_SPAN,clustering),method); \
		$(call check_positive_integer_diagnostic,\
			$(ANALYSIS_HVG_BINS),$(call needed_by,ANALYSIS_HVG_BINS,clustering),method); \
		$(call check_positive_integer_diagnostic,$(DIM_PCA),$(call needed_by,DIM_PCA,clustering),method); \
		$(call check_positive_integer_diagnostic,$(DIM_CLUSTERING),$(call needed_by,DIM_CLUSTERING,clustering),method); \
		$(call check_positive_integer_diagnostic,$(DIM_EMBEDDING),$(call needed_by,DIM_EMBEDDING,clustering),method); \
		$(call check_bool_diagnostic,$(PCA_ONLY_HVG),$(call needed_by,PCA_ONLY_HVG,clustering),method); \
		$(call check_positive_integer_diagnostic,$(NEIGHBORS),$(call needed_by,NEIGHBORS,clustering),method); \
		$(call check_float_diagnostic,$(RESOLUTION),$(call needed_by,RESOLUTION,clustering),method); \
		$(call check_float_diagnostic,$(MIN_DIST),$(call needed_by,MIN_DIST,clustering),method); \
		$(call check_float_diagnostic,$(SPREAD),$(call needed_by,SPREAD,clustering),method); \
	fi; \
	if grep -q 'scripts/traj/velocity.py' "$${dry_run}"; then \
		$(call check_choice_diagnostic,$(USE_REP),X_umap X_tsne,\
			$(call needed_by,USE_REP,velocity),core); \
		$(call check_positive_integer_diagnostic,$(DIM_MOMENT),$(call needed_by,DIM_MOMENT,velocity),method); \
		$(call check_bool_diagnostic,$(VELOCITY_ONLY_HVG),$(call needed_by,VELOCITY_ONLY_HVG,velocity),method); \
	fi; \
	if grep -q 'scripts/mstates/cellrank_mstates.py' "$${dry_run}"; then \
		$(call check_positive_integer_diagnostic,$(INITIAL_STATES),$(call needed_by,INITIAL_STATES,cellrank),method); \
		$(call check_positive_integer_diagnostic,$(TERMINAL_STATES),$(call needed_by,TERMINAL_STATES,cellrank),method); \
		$(call check_float_diagnostic,$(CELLRANK_STABILITY),$(call needed_by,CELLRANK_STABILITY,cellrank),method); \
		$(call check_float_diagnostic,$(CELLRANK_ALPHA),$(call needed_by,CELLRANK_ALPHA,cellrank),method); \
	fi; \
	if grep -q 'scripts/mstates/cotan_mstates.R' "$${dry_run}"; then \
		$(call check_bool_diagnostic,$(COTAN_ONLY_HVG),$(call needed_by,COTAN_ONLY_HVG,cotan),method); \
	fi; \
	if grep -q 'scripts/mstates/stream_mstates.py' "$${dry_run}"; then \
		$(call check_positive_integer_diagnostic,$(CLUSTER_NUMBER),$(call needed_by,CLUSTER_NUMBER,stream),method); \
		$(call check_float_diagnostic,$(ALPHA_EPG),$(call needed_by,ALPHA_EPG,stream),method); \
		$(call check_float_diagnostic,$(MU_EPG),$(call needed_by,MU_EPG,stream),method); \
		$(call check_float_diagnostic,$(LAMBDA_EPG),$(call needed_by,LAMBDA_EPG,stream),method); \
		$(call check_bool_diagnostic,$(EXTEND_EPG),$(call needed_by,EXTEND_EPG,stream),method); \
		$(call check_float_diagnostic,$(EXTEND_PARAMETER),$(call needed_by,EXTEND_PARAMETER,stream),method); \
		$(call check_bool_diagnostic,$(PRUNE_EPG),$(call needed_by,PRUNE_EPG,stream),method); \
		$(call check_bool_diagnostic,$(COLLAPSE_PARAMETER),$(call needed_by,COLLAPSE_PARAMETER,stream),method); \
	fi; \
	if grep -q 'scripts/mstates/knnbs_mstates.py' "$${dry_run}"; then \
		$(call check_parameter_diagnostic,\
			$(KNNBS_EMBEDDING),$(call needed_by,KNNBS_EMBEDDING,knnbs),method); \
		$(call check_positive_integer_diagnostic,\
			$(KNNBS_NEIGHBORS),$(call needed_by,KNNBS_NEIGHBORS,knnbs),method); \
	fi; \
	if grep -q 'scripts/bin/bin_cells_scboolseq.py' "$${dry_run}" \
			|| grep -q '"RULE" "bin-cells' "$${dry_run}"; then \
		$(call check_bool_diagnostic,\
			$(BIN_SCBOOLSEQ_ONLY_HVG),$(call needed_by,BIN_SCBOOLSEQ_ONLY_HVG,bin-cells),method); \
		if [ "$(BIN_SCBOOLSEQ_ONLY_HVG)" = "true" ]; then \
			$(call check_hvg_method_diagnostic,\
				$(BIN_HVG_FLAVOR),$(BIN_HVG_TOP),\
				$(call needed_by,BIN_HVG_FLAVOR,bin-cells),$(call needed_by,BIN_HVG_TOP,bin-cells),method); \
			$(call check_float_diagnostic,$(BIN_HVG_SPAN),$(call needed_by,BIN_HVG_SPAN,bin-cells),method); \
			$(call check_positive_integer_diagnostic,$(BIN_HVG_BINS),$(call needed_by,BIN_HVG_BINS,bin-cells),method); \
		fi; \
		$(call check_float_diagnostic,$(UNIMODAL_QUANTILE),$(call needed_by,UNIMODAL_QUANTILE,bin-cells),method); \
		$(call check_bool_diagnostic,$(ZEROES_ARE_ZEROES),$(call needed_by,ZEROES_ARE_ZEROES,bin-cells),method); \
	fi; \
	if grep -q 'scripts/bin/bin_clust_scboolseq.py' "$${dry_run}"; then \
		$(call check_float_diagnostic,$(NANS_THRESHOLD),$(call needed_by,NANS_THRESHOLD,bin-macrostates),method); \
		$(call check_float_diagnostic,$(BIMODAL_THRESHOLD),$(call needed_by,BIMODAL_THRESHOLD,bin-macrostates),method); \
		$(call check_float_diagnostic,$(ZEROINF_THRESHOLD),$(call needed_by,ZEROINF_THRESHOLD,bin-macrostates),method); \
		$(call check_float_diagnostic,$(UNIMODAL_THRESHOLD),$(call needed_by,UNIMODAL_THRESHOLD,bin-macrostates),method); \
	fi; \
	if grep -q 'scripts/bin/bin_dea.py' "$${dry_run}" \
			|| grep -q '"RULE" "bin-dea' "$${dry_run}"; then \
		$(call check_bool_diagnostic,$(BIN_DEA_ONLY_HVG),$(call needed_by,BIN_DEA_ONLY_HVG,bin-dea),method); \
		if [ "$(BIN_DEA_ONLY_HVG)" = "true" ]; then \
			$(call check_hvg_method_diagnostic,\
				$(BIN_HVG_FLAVOR),$(BIN_HVG_TOP),\
				$(call needed_by,BIN_HVG_FLAVOR,bin-dea),$(call needed_by,BIN_HVG_TOP,bin-dea),method); \
			$(call check_float_diagnostic,$(BIN_HVG_SPAN),$(call needed_by,BIN_HVG_SPAN,bin-dea),method); \
			$(call check_positive_integer_diagnostic,$(BIN_HVG_BINS),$(call needed_by,BIN_HVG_BINS,bin-dea),method); \
		fi; \
		$(call check_float_diagnostic,$(BIN_LOGFC),$(call needed_by,BIN_LOGFC,bin-dea),method); \
		$(call check_float_diagnostic,$(BIN_ALPHA),$(call needed_by,BIN_ALPHA,bin-dea),method); \
	fi; \
	if grep -q 'scripts/clust/markers.py' "$${dry_run}"; then \
		$(call check_float_diagnostic,$(LOGFC),$(call needed_by,LOGFC,dea),method); \
	fi; \
	if grep -q 'scripts/infer/spec.py' "$${dry_run}"; then \
		$(call check_file_diagnostic,$(SPEC_FILE),$(call needed_by,SPEC_FILE,spec),project); \
		$(call check_bool_diagnostic,$(SPEC_ONLY_HVG),$(call needed_by,SPEC_ONLY_HVG,spec),method); \
		if [ "$(SPEC_ONLY_HVG)" = "true" ]; then \
			$(call check_hvg_method_diagnostic,\
				$(BIN_HVG_FLAVOR),$(BIN_HVG_TOP),\
				$(call needed_by,BIN_HVG_FLAVOR,spec),$(call needed_by,BIN_HVG_TOP,spec),method); \
			$(call check_float_diagnostic,$(BIN_HVG_SPAN),$(call needed_by,BIN_HVG_SPAN,spec),method); \
			$(call check_positive_integer_diagnostic,$(BIN_HVG_BINS),$(call needed_by,BIN_HVG_BINS,spec),method); \
		fi; \
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
	if grep -q 'DOROTHEA_COMPATIBILITY' "$${dry_run}" && [ "$(PRIOR_KNOWLEDGE)" = "dorothea" ]; then \
		$(call check_bool_diagnostic,$(DOROTHEA_COMPATIBILITY),DOROTHEA_COMPATIBILITY,method); \
	fi; \
	if grep -q -- '--hcop-version' "$${dry_run}" && { [ "$(PRIOR_KNOWLEDGE)" = "collectri" ] || [ "$(PRIOR_KNOWLEDGE)" = "dorothea" ]; }; then \
		$(call check_parameter_diagnostic,$(HCOP_VERSION),HCOP_VERSION,external resource); \
	fi; \
	if grep -q 'DOROTHEA_LEVELS' "$${dry_run}" && [ "$(DOROTHEA_API)" = "current" ]; then \
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
	if [ -n "$(filter max-nodes-seed,$(check_targets))" ] || grep -q '"RULE" "max-nodes-seed' "$${dry_run}"; then \
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
	if [ -z "$(filter load-matrix,$(check_targets))" ] && grep -q 'download_gsm.sh' "$${dry_run}"; then \
		:; \
		$(foreach condition,$(running_conditions),\
			$(call check_parameter_diagnostic,\
				$(GSM_$(call toupper,$(condition))),\
				GSM_$(call toupper,$(condition)) \
					(needed by target 'load-matrix'),project);) \
	fi; \
	if grep -q 'download/import_matrix.py' "$${dry_run}" \
			&& { grep -q 'scripts/traj/velocity.py' "$${dry_run}" \
				|| grep -q 'scripts/mstates/cellrank_mstates.py' "$${dry_run}"; }; then \
		$(call report_check_error,matrix input mode does not provide spliced/unspliced layers \
			required by velocity-dependent modules); \
	fi; \
	if grep -q 'scripts/clust/annotation.py' "$${dry_run}"; then \
		$(call check_parameter_diagnostic,$(LABEL),LABEL (needed by target 'annotation'),project); \
	fi; \
	if grep -q 'scripts/mstates/knnbs_mstates.py' "$${dry_run}" \
			|| grep -q 'KNNBS_CENTRALITY_' "$${dry_run}"; then \
		:; \
		$(foreach condition,$(running_conditions),\
			$(call check_knnbs_seed_diagnostic,\
				$(call knnbs_centrality,$(condition)),\
				$(call knnbs_periphery,$(condition)),$(condition));) \
	fi; \
	flush_check_reports "$${project_checks}" "$${core_checks}" \
		"$${method_checks}" "$${external_resource_checks}"; \
	if [ "$(__check_externals__)" = "true" ]; then \
		h5ad_report="$$(mktemp)"; \
		if ! $(call conda_run,scbolt-core) python $(scripts_dir)/utils/check_h5ad_pipeline.py \
				--dry-run "$${dry_run}" --conditions $(conditions) > "$${h5ad_report}"; then \
			missing=1; \
		fi; \
		while IFS=$$'\t' read -r status message; do \
			if [ -z "$${status}" ]; then \
				continue; \
			elif [ "$${status}" = "success" ]; then \
				check_success "$${message}"; \
			elif [ "$${status}" = "warning" ]; then \
				check_warning "$${message}"; \
			elif [ "$${status}" = "failure" ]; then \
				check_failure "$${message}"; \
				missing=1; \
			fi; \
		done < "$${h5ad_report}"; \
		rm -f "$${h5ad_report}"; \
	fi; \
	if [ "$(__check_externals__)" = "true" ]; then \
		if grep -q 'repeat_msk.gtf' "$${dry_run}"; then \
			$(call check_file_diagnostic,$(public_dir)/transcriptome/repeat_msk.gtf,repeat masker annotation); \
		fi; \
	fi; \
	flush_check_reports "$${file_checks}"; \
	if [ "$(__check_externals__)" = "true" ]; then \
		$(call check_command_diagnostic,conda); \
		if command -v conda >/dev/null 2>&1; then \
			conda_envs="$$(conda env list | awk '{print $$1}')"; \
			conda_jobs=""; \
			conda_index=0; \
			for env in $$({ \
				grep -oE 'conda run[^;|&]* -n [^ ]+' "$${dry_run}" || true; \
			} | awk '{print $$NF}' | awk '!seen[$$0]++'); do \
				if printf '%s\n' "$${conda_envs}" | grep -qx "$${env}"; then \
					conda_index=$$((conda_index + 1)); \
					conda_report="$${conda_report_dir}/$${conda_index}.report"; \
					conda_status="$${conda_report_dir}/$${conda_index}.status"; \
					printf 'success\t%s\n' "conda environment found: $${env}" > "$${conda_report}"; \
					env_yaml="$(scbolt_root)/envs/$${env#scbolt-}.yml"; \
					git_packages=""; \
					case "$${env}" in \
						scbolt-bonesis) git_packages="--git-package bonesis=$(BONESIS_HASH)";; \
						scbolt-velocity) git_packages="--git-package scvelo=$(SCVELO_HASH)";; \
					esac; \
					( \
						python3 $(scripts_dir)/utils/check_conda_env.py \
							--env "$${env}" --yaml "$${env_yaml}" $${git_packages} \
							>> "$${conda_report}"; \
						printf '%s\n' "$$?" > "$${conda_status}"; \
					) & \
					conda_jobs="$${conda_jobs} $${conda_index}:$$!"; \
				else \
					$(call report_check_error,required conda environment not found: $${env}); \
				fi; \
			done; \
			for conda_job in $${conda_jobs}; do \
				conda_index="$${conda_job%%:*}"; \
				conda_pid="$${conda_job#*:}"; \
				conda_report="$${conda_report_dir}/$${conda_index}.report"; \
				conda_status="$${conda_report_dir}/$${conda_index}.status"; \
				wait "$${conda_pid}" || true; \
				if [ "$$(cat "$${conda_status}" 2>/dev/null || printf '1')" -ne 0 ]; then \
					missing=1; \
				fi; \
				while IFS=$$'\t' read -r status message; do \
					if [ -z "$${status}" ]; then \
						continue; \
					elif [ "$${status}" = "success" ]; then \
						check_success "$${message}"; \
					elif [ "$${status}" = "warning" ]; then \
						check_warning "$${message}"; \
					elif [ "$${status}" = "failure" ]; then \
						check_failure "$${message}"; \
						missing=1; \
					fi; \
				done < "$${conda_report}"; \
			done; \
		fi; \
		flush_check_reports "$${conda_checks}"; \
		if grep -qE '(^|[[:space:]])cellranger count([[:space:]]|$$)' "$${dry_run}"; then \
			$(call check_command_diagnostic,cellranger); \
		fi; \
		if grep -q -- '--graph-formats' "$${dry_run}"; then \
			$(call check_command_diagnostic,dot); \
		fi; \
		flush_check_reports "$${command_checks}"; \
	fi; \
	if [ "$${missing}" -ne 0 ]; then \
		$(call check_failure,check failed for $(check_target_label)); \
		$(print_check_reports); \
		exit 1; \
	fi; \
	$(call check_success,check passed for $(check_target_label)); \
	$(print_check_reports)
else
	$(call print_error,unsupported HELP=$(HELP) \(supported values: true, false\))
endif

## END CHECK ##
