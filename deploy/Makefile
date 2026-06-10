# AutoTest Platform — Docker 镜像构建与推送脚本
# 用于 CI/CD 流水线或本地构建

# --- 配置 ---
REGISTRY ?= docker.io/autotest
IMAGE_NAME ?= autotest-api
TAG ?= latest

.PHONY: build push build-all push-all

build:
	docker build -t $(REGISTRY)/$(IMAGE_NAME):$(TAG) -f Dockerfile.api .

push:
	docker push $(REGISTRY)/$(IMAGE_NAME):$(TAG)

# 构建多版本标签
build-all:
	docker build -t $(REGISTRY)/$(IMAGE_NAME):latest -t $(REGISTRY)/$(IMAGE_NAME):$(TAG) -f Dockerfile.api .

push-all:
	docker push $(REGISTRY)/$(IMAGE_NAME):latest
	docker push $(REGISTRY)/$(IMAGE_NAME):$(TAG)
