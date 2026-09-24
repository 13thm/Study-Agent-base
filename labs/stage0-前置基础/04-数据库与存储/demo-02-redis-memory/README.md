# Demo 04-2 · Redis 会话记忆

> **任务书**：[04-数据库与存储.md](../../../../my-docs/study01/stage0-前置基础/04-数据库与存储.md)
> **代码位置**：`../fastapi-chat-backend/app/services/memory.py`
> **依赖**：redis（无服务时自动降级 fakeredis）　**耗时**：2 小时

## 一、跑
```bash
bash run.sh
```
要跑真实 Redis：`cd .. && docker compose up -d redis`，然后
`APP_USE_FAKE_REDIS=0 bash run.sh`

## 二、这个 Demo 验证什么
5 个场景（对应任务书的 `verify_memory.py`）：

| # | 场景 | 期望 |
|---|---|---|
| ① | 第 1 轮说"我叫小明"，第 3 轮问"我叫什么" | 答对 ✅ 记忆生效 |
| ② | 滑动过期 | 读/写都会 `EXPIRE` 重置 TTL；手动改 TTL=2s 后等 3s，记忆消失 |
| ③ | LTRIM | 写 30 条，Redis 里只剩 `session_max_turns`(20) 条，且保留的是**最新的** |
| ④ | prompt 顺序 | system 在最前、历史按时间正序、当前问题在最后 |
| ⑤ | 冷热双层 | 说清 Redis 与 MySQL 各自负责什么 |

## 三、要读哪些代码（按顺序）
`app/services/memory.py` 全文（约 100 行，每段都有注释）：
- `append()`：`LPUSH` + `LTRIM` + `EXPIRE` 三连（这就是滑动窗口记忆）
- `history()`：`LRANGE` 后 **`reversed()`**（LPUSH 是倒序存的，拼 prompt 要正序）
- `build_prompt_messages()`：LLM 无状态 → "记忆"就是你每次重新拼的 messages 数组
- `app/core/redis_client.py`：有真 Redis 用真的、没有降级 fakeredis（**接口一致，业务代码零改动**）

## 四、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 加 `trim_to_tokens(n)`：按 token 数而不是条数裁剪（用 `estimate_tokens`） |
| 2 | ⭐⭐ | 实现冷层：把每轮对话异步写进 MySQL 的 messages 表，Redis miss 时回落加载并回填 |
| 3 | ⭐⭐ | 实现"读也刷新 TTL"的开关（有些业务要求**绝对过期**而不是滑动过期） |
| 4 | ⭐⭐⭐ | 用 Redis Stream 替代 List，实现"多端同步"（一个端发消息，其他端能收到） |

## 五、验收清单
- [ ] 5 个场景全部通过
- [ ] 能说出 `LPUSH + LTRIM` 为什么等于滑动窗口，以及为什么要 `reversed()`
- [ ] 能答"为什么 Redis + MySQL 双层"（不是二选一）
- [ ] 用真 Redis 跑过一遍（`docker compose up -d redis`），对比 fakeredis 的局限（不跨进程）
- [ ] 练习 1、2 完成

## 六、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
