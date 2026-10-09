# Demo 05-1 · Celery 最小可用

> **任务书**：[05-异步任务与消息队列.md](../../../../my-docs/study01/stage0-前置基础/05-异步任务与消息队列.md)
> **代码位置**：`../fastapi-chat-backend/app/tasks/{celery_app,demo}.py`
> **依赖**：celery[redis]（真实模式需 Redis）　**耗时**：1.5 小时

## 一、跑
```bash
bash run.sh
```
`bash run.sh` 跑无 Broker 模拟；真实 Celery 的命令在脚本末尾打印出来了

## 二、这个 Demo 验证什么
4 件事：
1. Producer → Broker → Worker → Backend 四段链路走通（`add.delay(3,4)` → 7）
2. **故意让任务抛异常**，看 traceback 是否完整可读（排查线上失败的唯一线索）
3. `include` 配错会怎样 → `Received unregistered task of type ...`
4. `acks_late` 的意义（任务不丢 vs 可能重复 → 所以要配幂等）

## 三、要读哪些代码（按顺序）
`app/tasks/celery_app.py` **逐行读注释**，重点是这几个配置为什么这么设：
- `task_acks_late` + `task_reject_on_worker_lost`：任务不丢的关键
- `worker_prefetch_multiplier=1`：长任务必须设 1，否则轻任务被饿死
- `task_soft_time_limit` vs `task_time_limit`：软超时给你清理机会，硬超时直接 SIGKILL
- `task_routes`：重活轻活分队列
- `task_serializer="json"` + `accept_content=["json"]`：**绝不用 pickle**（远程代码执行风险）

## 四、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 起真实 worker，用 `celery -A app.tasks.celery_app inspect active` 看正在跑的任务 |
| 2 | ⭐⭐ | `kill -9` worker，验证 `acks_late` 让任务被重新投递（对照关掉 acks_late 的情况） |
| 3 | ⭐⭐ | 把 `include` 里的模块名写错，复现 "unregistered task" 报错，再修回来 |
| 4 | ⭐⭐⭐ | 起 Flower 面板，观察队列长度、worker 忙碌度、任务耗时分布 |

## 五、验收清单
- [ ] 模拟模式跑通；有条件的话真实 worker 也跑通一次
- [ ] 能画出 `Producer → Broker → Worker → Backend` 的示意图
- [ ] 能说出 6 个关键配置各自防的是什么事故
- [ ] 能答"为什么不能用 pickle 序列化"
- [ ] 练习 2 完成（这个最能体现你理解 at-least-once）

## 六、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
