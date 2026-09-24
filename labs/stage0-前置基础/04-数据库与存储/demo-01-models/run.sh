#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
_d="$(pwd)"; while [ "$_d" != "/" ]; do [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }; _d="$(dirname "$_d")"; done
APP="${LAB_ROOT}/fastapi-chat-backend"
cd "${APP}"
hr() { printf '\n\033[36m══════ %s ══════\033[0m\n' "$1"; }

hr "Demo 04-1 · SQLAlchemy 三表建模（建表/索引/CRUD/级联/N+1）"
need_pkgs sqlalchemy
hr "SQLAlchemy 2.0 三表建模：8 个验证场景"
"${PYBIN}" scripts/demo04_1_db.py
hr "自己看一遍模型定义（2.0 声明式写法）"
echo "  app/db/models.py   ← Mapped[T] + mapped_column + relationship"
echo "  app/db/base.py     ← 引擎/连接池/SQLite 外键 PRAGMA"
echo "  app/db/repo.py     ← Repository 层（所有查询收敛在这里）"
