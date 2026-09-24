#!/usr/bin/env python3
"""把 alembic 生成的空迁移脚本，填充成"三步加非空列"的教学实现。

用法：python fill_migration.py migrations/versions/xxxx_add_source.py

为什么单独一个脚本，而不是写在 run.sh 的 heredoc 里？
    嵌套 heredoc + 三引号字符串会让 bash 的引号规则和外层的 Python 引号规则打架，
    我第一次就是这么写的，直接 SyntaxError。**能拆成文件就拆成文件**，
    这跟"逻辑与 IO 分离"是同一个道理：复杂度要隔离。
"""
from __future__ import annotations

import sys
from pathlib import Path

UPGRADE_OLD = """def upgrade() -> None:
    pass"""

UPGRADE_NEW = '''def upgrade() -> None:
    """三步加非空列：expand → backfill → contract（不停机变更的标准做法）。"""
    # ── 第 1 步 expand：先加【可空】列 ──
    # 加可空列是元数据操作，几乎瞬间完成，不会锁表。
    # batch_alter_table 是为了兼容 SQLite（它不支持 ALTER COLUMN，alembic 会重建表）。
    with op.batch_alter_table("messages") as b:
        b.add_column(sa.Column("source", sa.String(32), nullable=True))

    # ── 第 2 步 backfill：回填历史数据 ──
    # ⚠️ 生产上必须【分批】：按 id 区间每批 1000~5000 行，
    #    否则一个 UPDATE 扫全表 = 长事务 = 锁表 + 主从延迟暴涨。
    #    分批写法示例：
    #      for lo, hi in batches: op.execute(f"UPDATE messages SET source='unknown' "
    #                                        f"WHERE source IS NULL AND id BETWEEN {lo} AND {hi}")
    op.execute("UPDATE messages SET source = 'unknown' WHERE source IS NULL")

    # ── 第 3 步 contract：改成 NOT NULL + 默认值 ──
    # 只有在确认所有行都有值之后才能做，否则数据库会直接报错。
    with op.batch_alter_table("messages") as b:
        b.alter_column("source", nullable=False, server_default="api")'''

DOWNGRADE_OLD = """def downgrade() -> None:
    pass"""

DOWNGRADE_NEW = '''def downgrade() -> None:
    """回滚：直接删列。

    📌 注意 contract 模式的回滚陷阱：如果第 3 步已经上线并且新代码开始写 source 字段，
       回滚会把数据一起删掉。所以生产的做法是**回滚只回滚代码，不回滚表结构**，
       表结构的清理放到下一个版本（此时确认没有代码在用了）。
    """
    with op.batch_alter_table("messages") as b:
        b.drop_column("source")'''


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    p = Path(sys.argv[1])
    if not p.is_file():
        print(f"❌ 文件不存在: {p}")
        return 1
    s = p.read_text(encoding="utf-8")
    if UPGRADE_OLD not in s:
        print(f"⚠️  {p.name} 的 upgrade() 不是空的，跳过（可能已经填过了）")
        return 0
    s = s.replace(UPGRADE_OLD, UPGRADE_NEW).replace(DOWNGRADE_OLD, DOWNGRADE_NEW)
    p.write_text(s, encoding="utf-8")
    print(f"  ✅ 已写入三步迁移逻辑 → {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
