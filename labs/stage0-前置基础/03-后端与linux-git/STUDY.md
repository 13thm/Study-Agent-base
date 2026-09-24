# 1.熟悉一下fastapi 的框架结构把：
实际项目中，通常不会把所有代码塞进一个 main.py。推荐的分层结构：
```
myapp/
├── app/
│   ├── __init__.py
│   ├── main.py              # 应用入口，创建 FastAPI 实例
│   ├── core/                # 核心配置
│   │   ├── config.py        # 环境变量、设置
│   │   └── security.py      # JWT、密码加密等
│   ├── api/                 # 路由层
│   │   ├── __init__.py
│   │   ├── deps.py          # 依赖注入（如获取当前用户、DB session）
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py    # 汇总 v1 下所有路由
│   │       ├── users.py     # 用户相关接口
│   │       └── items.py     # 商品相关接口
│   ├── models/              # 数据库模型（SQLAlchemy ORM）
│   │   └── user.py
│   ├── schemas/             # Pydantic 模型（请求/响应体）
│   │   └── user.py
│   ├── crud/                # 数据库操作层
│   │   └── user.py
│   ├── services/            # 业务逻辑层（可选）
│   └── db/
│       ├── session.py       # 数据库连接
│       └── base.py
├── tests/
├── requirements.txt
└── .env
```
先看最简版本，理解核心概念：
```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="My API", version="1.0.0")

# 请求体模型
class Item(BaseModel):
    name: str
    price: float
    in_stock: bool = True

# GET 接口
@app.get("/")
def read_root():
    return {"message": "Hello FastAPI"}

# 路径参数 + 查询参数
@app.get("/items/{item_id}")
def get_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}

# POST 接口，自动校验请求体
@app.post("/items/")
def create_item(item: Item):
    return {"name": item.name, "price": item.price}
```
在看文件版本的：
1. app/main.py — 应用入口
```python
from fastapi import FastAPI
from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

# 挂载路由，统一前缀 /api/v1
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok"}
```
2. app/core/config.py — 配置管理
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "My API"
    DATABASE_URL: str = "sqlite:///./test.db"
    SECRET_KEY: str = "changeme"

    class Config:
        env_file = ".env"

settings = Settings()
```
3. app/schemas/user.py — Pydantic 模型
```python
from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True   # 允许从 ORM 对象转换
```
4. app/models/user.py — 数据库模型
```python
from sqlalchemy import Column, Integer, String, Boolean
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
```
5. app/crud/user.py — 数据操作
```python
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate

