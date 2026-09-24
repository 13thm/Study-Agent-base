#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
_d="$(pwd)"; while [ "$_d" != "/" ]; do [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }; _d="$(dirname "$_d")"; done
APP="${LAB_ROOT}/fastapi-chat-backend"; PORT="${PORT:-8000}"
need_pkgs websockets
bash "${APP}/scripts/serve.sh" start "${PORT}" || exit 1
hr "Demo 03-3 · WebSocket 双向多轮对话"
(cd "${APP}" && "${PYBIN}" scripts/demo03_3_ws.py)
