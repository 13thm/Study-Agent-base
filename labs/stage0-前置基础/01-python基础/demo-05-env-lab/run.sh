#!/usr/bin/env bash
# Demo 01-5 · 虚拟环境 5 个实验（在 /tmp 下建临时目录，跑完自动清理）
# ⚠️ 建议先自己手敲一遍再跑脚本对照，学习效果差 10 倍。
set -uo pipefail
cd "$(dirname "$0")"
bash env_experiments.sh all
