## BEGIN CLEAN ##

CLEAN_STALE ?= false
CLEAN_FORCE ?= false

define clean_help
	$(call command_help_header,\
		$(if $(filter true,$(SCBOLT_CLI)),\
			scbolt clean [<module...>|--all|--stale],\
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
	else \
		printf '  %-31s %s\n' 'CLEAN_TARGET=<module...>' 'modules whose outputs should be removed'; \
		printf '  %-31s %s\n' 'CLEAN_TARGET=all' 'ask before removing all generated module outputs'; \
		printf '  %-31s %s\n' 'CLEAN_STALE=true' 'ask before removing stale module outputs'; \
		printf '  %-31s %s\n' 'CLEAN_FORCE=true' 'skip confirmation for CLEAN_STALE=true'; \
		printf '  %-31s %s\n' 'HELP=true' 'display this help'; \
		printf '  %-31s %s\n' 'REFERENCES=<condition...>' 'select references'; \
	fi
endef

.PHONY: __clean-stale-module
__clean-stale-module:
	@printf 'status\t%s\n' "$$( $(call metadata_state_field,$(CLEAN_MODULE),status) )"
	printf 'deps\t%s\n' "$(strip $(progress_deps_$(CLEAN_MODULE)))"
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
	if [ "$(CLEAN_STALE)" = "true" ] && [ -z "$(clean_all)" ]; then \
		stale_outputs="$$(mktemp)"; \
		stale_cleanup="$$(mktemp)"; \
		trap 'rm -f "$${stale_outputs}" "$${stale_cleanup}"' EXIT; \
		stale_modules=" "; \
		is_stale() { \
			case "$${stale_modules}" in *" $$1 "*) return 0 ;; *) return 1 ;; esac; \
		}; \
		pending_modules=" "; \
		is_pending() { \
			case "$${pending_modules}" in *" $$1 "*) return 0 ;; *) return 1 ;; esac; \
		}; \
		for module in $(if $(clean_modules),$(clean_modules),$(reset_stages)); do \
			module_report="$$(mktemp)"; \
			$(nested_make) LOGGING=false __clean-stale-module \
				CLEAN_MODULE="$${module}" PARAMS="$(PARAMS)" > "$${module_report}"; \
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
				awk -F '\t' '$$1 == "output" { print $$2 }' "$${module_report}" >> "$${stale_outputs}"; \
				awk -F '\t' '$$1 == "output" || $$1 == "sidecar" { print $$2 }' \
					"$${module_report}" >> "$${stale_cleanup}"; \
				stale_modules="$${stale_modules}$${module} "; \
			fi; \
			rm -f "$${module_report}"; \
		done; \
		sort -u "$${stale_outputs}" -o "$${stale_outputs}"; \
		sort -u "$${stale_cleanup}" -o "$${stale_cleanup}"; \
		if [ ! -s "$${stale_outputs}" ]; then \
			printf '$(success_label) %s\n' "no stale outputs found"; \
			exit 0; \
		fi; \
		printf 'Found %s stale outputs:\n' "$$(wc -l < "$${stale_outputs}")"; \
		sed 's/^/  - /' "$${stale_outputs}"; \
		if [ "$(CLEAN_FORCE)" != "true" ]; then \
			if [ ! -t 0 ]; then \
				printf '$(warning_label) %s\n' "clean --stale cancelled: interactive confirmation unavailable"; \
				exit 0; \
			fi; \
			read -r -p "Remove stale outputs? [y/N] " choice; \
			case "$${choice}" in \
				y|Y|yes|YES) ;; \
				*) printf '$(warning_label) %s\n' "clean --stale cancelled"; exit 0 ;; \
			esac; \
		fi; \
		mapfile -t stale_path_array < "$${stale_cleanup}"; \
		recovered="$$(bytes_for_paths "$${stale_path_array[@]}")"; \
		rm -rf "$${stale_path_array[@]}"; \
		printf '$(success_label) %s\n' "cleaned stale outputs: $${recovered} bytes"; \
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
		printf '$(success_label) %s\n' "cleaned $${label}: $${bytes} bytes"; \
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
		printf '$(success_label) %s\n' "cleaned cache: $${cache_bytes} bytes"; \
	fi; \
	if should_clean "logs"; then \
		log_bytes="$$(bytes_for_paths "$(log_dir)")"; \
		rm -rf "$(log_dir)"; \
		recovered=$$((recovered + log_bytes)); \
		printf '$(success_label) %s\n' "cleaned logs: $${log_bytes} bytes"; \
	fi; \
	$(foreach module,$(clean_modules),\
		module_paths=( $(foreach path,$(strip $(RESET_TARGET_$(module))),"$(path)") ); \
		clean_paths "module '$(module)'" "$${module_paths[@]}";) \
	printf '$(success_label) %s\n' "recovered disk space: $${recovered} bytes"
else
	$(call print_error,unsupported HELP=$(HELP) \(supported values: true, false\))
endif

## END CLEAN ##
