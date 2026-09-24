# 模块 04 · 数据库与存储 —— 教学 Demo 目录

> **任务书**：[my-docs/study01/stage0-前置基础/04-数据库与存储.md](../../../my-docs/study01/stage0-前置基础/04-数据库与存储.md)
> **依赖**：`sqlalchemy` `aiosqlite` `redis`/`fakeredis` `minio`(可选) `alembic` `numpy` `psycopg`+`pgvector`(可选)
> **预计投入**：10~12 小时（5 个 Demo）
> **★ 好消息**：这 5 个 Demo **不需要 Docker 也能全部跑通** —— 代码里做了自动降级
> （SQLite 替 MySQL/PG、fakeredis 替 Redis、本地文件系统替 MinIO、numpy 替 PGVector），
> 想跑真实服务时 `docker compose up -d` 即可，**业务代码一行都不用改**。

---

## 一、目录结构

```
04-数据库与存储/
├── README.md                     ← 你在这里
├── docker-compose.yml            ← postgres(pgvector) / mysql / redis / minio（可选）
├── demo-01-models/               ① SQLAlchemy 三表建模      → app/db/{base,models,repo}.py
├── demo-02-redis-memory/         ② Redis 会话记忆           → app/services/memory.py
├── demo-03-minio/                ③ 对象存储上传全链路        → app/services/storage.py
├── demo-04-pgvector/             ④ 向量检索基础             → scripts/demo04_4_pgvector.py
└── demo-05-migration/            ⑤ Alembic 迁移四场景        → migrations/ + fill_migration.py
```
**代码本体都在 `../fastapi-chat-backend/`**（模块 03 建的仓库，本模块往里加数据层）。

---

## 二、一键跑

```bash
cd labs/stage0-前置基础
for d in 04-数据库与存储/demo-*/; do
  echo "═══ $d"; (cd "$d" && bash run.sh > /tmp/m4.log 2>&1 && echo "  ✅ OK" || { echo "  ❌"; tail -12 /tmp/m4.log; })
done
```
或 `make m4`。要跑真实服务：`cd 04-数据库与存储 && docker compose up -d`。

---

## 三、学习路径

| 时段 | Demo | 重点 |
|---|---|---|
| Day 1 上午 | 04-1 SQLAlchemy 三表 | 2.0 声明式写法、复合索引 + EXPLAIN 验证、级联删除、N+1 与 selectinload |
| Day 1 下午 | 04-2 Redis 会话记忆 | LPUSH+LTRIM 滑动窗口、滑动 TTL、冷热双层设计 |
| Day 2 上午 | 04-3 对象存储 | object key 规范、sha256 秒传、预签名 URL、路径穿越防护、**为什么文件不进数据库** |
| Day 2 下午 | 04-4 PGVector | 三种距离运算符、归一化后等价、HNSW vs IVFFlat、**过滤必须下推** |
| Day 3 | 04-5 Alembic | autogenerate 的局限、**加非空列的三步法**、downgrade 回滚、为什么生产禁用 autogenerate 直发 |

---

## 四、这个模块我踩到的 3 个坑（都已修，代码注释里有完整记录）

| 坑 | 现象 | 根因 | 教训 |
|---|---|---|---|
| **SQLite 默认不强制外键** | 删了 user，它的 3 个 session 还在库里（孤儿数据） | SQLite 的 `PRAGMA foreign_keys` 默认 OFF，`ondelete="CASCADE"` 形同虚设；MySQL/PG 默认强制 | 每个 SQLite 连接建立时执行 `PRAGMA foreign_keys=ON`；**这类"环境差异型"缺陷在本地测试才暴露，生产反而看起来正常** |
| **ORM 级联依赖内存里的关系集合** | `len(u.sessions)` 返回 0，`s.delete(u)` 不删子对象 | `expire_on_commit=False` + User 对象早就加载过 → 关系集合是**陈旧快照** | 要"库里有多少"就用查询；要用关系集合先 `s.refresh(obj, ["rel"])` |
| **异步引擎的驱动名** | `The asyncio extension requires an async driver` | 配置里是 `sqlite+pysqlite://`，我的替换只匹配 `sqlite://` | 按 `dialect+driver://` 格式拆解替换，不要靠字符串前缀猜 |

> 这三个坑全部是**被单元测试抓出来的**（`tests/test_db.py`）。这就是模块 06 的价值：
> 没有测试，它们会一直潜伏到生产环境才爆发。

---

## 五、必须口头答出的 6 个问题

| 问题 | 答案要点 | 在哪验证过 |
|---|---|---|
| 对话历史为什么放 Redis 不放 MySQL？ | 读写频繁（每轮 ≥2 次）、天然 TTL、内存级延迟（<1ms vs 5~20ms） | demo-02 场景⑤ |
| 那为什么还要 MySQL？ | Redis 会丢（重启/淘汰/故障），长期记录、统计、审计必须落盘 → **热 Redis + 冷 DB 双层** | demo-02 场景⑤ |
| 30 分钟无操作自动过期怎么实现？ | 每次读写后都 `EXPIRE key 1800`（滑动过期），不是只在创建时设一次 | demo-02 场景② |
| 文件为什么不进数据库？ | 大 BLOB 拖垮备份/主从/vacuum；DB 是为"小而多"的查询设计的；对象存储天然支持 CDN、预签名 URL、生命周期 | demo-03 场景⑥ |
| 为什么选 PG 而不是 MySQL？ | PGVector（业务数据+向量同库）、JSONB（半结构化元数据 + 可索引查询）、更强的扩展生态 | demo-04 查询2 |
| 表结构改了但线上有数据怎么办？ | Alembic 迁移；**加非空列必须三步**（加可空列 → 分批回填 → 改 NOT NULL），直接加会锁表 | demo-05 场景3 |

---

## 六、常见报错速查

| 报错 | 原因 | 解法 |
|---|---|---|
| `The asyncio extension requires an async driver` | URL 用的是同步驱动 | `sqlite+aiosqlite://` / `postgresql+asyncpg://` |
| `MissingGreenlet` | 异步 Session 里惰性加载 relationship | 用 `selectinload()` 显式预加载 |
| 删父对象子对象还在 | SQLite 没开外键 / 关系集合是陈旧快照 | `PRAGMA foreign_keys=ON` + `s.refresh()` |
| `Can't load plugin: sqlalchemy.dialects:postgresql.psycopg2` | 没装驱动 | `uv pip install "psycopg[binary]"` 或用 `postgresql+psycopg://` |
| MinIO 连接失败自动降级 | 没起 MinIO 服务 | 正常现象（会打印提示）；要跑真实的 `docker compose up -d minio` |
| alembic `Target database is not up to date` | 库里有表但没有 alembic_version | 先 `alembic stamp head` 或删库重来 |

---

## 七、完成后做什么

1. 回任务书打勾「四、模块完成判定」，更新 [00-进度看板](../../../my-docs/study01/00-进度看板.md)
2. **白板默写**：三张表的模型定义 + 一条带 `selectinload` 的查询
3. 把 3 个踩坑写进你自己的 `PITFALLS.md`（阶段 6 的简历素材）
4. 进入 [模块 05 · 异步任务与消息队列](../05-异步任务与消息队列/)
