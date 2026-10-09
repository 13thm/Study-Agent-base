# Demo 05-4 · 工作流编排（chain/group/chord）+ 定时任务

> **任务书**：[05-异步任务与消息队列.md](../../../../my-docs/study01/stage0-前置基础/05-异步任务与消息队列.md)
> **代码位置**：`../fastapi-chat-backend/app/tasks/ingest.py（build_pipeline）+ celery_app.py（beat_schedule）`
> **依赖**：celery　**耗时**：2 小时

## 一、跑
```bash
bash run.sh
```
`bash run.sh` 跑三种编排 + 加速比实测 + 三道思考题

## 二、这个 Demo 验证什么
1. **chain**：`parse_doc → embed_chunks`，上一步结果自动传给下一步
2. **group**：5 个文件并行，测加速比（`-c 4` 下预期约 4×）
3. **chord**：callback 真的等全部完成才触发（故意让一个子任务变慢验证）
4. **Beat**：三个定时任务的配置（crontab / 固定间隔）

## 三、要读哪些代码（按顺序）
1. `ingest.py::build_pipeline` —— `chord(group(chain(...) for ...), callback.s())` 的写法
2. `celery_app.py::beat_schedule` —— crontab 与秒级间隔两种写法
3. run.sh 末尾的**三道思考题答案**（chord 部分失败 / 为什么分队列 / 与多 Agent 编排的关系）

## 四、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 把并发度从 4 改成 1/2/8，画加速比曲线，找出拐点 |
| 2 | ⭐⭐ | 实现"chord 部分成功"语义：子任务永远不抛异常，返回 `{ok: False, error: ...}`，callback 里统计 |
| 3 | ⭐⭐ | 用 `group` 实现"1000 个文档分批灌库，每批 50 个，批间休息 1s"（保护 Embedding API） |
| 4 | ⭐⭐⭐ | 把 Beat 换成 redbeat（基于 Redis 的分布式定时任务），验证起两个 beat 实例不会重复触发 |

## 五、验收清单
- [ ] 三种编排都跑通，加速比数字记录在案
- [ ] 能答三道思考题（尤其"chord 里一个任务失败 callback 还跑不跑"）
- [ ] 能说出 chain/group/chord 分别对应 LangGraph 的什么概念
- [ ] 知道 Beat 只能起一个实例（多起会重复触发），高可用要用 redbeat
- [ ] 练习 1、2 完成

## 六、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
