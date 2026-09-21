#!/usr/bin/env python3
"""Mock 的 OpenAI 兼容 LLM 服务 —— 让 Demo 02-5 可以离线跑、不花一分钱。

它实现了 /v1/chat/completions 的最小子集，并且**故意制造真实世界的脏情况**：
    · 按 prompt 里的关键词决定延迟（模拟不同复杂度）
    · 一定比例的请求返回 429（模拟限流）
    · 一定比例的请求超时不响应（模拟上游卡死）
    · 一定比例的请求返回残缺 JSON（模拟模型输出不合法）
    · usage 字段真实返回 token 数（让成本统计有数据）

启动：python mock_llm_server.py            # 默认 127.0.0.1:8898
可用环境变量调故障率：
    FAIL_RATE_429=0.1 FAIL_RATE_TIMEOUT=0.05 FAIL_RATE_BADJSON=0.1
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Mock OpenAI 兼容服务")

RATE_429 = float(os.environ.get("FAIL_RATE_429", "0.08"))
RATE_TIMEOUT = float(os.environ.get("FAIL_RATE_TIMEOUT", "0.04"))
RATE_BADJSON = float(os.environ.get("FAIL_RATE_BADJSON", "0.08"))
SEED = int(os.environ.get("MOCK_SEED", "42"))
_rng = random.Random(SEED)
_stats = {"requests": 0, "429": 0, "timeout": 0, "badjson": 0, "prompt_tokens": 0, "completion_tokens": 0}


def _fake_answer(prompt: str) -> str:
    """按 prompt 生成一个"看起来像那么回事"的答案（内容固定，保证可复现）。"""
    topic = prompt.strip()[:40]
    return (f"关于「{topic}」的一句话解释：它是一种通过检索外部知识来增强生成质量的技术，"
            f"核心是把相关资料放进上下文，让模型基于证据回答而不是凭记忆编造。")


def _estimate_tokens(text: str) -> int:
    """粗略 token 估算：中文按 1.6 token/字，英文按 0.75 token/词。
    📌 阶段 1 模块 01 会用 tiktoken 做精确版，这里够用了。"""
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    other = len(text) - cjk
    return int(cjk * 1.6 + other * 0.3)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> JSONResponse:
    body = await request.json()
    _stats["requests"] += 1

    # ── 故障注入 ──
    # 📌 踩坑记录（真实发生的 bug）：
    #    我一开始写成 dice = random.Random(hash(prompt) ^ SEED).random()
    #    想法是"同一 prompt 结果一致 → 可复现"，结果**重试永远失败**：
    #    因为同一个 prompt 每次算出的 dice 完全相同，第一次 429，重试 3 次还是 429。
    #    重试机制的教学价值直接归零。
    #    正确做法：用【进程级 seeded RNG】—— 单次运行内是随机序列（重试有机会成功），
    #    但整个 run 的分布可复现（因为 seed 固定）。这才是"可复现的随机"。
    msgs = body.get("messages", [])
    prompt = msgs[-1]["content"] if msgs else ""
    dice = _rng.random()

    if dice < RATE_429:
        _stats["429"] += 1
        return JSONResponse(
            status_code=429,
            content={"error": {"message": "Rate limit reached (mock)", "type": "rate_limit_exceeded"}},
            headers={"Retry-After": "1"},
        )

    latency = 0.15 + (len(prompt) % 7) * 0.03               # 0.15 ~ 0.33s
    if dice < RATE_429 + RATE_TIMEOUT:
        _stats["timeout"] += 1
        await asyncio.sleep(30)      # 卡住足够久让客户端超时（不用 999，免得占着连接）
    await asyncio.sleep(latency)

    answer = _fake_answer(prompt)
    bad = dice > 1 - RATE_BADJSON
    if bad:
        _stats["badjson"] += 1
        # 三种典型脏输出：被截断 / 带围栏 / 带解释文字
        choice = _rng.choice(["truncate", "fence", "prefix"])
        payload = {"answer": answer, "confidence": 0.9}
        raw = json.dumps(payload, ensure_ascii=False)
        if choice == "truncate":
            text = raw[: len(raw) // 2]                      # 被 max_tokens 截断
        elif choice == "fence":
            text = f"```json\n{raw}\n```"
        else:
            text = f"好的，以下是结果：{raw} 希望对你有帮助"
    else:
        text = json.dumps({"answer": answer, "confidence": 0.9}, ensure_ascii=False)

    pt = _estimate_tokens(prompt) + 40
    ct = _estimate_tokens(text)
    _stats["prompt_tokens"] += pt
    _stats["completion_tokens"] += ct

    return JSONResponse({
        "id": f"chatcmpl-mock-{_stats['requests']}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model", "mock-llm"),
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": text},
            "finish_reason": "length" if bad else "stop",
        }],
        "usage": {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct},
    })


@app.get("/stats")
async def stats() -> dict:
    return _stats


@app.post("/stats/reset")
async def reset() -> dict:
    for k in _stats:
        _stats[k] = 0
    return {"ok": True}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8898"))
    print(f"🤖 Mock LLM 服务: http://127.0.0.1:{port}/v1/chat/completions")
    print(f"   故障率: 429={RATE_429:.0%}  超时={RATE_TIMEOUT:.0%}  脏JSON={RATE_BADJSON:.0%}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
