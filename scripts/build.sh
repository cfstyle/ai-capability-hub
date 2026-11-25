#!/usr/bin/env bash
set -euo pipefail

# 构建共享 Python 底座 mcp-runner:latest 与各应用镜像
# 用法:
#   ./scripts/build.sh
#   APT_MIRROR=http://mirrors.tencent.com PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple NPM_REGISTRY=https://registry.npmmirror.com ./scripts/build.sh

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

APT_MIRROR="${APT_MIRROR:-}"
PIP_INDEX_URL="${PIP_INDEX_URL:-}"
NPM_REGISTRY="${NPM_REGISTRY:-}"

echo "[1/2] Building shared Python base image: mcp-runner:latest ..."
docker build \
  ${APT_MIRROR:+--build-arg APT_MIRROR="$APT_MIRROR"} \
  ${PIP_INDEX_URL:+--build-arg PIP_INDEX_URL="$PIP_INDEX_URL"} \
  -t mcp-runner:latest \
  ./services/runner

echo "[2/2] Building docker-compose services (hub-core shares mcp-runner:latest) ..."
docker-compose build \
  ${APT_MIRROR:+--build-arg APT_MIRROR="$APT_MIRROR"} \
  ${PIP_INDEX_URL:+--build-arg PIP_INDEX_URL="$PIP_INDEX_URL"} \
  ${NPM_REGISTRY:+--build-arg NPM_REGISTRY="$NPM_REGISTRY"}

echo "Build complete."
