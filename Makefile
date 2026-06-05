.PHONY: install test smoke regression report clean help

# 默认环境
ENV ?= dev
TAGS ?= smoke
WORKERS ?= 4

help: ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## 安装依赖
	pip install -e ".[all]"

lock: ## 锁定依赖版本（生成 requirements.lock）
	pip install pip-tools
	pip-compile pyproject.toml -o requirements.lock --extra all --strip-extras --resolver backtracking
	@echo ">>> requirements.lock 已更新 <<<"

sync: ## 从 lock 文件同步安装
	pip-sync requirements.lock

test: ## 运行所有测试
	pytest --env=$(ENV) -v --alluredir=reports/allure-results

smoke: ## 运行冒烟测试
	pytest --env=$(ENV) -m smoke -v --alluredir=reports/allure-results

regression: ## 运行回归测试
	pytest --env=$(ENV) -m regression -v --alluredir=reports/allure-results

parallel: ## 并行执行测试
	pytest --env=$(ENV) -n $(WORKERS) -v --alluredir=reports/allure-results

report: ## 生成 Allure 报告
	allure serve reports/allure-results

report-html: ## 生成 HTML 报告
	pytest --env=$(ENV) --html=reports/html/report.html --self-contained-html

collect: ## 只收集用例不执行
	pytest --collect-only --env=$(ENV)

debug: ## 调试模式（详细日志）
	pytest --env=$(ENV) -v --log-cli-level=DEBUG

clean: ## 清理报告和日志
	rm -rf reports/* logs/* .pytest_cache __pycache__ */__pycache__
