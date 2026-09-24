# Demo 03-3 · WebSocket 实时对话

> **任务书**：[03-后端基础与Linux和Git.md → Demo 03-3](../../../../my-docs/study01/stage0-前置基础/03-后端基础与Linux和Git.md)
> **代码位置**：`../../fastapi-chat-backend/app/api/ws.py` + `app/static/ws.html` + `scripts/demo03_3_ws.py`
> **依赖**：`fastapi` `websockets`　**耗时**：2 小时

## 一、跑
```bash
bash run.sh                                   # 命令行客户端连发多轮
open http://127.0.0.1:8000/static/ws.html      # 浏览器版（有连接状态灯）
```

## 二、必须实现的 5 件事
| 事项 | 代码位置 | 不做会怎样 |
|---|---|---|
| `ConnectionManager` 按 session 分组 | `ws.py` 的类 | 无法做多端同步/广播 |
| 断开清理放 **`finally`** | `ws_chat()` 末尾 | 拔网线/关浏览器后连接堆积 → 内存泄漏 + 广播报错 |
| 心跳（每 20s ping） | `heartbeat()` 任务 | 代理静默断开，客户端不知道 |
| 消息类型分离（`start/token/done/error/stats`） | 各 `send_json` | 客户端无法区分"正文"和"控制帧" |
| 广播排除发起者 | `broadcast(exclude=ws)` | **客户端收到自己的回声，且插在 token 流中间导致错位** |

> 最后一条是我真踩的坑：第一版没排除发送者，命令行客户端打印顺序全乱
> （`/stats` 的回复位置跑到了上一轮的 sync 消息后面）。已修，代码注释里留了记录。

## 三、★ README 必答题：Agent 产品为什么主流选 SSE 而不是 WebSocket？
```
· LLM 输出本来就是【单向流】，SSE 的能力刚好够，WS 的双向性用不上
· SSE 走普通 HTTP：天然穿透网关 / CDN / 企业代理；WS 需要 Upgrade 握手，
  某些老代理和 WAF 会直接掐掉
· SSE 有标准的断线重连机制（浏览器自动重连 + Last-Event-ID 续传）；
  WS 要自己写心跳、重连、消息补发
· SSE 调试简单：curl -N 就能看；WS 要专门的客户端
· 需要 WS 的场景：语音实时交互、用户中途打断生成、多端同步、协作编辑
→ 结论：默认 SSE，有明确的双向需求才上 WS
```

## 四、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 客户端加"自动重连"：断开后 1s/2s/4s 指数退避重连，最多 5 次 |
| 2 | ⭐⭐ | 实现"用户中途打断生成"：客户端发 `{"type":"stop"}`，服务端取消生成任务（`task.cancel()`） |
| 3 | ⭐⭐ | 把连接注册表搬到 Redis（`SADD ws:sess:{id} {conn_id}`），支持多进程部署下的广播（用 pub/sub） |
| 4 | ⭐⭐⭐ | 同一个会话开两个浏览器标签，验证"多端同步"：一端发消息，另一端能收到 sync 帧 |

## 五、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
