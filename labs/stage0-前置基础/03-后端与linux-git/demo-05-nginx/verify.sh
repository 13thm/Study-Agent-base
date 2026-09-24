#!/usr/bin/env bash
# Demo 03-5 验证脚本：负载均衡 / SSE 穿透 / 限流 / 大文件
set -uo pipefail
BASE="${BASE:-http://127.0.0.1:8080}"
hr() { printf '\n\033[36m── %s ──\033[0m\n' "$1"; }

hr "0. 环境检查"
docker compose ps --format 'table {{.Name}}\t{{.Status}}' 2>/dev/null || echo "  (docker compose ps 不可用)"
curl -sf "${BASE}/health/live" >/dev/null && echo "  ✅ nginx → 上游连通" || { echo "  ❌ 不通，先 docker compose up -d"; exit 1; }

hr "1. 负载均衡：连发 10 次，看两个实例各分到几次"
for i in $(seq 1 10); do curl -s "${BASE}/health/live" -o /dev/null -w "%{http_code} "; done; echo
echo "  → 看 nginx 日志里的 upstream 分布："
docker compose logs nginx 2>/dev/null | grep -oE 'up=[0-9.]+:8000' | sort | uniq -c || \
  echo "  （用 docker compose exec nginx tail /var/log/nginx/access.log 手动看）"

hr "2. SSE 穿透验证（★ 最重要）"
echo "  经 nginx（有 proxy_buffering off）："
START=$(date +%s%N 2>/dev/null || python3 -c 'import time;print(int(time.time()*1e9))')
curl -sN "${BASE}/api/chat/stream?q=测试SSE" 2>/dev/null | head -6 | while IFS= read -r l; do
  NOW=$(python3 -c 'import time;print(f"{time.time():.2f}")'); echo "    [${NOW}] ${l:0:60}"
done
echo "  → 每帧时间戳应该【递增】（逐帧到达）。若全部同一时刻 = 被缓冲了。"
echo "  对照实验：把 nginx.conf 里的 proxy_buffering off 注释掉，docker compose restart nginx，再跑一次"

hr "3. 限流验证（10r/s + burst 20）"
CODES=$(for i in $(seq 1 60); do curl -s -o /dev/null -w "%{http_code}\n" "${BASE}/api/items"; done | sort | uniq -c)
echo "$CODES" | sed 's/^/    /'
echo "  → 应该看到大量 503（nginx 限流默认返回 503，可用 limit_req_status 429 改成 429）"

hr "4. 大文件上传（client_max_body_size 50m）"
dd if=/dev/zero of=/tmp/big.bin bs=1m count=5 2>/dev/null
curl -s -o /dev/null -w "    5MB 上传 → %{http_code}\n" -X POST "${BASE}/api/items" \
     -F "file=@/tmp/big.bin" 2>/dev/null || echo "    (该接口不接受文件，返回 422 也算通过：说明没被 nginx 的 413 挡住)"
rm -f /tmp/big.bin

hr "5. WebSocket 穿透"
echo "  浏览器打开 ${BASE}/static/ws.html → 点连接 → 应显示绿点"
echo "  或命令行： python -c \"import asyncio,websockets;...\" （见 demo-03 的客户端脚本）"
