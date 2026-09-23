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

# ── 标准库 ─────────────────────────────────────────────
import asyncio                           # 用于 sleep（模拟延迟、模拟卡死）
import json                              # 构造响应体
import os                                # 读环境变量
import random                            # 故障注入 + 脏输出类型选择
import time                              # 生成 created 时间戳

# ── Web 框架 ───────────────────────────────────────────
from fastapi import FastAPI, Request     # FastAPI 主类 + 请求对象
from fastapi.responses import JSONResponse  # 可以自定义状态码/headers 的响应

# 创建 FastAPI 应用实例
# 这是所有路由的宿主，uvicorn 启动时会把请求路由到它
app = FastAPI(title="Mock OpenAI 兼容服务")


# ═════════════════════════════════════════════════════════════
# 配置：从环境变量读故障率（方便调试不同场景）
# ═════════════════════════════════════════════════════════════
# os.environ.get(键, 默认值) —— 环境变量没设时用默认
# float(...) 把字符串转成浮点数
# 格式：FAIL_RATE_429=0.1 python mock_llm_server.py
RATE_429 = float(os.environ.get("FAIL_RATE_429", "0.08"))       # 8% 概率返回 429
RATE_TIMEOUT = float(os.environ.get("FAIL_RATE_TIMEOUT", "0.04"))  # 4% 概率卡死
RATE_BADJSON = float(os.environ.get("FAIL_RATE_BADJSON", "0.08"))  # 8% 概率返回脏 JSON

# 随机种子，保证整个 run 的"故障分布"可复现
SEED = int(os.environ.get("MOCK_SEED", "42"))

# ★ 模块级 RNG，进程生命周期内共享
#   为什么不每次请求 random.Random(SEED)？
#   见下面 chat_completions 里的"踩坑记录"
_rng = random.Random(SEED)

# 运行统计（内存里累计，重启清零）
_stats = {
    "requests": 0,           # 总请求数
    "429": 0,                # 返回 429 的次数
    "timeout": 0,            # 模拟卡死的次数
    "badjson": 0,            # 返回脏 JSON 的次数
    "prompt_tokens": 0,      # 累计输入 token
    "completion_tokens": 0,  # 累计输出 token
}


# ═════════════════════════════════════════════════════════════
# 工具函数
# ═════════════════════════════════════════════════════════════
def _fake_answer(prompt: str) -> str:
    """按 prompt 生成一个"看起来像那么回事"的答案（内容固定，保证可复现）。

    📌 为什么叫 _fake？
        下划线前缀是 Python 约定，表示"这是模块私有的，外部别直接调"。
        它只服务于 mock 服务内部，不该被当公共 API。

    📌 "内容固定"是什么意思？
        同样的 prompt 永远得到同样的答案。原因：
          1. topic 是从 prompt 里截取的（确定性）
          2. 模板里的文字是写死的（确定性）
        没有随机成分 → 同输入同输出 → 批量评测时 A/B 对比公平
    """
    # 截取前 40 个字符做"话题"
    # prompt.strip() 先去掉首尾空白；[:40] 是切片，超过 40 字符就截断
    topic = prompt.strip()[:40]

    # f-string 拼接：把 topic 嵌入到一段"看起来很合理"的解释里
    # 这就是"假装回答了"，实际内容不重要——重要的是格式和可复现性
    return (f"关于「{topic}」的一句话解释：它是一种通过检索外部知识来增强生成质量的技术，"
            f"核心是把相关资料放进上下文，让模型基于证据回答而不是凭记忆编造。")


def _estimate_tokens(text: str) -> int:
    """粗略 token 估算：中文按 1.6 token/字，英文按 0.75 token/词。
    📌 阶段 1 模块 01 会用 tiktoken 做精确版，这里够用了。"""
    # 统计中日韩字符（CJK）的数量
    # "\u4e00" 是"一"的 Unicode 码点，"\u9fff" 是 CJK 统一汉字区块的末尾
    # 生成器 + sum：遍历每个字符，是 CJK 就贡献 1，否则贡献 0，全部相加
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")

    # 非 CJK 字符的数量（近似认为都是英文/符号/数字）
    other = len(text) - cjk

    # 经验系数：
    #   CJK：1.6 token/字（中文一般 1~2 token/字，取 1.6 是个折中）
    #   other：0.3 token/字符（英文约 4 字符/token，所以 1/4 = 0.25；这里取 0.3 略宽松）
    # 最后 int() 取整——token 数必须是整数
    return int(cjk * 1.6 + other * 0.3)


