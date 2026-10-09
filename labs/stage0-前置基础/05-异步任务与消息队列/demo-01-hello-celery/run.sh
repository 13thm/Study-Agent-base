#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
_d="$(pwd)"; while [ "$_d" != "/" ]; do [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }; _d="$(dirname "$_d")"; done
APP="${LAB_ROOT}/fastapi-chat-backend"
cd "${APP}"
hr() { printf '\n\033[36m══════ %s ══════\033[0m\n' "$1"; }

hr "Demo 05-1 · Celery 最小可用（提交→执行→取结果）"
hr "Celery 四个 Demo 的无 Broker 模拟（任务代码是真实生产代码）"
"${PYBIN}" scripts/demo05_simulate.py --only 1
hr "要跑真实 Celery"
cat <<'EOF'
  docker compose -f ../05-异步任务与消息队列/docker-compose.yml up -d redis
  celery -A app.tasks.celery_app worker -l info -Q default,heavy -c 2
  # 另开终端：
  python -c "from app.tasks.demo import add; print(add.delay(3,4).get())"
EOF
hr "相关代码"
echo "  app/tasks/celery_app.py  ← 全部生产级配置（逐行有注释）"
echo "  app/tasks/demo.py        ← add / heavy_task / flaky_call / 死信"
