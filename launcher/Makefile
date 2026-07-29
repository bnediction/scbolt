SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:

ROOT := $(abspath ..)
BUILD_DIR ?= $(ROOT)/build/launcher
DIST_DIR ?= $(ROOT)/dist
VERSION ?= $(shell tr -d '[:space:]' < $(ROOT)/VERSION)
REVISION ?= $(shell git -C $(ROOT) rev-parse HEAD 2>/dev/null || printf unknown)
IMAGE ?= ghcr.io/bnediction/scbolt:v$(VERSION)
GOCACHE ?= $(shell go env GOCACHE)

GO_BUILD := env CGO_ENABLED=0 GOCACHE=$(GOCACHE) go build
GO_LDFLAGS := -s -w \
	-X main.launcherVersion=$(VERSION) \
	-X main.sourceRevision=$(REVISION) \
	-X main.defaultImage=$(IMAGE)

.PHONY: all release manifest manifest-check test native linux-amd64 windows-amd64 darwin-amd64 darwin-arm64

all: linux-amd64 windows-amd64 darwin-amd64 darwin-arm64

release: BUILD_DIR := $(DIST_DIR)
release: all

manifest:
	cd $(ROOT)
	env GOCACHE=$(GOCACHE) go run ./launcher/scbolt \
		__generate-completion-manifest --root .

manifest-check:
	cd $(ROOT)
	tmp="$$(mktemp)"
	trap 'rm -f "$${tmp}"' EXIT
	env GOCACHE=$(GOCACHE) go run ./launcher/scbolt \
		__generate-completion-manifest --root . \
		--output "$${tmp}"
	cmp launcher/scbolt/completion_manifest.json "$${tmp}"

test: manifest-check
	cd $(ROOT)
	env GOCACHE=$(GOCACHE) go test ./launcher/...

native: manifest
	mkdir -p $(BUILD_DIR)
	cd $(ROOT)
	$(GO_BUILD) \
		-ldflags '$(GO_LDFLAGS)' \
		-o $(BUILD_DIR)/scbolt-native ./launcher/scbolt

linux-amd64: manifest
	mkdir -p $(BUILD_DIR)
	cd $(ROOT)
	GOOS=linux GOARCH=amd64 $(GO_BUILD) \
		-ldflags '$(GO_LDFLAGS)' \
		-o $(BUILD_DIR)/scbolt-linux-amd64 ./launcher/scbolt

windows-amd64: manifest
	mkdir -p $(BUILD_DIR)
	cd $(ROOT)
	GOOS=windows GOARCH=amd64 $(GO_BUILD) \
		-ldflags '$(GO_LDFLAGS)' \
		-o $(BUILD_DIR)/scbolt-windows-amd64.exe ./launcher/scbolt

darwin-amd64: manifest
	mkdir -p $(BUILD_DIR)
	cd $(ROOT)
	GOOS=darwin GOARCH=amd64 $(GO_BUILD) \
		-ldflags '$(GO_LDFLAGS)' \
		-o $(BUILD_DIR)/scbolt-darwin-amd64 ./launcher/scbolt

darwin-arm64: manifest
	mkdir -p $(BUILD_DIR)
	cd $(ROOT)
	GOOS=darwin GOARCH=arm64 $(GO_BUILD) \
		-ldflags '$(GO_LDFLAGS)' \
		-o $(BUILD_DIR)/scbolt-darwin-arm64 ./launcher/scbolt