# ═════════════════════════════════════════════════════════════
# 核心路由：/v1/chat/completions
# ═════════════════════════════════════════════════════════════
# @app.post(路径) 是 FastAPI 的路由装饰器：告诉框架"POST 这个路径时调这个函数"
# 路径和 OpenAI 官方 API 一致，这样客户端改个 base_url 就能切过来
@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> JSONResponse:
    # ★ async def 让 FastAPI 用异步方式处理请求
    #   好处：await asyncio.sleep(30) 时不会阻塞其他请求
    #   如果用同步 def，一个请求卡住就把整个服务堵死了

    # ── 读取请求体 ────────────────────────────────────
    # request.json() 是 async 方法，必须 await
    # 它把请求体的 JSON 解析成 dict
    body = await request.json()

    # 统计请求数（在故障判定之前 +1，表示"收到了"）
    _stats["requests"] += 1

    # ── 故障注入 ──
    # 📌 踩坑记录（真实发生的 bug）：
    #    我一开始写成 dice = random.Random(hash(prompt) ^ SEED).random()
    #    想法是"同一 prompt 结果一致 → 可复现"，结果**重试永远失败**：
    #    因为同一个 prompt 每次算出的 dice 完全相同，第一次 429，重试 3 次还是 429。
    #    重试机制的教学价值直接归零。
    #    正确做法：用【进程级 seeded RNG】—— 单次运行内是随机序列（重试有机会成功），
    #    但整个 run 的分布可复现（因为 seed 固定）。这才是"可复现的随机"。

    # ── 从请求里抽 prompt ─────────────────────────────
    msgs = body.get("messages", [])
    # msgs[-1] 取最后一条消息（用户消息通常放最后）
    # 三元表达式兜底：messages 为空时 prompt 用空字符串
    prompt = msgs[-1]["content"] if msgs else ""

    # ★ 用模块级 RNG 取一个 [0.0, 1.0) 的随机数
    #   每次调用结果不同（在同一个 run 内），但整个 run 分布可复现
    #   这是"重试有机会成功"的关键
    dice = _rng.random()

    # ── 故障 1：429 限流 ─────────────────────────────
    # 8% 概率命中
    if dice < RATE_429:
        _stats["429"] += 1
        # JSONResponse 允许自定义 status_code 和 headers
        # Retry-After: 1 是告诉客户端"1 秒后再试"——真实 API 也会返回这个头
        return JSONResponse(
            status_code=429,
            content={"error": {"message": "Rate limit reached (mock)", "type": "rate_limit_exceeded"}},
            headers={"Retry-After": "1"},
        )

    # ── 延迟模拟 ────────────────────────────────────
    # 按 prompt 长度算一个 0.15~0.33s 的延迟
    # len(prompt) % 7 得到 0~6，乘 0.03 得到 0~0.18
    # 这样"长度不同 → 延迟不同"，模拟"不同复杂度的请求耗时不同"
    latency = 0.15 + (len(prompt) % 7) * 0.03

    # ── 故障 2：超时（卡死） ─────────────────────────
    # 注意这里的判定是"在 429 的基础上再累加"
    # 即：dice ∈ [RATE_429, RATE_429 + RATE_TIMEOUT) 才命中
    # 这样三个故障的概率互不重叠，总和 ≤ 1
    if dice < RATE_429 + RATE_TIMEOUT:
        _stats["timeout"] += 1
        # ★ sleep(30) 让客户端超时
        #   为什么是 30 而不是 999？
        #   因为 sleep 会占着这个协程和连接，30 秒足够让客户端超时了，
        #   不必真的睡 999 秒（否则容易把服务端连接池占满）
        await asyncio.sleep(30)

    # ── 正常延迟 ────────────────────────────────────
    # 走到这里说明没命中"超时"故障，正常 sleep 一小下
    await asyncio.sleep(latency)

    # ── 构造答案 ────────────────────────────────────
    answer = _fake_answer(prompt)

    # ── 故障 3：返回脏 JSON ──────────────────────────
    # dice > 1 - RATE_BADJSON 等价于 dice ∈ (1-RATE, 1]，即顶部 RATE 的区间
    # 这是"用同一个 dice 判断多个不重叠区间"的技巧
    bad = dice > 1 - RATE_BADJSON

    if bad:
        _stats["badjson"] += 1
        # 三种典型脏输出：被截断 / 带围栏 / 带解释文字
        # 这里让_rng再抽一次，决定这次脏成什么样
        choice = _rng.choice(["truncate", "fence", "prefix"])

        # 先构造一份"干净的" JSON 文本，再按 choice 弄脏
        payload = {"answer": answer, "confidence": 0.9}
        raw = json.dumps(payload, ensure_ascii=False)

        if choice == "truncate":
            # 截断到一半——模拟 max_tokens 用光
            # len(raw) // 2 是整除，取一半长度
            text = raw[: len(raw) // 2]
        elif choice == "fence":
            # 包一层 markdown 围栏——模型最常见的多余包装
            text = f"```json\n{raw}\n```"
        else:
            # 前后加解释文字——模型"话多"的表现
            text = f"好的，以下是结果：{raw} 希望对你有帮助"
    else:
        # 没命中脏 JSON 故障，返回干净的 JSON
        text = json.dumps({"answer": answer, "confidence": 0.9}, ensure_ascii=False)

    # ── 计算 token 数 ──────────────────────────────
    # 输入 token = prompt 本身的 token + 40（近似 system prompt 的开销）
    pt = _estimate_tokens(prompt) + 40
    ct = _estimate_tokens(text)

    # 累计到统计里
    _stats["prompt_tokens"] += pt
    _stats["completion_tokens"] += ct

    # ── 返回 OpenAI 兼容的响应 ──────────────────────
    # 结构严格按 OpenAI Chat Completions API，客户端才能"无感切换"
    return JSONResponse({
        "id": f"chatcmpl-mock-{_stats['requests']}",       # 每次唯一
        "object": "chat.completion",
        "created": int(time.time()),                        # Unix 时间戳（整数秒）
        "model": body.get("model", "mock-llm"),             # 回显请求里的 model
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": text},
            # ★ finish_reason 是关键：脏 JSON 时是 "length"，正常是 "stop"
            #   真实场景里 "length" 意味着"没说完，被 max_tokens 截断了"
            "finish_reason": "length" if bad else "stop",
        }],
        "usage": {
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": pt + ct,
        },
    })


