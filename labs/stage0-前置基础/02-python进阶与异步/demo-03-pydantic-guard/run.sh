#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"

# ── 自动定位 lab 的 .venv 与共享函数（hr / need_pkgs / wait_http）──
_d="$(pwd)"
while [ "$_d" != "/" ]; do
  [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }
  _d="$(dirname "$_d")"
done
${PYBIN} guard.py
