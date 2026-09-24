#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
_d="$(pwd)"; while [ "$_d" != "/" ]; do [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }; _d="$(dirname "$_d")"; done
APP="${LAB_ROOT}/fastapi-chat-backend"
cd "${APP}"
hr() { printf '\n\033[36m══════ %s ══════\033[0m\n' "$1"; }

hr "Demo 04-3 · 对象存储上传全链路（sha256 秒传 / 预签名 URL / 权限）"
hr "对象存储：7 个验证场景"
"${PYBIN}" scripts/demo04_3_minio.py
hr "用真 MinIO 跑一遍（可选）"
echo "  docker compose -f ../04-数据库与存储/docker-compose.yml up -d minio"
echo "  APP_MINIO_ENDPOINT=localhost:9000 ${PYBIN} scripts/demo04_3_minio.py"
hr "相关代码"
echo "  app/services/storage.py  ← ObjectStorage 抽象 + MinIO/本地双实现"
echo "  tests/test_storage.py    ← 路径穿越、预签名过期/篡改的测试"
