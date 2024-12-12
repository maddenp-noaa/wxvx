export RECIPE_DIR := $(shell cd ./recipe && pwd)

BUILDNUM := $(call val,.buildnum)
CHANNELS := $(addprefix -c ,$(shell tr '\n' ' ' <$(RECIPE_DIR)/channels)) -c local
INFOJSON := src/wxvx/resources/info.json
METADEPS := $(RECIPE_DIR)/meta.yaml $(INFOJSON)
NAME     := $(call val,.name)
TARGETS  := devshell env format lint package test typecheck unittest
VERSION  := $(call val,.version)

val = $(shell jq -r $(1) $(INFOJSON))

.PHONY: $(TARGETS)

all:
	$(error Valid targets are: $(TARGETS))

devshell:
	condev-shell || true

env: package
	@echo conda create -y -n $(NAME)-$(VERSION)-$(BUILDNUM) $(CHANNELS) $(NAME)=$(VERSION)=*_$(BUILDNUM)

format:
	@./format

lint:
	recipe/run_test.sh lint

package:
	conda build $(CHANNELS) --error-overlinking --override-channels $(RECIPE_DIR)

test:
	recipe/run_test.sh

typecheck:
	recipe/run_test.sh typecheck

unittest:
	recipe/run_test.sh unittest
