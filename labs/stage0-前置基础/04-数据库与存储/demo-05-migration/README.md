# Demo 04-5 · Alembic 迁移四场景

> **任务书**：[04-数据库与存储.md](../../../../my-docs/study01/stage0-前置基础/04-数据库与存储.md)
> **代码位置**：`../fastapi-chat-backend/{alembic.ini,migrations/} + fill_migration.py`
> **依赖**：alembic　**耗时**：2 小时

## 一、跑
```bash
bash run.sh
```
演练在独立的 `data/migration_demo.db` 上做，跑完自动清理生成的迁移脚本（真实项目里迁移脚本要提交进 git）

## 二、这个 Demo 验证什么
5 个场景：

| # | 场景 | 关键点 |
|---|---|---|
| 1 | 从零建表 | `revision --autogenerate` → **人工逐行检查** → `upgrade head` |
| 2 | 加表/加可空列 | autogenerate 的正常工作流 |
| 3 | ★ **给已有表加非空列** | 必须三步：加可空列 → 分批回填 → 改 NOT NULL（直接加会锁表/失败） |
| 4 | `downgrade -1` 回滚再 `upgrade head` | 验证迁移可逆 |
| 5 | 还原 models.py | 演练不留垃圾 |

## 三、要读哪些代码（按顺序）
1. `migrations/env.py` —— 两个必须做对的点：`target_metadata = Base.metadata`（否则 autogenerate 会生成 DROP TABLE）、
   URL 从 settings 读（不硬编码在 alembic.ini）；`render_as_batch=True`（SQLite 需要）
2. `fill_migration.py` —— 场景 3 的三步迁移实现（expand → backfill → contract），
   **注释里写了生产上 backfill 必须分批的原因**（长事务锁表 + 主从延迟）
3. `run.sh` 末尾 —— 《为什么生产禁用 autogenerate 直接执行》的三个真实风险

## 四、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 用 `alembic stamp head` 把一个"已有表但没有 alembic_version"的库接管进来 |
| 2 | ⭐⭐ | 写一个**重命名列**的迁移（autogenerate 会生成 drop+add，你要手改成 `alter_column`） |
| 3 | ⭐⭐ | 用 `alembic upgrade head --sql` 生成离线 SQL 给 DBA 审核 |
| 4 | ⭐⭐⭐ | 实现 backfill 的分批版本（按 id 区间每批 1000 行），并在 10 万行的表上测耗时与锁等待 |

## 五、验收清单
- [ ] 5 个场景全部跑通
- [ ] 能说出 autogenerate 会漏掉的 4 类东西（索引参数 / 注释与引擎 / 数据迁移 / **重命名被当成 drop+add**）
- [ ] 能默写"加非空列的三步法"并说清为什么
- [ ] 能答"为什么生产禁用 autogenerate 直接执行"（三个风险）
- [ ] 练习 2、3 完成

## 六、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
