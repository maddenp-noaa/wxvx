val = $(shell jq -r $(1) $(METAJSON))

RECIPE_DIR = $(shell cd ./recipe && pwd)
BUILD      = $(call val,.build)
BUILDNUM   = $(call val,.buildnum)
CHANNELS   = $(addprefix -c ,$(shell tr '\n' ' ' <$(RECIPE_DIR)/channels)) -c local
NAME       = $(call val,.name)
VERSION    = $(call val,.version)
METADEPS   = $(RECIPE_DIR)/meta.yaml src/wxvx/resources/info.json
METAJSON   = $(RECIPE_DIR)/meta.json
TARGETS    = devshell env format lint meta package test typecheck unittest

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

package: meta
	conda build $(CHANNELS) --error-overlinking --override-channels $(RECIPE_DIR)

test:
	recipe/run_test.sh

typecheck:
	recipe/run_test.sh typecheck

unittest:
	recipe/run_test.sh unittest

$(METAJSON): $(METADEPS)
	condev-meta
