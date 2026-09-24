# Demo 04-1 · SQLAlchemy 三表建模

> **任务书**：[04-数据库与存储.md](../../../../my-docs/study01/stage0-前置基础/04-数据库与存储.md)
> **代码位置**：`../fastapi-chat-backend/app/db/{base,models,repo}.py`
> **依赖**：sqlalchemy（默认 SQLite，可切 MySQL/PG）　**耗时**：2.5 小时

## 一、跑
```bash
bash run.sh
```
无需 Docker：默认用 `data/app.db`（SQLite）。要换 MySQL/PG：
```bash
cd .. && docker compose up -d mysql postgres
cd ../fastapi-chat-backend
APP_DATABASE_URL='mysql+pymysql://root:pw@localhost:3306/agent' python scripts/demo04_1_db.py
APP_DATABASE_URL='postgresql+psycopg://postgres:pw@localhost:5432/agent' python scripts/demo04_1_db.py
```

## 二、这个 Demo 验证什么
8 个场景：

| # | 场景 | 期望 |
|---|---|---|
| 1 | 建表 | 4 张表（users / chat_sessions / messages / user_files） |
| 2 | 复合索引 | `idx_msg_session_created (session_id, created_at)` 存在 |
| 3 | 造数据 | 3 用户 / 5 会话 / 128+ 消息 |
| 4 | 查最近 5 条 | **按时间正序**返回（拼 prompt 要用正序） |
| 5 | EXPLAIN | `SEARCH messages USING INDEX idx_msg_session_created` ✅ 走了复合索引 |
| 6 | JOIN + SUM 聚合 | 按用户统计 token 消耗 |
| 7 | 级联删除 | 删 user → 会话与消息连带删除 |
| 8 | N+1 | `selectinload` 一次查询拿到全部会话与消息（2 条 SQL） |

## 三、要读哪些代码（按顺序）
1. `app/db/models.py` —— 2.0 声明式写法（`Mapped[T]` + `mapped_column`）、
   `relationship(cascade="all, delete-orphan", back_populates=...)`、`__table_args__` 复合索引、
   `lazy="selectin"`（**为什么不加会在异步下抛 MissingGreenlet**）
2. `app/db/base.py` —— 连接池四个参数（`pool_pre_ping` 防"MySQL server has gone away"）、
   同步/异步双引擎、**SQLite 的 `PRAGMA foreign_keys=ON`**、yield 型依赖
3. `app/db/repo.py` —— Repository 层的意义、`s.get()` 的身份映射缓存、
   `delete_user` 里那段**长注释（ORM 级联依赖内存关系集合的坑）**

## 四、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 加 `Message.is_pinned` 字段，写一个 `list_pinned(session_id)` 查询 |
| 2 | ⭐⭐ | 把 `get_recent_messages` 改成**异步版**（`AsyncSession` + `await s.execute`），跑通并对比写法差异 |
| 3 | ⭐⭐ | 故意去掉 `lazy="selectin"`，在异步 Session 下复现 `MissingGreenlet`，再修回来 |
| 4 | ⭐⭐⭐ | 用 `APP_DATABASE_URL` 切到 MySQL 和 PG 各跑一遍，记录 EXPLAIN 输出的差异（MySQL 看 `key` 列，PG 用 `EXPLAIN ANALYZE`） |
| 5 | ⭐⭐⭐ | 造 10 万条消息，对比"有复合索引 vs 只有 session_id 单列索引"的查询耗时 |

## 五、验收清单
- [ ] 8 个场景全部通过，EXPLAIN 证明走了复合索引
- [ ] **白板默写**：三张表的模型定义 + 一条带 `selectinload` 的查询
- [ ] `tests/test_db.py` 全绿（9 个用例，含级联、去重、软删）
- [ ] 能说出 ORM 级联为什么会失效（陈旧关系集合）以及 SQLite 外键的坑
- [ ] 练习 1~3 完成

## 六、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
