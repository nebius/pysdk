# Directory for the submodule and output directory for generated files
PROTO_DIR = nebius-api
OUT_DIR = src/nebius/api
OUT_NEW_DIR = src/nebius/api-new

# Always execute these targets
.PHONY: update-submodule compile-proto update-proto gen-doc tag-ver tag-ver-push

# Ensure that update-proto is the default target
.DEFAULT_GOAL := update-proto

update-submodule:
	git submodule update --init --recursive --remote

# TODO: remove "--timeout 0"
compile-proto:
	rm -rf $(OUT_NEW_DIR)
	mkdir $(OUT_NEW_DIR)
	buf generate $(PROTO_DIR) --include-imports --timeout 0
	rm -rf $(OUT_NEW_DIR)/google
	find $(OUT_NEW_DIR) -type d -exec touch {}/__init__.py \;
	rm -rf $(OUT_DIR)
	mv $(OUT_NEW_DIR) $(OUT_DIR)

move-imports:
	find $(OUT_DIR) -type f -name "*.py" ! -name "__init__.py" -exec python3 src/nebius/base/protos/compiler/mover.py --level warning --input {} --output {} --prefix buf=nebius.api.buf nebius=nebius.api.nebius \;
	find $(OUT_DIR) -type f -name "*.pyi" -exec python3 src/nebius/base/protos/compiler/mover.py --level warning --input {} --output {} --prefix buf=nebius.api.buf nebius=nebius.api.nebius \;

generate: compile-proto move-imports

update-proto: update-submodule generate

gen-doc:
	pydoctor || true

tag-ver:
	src/scripts/tag_version.sh --no-push

tag-ver-push:
	src/scripts/tag_version.sh --push
