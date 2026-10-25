PROJECT_NAME=general-extract-v2
PYCMD=python
PIPCMD=pip
ENV_PATH=venv
ROOT_PACKAGE=extractor_pdf

.PHONY: help deps test dryrun extract

help: Makefile
	@echo
	@echo " Choose a command to run in "$(PROJECT_NAME)":"
	@echo
	@sed -n 's/^##//p' $< | column -t -s ':' |  sed -e 's/^/ /'

## deps: Install all the dependencies
deps:
	$(PIPCMD) install -r requirements.txt

## update_deps: Use when requirements.txt updated
update_deps:
	$(PIPCMD) install -r requirements.txt -U

## test: 本地解析链路自检（不调用 LLM）
test:
	$(PYCMD) extractor_pdf/test_local_parsing.py

## dryrun: 解析+切窗自检（不调用 LLM），用法 make dryrun file=合同.pdf
dryrun:
	$(PYCMD) -m $(ROOT_PACKAGE) "$(file)" --dry-run

## extract: 抽取合同要素，用法 make extract file=合同.pdf out=result.json
extract:
	$(PYCMD) -m $(ROOT_PACKAGE) "$(file)" -o "$(out)"
