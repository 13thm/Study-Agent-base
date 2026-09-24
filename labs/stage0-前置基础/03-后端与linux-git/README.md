# 模块 03 · 后端基础、Linux、Git —— 教学 Demo 目录

> **任务书**：[my-docs/study01/stage0-前置基础/03-后端基础与Linux和Git.md](../../../my-docs/study01/stage0-前置基础/03-后端基础与Linux和Git.md)
> **依赖**：`fastapi` `uvicorn` `httpx` `websockets`（demo-05 另需 Docker）
> **预计投入**：12~14 小时（6 个 Demo）
> **完成标志**：`fastapi-chat-backend` 能在本地跑起来，SSE / WS / 幂等三个能力都能演示，Git 12 练习手敲过一遍

---

## 一、这个模块的产出是一个**真仓库**

模块 01/02 的 demo 是独立脚本，本模块开始不一样：
**`../fastapi-chat-backend/` 就是阶段 0 的最终交付物**，模块 03 搭骨架，模块 04/05/06 继续往里加。

```
fastapi-chat-backend/
├── app/
│   ├── main.py               create_app + 挂路由 + lifespan（模块03）
│   ├── config.py             pydantic-settings 配置（模块03）
│   ├── core/
│   │   ├── errors.py         AppError 层次 + 全局 handler（模块03）
│   │   ├── middleware.py     request_id + 耗时 + JSON 日志（模块03）
│   │   ├── redis_client.py   Redis 封装，无 Redis 自动降级 fakeredis（模块03）
│   │   └── idempotency.py    幂等三态机（模块03）
│   ├── schemas/              item.py / chat.py（模块03）
│   ├── services/             item.py / memory.py / chat.py（模块03，★不 import fastapi）
│   ├── api/                  items / stream / ws / agent / health（模块03）
│   ├── llm/client.py         LLM 唯一出口（模块03，模块06 靠它 mock）
│   ├── db/                   models / base / repo（模块04）
│   ├── tasks/                celery_app / ingest（模块05）
│   └── static/               sse.html / ws.html / progress.html（模块03、05）
├── scripts/                  各 demo 的驱动脚本 + serve.sh（启停服务）
├── tests/                    pytest（模块06）
└── deploy/nginx/             反代配置（模块03 demo-05 也有一份带注释的教学版）
```

## 二、目录结构

```
03-后端与linux-git/
├── README.md                 ← 你在这里
├── demo-01-crud/             ① CRUD + 分层 + 统一错误体     → app/api/items.py, services/item.py
├── demo-02-sse/              ② SSE 打字机                  → app/api/stream.py, static/sse.html
├── demo-03-websocket/        ③ WebSocket 双向               → app/api/ws.py, static/ws.html
├── demo-04-idempotent/       ④ 幂等执行                     → app/core/idempotency.py, api/agent.py
├── demo-05-nginx/            ⑤ Nginx 反代/负载均衡/SSE穿透   → nginx.conf + docker-compose.yml + verify.sh
└── demo-06-git-drill/        ⑥ Git 12 练习自动化演练         → drill.sh
```
每个 demo 目录里有 `README.md`（教学目标/预期输出/练习/验收）和 `run.sh`（一键跑）。
**代码本体在 `../fastapi-chat-backend/`**，README 里都标了对应文件路径。

## 三、学习路径

```
Day 1 ── Demo 03-1 CRUD（3h）
   ① bash demo-01-crud/run.sh，然后打开 /docs 手动调一遍所有接口   (30 min)
   ② 读 app/core/errors.py + middleware.py（统一错误体、request_id）  (30 min)
   ③ 读 app/services/item.py，确认它不 import fastapi              (15 min)
   ④ 练习 2（换 SQLite）、练习 5（写 8 个 service 层测试）           (120 min)

Day 2 上午 ── Demo 03-2 SSE（2h）★ Agent 产品的命脉
   ① bash demo-02-sse/run.sh + 浏览器打开 sse.html 看打字机         (20 min)
   ② 读 app/api/stream.py 的三个关键设计（响应头/断开感知/错误帧）    (30 min)
   ③ 做"删掉 X-Accel-Buffering 会怎样"的对照实验（配合 demo-05）     (30 min)
   ④ 练习 2、4                                                    (40 min)

Day 2 下午 ── Demo 03-3 WebSocket（1.5h）
   ① bash demo-03-websocket/run.sh + 浏览器 ws.html                (15 min)
   ② 读 ConnectionManager，重点看 finally 清理和 broadcast(exclude=)  (30 min)
   ③ 背下"SSE vs WS 怎么选"（README 第三节）                        (10 min)
   ④ 练习 2（打断生成）                                             (35 min)

Day 3 上午 ── Demo 03-4 幂等（2.5h）★ 面试高频
   ① bash demo-04-idempotent/run.sh 看四组验证                      (15 min)
   ② 读 app/core/idempotency.py 的三态机                            (40 min)
   ③ 练习 1（DB 唯一约束兜底）、练习 4（回查下游）                    (90 min)

Day 3 下午 ── Demo 03-5 Nginx（1.5h）
   ① docker compose up -d && bash verify.sh                        (20 min)
   ② 做 proxy_buffering 的对照实验（README 第三节）★                 (30 min)
   ③ 读 nginx.conf 的全部注释                                       (20 min)
   ④ 练习 2（按 API Key 限流）                                      (20 min)

Day 4 ── Demo 03-6 Git（2h）
   ① bash drill.sh 看 12 个练习的完整输出                           (10 min)
   ② **自己在 /tmp 新仓库手敲复现练习 2/4/5/8/9**                    (90 min) ★
   ③ 在 GitHub 上走一次真实 PR（练习 10）                            (20 min)

Day 5 ── Linux 命令清单（任务书第二节的 Linux 部分）
   在自己的机器/虚拟机上把清单里的命令逐条敲一遍，重点：
     tail -f + grep 组合排查日志、lsof -i :8000 找端口、
     ps aux | grep、chmod 755、ssh + scp、tmux（跑长任务不怕断线）
```

