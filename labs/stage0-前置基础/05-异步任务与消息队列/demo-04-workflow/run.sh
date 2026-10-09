#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
_d="$(pwd)"; while [ "$_d" != "/" ]; do [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }; _d="$(dirname "$_d")"; done
APP="${LAB_ROOT}/fastapi-chat-backend"
cd "${APP}"
hr() { printf '\n\033[36m══════ %s ══════\033[0m\n' "$1"; }

hr "Demo 05-4 · 工作流编排（chain/group/chord）+ 定时任务"
hr "chain / group / chord 与三道思考题"
"${PYBIN}" scripts/demo05_simulate.py --only 4
