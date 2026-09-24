#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
_d="$(pwd)"; while [ "$_d" != "/" ]; do [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }; _d="$(dirname "$_d")"; done
APP="${LAB_ROOT}/fastapi-chat-backend"
cd "${APP}"
hr() { printf '\n\033[36m══════ %s ══════\033[0m\n' "$1"; }

hr "Demo 04-2 · Redis 会话记忆（滑动窗口 + TTL + 冷热双层）"
hr "Redis 会话记忆：5 个验证场景"
"${PYBIN}" scripts/demo04_2_redis_memory.py
hr "记忆层代码位置"
echo "  app/services/memory.py   ← LPUSH + LTRIM + EXPIRE 滑动窗口"
echo "  app/api/agent.py         ← POST /api/chat（带记忆的对话接口）"
hr "用真 Redis 跑一遍（可选）"
echo "  docker compose -f ../04-数据库与存储/docker-compose.yml up -d redis"
echo "  APP_USE_FAKE_REDIS=0 ${PYBIN} scripts/demo04_2_redis_memory.py"
