.PHONY: typecheck lint unused duplication modulesize security check

typecheck:
	mypy core/ expense_month/

lint:
	ruff check core/ expense_month/ scripts/
	ruff format --check core/ expense_month/ scripts/

unused:
	vulture core/ expense_month/ vulture_whitelist.py --min-confidence 80

duplication:
	pylint --rcfile=pyproject.toml --ignore=migrations core/ expense_month/

modulesize:
	python scripts/check_module_sizes.py

security:
	semgrep --config=p/django --config=p/python core/ expense_month/ --error --quiet

check: typecheck lint unused duplication modulesize security
