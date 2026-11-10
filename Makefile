.PHONY: run validate test check export
run:
	python -m ingredient_api
validate:
	python scripts/validate_data.py
test:
	python -m unittest discover -s tests -v
check: validate test
	python -m compileall -q ingredient_api scripts examples tests
export:
	python scripts/export_data.py --output dist
