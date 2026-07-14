# Directory for the submodule and output directory for generated files
PROTO_DIR = nebius-api
# Always execute these targets
.PHONY: update-submodule compile-proto check-generated bootstrap-generator update-proto gen-doc tag-ver tag-ver-push

# Ensure that update-proto is the default target
.DEFAULT_GOAL := update-proto

update-submodule:
	git submodule update --init --recursive --remote

compile-proto:
	python3 scripts/generate_api.py

check-generated:
	python3 scripts/generate_api.py --check

bootstrap-generator:
	python3 scripts/bootstrap_generator.py

generate: compile-proto

update-proto: update-submodule generate

gen-doc:
	pydoctor || true

tag-ver:
	src/scripts/tag_version.sh --no-push

tag-ver-push:
	src/scripts/tag_version.sh --push
