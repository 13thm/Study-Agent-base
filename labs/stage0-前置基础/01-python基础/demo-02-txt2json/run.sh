#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"

# ── 自动定位 lab 的 .venv 与共享函数（hr / need_pkgs / wait_http）──
_d="$(pwd)"
while [ "$_d" != "/" ]; do
  [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }
  _d="$(dirname "$_d")"
done
hr() { printf '\n\033[36m── %s ──\033[0m\n' "$1"; }

hr "1. 正常跑：12 行脏数据，容错解析"
python3 converter.py --show 4

hr "2. 输出文件长什么样（前 40 行）"
head -40 data/out/chat_log.json

hr "3. 边界：空文件 → total=0，不报错"
python3 converter.py --src data/edge/empty.txt --dst data/out/empty.json --show 0

hr "4. 边界：全是脏数据 → valid=0，errors 记录全部行号"
python3 converter.py --src data/edge/all_dirty.txt --dst data/out/dirty.json --show 0

hr "5. 边界：非 UTF-8 文件 → 友好报错 + 退出码 3"
python3 converter.py --src data/edge/gbk.txt --dst data/out/gbk.json ; echo "退出码 = $?"

hr "6. --strict 模式：一遇脏行就失败 + 退出码 2（对照实验）"
python3 converter.py --strict ; echo "退出码 = $?"

hr "7. 输入文件不存在 → 退出码 1"
python3 converter.py --src nope.txt ; echo "退出码 = $?"
