# 模块 05 · 异步任务与消息队列 —— 教学 Demo 目录

> **任务书**：[my-docs/study01/stage0-前置基础/05-异步任务与消息队列.md](../../../my-docs/study01/stage0-前置基础/05-异步任务与消息队列.md)
> **依赖**：`celery[redis]`（真实模式另需 Docker 起 Redis）
> **预计投入**：8~10 小时（4 个 Demo）
> **★ 无 Broker 也能学**：`scripts/demo05_simulate.py` 用一个 100 行的迷你运行时复刻了 Celery 的
> 核心语义（bind/retries/update_state/autoretry_for/chain/group/chord），
> **跑的是真实的生产任务代码**（`app/tasks/*.py` 一行没改），只换了执行器。

---

## 一、为什么这个模块必须做

任务书原话：*你在阶段 2 会遇到这个场景：用户上传 200 页 PDF，你同步在请求里解析+切块+向量化
→ 网关 60 秒超时，用户看到 502，你还不知道。*

**一句话总结：HTTP 请求是用来「受理」的，不是用来「干完活」的。**

Demo 05-2 会实测这个数字：`POST /api/files/9/parse` 的受理耗时 **0.74ms**（要求 <50ms）。

---

## 二、目录结构

```
05-异步任务与消息队列/
├── README.md                    ← 你在这里
├── docker-compose.yml           ← redis + worker + beat + flower(可选)
├── demo-01-hello-celery/        ① 最小可用：提交→执行→取结果
├── demo-02-progress/            ② ★ 进度上报 + SSE 推送（本模块重点）
├── demo-03-retry/               ③ 失败重试与死信兜底（四种故障模式）
└── demo-04-workflow/            ④ chain/group/chord 编排 + 定时任务
```
代码位置：
```
../fastapi-chat-backend/
├── app/tasks/celery_app.py      ← Celery 实例 + 全部生产级配置（逐行注释）
├── app/tasks/demo.py            ← add / heavy_task / flaky_call / 死信 / 定时任务
├── app/tasks/ingest.py          ← parse_doc / embed_chunks / rebuild_index + build_pipeline
├── app/tasks/local_runner.py    ← 无 Broker 的本地执行器（教学/开发用）
├── app/api/tasks.py             ← POST /parse、GET /tasks/{id}、GET /tasks/{id}/stream
└── scripts/demo05_simulate.py   ← 四个 Demo 的一键演示
```

---

## 三、两种运行模式

### 模式 A · 无 Broker 模拟（默认，随时随地能跑）
```bash
cd ../fastapi-chat-backend && python scripts/demo05_simulate.py        # 四个 Demo 全跑
python scripts/demo05_simulate.py --only 3                             # 只跑重试与死信
```

### 模式 B · 真实 Celery（要 Docker）
```bash
cd 05-异步任务与消息队列 && docker compose up -d
cd ../fastapi-chat-backend
celery -A app.tasks.celery_app worker -l info -Q default,heavy,dead_letter -c 2
celery -A app.tasks.celery_app beat -l info                # 另开终端（定时任务）
python -c "from app.tasks.demo import add; print(add.delay(3,4).get())"
# 监控面板（可选）：docker compose --profile monitoring up -d flower → http://localhost:5555
```

---

## 四、四个 Demo 的实测结果

### Demo 05-2 进度上报（★ 重点）
```
POST /api/files/9/parse → parse-1789513397-0002   受理耗时 0.74ms   ✅ <50ms
SSE 进度流：
    [ 0.01s] WATCHING
    [ 0.01s] PENDING    queued
    [ 0.32s] PROGRESS   parsing      5.8%
    [ 0.62s] PROGRESS   parsing     11.6%
    ...
    [ 2.44s] PROGRESS   parsing     52.1%
    [ 2.74s] SUCCESS    done         100%
✅ 收到 11 个不同状态帧（只在变化时推，不刷重复数据）
```
> 📌 这里我踩了一个真实的设计缺陷：parse 阶段报 0~100%、embed 阶段又报 0~100%，
> 前端进度条走到 100% 之后**又跳回 20%**，用户以为任务重跑了。
> 修法：每个阶段只负责自己那段区间（parsing 0~60%、embedding 60~95%），
> 由外层换算全局百分比，并加"单调保护"（`max(overall, last_pct)`）。
> 这个坑是被 `tests/test_tasks_api.py` 的"进度必须单调递增"断言抓出来的。

