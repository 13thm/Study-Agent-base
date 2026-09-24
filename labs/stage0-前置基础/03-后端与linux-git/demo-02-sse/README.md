# Demo 03-2 · SSE 打字机接口

> **任务书**：[03-后端基础与Linux和Git.md → Demo 03-2](../../../../my-docs/study01/stage0-前置基础/03-后端基础与Linux和Git.md)
> **代码位置**：`../../fastapi-chat-backend/app/api/stream.py` + `app/static/sse.html`
> **依赖**：`fastapi` `uvicorn`　**耗时**：2 小时

## 一、跑
```bash
bash run.sh                                    # 启动服务 + 4 个验证场景
open http://127.0.0.1:8001/static/sse.html     # ★ 浏览器里看打字机效果（最有感的一步）
curl -N "http://127.0.0.1:8001/api/chat/stream?q=什么是SSE"     # 命令行看逐帧
```

## 二、SSE 协议的 4 个硬规则
| 规则 | 不遵守会怎样 |
|---|---|
| `Content-Type: text/event-stream` | 浏览器 `EventSource` 直接报错 |
| 每帧 `data: <payload>\n\n`（**两个换行**） | 少一个换行 → 客户端永远收不到这一帧 |
| `X-Accel-Buffering: no` + Nginx 侧 `proxy_buffering off` | **经过 Nginx 后流式变一次性返回**（99% 的人上线后踩这个） |
| 长任务加心跳帧 `: ping\n\n` | 代理默认 60s 无数据就断连 |

## 三、代码里的三个关键设计
```python
# ① 响应头（app/api/stream.py 的 SSE_HEADERS）
{"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}

# ② 客户端断开要能感知，否则白烧 Token
if await request.is_disconnected():
    print("[SSE] 客户端断开，停止生成"); return

# ③ 流已经开始就不能再改状态码 → 错误用"错误帧"告知
except Exception as e:
    yield _frame("error", {"message": f"{type(e).__name__}: {e}"})
finally:
    yield "data: [DONE]\n\n"
```
第 ③ 点是新手最容易忽略的：**HTTP 状态码在第一帧发出时就定死了**，
后面出错只能靠协议内的错误事件表达。阶段 2 项目 1 的 F6 会把这个模式扩展成
`stage / delta / citation / done` 四种事件。

## 四、验证清单（run.sh 会逐个跑）
- [ ] 响应头含 `text/event-stream` 和 `x-accel-buffering: no`
- [ ] `curl -N` 能看到帧**逐个到达**（时间戳递增，不是一次性）
- [ ] 浏览器页面显示"完成 N 字 / M 帧 / 总耗时 / 首帧延迟"
- [ ] 点"中断"按钮 → **服务端日志出现 `[SSE] 客户端断开，停止生成`**
- [ ] 经 Nginx 后依然流式（去 demo-05-nginx 做对照实验：注释掉 `proxy_buffering off` 看它变成一次性返回）

## 五、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 把 `use_llm=true` 跑通（需要模块 02 的 mock LLM 服务在 8898 端口） |
| 2 | ⭐⭐ | 加 `event: citation` 帧，在答案中间推送引用来源（阶段 2 项目 1 的 F6） |
| 3 | ⭐⭐ | 实现 `Last-Event-ID` 断线续传：每帧带 id，重连时从断点继续 |
| 4 | ⭐⭐⭐ | 加 30s 心跳帧 `: ping\n\n`，并用 Nginx 的 `proxy_read_timeout 20s` 验证它真的保住了连接 |

## 六、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