## 四、一键跑全部
```bash
cd labs/stage0-前置基础
export PYBIN=$PWD/.venv/bin/python
for d in 03-后端与linux-git/demo-0{1,2,3,4}-*/; do
  echo "═══ $d"; (cd "$d" && bash run.sh >/tmp/m3.log 2>&1 && echo "  ✅ OK" || { echo "  ❌ FAIL"; tail -15 /tmp/m3.log; })
done
bash ../fastapi-chat-backend/scripts/serve.sh stop 8000   # 别忘了停服务
# demo-05 需要 Docker：cd demo-05-nginx && docker compose up -d && bash verify.sh
# demo-06 无副作用：  cd demo-06-git-drill && bash drill.sh
```

## 五、必须口头答出的 6 个问题
| 问题 | 答案要点 | 在哪验证过 |
|---|---|---|
| SSE 和 WebSocket 怎么选？ | LLM 输出是单向流 → SSE 够用；SSE 走普通 HTTP 天然穿透网关/CDN，有标准断线重连；WS 只在需要"打断生成/语音实时/多端同步"时用 | demo-03 README 第三节 |
| 流式接口上线后不流式了，怎么回事？ | 被代理缓冲。四个开关：`proxy_buffering off`、`proxy_cache off`、`gzip off`、`chunked_transfer_encoding off`，加长 `proxy_read_timeout`；应用侧发 `X-Accel-Buffering: no` | demo-05 对照实验 |
| 幂等键为什么客户端生成？ | 服务端生成 → 重试时是新 key → 保护失效。客户端生成表达"同一次业务意图" | demo-04 场景 ④ |
| `Depends` 解决什么问题？ | 依赖注入 + 复用 + 可测试（`dependency_overrides`）+ 生命周期管理（yield 型自动清理） | demo-01 练习 4 |
| 为什么 services 层不能 import fastapi？ | 换框架/写测试/被 Celery 调用时全要重做。`grep -c fastapi app/services/*.py` 应该是 0 | demo-01 第二节 |
| reset --hard 删掉的提交能找回吗？ | 能，`git reflog`（默认保留 90 天）。但 `git clean -fd` 删掉的未追踪文件找不回 | demo-06 练习 8 |

## 六、常见报错速查
| 报错 | 原因 | 解法 |
|---|---|---|
| `Address already in use :8000` | 上次的服务没停 | `bash ../fastapi-chat-backend/scripts/serve.sh stop 8000`；或 `lsof -i :8000` 找 pid 后 kill；或 `PORT=8002 bash run.sh` |
| `ModuleNotFoundError: app` | 没在 `fastapi-chat-backend/` 目录下跑 | `cd ../fastapi-chat-backend && python -m uvicorn app.main:app` |
| SSE 一次性返回全部 | 经代理时被缓冲 | 见上面第 2 个问题 |
| WS 连上立刻断 | Nginx 没配 Upgrade 头 | `proxy_set_header Upgrade $http_upgrade;` + `Connection "upgrade"` |
| 幂等测试全 409 | 上次的 key 还在（fakeredis 是进程内存，重启即清；真 Redis 不会） | 换个新 key，或 `redis-cli FLUSHDB` |
| `docker compose up` 卡在 api healthy | 容器里首次 pip install 较慢 | 等 1~2 分钟；`docker compose logs api1` 看进度 |
