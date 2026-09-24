#!/usr/bin/env bash
# Demo 03-5 · Nginx 反向代理（需要 Docker）
set -uo pipefail
cd "$(dirname "$0")"
_d="$(pwd)"; while [ "$_d" != "/" ]; do [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }; _d="$(dirname "$_d")"; done

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  hr "Demo 03-5 · Nginx 反向代理"
  bad "Docker 不可用，跳过实机验证。下面是配置讲解（读完再找有 Docker 的环境跑一次）"
  echo
  echo "── nginx.conf 里的 4 个教学重点 ──"
  grep -nE "limit_req_zone|upstream api_pool|proxy_buffering off|client_max_body_size|X-Forwarded-For|X-Request-ID|Upgrade" nginx.conf | sed 's/^/  /'
  echo
  echo "── 启动命令 ──"
  echo "  docker compose up -d && bash verify.sh && docker compose down"
  exit 0
fi

hr "Demo 03-5 · Nginx 反向代理（docker compose 起 1 nginx + 2 api）"
docker compose up -d
echo "▶ 等待三个容器 healthy（首次要装依赖，约 1~2 分钟）..."
for i in $(seq 1 120); do
  n=$(docker compose ps --format json 2>/dev/null | grep -c '"Health":"healthy"' || echo 0)
  [ "${n:-0}" -ge 3 ] && break
  sleep 2
done
docker compose ps
bash verify.sh
echo
echo "▶ 演示结束。停止：docker compose down"
