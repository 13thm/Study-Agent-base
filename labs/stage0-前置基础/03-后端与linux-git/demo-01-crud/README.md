# Demo 03-1 · 标准 CRUD 服务（分层架构起点）

> **任务书**：[03-后端基础与Linux和Git.md → Demo 03-1](../../../../my-docs/study01/stage0-前置基础/03-后端基础与Linux和Git.md)
> **代码位置**：`../../fastapi-chat-backend/app/`（本 Demo 就是这个仓库的起点，模块 04/05/06 会继续往里加）
> **依赖**：`fastapi` `uvicorn` `httpx`　**耗时**：3 小时

## 一、跑
```bash
bash run.sh      # 自动启动服务（端口 8000）→ 跑 13 个场景 → 提示如何停服
```
启动后可以直接开浏览器玩：
- Swagger UI：http://127.0.0.1:8000/docs （**能在页面上调所有接口**）
- 首页索引：http://127.0.0.1:8000/

## 二、分层结构（★ 本 Demo 最重要的产出）
```
fastapi-chat-backend/app/
├── main.py            create_app + 挂路由 + 生命周期（不写业务）
├── config.py          pydantic-settings 读环境变量（APP_ 前缀）
├── core/
│   ├── errors.py      AppError 异常层次 + 全局 handler（统一错误响应体）
│   ├── middleware.py  request_id 注入 + 耗时统计 + JSON 访问日志
│   ├── redis_client.py Redis 封装（无 Redis 时自动降级 fakeredis）
│   └── idempotency.py 幂等三态机（Demo 03-4）
├── schemas/           Pydantic 模型（Create / Update / Out 三层）
├── services/          ★ 业务逻辑，【不 import fastapi】
├── api/               路由层，只做"校验参数 → 调 service → 包装响应"
└── llm/client.py      LLM 访问的唯一出口（模块 06 靠它做 mock）
```
**验证分层的硬指标**：
```bash
grep -c fastapi ../fastapi-chat-backend/app/services/*.py     # 必须全是 0
```

## 三、13 个场景与预期
| # | 请求 | 预期 |
|---|---|---|
| 0 | `GET /health/ready` | 200，显示 redis 后端（fakeredis 或真实） |
| 1 | `POST /api/items` | **201** + 返回带 id/created_at 的完整对象 |
| 2-5 | 查详情 / PATCH / 分页 / 搜索 | 200 |
| 6 | `GET /api/items/999999` | **404** `{"error":{"code":"NOT_FOUND",...}}` |
| 7 | `?size=99999` | **422**，message 是人话（不是 FastAPI 默认那一坨） |
| 8 | 缺必填字段 | 422 |
| 9 | 多余字段（`extra="forbid"`） | 422 |
| 10 | `price=-5` | 422（`ge=0` 生效） |
| 11 | `DELETE` | **204 无响应体** |
| 12 | 删后再查 | 404 |

**每个响应都带 `X-Request-ID`** —— 用户报障时给你这个 id，就能捞出全链路日志。

## 四、统一错误响应体（要养成的习惯）
```json
{"error": {"code": "NOT_FOUND", "message": "item 999999 不存在", "request_id": "b1f3a2c9d1e4"}}
```
而不是有的接口 `{"detail": "..."}`、有的 `{"msg": "..."}`、有的直接吐 500 HTML traceback。
实现见 `app/core/errors.py`，其中 `RequestValidationError` 的 handler 把 FastAPI 默认的
嵌套错误翻译成了人话（对照场景 7 的输出看）。

## 五、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 加 `GET /api/items/{id}/similar`，按 tags 交集数量排序返回相似项 |
| 2 | ⭐⭐ | 把 `services/item.py` 的内存 dict 换成 SQLite（用标准库 `sqlite3`，先别上 SQLAlchemy） |
| 3 | ⭐⭐ | 加 `POST /api/items/batch`，接收数组，**部分成功时返回 207 Multi-Status** 并逐条给结果 |
| 4 | ⭐⭐ | 加一个 `Depends` 的鉴权依赖（读 `X-API-Key`，不对就 401），并给某个接口挂上 |
| 5 | ⭐⭐⭐ | 给 `services/item.py` 写 8 个 pytest（**不起 HTTP 服务，直接调函数** —— 体会分层带来的可测性） |

## 六、验收清单
- [ ] 13 个场景全部符合预期，每个响应都有 X-Request-ID
- [ ] `grep -c fastapi app/services/*.py` 全为 0
- [ ] `/docs` 里手动调完所有接口
- [ ] 422 的 message 是人话（自己写的 handler 生效）
- [ ] 能白板写出：`Depends` 的 yield 型依赖 + 全局异常处理器 + request_id 中间件

## 七、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
