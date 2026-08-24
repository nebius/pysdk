.PHONY: gen-doc

gen-doc:
	rm -rf docs/generated
	PYTHONPATH=src pydoctor
	python scripts/check_generated_docs.py docs/generated
