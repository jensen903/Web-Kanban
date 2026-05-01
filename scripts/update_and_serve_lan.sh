#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

export WEB_KANBAN_DATA_ROOT="${WEB_KANBAN_DATA_ROOT:-/Users/apple/窄巷口/可视化看板}"
export WEB_KANBAN_RAW_DIR="${WEB_KANBAN_RAW_DIR:-${WEB_KANBAN_DATA_ROOT}/Inputs/经营数据}"
export WEB_KANBAN_RAW_ARCHIVE_DIR="${WEB_KANBAN_RAW_ARCHIVE_DIR:-${WEB_KANBAN_DATA_ROOT}/Inputs/经营数据_历史备份}"
export WEB_KANBAN_STORE_MASTER_DIR="${WEB_KANBAN_STORE_MASTER_DIR:-${WEB_KANBAN_DATA_ROOT}/Master_门店主表}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-4180}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "${PROJECT_ROOT}"

echo "==> 项目目录: ${PROJECT_ROOT}"
echo "==> 原始数据目录: ${WEB_KANBAN_RAW_DIR}"
echo "==> 历史归档目录: ${WEB_KANBAN_RAW_ARCHIVE_DIR}"
echo "==> 门店主表目录: ${WEB_KANBAN_STORE_MASTER_DIR}"
echo "==> 服务地址: http://${HOST}:${PORT}"

echo "==> Step 1/4: 更新标准化数据层"
"${PYTHON_BIN}" src/data_pipeline/build_local_warehouse.py

echo "==> Step 2/4: 重建查询库"
"${PYTHON_BIN}" src/data_pipeline/build_query_db.py

echo "==> Step 3/4: 导出前端数据集"
"${PYTHON_BIN}" src/data_pipeline/export_frontend_dataset.py

echo "==> Step 4/4: 启动局域网看板服务"
HOST="${HOST}" PORT="${PORT}" "${PYTHON_BIN}" src/backend/server.py