### Demo 05-3 失败重试与死信
```
mode         结果        尝试次数   退避序列
ok           SUCCESS      1        []
transient    SUCCESS      3        [0.05, 0.1]     ← autoretry_for 生效
permanent    FAILURE      1        []              ← ★ 一次都没重试（不在白名单）
timeout      FAILURE      1        []              ← 进了死信队列
[dead-letter] {'task': 'timeout_demo', 'reason': 'SoftTimeLimitExceeded'}
死信处理任务：SUCCESS，处理了 1 条
```

### Demo 05-4 编排
```
chain : parse_doc → embed_chunks，上一步结果自动传给下一步 ✅
group : 5 个文件 串行 vs 并行(-c 4)，测加速比
chord : rebuild_index 在所有子任务之后触发（含那个故意变慢的）✅
```

---

## 五、必须口头答出的 5 个问题

| 问题 | 答案要点 |
|---|---|
| 用户上传 500 页文档，你怎么设计？ | 接口只做"受理"（存 MinIO + 写元数据 + 投任务，<50ms 返回 task_id）→ Worker 异步解析/分块/向量化（`update_state` 上报进度）→ 前端轮询或 SSE 看进度 → 失败进死信 + 可重放。**绝不在 HTTP 请求里干重活** |
| `acks_late` 解决什么？ | 默认是"取走消息就 ack"，worker 崩了任务就永久丢失；`acks_late=True` 改成"执行完才 ack"，崩溃后消息重回队列 → 不丢任务。代价是 at-least-once 语义（可能重复执行）→ **所以必须配幂等设计** |
| `update_state` 怎么用？ | `self.update_state(state="PROGRESS", meta={...})`，meta 会被写进 backend，接口层轮询它。要点：① 别每处理一条就上报（每 10% 一次）② SSE 端只在**状态变化**时推帧 |
| 为什么重活轻活要分队列？ | 一个 worker 预取了一批轻任务，却被一个 30 分钟的重任务占住 → 轻任务全部饿死。解法：分队列 + 各队列独立 worker 数 + `worker_prefetch_multiplier=1` |
| 这跟多 Agent 编排有什么关系？ | chain=依赖边、group=并行分派、chord=汇聚节点。LangGraph 的 StateGraph 是同一套心智模型（Send API ≈ group，条件边 ≈ 分支，汇聚节点 ≈ chord callback），只是多了状态持久化和中断能力 |

---

## 六、我在这个模块踩的坑（已修，注释里有记录）

| 坑 | 现象 | 根因 |
|---|---|---|
| **Celery 任务对象包了两层** | 传进去的 `FakeSelf` 变成了业务参数，`self.request.retries` 永远是 0 → 无限重试到 max_retries | `task.run` 是 Celery 包装过的（签名里看不到 self，调用时注入 Task 实例）；真正未绑定的原函数在 `task._orig_run.__func__` |
| **进度条往回跳** | parsing 到 100% 后 embedding 又从 20% 开始 | 两个阶段各自报 0~100%，没有全局编排 |
| **mock 故障是确定性的** | 重试永远失败（第一次 429，重试还是 429） | 用 `hash(prompt)` 做随机种子 → 同一请求每次 dice 相同。改用进程级 seeded RNG |

---

## 七、完成后做什么

1. 回任务书打勾，更新进度看板
2. 画出 `Producer → Broker → Worker → Backend` 的示意图（手绘拍照即可）
3. 把"受理耗时 0.74ms"和"进度单调递增的坑"记进面试素材
4. 进入 [模块 06 · 代码规范与单元测试](../06-代码规范与单元测试/)
