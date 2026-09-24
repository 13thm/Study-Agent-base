#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
_d="$(pwd)"; while [ "$_d" != "/" ]; do [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }; _d="$(dirname "$_d")"; done
APP="${LAB_ROOT}/fastapi-chat-backend"; PORT="${PORT:-8000}"
bash "${APP}/scripts/serve.sh" start "${PORT}" || exit 1
hr "Demo 03-4 · 幂等执行接口（并发 10 次只生效 1 次）"
(cd "${APP}" && "${PYBIN}" scripts/demo03_4_idempotent.py --base-url "http://127.0.0.1:${PORT}")
