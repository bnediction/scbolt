## BEGIN CLEAN ##

define clean_help
	$(call command_help_header,\
		$(if $(filter true,$(SCBOLT_CLI)),\
			scbolt clean [<module...>|--all],\
			make clean [CLEAN_TARGET=<module...>|all] [HELP=true]),\
		Clean cache$(comma) logs and optionally remove selected module outputs.)
	@printf '%s\n' 'Without modules, clean asks before removing cache and logs.'
	@printf '%s\n\n' 'With --all, clean asks before removing cache, logs, and all generated module outputs.'
	@printf '$(bold)Parameters$(nc)\n'
	@if [ "$(SCBOLT_CLI)" = "true" ]; then \
		printf '  %-31s %s\n' '<module...>' 'modules whose outputs should be removed'; \
		printf '  %-31s %s\n' '--all' 'ask before removing all generated module outputs'; \
		printf '  %-31s %s\n' '--help, -h' 'display this help'; \
		printf '  %-31s %s\n' '--params=<file>' 'select parameter file'; \
		printf '  %-31s %s\n' '--references=<condition...>' 'select references'; \
	else \
		printf '  %-31s %s\n' 'CLEAN_TARGET=<module...>' 'modules whose outputs should be removed'; \
		printf '  %-31s %s\n' 'CLEAN_TARGET=all' 'ask before removing all generated module outputs'; \
		printf '  %-31s %s\n' 'HELP=true' 'display this help'; \
		printf '  %-31s %s\n' 'REFERENCES=<condition...>' 'select references'; \
	fi
endef

.PHONY: clean
clean:
ifeq ($(HELP),true)
	$(clean_help)
else ifeq ($(HELP),false)
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
