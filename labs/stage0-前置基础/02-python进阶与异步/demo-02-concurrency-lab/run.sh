#!/usr/bin/env bash
# 自动起 mock 服务 → 跑 7 组实验 → 关掉服务
set -uo pipefail
cd "$(dirname "$0")"

# ── 自动定位 lab 的 .venv 与共享函数（hr / need_pkgs / wait_http）──
_d="$(pwd)"
while [ "$_d" != "/" ]; do
  [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }
  _d="$(dirname "$_d")"
done
PORT="${PORT:-8899}"
BASE="http://127.0.0.1:$PORT"

echo "▶ 启动 mock 慢服务（${BASE}）..."
${PYBIN} slow_server.py > /tmp/slow_server.log 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null; echo "▶ mock 服务已停止 (pid=${SERVER_PID})"' EXIT

for i in $(seq 1 40); do
  curl -sf "${BASE}/health" >/dev/null 2>&1 && break
  sleep 0.25
done
curl -sf "${BASE}/health" >/dev/null || { echo "❌ mock 服务启动失败，看 /tmp/slow_server.log"; exit 1; }
echo "✅ mock 服务就绪 (pid=${SERVER_PID})"

${PYBIN} bench.py --base-url "${BASE}" --save out/bench_result.json "$@"
