# Demo 03-4 · 幂等执行接口

> **任务书**：[03-后端基础与Linux和Git.md → Demo 03-4](../../../../my-docs/study01/stage0-前置基础/03-后端基础与Linux和Git.md)
> **代码位置**：`../../fastapi-chat-backend/app/core/idempotency.py` + `app/api/agent.py`
> **依赖**：`fastapi` `httpx`（Redis 可选，无则自动用 fakeredis）　**耗时**：2.5 小时

## 一、跑
```bash
bash run.sh
```

## 二、我的实测输出
```
① 并发 10 个相同 Idempotency-Key（wait=false）
   状态码分布: 200×1  409×9
   服务端真实执行次数: 1  ✅
   409 响应体: 相同 Idempotency-Key 的请求正在处理中

② 并发 6 个相同 key（wait=true，等待首次完成）
   200×6  其中重放 5 次
   返回的 txn_id 种类: 1  ✅ 全部相同
   服务端真实执行次数: 1 ✅

③ 串行重复两次
   第1次: replay=False txn=txn_397ad6ad6b
   第2次: replay=True  txn=txn_397ad6ad6b
   txn_id 相同? True ✅（幂等不只是拒绝重复，而是返回首次的结果）

④ 不带 Idempotency-Key → 422 VALIDATION_ERROR
```

## 三、三态机（核心设计）
```
       ┌── SET NX EX 成功 ──→ PROCESSING（我在执行，别人等着或 409）
请求到达┤
       └── key 已存在 ──→ 看状态：
              PROCESSING → 等待（wait=true）或 409（wait=false）
              DONE       → 直接返回缓存结果（idempotent_replay=true）
              FAILED     → 删 key，允许重试
执行完成 → complete(key, result)   写入 DONE + 结果，TTL 24h
执行失败 → fail(key)               删掉 key，允许重试
```

## 四、四个必答问题
| 问题 | 答案 |
|---|---|
| **幂等键为什么必须由客户端生成？** | 服务端生成的话，客户端重试时拿到的是**新 key**，两次请求被当成不同操作 → 保护完全失效。客户端生成表达的是"这是同一次业务意图"。Stripe / 支付宝都是这个设计。 |
| **为什么 `SET NX EX` 要一条命令？** | 分成 `SETNX` + `EXPIRE` 两步的话，中间进程崩了 → key 永不过期 → 这个业务操作**永久卡死**。一条命令保证原子性。 |
| **最难的情况是什么？** | **超时**：请求发出去了，下游可能已经执行成功，但你没收到响应。这时不能简单标 FAILED（会导致重复执行）。阶段 3 模块 03 Demo 3-3 的解法是：保持 PROCESSING + 回查下游是否已产生效果（如查 SMTP 日志有没有 message_id）。 |
| **Agent 场景为什么特别需要？** | LLM 可能重复调用同一个工具（死循环/重试），工具超时后 Agent 以为失败会再调一次 → 重复发邮件/重复下单。这是生产事故里最常见的一类，且**测试环境很难复现**（因为不超时）。 |

## 五、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 加第二层防护：SQLite/PG 唯一约束 `(request_id, action)`，然后把 Redis 停掉验证依然只执行一次 |
| 2 | ⭐⭐ | 实现"PROCESSING 超时自动释放"：起一个后台任务扫描超过 5 分钟仍 PROCESSING 的 key |
| 3 | ⭐⭐ | 把幂等键透传给下游（模拟一个支持 `Idempotency-Key` 的第三方 API），验证端到端幂等 |
| 4 | ⭐⭐⭐ | 实现"回查下游"逻辑：超时后不直接标 FAILED，而是查下游的交易记录决定是否已成功（阶段 3 的做法） |

## 六、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
