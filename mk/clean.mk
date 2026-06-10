## BEGIN CLEAN ##

CLEAN_STALE ?= false
CLEAN_FORCE ?= false
clean_success_label = $(if $(green),$(green)✓$(nc),✓)

define clean_help
	$(call command_help_header,\
		$(if $(filter true,$(SCBOLT_CLI)),\
			scbolt clean [<module...>] [options],\
			make clean [CLEAN_TARGET=<module...>|all] [HELP=true]),\
		Clean cache$(comma) logs and optionally remove selected module outputs.)
	@printf '%s\n' 'Without modules, clean asks before removing cache and logs.'
	@printf '%s\n' 'With --stale, clean asks before removing stale module outputs, making them pending.'
	@printf '%s\n\n' 'With --all, clean asks before removing cache, logs, and all generated module outputs.'
	@printf '$(bold)Parameters$(nc)\n'
	@if [ "$(SCBOLT_CLI)" = "true" ]; then \
		printf '  %-31s %s\n' '<module...>' 'modules whose outputs should be removed'; \
		printf '  %-31s %s\n' '--all' 'ask before removing all generated module outputs'; \
		printf '  %-31s %s\n' '--stale' 'ask before removing stale module outputs'; \
		printf '  %-31s %s\n' '--force' 'skip confirmation for --stale'; \
		printf '  %-31s %s\n' '--help, -h' 'display this help'; \
		printf '  %-31s %s\n' '--params=<file>' 'select parameter file'; \
		printf '  %-31s %s\n' '--references=<condition...>' 'select references'; \
		printf '  %-31s %s\n' '-o <file>, --old-file=<file>' 'keep one trusted file during --stale'; \
	else \
		printf '  %-31s %s\n' 'CLEAN_TARGET=<module...>' 'modules whose outputs should be removed'; \
		printf '  %-31s %s\n' 'CLEAN_TARGET=all' 'ask before removing all generated module outputs'; \
		printf '  %-31s %s\n' 'CLEAN_STALE=true' 'ask before removing stale module outputs'; \
		printf '  %-31s %s\n' 'CLEAN_FORCE=true' 'skip confirmation for CLEAN_STALE=true'; \
		printf '  %-31s %s\n' 'HELP=true' 'display this help'; \
		printf '  %-31s %s\n' 'REFERENCES=<condition...>' 'select references'; \
		printf '  %-31s %s\n' 'OLD_FILES=<file...>' 'keep trusted files during CLEAN_STALE=true'; \
	fi
endef

.PHONY: __clean-stale-module
__clean-stale-module:
	@printf 'status\t%s\n' "$$( $(call metadata_state_field,$(CLEAN_MODULE),status) )"
	printf 'deps\t%s\n' "$(strip $(progress_deps_$(CLEAN_MODULE)))"
	$(call metadata_state_field,$(CLEAN_MODULE),stale-targets) | sed 's/^/stale-output	/'
	$(call metadata_state_field,$(CLEAN_MODULE),stale-cleanup) | sed 's/^/stale-cleanup	/'
	$(foreach path,$(strip $(RESET_TARGET_$(CLEAN_MODULE))),\
		printf 'output\t%s\n' '$(path)';)
	$(call metadata_state_field,$(CLEAN_MODULE),sidecars) | sed 's/^/sidecar	/'

.PHONY: clean
clean:
ifeq ($(HELP),true)
	$(clean_help)
else ifeq ($(HELP),false)
ifneq ($(filter $(CLEAN_STALE),true false),$(CLEAN_STALE))
	$(call print_error,unsupported CLEAN_STALE=$(CLEAN_STALE) \(supported values: true, false\))
endif
ifneq ($(filter $(CLEAN_FORCE),true false),$(CLEAN_FORCE))
	$(call print_error,unsupported CLEAN_FORCE=$(CLEAN_FORCE) \(supported values: true, false\))
