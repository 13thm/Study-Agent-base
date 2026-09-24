#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
_d="$(pwd)"; while [ "$_d" != "/" ]; do [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }; _d="$(dirname "$_d")"; done
APP="${LAB_ROOT}/fastapi-chat-backend"; PORT="${PORT:-8001}"
bash "${APP}/scripts/serve.sh" start "${PORT}" || exit 1
trap 'bash "${APP}/scripts/serve.sh" stop "${PORT}"' EXIT
export BASE="http://127.0.0.1:${PORT}"
hr "Demo 03-2 · SSE 流式输出"
bash "${APP}/scripts/demo03_2_sse.sh"
