#!/usr/bin/env bash
# ============================================================================
# AutoTest Platform — K8s 一键部署脚本
# ============================================================================
# Usage:
#   ./deploy.sh              # 使用 base 配置部署
#   ./deploy.sh dev          # 使用 dev overlay 部署
#   ./deploy.sh prod         # 使用 prod overlay 部署
#   ./deploy.sh --delete     # 删除所有资源
#   ./deploy.sh dev --delete # 删除 dev overlay 资源
# ============================================================================

set -euo pipefail

ENV="${1:-base}"
ACTION="${2:-apply}"

# Parse flags
if [[ "$ENV" == "--delete" ]]; then
    ENV="base"
    ACTION="delete"
fi
if [[ "$ACTION" == "--delete" ]]; then
    ACTION="delete"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="${SCRIPT_DIR}/k8s"

case "$ENV" in
    dev|prod)
        KUSTOMIZE_DIR="${K8S_DIR}/overlays/${ENV}"
        ;;
    base)
        KUSTOMIZE_DIR="${K8S_DIR}/base"
        ;;
    *)
        echo "Usage: $0 [base|dev|prod] [--delete]"
        exit 1
        ;;
esac

echo "============================================"
echo " AutoTest Platform · K8s Deploy"
echo " Environment: ${ENV}"
echo " Action:      ${ACTION}"
echo " Directory:   ${KUSTOMIZE_DIR}"
echo "============================================"

# Check prerequisites
for cmd in kubectl; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "ERROR: $cmd is not installed"
        exit 1
    fi
done

# Check cluster connectivity
if ! kubectl cluster-info &> /dev/null; then
    echo "ERROR: Cannot connect to Kubernetes cluster"
    exit 1
fi

if [[ "$ACTION" == "delete" ]]; then
    echo ""
    read -rp "Are you sure you want to DELETE all resources in '${ENV}'? [y/N] " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo "Aborted."
        exit 0
    fi
fi

echo ""

if command -v kustomize &> /dev/null && [[ "$ACTION" == "apply" ]]; then
    echo "[1/2] Building kustomize overlay..."
    kustomize build "$KUSTOMIZE_DIR" | kubectl apply -f -
else
    echo "[1/2] Applying resources via kubectl..."
    kubectl "$ACTION" -k "$KUSTOMIZE_DIR"
fi

echo ""

if [[ "$ACTION" == "apply" ]]; then
    echo "[2/2] Waiting for deployments to be ready..."
    kubectl -n autotest wait --for=condition=available \
        --timeout=300s \
        deployment/autotest-api \
        deployment/autotest-worker \
        2>/dev/null || true

    echo ""
    echo "============================================"
    echo " Deploy Status"
    echo "============================================"
    kubectl -n autotest get all
    echo ""
    echo "============================================"
    echo " Endpoints"
    echo "============================================"
    echo "  API (ClusterIP):  http://autotest-api.autotest:8000"
    echo "  Swagger UI:       http://autotest-api.autotest:8000/docs"
    echo "  Health:           http://autotest-api.autotest:8000/health"
    echo ""
    echo "To access locally:"
    echo "  kubectl -n autotest port-forward svc/autotest-api 8000:8000"
    echo "============================================"
else
    echo "Resources deleted successfully."
fi
