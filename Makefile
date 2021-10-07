.DEFAULT_GOAL:=help

.PHONY: help
help: ## Display this help message
	@echo 'Usage: make <command>'
	@cat $(MAKEFILE_LIST) | grep '^[a-zA-Z]'  | \
	    sort | \
	    awk -F ':.*?## ' 'NF==2 {printf "  %-26s%s\n", $$1, $$2}'

.PHONY: wheel
wheel: ## Produce a python wheel
	poetry build

.PHONY: clean-pyc
clean-pyc: ## Remove python bytecode files and folders such as __pycache__
	find . -name '*.pyc' -exec rm --force {} +
	find . -name '*.pyo' -exec rm --force {} +
	find . -type d -name '__pycache__' -prune -exec rm -rf {} \;
	rm -rf .mypy_cache

.PHONY: clean-build
clean-build: ## Remove any python build artifacts
	rm --force --recursive build/
	rm --force --recursive dist/
	rm --force --recursive *.egg-info

.PHONY: mypy
# if tests contain errors they cannot test correct
mypy: ## Run `mypy`, a static type checker for python, see 'htmlcov/mypy/index.html'
	poetry run mypy --strict src/ --html-report=htmlcov/mypy --junit-xml=junit/mypy.xml

.PHONY: lint
lint: ## Run linters: flake8, codespell
	poetry run flake8
	poetry run codespell -f $$(find src -name '*.py') bin/dev_console.py

.PHONY: format
format: ## Run formatters: black, isort
	poetry run black .
	poetry run isort .

.PHONY: format-check
format-check: ## Let formatters only check whether any change would be made
	poetry run black --check .
	poetry run isort --check .

.PHONY: setup
setup: ## Setup development environment
	@echo 'Requires poetry from - https://poetry.eustace.io/docs/'
	poetry install
	poetry run pre-commit install
