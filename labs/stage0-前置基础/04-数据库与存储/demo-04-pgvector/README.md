# Demo 04-4 · PGVector 与向量检索基础

> **任务书**：[04-数据库与存储.md](../../../../my-docs/study01/stage0-前置基础/04-数据库与存储.md)
> **代码位置**：`../fastapi-chat-backend/scripts/demo04_4_pgvector.py`
> **依赖**：numpy；真实模式另需 PG + pgvector 扩展　**耗时**：1.5 小时

## 一、跑
```bash
bash run.sh
```
**降级模式（默认）**：用 numpy 手算余弦相似度，验证同样的结论，并打印真实环境该执行的 SQL。
**真实模式**：
```bash
docker run -d --name pg -p 5432:5432 -e POSTGRES_PASSWORD=pw pgvector/pgvector:pg16
APP_DATABASE_URL=postgresql://postgres:pw@localhost:5432/postgres python scripts/demo04_4_pgvector.py
```

## 二、这个 Demo 验证什么
5 组查询/实验：
| # | 内容 | 你会得到 |
|---|---|---|
| 1 | 纯向量相似度（`<=>` 余弦距离） | Top3 + 分数 |
| 2 | 向量 + JSONB 元数据 + 租户过滤 | **过滤下推**的 SQL 写法，以及"后过滤是安全事故"的解释 |
| 3 | 三种距离运算符 | `<=>` 余弦 / `<->` L2 / `<#>` 内积；**实测 L2² = 2-2cos** ✅ |
| 4 | HNSW vs IVFFlat | 参数含义、内存/速度取舍、适用规模 |
| 5 | 暴力检索耗时 | 1000 条 × 384 维的实测 ms，推出"100 万条必须上 ANN 索引" |

## 三、要读哪些代码（按顺序）
`scripts/demo04_4_pgvector.py`：
- `run_pg()` 是真实模式的三条 SQL（`CREATE EXTENSION vector` / `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)` / `ORDER BY embedding <=> $1`）
- `run_numpy()` 是降级模式，**每条 numpy 计算后面都跟着对应的 PG SQL**，两边对照着看
- `fake_embed()` 里注入了"主题信号"，让检索结果可预期（真实项目用 bge-small-zh，见阶段 2 模块 01）

## 四、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 把 DIM 从 384 改成 1024，记录建索引耗时与磁盘占用的变化 |
| 2 | ⭐⭐ | 起真实 PG，建 HNSW 与 IVFFlat 两种索引，对比 1000 条数据的查询 P95 |
| 3 | ⭐⭐⭐ | 灌 10 万条随机向量，以暴力检索为 ground truth 算 HNSW 的 Recall@10，调 `ef_search` 画"召回-延迟"曲线（这就是阶段 2 模块 01 Demo 2-3 的核心实验） |

## 五、验收清单
- [ ] 5 组查询全部跑通（降级模式即可，有 PG 更好）
- [ ] 能答"余弦和欧氏距离什么时候排序结果一致"（归一化后）
- [ ] 能答"为什么过滤条件必须下推到数据库"（效果 + 安全两个理由）
- [ ] 能说出 HNSW 的 `m` / `ef_construction` / `ef_search` 各调什么
- [ ] 练习 2 完成

## 六、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
