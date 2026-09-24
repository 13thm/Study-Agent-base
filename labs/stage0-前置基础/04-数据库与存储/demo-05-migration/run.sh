#!/usr/bin/env bash
# Demo 04-5 · Alembic 迁移四场景演练
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"    # ★ 必须在 cd 之前记住自己的位置
cd "$(dirname "$0")"
_d="$(pwd)"; while [ "$_d" != "/" ]; do [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }; _d="$(dirname "$_d")"; done
APP="${LAB_ROOT}/fastapi-chat-backend"
cd "${APP}"
export APP_DATABASE_URL="sqlite+pysqlite:///./data/migration_demo.db"
rm -f data/migration_demo.db
ALEMBIC="${PYBIN} -m alembic"
hr() { printf '\n\033[36m══════ %s ══════\033[0m\n' "$1"; }
say() { printf '\033[33m$ %s\033[0m\n' "$1"; }

hr "场景 1 · 从零建表：autogenerate → 人工检查 → upgrade head"
say "alembic revision --autogenerate -m 'init tables'"
${ALEMBIC} revision --autogenerate -m "init tables" 2>&1 | tail -8
REV1=$(${ALEMBIC} heads 2>/dev/null | awk '{print $1}')
echo "  → 生成的迁移脚本: migrations/versions/${REV1}_init_tables.py"
echo "  ⚠️ 【必须人工检查】autogenerate 会漏掉这些东西（任务书要求你能举例）："
echo "     · 索引的特定参数（如 PG 的 CONCURRENTLY）"
echo "     · 表/列的注释、存储引擎、分区设置"
echo "     · 数据迁移（加列后的默认值回填，它只会写 server_default）"
echo "     · 重命名（它看成 drop + add，会丢数据！要手动改成 alter_column）"
say "alembic upgrade head"
${ALEMBIC} upgrade head 2>&1 | tail -3
say 'python -c "查表"'
${PYBIN} -c "
import sqlite3
c = sqlite3.connect('data/migration_demo.db')
print('  表:', [r[0] for r in c.execute(\"select name from sqlite_master where type='table'\")])
print('  alembic_version:', list(c.execute('select * from alembic_version')))"

hr "场景 2 · 加一个可空列（最常见的变更）"
cat >> app/db/models.py <<'EOF'


# ── Demo 04-5 场景2/3 临时新增的字段（演练完会被 run.sh 还原）──
class DemoExtra(Base):
    __tablename__ = "demo_extra"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    note: Mapped[str | None] = mapped_column(String(200))
EOF
say "alembic revision --autogenerate -m 'add demo_extra table'"
${ALEMBIC} revision --autogenerate -m "add demo_extra table" 2>&1 | tail -4
say "alembic upgrade head"
${ALEMBIC} upgrade head 2>&1 | tail -2

hr "场景 3 · ★ 给已有表加【非空】列 —— 必须分三步（直接加会锁表/失败）"
cat <<'EOF'
  错误做法：ALTER TABLE messages ADD COLUMN source VARCHAR(32) NOT NULL;
    → 已有 13 万行数据没有这个值，数据库要么报错，要么用一个隐式默认值填满
    → 大表上这条 DDL 会【长时间持有锁】，线上服务直接卡死

  正确的三步（膨胀-收缩模式 expand/contract）：
    第1步 expand  : 加【可空】列（瞬间完成，不锁表）
    第2步 backfill: 分批 UPDATE 回填历史数据（每批 1000 行，避免长事务）
    第3步 contract: 改成 NOT NULL + 加默认值（此时所有行都有值了）

  为什么必须这样：整个过程服务不停机，且任何一步失败都能回滚。
  这是"表结构改了但线上已有数据"的标准答案，面试聊工程必问。
EOF
say "alembic revision -m 'add messages.source (3 steps)'   # 手写，不用 autogenerate"
GEN=$(${ALEMBIC} revision -m "add messages source in 3 steps" 2>&1)
echo "${GEN}" | tail -2 | sed 's/^/    /'
F=$(echo "${GEN}" | grep -oE 'migrations/versions/[A-Za-z0-9_]+\.py' | head -1)
if [ -z "${F}" ]; then
  bad "没找到生成的迁移脚本"
else
  "${PYBIN}" "${HERE}/fill_migration.py" "${F}"
  say "alembic upgrade head"
  ${ALEMBIC} upgrade head 2>&1 | tail -2
  ${PYBIN} -c "
import sqlite3
c = sqlite3.connect('data/migration_demo.db')
cols = [r[1] for r in c.execute('PRAGMA table_info(messages)')]
print('  messages 列:', cols)
print('  ✅ source 列已加上（NOT NULL + 默认值 api）' if 'source' in cols else '  ❌ 没加上')"
fi

hr "场景 4 · downgrade 回滚再 upgrade 回来"
say "alembic downgrade -1"
${ALEMBIC} downgrade -1 2>&1 | tail -2
${PYBIN} -c "
import sqlite3
c=sqlite3.connect('data/migration_demo.db')
cols=[r[1] for r in c.execute('PRAGMA table_info(messages)')]
print('  回滚后 messages 列:', cols, '← source 已移除 ✅' if 'source' not in cols else '')"
say "alembic upgrade head"
${ALEMBIC} upgrade head 2>&1 | tail -2
say "alembic history"
${ALEMBIC} history 2>&1 | tail -5

hr "场景 5 · 还原 models.py（演练不留垃圾）"
${PYBIN} - <<'EOF'
from pathlib import Path
p = Path("app/db/models.py"); s = p.read_text(encoding="utf-8")
marker = "\n\n# ── Demo 04-5 场景2/3 临时新增的字段"
if marker in s:
    p.write_text(s[:s.index(marker)] + "\n", encoding="utf-8")
    print("  ✅ models.py 已还原")
EOF
rm -f migrations/versions/*.py
echo "  ✅ 迁移脚本已清理（真实项目里迁移脚本要提交进 git，绝不能删）"

hr "《为什么生产禁用 autogenerate 直接执行》—— 三个真实风险"
cat <<'EOF'
  ① 它把「重命名列」识别成「删列 + 加列」→ 数据直接丢失，且不会警告你
  ② 它生成的 DDL 不带 CONCURRENTLY / 不分批 → 大表上会长时间锁表，线上卡死
  ③ 它不知道你删掉的模型是「故意下线」还是「忘了 import」
     （env.py 里少 import 一个 models 文件，autogenerate 就会生成 DROP TABLE）
  → 规范：autogenerate 只用来【起草】，人工逐行 review 后再执行；
     生产变更走 DBA 审核 + 灰度 + 可回滚脚本，且必须在预发环境演练过。
EOF
