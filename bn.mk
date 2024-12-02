#!/usr/bin/env make

.ONESHELL:

SHELL = /bin/bash
MAKEFLAGS += --silent
CONFIG = bn-config.mk

include $(CONFIG)

CONDA_ACTIVATE = source $$(conda info --base)/etc/profile.d/conda.sh ; conda activate ; conda activate
CONDA_DEACTIVATE = source $$(conda info --base)/etc/profile.d/conda.sh ; conda deactivate ; conda deactivate

# colors
NC = \033[0m
RED = \033[0;31m
BOLDRED = \033[1;31m
GREEN = \033[0;32m
BOLDGREEN = \033[1;32m
BOLD=\033[1m

define section
	@echo -e '$(GREEN)===== $(1) =====$(NC)'
endef

# directories
output = $(dir $(BN))

NODES_COMPARISON = $(output)/nodes_intersection.txt

##@ Help

.PHONY: help
help: ## display this help and exit
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make $(GREEN)<command>$(NC) [sample=control+treated+integrated] (default:sample=control+treated+integrated)\n\
	pipeline analysing Boolean Network models, and optionally comparing it with a reference model."}/^[a-zA-Z_-]+:.*?##/ \
	{ printf "  $(GREEN)%-22s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(BOLD)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Clean

.PHONY: clean
clean: ## clear results
	find $(dir $(BN))/* ! -name "$(notdir $(BN))" -exec rm -rf "{}" \;

##@ Comparison

.PHONY:
node-comparison: $(NODES_COMPARISON) ## get the common nodes between two Boolean Networks

$(NODES_COMPARISON): $(BN) $(REF)
	$(CONDA_ACTIVATE) bn
		python bonesis-tools/clitools/bn/get_nodes.py $(firstword $^) > $(dir $(firstword $^))nodes.txt
		python bonesis-tools/clitools/genename_standardization.py $(dir $(firstword $^))nodes.txt $(dir $(firstword $^))nodes.txt \
			--organism $(ORGANISM) --q
		python bonesis-tools/clitools/bn/get_nodes.py $(lastword $^) > $(dir $(lastword $^))nodes.txt
		python bonesis-tools/clitools/genename_standardization.py $(dir $(lastword $^))nodes.txt $(dir $(lastword $^))nodes.txt \
			--organism $(ORGANISM) --q
		comm -12 <(sort $(dir $(firstword $^))nodes.txt) <(sort $(dir $(lastword $^))nodes.txt) > $@
	$(CONDA DEACTIVATE)
