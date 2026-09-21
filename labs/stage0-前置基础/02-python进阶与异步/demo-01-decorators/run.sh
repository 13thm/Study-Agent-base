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

hr "装饰器三连 · 7 个场景（含 3 个必须验证的现象）"
$PYBIN demo_decorators.py