def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def create_user(db: Session, user: UserCreate):
    db_user = User(username=user.username, email=user.email,
                   hashed_password=user.password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
```
6. app/api/deps.py — 依赖注入
```python
from app.db.session import SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
7. app/api/v1/users.py — 路由接口
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas.user import UserCreate, UserOut
from app.crud import user as crud_user

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/{user_id}", response_model=UserOut)
def read_user(user_id: int, db: Session = Depends(get_db)):
    user = crud_user.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/", response_model=UserOut, status_code=201)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    return crud_user.create_user(db, user)
```

# 2.SSE 是如何实现的 过程了解 能看懂
SSE = 你打开一个"广播频道"，服务器像个电台，一直给你播报。你只要不关，它就一直说。
## 核心原理
1. 靠一个特殊的 Content-Type
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```
只要响应头是这个，浏览器就知道这是流式推送。  

2. 数据格式特别简单，就是纯文本

服务器发给浏览器的每条消息，长这样：
```
data: 你好\n\n
```
就这。多条消息就是：
```
data: 第一条\n\n
data: 第二条\n\n
data: 第三条\n\n
```
3. 一个连接，服务器"憋着"不关

普通 HTTP 响应发完就 close。SSE 服务器发完一条继续留着连接，等有新消息再写。

## SSE 消息的完整格式
一条消息可以带 4 种字段：

| 字段   | 作用                         | 例子          |
| ------ | ---------------------------- | ------------- |
| data   | 消息内容（必须有）           | data: hello   |
| event  | 事件类型（自定义）           | event: notify |
| id     | 消息 ID，断线重连时用        | id: 42        |
| retry  | 断线后多少毫秒重连           | retry: 3000   |
FastAPI 内置了 StreamingResponse，可以直接做 SSE。
```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio

app = FastAPI()

async def event_generator():
    """生成器：每次 yield 一条 SSE 消息"""
    for i in range(5):
        # 关键格式：data: xxx\n\n
        yield f"data: 这是第 {i} 条消息\n\n"
        await asyncio.sleep(1)  # 每秒发一条

@app.get("/stream")
async def stream():
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"   # 关键！告诉浏览器这是 SSE
    )
```

真的 大模型的是没有asyncio.sleep(1)
```python
async for chunk in openai_client.chat.completions.create(..., stream=True):
    token = chunk.choices[0].delta.content
    if token:
        yield f"data: {json.dumps({'token': token})}\n\n"
    # 注意：这里没有 sleep！
```

# 3. websocket 这个协议的主要工作原理
普通 HTTP 请求（你现在刷网页用的）：
```
浏览器: 我要数据！ ────────────> 服务器
浏览器: <──────────── 给你数据    服务器
       （连接关闭，拜拜）

下次想要数据，得重新敲门再来一遍。
```
WebSocket：
```
浏览器: 我要建个"专线" ────────> 服务器
       <──────────── 好，通了
       （连接不关！）

浏览器: 消息1 ────────────────> 服务器
浏览器: <──────────────── 消息2   服务器
浏览器: 消息3 ────────────────> 服务器
浏览器: <──────────────── 消息4   服务器
       ...想聊多久聊多久...
```
一句话：

HTTP 是"敲一次门，说一句话，走人"。
WebSocket 是"打个电话，双方随便说，想说多久说多久"。

## WebSocket 的核心原理

1. 它靠 HTTP "借壳上市"
WebSocket 不是凭空建立的，它先发一个特殊的 HTTP 请求，叫握手（Handshake）
```
浏览器 → 服务器：

GET /chat HTTP/1.1
Host: example.com
Upgrade: websocket              ← 我要升级成 WebSocket
Connection: Upgrade             ← 我要升级
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==   ← 随机 key
Sec-WebSocket-Version: 13
```
服务器如果同意，回复：
```
HTTP/1.1 101 Switching Protocols   ← 101 表示"切换协议"
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=   ← 加密后的 key
```

2. 握手之后，连接一直开着
不像 HTTP 请求完就关。WebSocket 建完连接就一直保持，双方随时可以说话。

3. 数据是"帧"（frame）传输
握手后，数据不再用 HTTP 格式，而是WebSocket 帧：
```
[FIN][opcode][mask][payload length][masking key][payload]
```
看着复杂，但你不用管——库都帮你封装好了。你只需要知道：

文本帧：传字符串（JSON）

二进制帧：传文件、图片

Ping/Pong 帧：心跳保活

Close 帧：关闭连接

4. 全双工（真正的双向）
HTTP 是"半双工"（一来一回），WebSocket 是"全双工"——双方同时都能发。

## 完整案例：WebSocket + 大模型流式对话（带打断）

后端 main.py
```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from openai import AsyncOpenAI
import json, asyncio

app = FastAPI()
client = AsyncOpenAI(api_key="your-key", base_url="https://api.deepseek.com")

@app.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket):
    await websocket.accept()

    # 队列：用户消息先进队列，生成任务再消费
    user_queue: asyncio.Queue = asyncio.Queue()
    cancel_event = asyncio.Event()

    # ---- 任务1：专门收客户端消息，丢进队列 ----
    async def receiver():
        try:
            while True:
                raw = await websocket.receive_text()
                data = json.loads(raw)
                if data["type"] == "stop":
                    cancel_event.set()          # 打断
                elif data["type"] == "user_message":
                    cancel_event.clear()
                    await user_queue.put(data["content"])
        except WebSocketDisconnect:
            await user_queue.put(None)          # 通知生成任务退出

    # ---- 任务2：专门消费队列，调大模型，流式推回 ----
    async def generator():
        while True:
            prompt = await user_queue.get()
            if prompt is None:
                break

            try:
                stream = await client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                )

                async for chunk in stream:
                    if cancel_event.is_set():
                        await websocket.send_text(json.dumps({
                            "type": "done", "reason": "cancelled"
                        }))
                        cancel_event.clear()
                        break

                    delta = chunk.choices[0].delta.content
                    if delta:
                        await websocket.send_text(json.dumps({
                            "type": "token", "content": delta
                        }, ensure_ascii=False))

                else:
                    # 正常生成完（for 没被 break）
                    await websocket.send_text(json.dumps({"type": "done"}))

            except Exception as e:
                await websocket.send_text(json.dumps({
                    "type": "error", "message": str(e)
                }))

    recv_task = asyncio.create_task(receiver())
    gen_task = asyncio.create_task(generator())

    await asyncio.gather(recv_task, gen_task)
    await websocket.close()
```
WebSocket 连接
   ├── receiver 任务：收消息 → 丢进队列
   └── generator 任务：从队列取 → 调模型 → 流式推回

两个任务并发跑，互不阻塞。
打断靠 cancel_event。


前端
```html
<!DOCTYPE html>
<html>
<body>
  <input id="input" placeholder="说点什么...">
  <button onclick="send()">发送</button>
  <button onclick="stop()">停止</button>
  <pre id="output"></pre>

<script>
  const ws = new WebSocket("ws://localhost:8000/ws/chat");
  const output = document.getElementById("output");
  let current = "";

  ws.onopen = () => console.log("已连接");

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "token") {
      current += msg.content;
      output.textContent = current;          // 打字机效果
    } else if (msg.type === "done") {
      current += "\n\n";
      output.textContent = current;
    } else if (msg.type === "error") {
      console.error(msg.message);
    }
  };

  ws.onclose = () => console.log("连接关闭");

  function send() {
    const text = document.getElementById("input").value;
    if (!text) return;
    ws.send(JSON.stringify({ type: "user_message", content: text }));
    current += `\n我: ${text}\nAI: `;
    output.textContent = current;
    document.getElementById("input").value = "";
  }

  function stop() {
    ws.send(JSON.stringify({ type: "stop" }));   // 打断！
  }
</script>
</body>
</html>
```

最后结果：
```
我: 讲个长故事
AI: 从前有座山（可点击"停止"）
    → 点停止 → AI 立即停在"从前有座山"
```

# 4. ngnix 相关内容
1.如果你有后端服务和前端服务怎么转发怎么联通他们
2. 啥限流 服务转发啥的 都要熟悉


# 5 git 常用的一些方法命令

先记住四个"区域"
```
你的电脑                     Git 仓库（.git 文件夹）
┌─────────────┐            ┌──────────────┐         ┌─────────────┐
│  工作区      │  git add   │   暂存区      │ git     │   本地仓库   │
│ (你正在写的   │ ─────────> │ (准备提交的    │ commit> │ (已存档的    │
│  那些文件)    │            │  那些文件)     │         │  历史版本)   │
└─────────────┘            └──────────────┘         └─────────────┘
                                                          │
                                                          │ git push
                                                          ▼
                                                    ┌─────────────┐
                                                    │  远程仓库    │
                                                    │ (GitHub等)  │
                                                    └─────────────┘
```
> 工作区 → git add → 暂存区 → git commit → 本地仓库 → git push → 远程仓库


最标准的日常流程
```
# ===== 每天开工 =====
git switch main
git pull

# ===== 开新功能 =====
git switch -c feature-xxx

# ===== 写代码，循环 =====
git status
git add .
git commit -m "feat: xxx"

# ===== 推上去 =====
git push -u origin feature-xxx

# ===== 去 GitHub 开 PR，等 review，合并 =====

# ===== 回到 main 更新 =====
git switch main
git pull
git branch -d feature-xxx
```


# 6.幂等执行接口
是什么？有什么？

## 那"幂等执行接口"到底是啥？
一句话:给接口加个"防重复"机制。同一个请求，不管因为网络卡顿、用户狂点、程序重试等原因发来多少次，服务器只真正执行一次，后面的都返回第一次的结果。
就像给接口装了个"认人"的门卫：

怎么实现？核心就一招：客户端给请求起个"身份证号"
关键设计：幂等键（Idempotency-Key）
客户端每次发请求，带一个唯一 ID：


```html
┌──────────┐                              ┌──────────────┐
│  客户端    │                              │   服务器       │
└────┬─────┘                              └──────┬───────┘
     │                                            │
     │  POST /order                               │
     │  Idempotency-Key: abc-123                  │
     │  ────────────────────────────────────────> │
     │                                            │
     │                              ┌─────────────┴─────────────┐
     │                              │ SET abc-123 NX EX 86400   │
     │                              └─────────────┬─────────────┘
     │                                            │
     │                              ┌─────────────┴──────────────┐
     │                              │ 成功？                      │
     │                              └──┬──────────────────────┬──┘
     │                         是 ↙                       ↘ 否
     │                    ┌──────────┐              ┌─────────────┐
     │                    │PROCESSING│              │查 key 状态   │
     │                    │干活...    │              └──────┬──────┘
     │                    │写 DONE   │                     │
     │                    └────┬─────┘          ┌──────────┼──────────┐
     │                         │                │          │          │
     │                         │           PROCESSING    DONE      FAILED
     │                         │                │          │          │
     │                         │           wait? 等   返回缓存    删key
     │                         │           或 409     结果         允许重试
     │                         │                │          │
     │  <──────────────────────┴────────────────┴──────────┘
     │  200 + 结果（第1次 replay=false，后续 replay=true）

```

## 一句话总结

等执行接口 = 给接口发个"身份证"，让服务器只认一次。

不管因为网络卡顿、用户狂点、程序重试发来多少次，服务器只真正干活一次，后面的都返回第一次的结果。

用处：支付、订单、发消息、AI Agent 调工具、秒杀、消息队列——凡是"重复执行会出事"的写操作，都该上幂等。