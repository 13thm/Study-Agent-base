#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
_d="$(pwd)"; while [ "$_d" != "/" ]; do [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }; _d="$(dirname "$_d")"; done
APP="${LAB_ROOT}/fastapi-chat-backend"
cd "${APP}"
hr() { printf '\n\033[36m══════ %s ══════\033[0m\n' "$1"; }

hr "Demo 04-4 · PGVector 与向量检索基础"
need_pkgs numpy
hr "PGVector（无 PG 时自动降级为 numpy 等价演示）"
"${PYBIN}" scripts/demo04_4_pgvector.py
hr "要跑真实 PGVector"
cat <<'EOF'
  docker run -d --name pg -p 5432:5432 -e POSTGRES_PASSWORD=pw pgvector/pgvector:pg16
  psql "postgresql://postgres:pw@localhost:5432/postgres" -c "CREATE EXTENSION vector;"
  APP_DATABASE_URL=postgresql://postgres:pw@localhost:5432/postgres \
    python scripts/demo04_4_pgvector.py
  或直接：docker compose -f ../04-数据库与存储/docker-compose.yml up -d postgres
EOF