endif
	@recovered=0; \
	if [ -n "$(clean_all)" ]; then \
		if [ -n "$(OLD_FILES)" ]; then \
			printf '$(warning_label) %s\n' "clean --all may remove trusted old files:"; \
			$(foreach path,$(OLD_FILES),printf '  - %s\n' '$(path)';) \
		fi; \
		if [ ! -t 0 ]; then \
			printf '$(warning_label) %s\n' "skipped --all: interactive confirmation unavailable"; \
			exit 0; \
		fi; \
		read -r -p "Clean cache, logs, and all generated module outputs? (y/[n]): " choice; \
		case "$${choice}" in \
			y|Y|yes|YES) ;; \
			*) printf '$(warning_label) %s\n' "clean --all cancelled"; exit 0 ;; \
		esac; \
	fi; \
	bytes_for_paths() { \
		total=0; \
		for path in "$$@"; do \
			if [ -e "$${path}" ] || [ -L "$${path}" ]; then \
				size="$$(du -sb "$${path}" 2>/dev/null | awk '{ print $$1 }')"; \
				total=$$((total + $${size:-0})); \
			fi; \
		done; \
		printf '%s\n' "$${total}"; \
	}; \
	format_bytes() { \
		awk -v bytes="$$1" 'BEGIN { \
			split("B KB MB GB TB PB", units, " "); \
			value = bytes + 0; \
			unit = 1; \
			while (value >= 1000 && unit < 6) { value /= 1000; unit++ } \
			if (unit == 1) { printf "%d %s", value, units[unit] } \
			else if (value >= 10) { printf "%.1f %s", value, units[unit] } \
			else { printf "%.2f %s", value, units[unit] } \
		}'; \
	}; \
	cleanup_path_for_output() { \
		path="$$1"; \
		module_name="$${2:-}"; \
		if [ -d "$${path}" ]; then \
			printf '%s\n' "$${path}"; \
			return 0; \
		fi; \
		parent="$$(dirname "$${path}")"; \
		if [ -z "$${parent}" ] || [ "$${parent}" = "." ] || [ "$${parent}" = "/" ]; then \
			printf '%s\n' "$${path}"; \
			return 0; \
		fi; \
		if [ "$${module_name}" = "bn-submin" ] || [ "$${module_name}" = "bn-diverse" ]; then \
			ensemble_dir="$$(dirname "$${parent}")"; \
			if [ -n "$${ensemble_dir}" ] && [ "$${ensemble_dir}" != "." ] && [ "$${ensemble_dir}" != "/" ]; then \
				for old_file in $(OLD_FILES); do \
					case "$${old_file}" in \
						"$${ensemble_dir}"|"$${ensemble_dir}"/*) printf '%s\n' "$${parent}"; return 0 ;; \
					esac; \
				done; \
				printf '%s\n' "$${ensemble_dir}"; \
				return 0; \
			fi; \
		fi; \
		for old_file in $(OLD_FILES); do \
			case "$${old_file}" in \
				"$${parent}"|"$${parent}"/*) printf '%s\n' "$${path}"; return 0 ;; \
			esac; \
		done; \
		printf '%s\n' "$${parent}"; \
	}; \
	prune_nested_paths() { \
		input="$$1"; \
		output="$$2"; \
		: > "$${output}"; \
		while IFS= read -r path; do \
			[ -z "$${path}" ] && continue; \
			skip=0; \
			while IFS= read -r parent; do \
				[ -z "$${parent}" ] && continue; \
				[ "$${path}" = "$${parent}" ] && continue; \
				case "$${path}" in "$${parent}"/*) skip=1; break ;; esac; \
			done < "$${input}"; \
			if [ "$${skip}" -eq 0 ]; then \
				printf '%s\n' "$${path}" >> "$${output}"; \
			fi; \
		done < "$${input}"; \
	}; \
	if [ "$(CLEAN_STALE)" = "true" ] && [ -z "$(clean_all)" ]; then \
		stale_outputs="$$(mktemp)"; \
		stale_cleanup="$$(mktemp)"; \
		stale_pruned="$$(mktemp)"; \
		trap 'rm -f "$${stale_outputs}" "$${stale_cleanup}" "$${stale_pruned}"' EXIT; \
		stale_modules=" "; \
		is_stale() { \
			case "$${stale_modules}" in *" $$1 "*) return 0 ;; *) return 1 ;; esac; \
		}; \
		pending_modules=" "; \
		is_pending() { \
			case "$${pending_modules}" in *" $$1 "*) return 0 ;; *) return 1 ;; esac; \
		}; \
		is_old_file() { \
			case " $(OLD_FILES) " in *" $$1 "*) return 0 ;; *) return 1 ;; esac; \
		}; \
		for module in $(if $(clean_modules),$(clean_modules),$(reset_stages)); do \
			module_report="$$(mktemp)"; \
			$(nested_make) LOGGING=false __clean-stale-module \
				CLEAN_MODULE="$${module}" PARAMS="$(PARAMS)" OLD_FILES="$(OLD_FILES)" \
				> "$${module_report}"; \
			module_status="$$(awk -F '\t' '$$1 == "status" { print $$2; exit }' "$${module_report}")"; \
			module_deps="$$(awk -F '\t' '$$1 == "deps" { print $$2; exit }' "$${module_report}")"; \
			module_pending=0; \
			module_stale=0; \
			if [ "$${module_status}" = "pending" ]; then \
				module_pending=1; \
			elif [ "$${module_status}" = "stale" ]; then \
				module_stale=1; \
			elif [ "$${module_status}" = "done" ]; then \
				for dependency in $${module_deps}; do \
					if is_stale "$${dependency}"; then \
						module_stale=1; \
						break; \
					elif is_pending "$${dependency}"; then \
						module_stale=1; \
						break; \
					fi; \
				done; \
			fi; \
			if [ "$${module_pending}" -eq 1 ]; then \
				pending_modules="$${pending_modules}$${module} "; \
			elif [ "$${module_stale}" -eq 1 ]; then \
				while IFS='	' read -r kind path; do \
					if [ "$${kind}" = "output" ] && is_old_file "$${path}"; then \
						continue; \
					fi; \
					if [ "$${module_status}" = "stale" ] && [ "$${kind}" = "stale-output" ]; then \
						cleanup_path="$$(cleanup_path_for_output "$${path}" "$${module}")"; \
						printf '%s\n' "$${cleanup_path}" >> "$${stale_outputs}"; \
						printf '%s\n' "$${cleanup_path}" >> "$${stale_cleanup}"; \
					fi; \
					if [ "$${module_status}" = "stale" ] && [ "$${kind}" = "stale-cleanup" ]; then \
						printf '%s\n' "$${path}" >> "$${stale_cleanup}"; \
					fi; \
					if [ "$${module_status}" != "stale" ] && [ "$${kind}" = "output" ]; then \
						cleanup_path="$$(cleanup_path_for_output "$${path}" "$${module}")"; \
						printf '%s\n' "$${cleanup_path}" >> "$${stale_outputs}"; \
						printf '%s\n' "$${cleanup_path}" >> "$${stale_cleanup}"; \
					fi; \
					if [ "$${module_status}" != "stale" ] && [ "$${kind}" = "sidecar" ]; then \
						printf '%s\n' "$${path}" >> "$${stale_cleanup}"; \
					fi; \
				done < "$${module_report}"; \
				stale_modules="$${stale_modules}$${module} "; \
			fi; \
			rm -f "$${module_report}"; \
		done; \
		sort -u "$${stale_outputs}" -o "$${stale_outputs}"; \
		sort -u "$${stale_cleanup}" -o "$${stale_cleanup}"; \
		prune_nested_paths "$${stale_outputs}" "$${stale_pruned}"; \
		mv "$${stale_pruned}" "$${stale_outputs}"; \
		sort -u "$${stale_outputs}" -o "$${stale_outputs}"; \
		prune_nested_paths "$${stale_cleanup}" "$${stale_pruned}"; \
		mv "$${stale_pruned}" "$${stale_cleanup}"; \
		sort -u "$${stale_cleanup}" -o "$${stale_cleanup}"; \
		if [ ! -s "$${stale_outputs}" ]; then \
			printf '$(clean_success_label) %s\n' "no stale outputs found"; \
			exit 0; \
		fi; \
		printf 'Found %s stale outputs:\n' "$$(wc -l < "$${stale_outputs}")"; \
		while IFS= read -r path; do \
			path_size="$$(bytes_for_paths "$${path}")"; \
			printf '  - %s (%s)\n' "$${path}" "$$(format_bytes "$${path_size}")"; \
		done < "$${stale_outputs}"; \
		if [ "$(CLEAN_FORCE)" != "true" ]; then \
			if [ ! -t 0 ]; then \
				printf '$(warning_label) %s\n' "clean --stale cancelled: interactive confirmation unavailable"; \
				exit 0; \
			fi; \
			read -r -p "Remove stale outputs? (y/[n]): " choice; \
			case "$${choice}" in \
				y|Y|yes|YES) ;; \
				*) printf '$(warning_label) %s\n' "clean --stale cancelled"; exit 0 ;; \
			esac; \
		fi; \
		mapfile -t stale_path_array < "$${stale_cleanup}"; \
		recovered="$$(bytes_for_paths "$${stale_path_array[@]}")"; \
		rm -rf "$${stale_path_array[@]}"; \
		printf '$(clean_success_label) %s\n' "cleaned stale outputs: $$(format_bytes "$${recovered}")"; \
		exit 0; \
	fi; \
	should_clean() { \
		label="$$1"; \
		if [ -n "$(clean_modules)" ]; then \
			return 0; \
		fi; \
		if [ ! -t 0 ]; then \
			printf '$(warning_label) %s\n' "skipped $${label}: interactive confirmation unavailable"; \
			return 1; \
		fi; \
		read -r -p "Clean $${label}? ([y]/n): " choice; \
		case "$${choice}" in \
			""|y|Y|yes|YES) return 0 ;; \
			*) printf '$(warning_label) %s\n' "skipped $${label}"; return 1 ;; \
		esac; \
	}; \
	clean_paths() { \
		label="$$1"; \
		shift; \
		bytes="$$(bytes_for_paths "$$@")"; \
		if [ "$$#" -gt 0 ]; then \
			rm -rf "$$@"; \
		fi; \
		recovered=$$((recovered + bytes)); \
		printf '$(clean_success_label) %s\n' "cleaned $${label}: $$(format_bytes "$${bytes}")"; \
	}; \
	mapfile -t cache_dirs < <( \
		find . -type d \( -name "__pycache__" -o -name "cache" \) -print \
			| awk 'NF && !seen[$$0]++' \
	); \
	if should_clean "cache"; then \
		cache_bytes="$$(bytes_for_paths "$${cache_dirs[@]}")"; \
		if [ "$${#cache_dirs[@]}" -gt 0 ]; then \
			rm -rf "$${cache_dirs[@]}"; \
		fi; \
		mapfile -t pyc_files < <( \
			find . -type f -name "*.pyc" -print | awk 'NF && !seen[$$0]++' \
		); \
		pyc_bytes="$$(bytes_for_paths "$${pyc_files[@]}")"; \
		if [ "$${#pyc_files[@]}" -gt 0 ]; then \
			rm -f "$${pyc_files[@]}"; \
		fi; \
		cache_bytes=$$((cache_bytes + pyc_bytes)); \
		recovered=$$((recovered + cache_bytes)); \
		printf '$(clean_success_label) %s\n' "cleaned cache: $$(format_bytes "$${cache_bytes}")"; \
	fi; \
	if should_clean "logs"; then \
		log_bytes="$$(bytes_for_paths "$(log_dir)")"; \
		rm -rf "$(log_dir)"; \
		recovered=$$((recovered + log_bytes)); \
		printf '$(clean_success_label) %s\n' "cleaned logs: $$(format_bytes "$${log_bytes}")"; \
	fi; \
	$(foreach module,$(clean_modules),\
		module_paths=( $(foreach path,$(strip $(RESET_TARGET_$(module))),"$(path)") ); \
		clean_paths "module '$(module)'" "$${module_paths[@]}";) \
	printf '$(clean_success_label) %s\n' "recovered disk space: $$(format_bytes "$${recovered}")"
else
	$(call print_error,unsupported HELP=$(HELP) \(supported values: true, false\))
endif

## END CLEAN ##
