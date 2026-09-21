#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"

# ── 自动定位 lab 的 .venv 与共享函数（hr / need_pkgs / wait_http）──
_d="$(pwd)"
while [ "$_d" != "/" ]; do
  [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }
  _d="$(dirname "$_d")"
done
hr() { printf '\n\033[36m══════ %s ══════\033[0m\n' "$1"; }
hr "1. 内置 8 个用例（python state.py）"
${PYBIN} state.py
hr "2. 用 pytest 跑同一批用例（验证两种跑法都行）"
${PYBIN} -m pytest state.py -v 2>&1 | tail -14
hr "3. mypy 静态检查（TypedDict 的价值就在这里：运行时不校验，靠 mypy）"
${PYBIN} -m mypy state.py --ignore-missing-imports 2>&1 | tail -5
