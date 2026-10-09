# Demo 05-3 · 失败重试与死信兜底

> **任务书**：[05-异步任务与消息队列.md](../../../../my-docs/study01/stage0-前置基础/05-异步任务与消息队列.md)
> **代码位置**：`../fastapi-chat-backend/app/tasks/demo.py（flaky_call / push_dead_letter）`
> **依赖**：celery　**耗时**：2 小时

## 一、跑
```bash
bash run.sh
```
`bash run.sh` 跑四种故障模式的对照

## 二、这个 Demo 验证什么
| mode | 行为 | 期望结果 | 我的实测 |
|---|---|---|---|
| `ok` | 直接成功 | SUCCESS，重试 0 次 | 1 次尝试 ✅ |
| `transient` | 前 2 次抛 TransientError | **重试后 SUCCESS** | 3 次尝试，退避 [0.05, 0.1] ✅ |
| `permanent` | 抛 PermanentError | 立即 FAILURE，**不重试** | 1 次尝试 ✅ 未被误重试 |
| `timeout` | 超 soft_time_limit | FAILURE + **进死信队列** | 死信 1 条，处理任务消费掉 ✅ |

## 三、要读哪些代码（按顺序）
1. `flaky_call` 的装饰器参数：`autoretry_for=(TransientError,)` / `retry_backoff=True` /
   `retry_jitter=True` / `max_retries=5` —— **每一个都对应一个真实事故**
2. `push_dead_letter` 的注释：为什么必须有死信（否则失败任务**静默消失**，用户以为在处理）
3. `SoftTimeLimitExceeded` 的处理：软超时给你清理机会（关文件、回滚、上报），硬超时直接 SIGKILL

## 四、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 把死信从内存 list 换成 Redis LIST（`LPUSH dead_letter`），并写一个查询接口 |
| 2 | ⭐⭐ | 加 `retry_backoff_max=30`，验证退避不会无限增长 |
| 3 | ⭐⭐ | 实现"人工重放死信"接口：把死信里的参数重新投进队列 |
| 4 | ⭐⭐⭐ | 用 RabbitMQ 的原生 DLX（死信交换机）替代应用层死信，对比两种方案 |

## 五、验收清单
- [ ] 四种 mode 的结果与期望完全一致
- [ ] 能答"为什么 `permanent` 不能重试"（重试白名单的意义）
- [ ] 能答"为什么需要 jitter"（防止一批任务同时重试打爆刚恢复的下游 = 重试风暴）
- [ ] 能答"死信队列里该存什么"（原始参数 + 失败原因 + 时间，才能重放）
- [ ] 练习 1、3 完成

## 六、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
