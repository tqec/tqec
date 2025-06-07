.PHONY: check-fix
check-fix:
	ruff check --fix --target-version py310

.PHONY: check-format
check-format:
	ruff format

.PHONY: check-ruff-all
check-ruff-all:
	ruff check --fix --target-version py310
	ruff format
