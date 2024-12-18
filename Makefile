val = $(shell jq -r $(1) $(METAJSON))

BUILD      = $(call val,.build)
BUILDNUM   = $(call val,.buildnum)
CHANNELS   = $(addprefix -c ,$(shell tr '\n' ' ' <$(RECIPE_DIR)/channels)) -c local
METADEPS   = $(RECIPE_DIR)/meta.yaml src/*/resources/info.json
METAJSON   = $(RECIPE_DIR)/meta.json
NAME       = $(call val,.name)
RECIPE_DIR = $(shell cd ./recipe && pwd)
TARGETS    = devshell env format lint package test typecheck unittest
VERSION    = $(call val,.version)

export RECIPE_DIR := $(RECIPE_DIR)

.PHONY: $(TARGETS)

all:
	$(error Valid targets are: $(TARGETS))

devshell:
	condev-shell || true

env: package
	conda create -y -n $(NAME)-$(VERSION)-$(BUILDNUM) $(CHANNELS) $(NAME)=$(VERSION)=$(BUILD)

format:
	@./format

lint:
	recipe/run_test.sh lint

meta: $(METAJSON)

package:
	conda build $(CHANNELS) --error-overlinking --override-channels $(RECIPE_DIR)

test:
	recipe/run_test.sh

typecheck:
	recipe/run_test.sh typecheck

unittest:
	recipe/run_test.sh unittest

$(METAJSON): $(METADEPS)
	condev-meta
