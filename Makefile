# Directory for the submodule and output directory for generated files
PROTO_DIR = nebius-api

# Always execute these targets
.PHONY: update-submodule compile-proto generate check-generated verify-generated update-proto gen-doc tag-ver tag-ver-push

# Ensure that update-proto is the default target
.DEFAULT_GOAL := update-proto

update-submodule:
	git submodule update --init --recursive --remote

compile-proto:
	python scripts/generate_api.py

generate: compile-proto

check-generated:
	python scripts/generate_api.py --check

verify-generated:
	python scripts/generate_api.py --verify-partitions --jobs 2

update-proto: update-submodule generate

gen-doc:
	pydoctor

tag-ver:
	src/scripts/tag_version.sh --no-push

tag-ver-push:
	src/scripts/tag_version.sh --push
