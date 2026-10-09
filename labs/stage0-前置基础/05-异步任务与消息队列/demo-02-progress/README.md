# Demo 05-2 · 进度上报 + SSE 推送（★ 本模块重点）

> **任务书**：[05-异步任务与消息队列.md](../../../../my-docs/study01/stage0-前置基础/05-异步任务与消息队列.md)
> **代码位置**：`../fastapi-chat-backend/app/{tasks/ingest.py,tasks/local_runner.py,api/tasks.py}`
> **依赖**：fastapi + redis/fakeredis　**耗时**：2.5 小时

## 一、跑
```bash
bash run.sh
```
脚本会自己起服务、提交任务、消费 SSE 流、再停服务，全自动

## 二、这个 Demo 验证什么
两步：
1. **任务侧**：`update_state(state="PROGRESS", meta={current,total,pct})` 逐步上报
2. **接口侧**：
   - `POST /api/files/{id}/parse` 受理耗时 **<50ms**（实测 0.74ms）→ 证明没在请求里干活
   - `GET /api/tasks/{id}/stream` SSE 推送，**只在状态变化时推帧**（实测 11 个不同帧）
   - 进度**单调递增**（0 → 5.8% → 11.6% → ... → 100%）

## 三、要读哪些代码（按顺序）
1. `app/tasks/ingest.py::parse_doc` —— 进度上报的正确姿势：**每 10% 报一次**，不要每块都报
2. `app/tasks/local_runner.py::STAGE_SPAN` —— ★ 多阶段任务的全局进度换算（我踩的坑，注释里有完整记录）
3. `app/api/tasks.py::task_stream` —— SSE 端只在 `sig != last` 时推帧；`request.is_disconnected()` 感知断开
4. `tests/test_tasks_api.py` —— 4 个断言：受理耗时 / 状态序列含 PROGRESS / 进度到 100 / **单调递增**

## 四、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 前端做一个进度条页面（`app/static/progress.html`），用 EventSource 消费这个 SSE |
| 2 | ⭐⭐ | 加"取消任务"：`POST /api/tasks/{id}/cancel`，worker 侧用 `revoke(terminate=True)` |
| 3 | ⭐⭐ | 任务失败时 SSE 推 `{"state":"FAILURE","error":"..."}` 而不是让前端一直等 |
| 4 | ⭐⭐⭐ | 进度写 Redis 改成写 PG（重启后可恢复），对比两种方案的读写延迟 |

## 五、验收清单
- [ ] 受理耗时 <50ms 的实测数字记录在案
- [ ] SSE 帧序列完整，进度单调递增到 100%
- [ ] 客户端提前断开时服务端不报错不泄漏（`finally` 清理）
- [ ] 能讲清"多阶段任务的进度为什么会往回跳"以及修法
- [ ] 练习 1、3 完成

## 六、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
