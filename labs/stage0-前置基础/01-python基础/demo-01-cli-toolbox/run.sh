#!/usr/bin/env bash
# 一键演示 Demo 01-1。用法：bash run.sh
set -uo pipefail
cd "$(dirname "$0")"

# ── 自动定位 lab 的 .venv 与共享函数（hr / need_pkgs / wait_http）──
_d="$(pwd)"
while [ "$_d" != "/" ]; do
  [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }
  _d="$(dirname "$_d")"
done
hr() { printf '\n\033[36m── %s ──\033[0m\n' "$1"; }

hr "0. 先看 --help（好的 CLI 自带说明书）"
python3 toolbox.py --help

hr "1. freq：递归读目录，合并统计词频 Top 5"
python3 toolbox.py freq --path corpus/ --top 5

hr "2. stat：逐文件字符统计（含合计行）"
python3 toolbox.py stat --path corpus/

hr "3. clean：清洗并另存（out/ 目录自动创建）"
python3 toolbox.py clean --in corpus/a.txt --out out/a.clean.txt

hr "4. 异常边界：路径不存在 → 友好错误 + 退出码 1（不是 traceback）"
python3 toolbox.py freq --path 不存在的目录/ ; echo "退出码 = $?"

hr "5. 参数错误：--top 传了字符串 → argparse 自动报错 + 退出码 2"
python3 toolbox.py freq --path corpus/ --top abc ; echo "退出码 = $?"

hr "6. text_utils 自测（纯函数层，无 IO）"
python3 text_utils.py