# ═════════════════════════════════════════════════════════════
# 辅助路由：统计 / 重置 / 健康检查
# ═════════════════════════════════════════════════════════════
@app.get("/stats")
async def stats() -> dict:
    """查看累计统计（方便调试：验证注入的故障率符合预期）。"""
    return _stats


@app.post("/stats/reset")
async def reset() -> dict:
    """清零统计，方便下一轮实验用干净的计数。"""
    for k in _stats:
        _stats[k] = 0
    return {"ok": True}


@app.get("/health")
async def health() -> dict:
    """健康检查端点。生产环境里 K8s / 负载均衡会定时打它判断服务是否活着。"""
    return {"status": "ok"}


# ═════════════════════════════════════════════════════════════
# 启动入口
# ═════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn   # ★ 局部 import：只有真正运行时才需要

    # 允许用环境变量覆盖端口（默认 8898）
    # 8898 是随机挑的高位端口，避免和常用服务冲突
    port = int(os.environ.get("PORT", "8898"))

    # 启动信息：告诉用户"服务在哪、故障率多少"
    # :.0% 把浮点数格式化成百分比（0.08 → 8%）
    print(f"🤖 Mock LLM 服务: http://127.0.0.1:{port}/v1/chat/completions")
    print(f"   故障率: 429={RATE_429:.0%}  超时={RATE_TIMEOUT:.0%}  脏JSON={RATE_BADJSON:.0%}")

    # uvicorn.run 是 ASGI 服务器的启动入口
    # host=127.0.0.1：只监听本机，安全（不暴露到局域网）
    # log_level="warning"：只打印 warning 及以上，避免每条请求都刷日志
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")