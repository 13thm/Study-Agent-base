#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
_d="$(pwd)"; while [ "$_d" != "/" ]; do [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }; _d="$(dirname "$_d")"; done
APP="${LAB_ROOT}/fastapi-chat-backend"; PORT="${PORT:-8000}"
bash "${APP}/scripts/serve.sh" start "${PORT}" || exit 1
trap 'echo; echo "▶ 停止服务: bash ${APP}/scripts/serve.sh stop ${PORT}"' EXIT
hr "Demo 03-1 · CRUD 全流程 + 统一错误响应体"
(cd "${APP}" && "${PYBIN}" scripts/demo03_1_crud.py --base-url "http://127.0.0.1:${PORT}")
