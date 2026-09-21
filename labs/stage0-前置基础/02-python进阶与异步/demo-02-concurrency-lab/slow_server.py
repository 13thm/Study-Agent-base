#!/usr/bin/env python3
"""Mock 慢服务 —— 用于 Demo 02-2 的并发对照实验。

为什么要自己起一个服务，而不是打真实网站？
    ① 可控：延迟精确是 0.5s，实验结果可复现
    ② 合法：不打别人的服务器（压测公网服务可能违反对方 ToS）
    ③ 稳定：不受网络波动影响，测出来的差异才真的是"串行 vs 并发"的差异

启动：python slow_server.py            （默认 127.0.0.1:8899）
     uvicorn slow_server:app --port 8899
"""
from __future__ import annotations

import asyncio
import os
import time

from fastapi import FastAPI

app = FastAPI(title="Mock 慢服务", description="每个请求固定 sleep，用于并发实验")

# 用模块级计数器验证"服务端真的收到了 N 个请求"（而不是客户端在骗你）
_stats = {"requests": 0, "start": time.time()}


@app.get("/slow")
async def slow(delay: float = 0.5) -> dict:
    """固定延迟接口。delay 可通过查询参数调整（做不同实验时用）。"""
    await asyncio.sleep(delay)          # ★ 这是"非阻塞等待"，不会卡住事件循环
    _stats["requests"] += 1
    return {"ok": True, "n": _stats["requests"], "delay": delay}


@app.get("/slow-blocking")
async def slow_blocking(delay: float = 0.5) -> dict:
    """⚠️ 反面教材：在 async 接口里用 time.sleep（阻塞整个事件循环）。

    用它做对照实验：并发 20 个请求打这个端点，会发现**服务端也是串行的**，
    总耗时约 20×0.5=10s，而打 /slow 只需要 ~0.6s。
    这就是"事件循环被卡死"的服务端版本。
    """
    time.sleep(delay)                   # ❌ 阻塞！整个 worker 的所有请求都在等
    _stats["requests"] += 1
    return {"ok": True, "n": _stats["requests"], "blocking": True}


@app.get("/stats")
async def stats() -> dict:
    return {"requests": _stats["requests"], "uptime_s": round(time.time() - _stats["start"], 1)}


@app.post("/stats/reset")
async def reset() -> dict:
    _stats["requests"] = 0
    _stats["start"] = time.time()
    return {"ok": True}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8899"))
    print(f"🚀 Mock 慢服务启动: http://127.0.0.1:{port}")
    print("   /slow?delay=0.5          非阻塞延迟（正常写法）")
    print("   /slow-blocking?delay=0.5 阻塞延迟（反面教材，做对照实验用）")
    print("   /stats                   查看服务端收到的请求数")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
