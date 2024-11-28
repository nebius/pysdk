# Directory for the submodule and output directory for generated files
PROTO_DIR = nebius-api
OUT_DIR = src/nebius/api

# Always execute these targets
.PHONY: update-submodule compile-proto update-proto

# Ensure that update-proto is the default target
.DEFAULT_GOAL := update-proto

update-submodule:
	git submodule update --init --recursive --remote

compile-proto:
	rm -rf $(OUT_DIR)
	mkdir $(OUT_DIR)
	buf generate nebius-api --include-imports
	rm -rf $(OUT_DIR)/google
	find $(OUT_DIR) -type d -exec touch {}/__init__.py \;

move-imports:
	find $(OUT_DIR) -type f -name "*.py" -exec python3 src/compiler/mover.py --level warning --input {} --output {} --prefix buf=nebius.api.buf nebius=nebius.api.nebius \;
	find $(OUT_DIR) -type f -name "*.pyi" -exec python3 src/compiler/mover.py --level warning --input {} --output {} --prefix buf=nebius.api.buf nebius=nebius.api.nebius \;

update-proto: update-submodule compile-proto move-imports
