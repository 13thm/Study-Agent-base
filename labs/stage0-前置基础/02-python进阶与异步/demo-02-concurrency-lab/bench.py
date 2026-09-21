#!/usr/bin/env python3
"""串行 vs 并发对照实验 —— Demo 02-2。

📌 这个 Demo 的唯一目的是**拿到数字**。
    面试说"我懂异步"没有说服力；说"20 个请求串行 10.03s、并发 0.61s，提速 16.4 倍"
    才有说服力。而且你会亲眼看到一个反直觉的事实：
    **加了 async 关键字并不会让代码变快**（方案 B 和 A 一样慢）。

七组实验：
    A  for + requests/httpx 同步串行        → ~10s
    B  for + await httpx 异步串行           → ~10s   ★ async ≠ 并发
    C  asyncio.gather 全并发                → ~0.6s
    D  gather + Semaphore(5) 限流           → ~2.2s  ★ 保护下游
    E  在协程里用 time.sleep                → ~50s   ★ 事件循环被卡死
    F  每次请求新建 AsyncClient             → 比 C 慢（连接复用/握手开销）
    G  服务端阻塞（/slow-blocking）          → 服务端自己变成串行

跑法：bash run.sh （会自动起 mock 服务、跑完自动关）
     或 python bench.py --base-url http://127.0.0.1:8899 --only AC
"""
from __future__ import annotations

import argparse
import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

N = 20                 # 请求数
DELAY = 0.5            # 每个请求的服务端延迟（秒）


def _hr(title: str) -> None:
    print(f"\n{'═' * 70}\n{title}\n{'═' * 70}")


# ═════════════════════════════════════════════════════════════
# A · 同步串行
# ═════════════════════════════════════════════════════════════
def bench_a_sync(base_url: str) -> tuple[float, int]:
    """for 循环 + 同步请求。最直觉的写法，也最慢。"""
    ok = 0
    t0 = time.perf_counter()
    with httpx.Client(timeout=10) as client:        # httpx.Client 是同步版
        for _ in range(N):
            r = client.get(f"{base_url}/slow", params={"delay": DELAY})
            r.raise_for_status()
            ok += 1
    return time.perf_counter() - t0, ok


# ═════════════════════════════════════════════════════════════
# B · 异步但串行（★ 反直觉实验）
# ═════════════════════════════════════════════════════════════
async def bench_b_async_serial(base_url: str) -> tuple[float, int]:
    """for 循环里 await —— 加了 async，但**依然是一个个等**。

    📌 这是新手最大的误解：以为写了 async def 就自动并发了。
        await 的语义是"在这里等它完成"，循环里逐个 await = 串行。
        并发的前提是**先创建多个任务，再一起等**（gather / create_task / TaskGroup）。
    """
    ok = 0
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=10) as client:
        for _ in range(N):
            r = await client.get(f"{base_url}/slow", params={"delay": DELAY})
            r.raise_for_status()
            ok += 1
    return time.perf_counter() - t0, ok


# ═════════════════════════════════════════════════════════════
# C · 全并发
# ═════════════════════════════════════════════════════════════
async def bench_c_gather(base_url: str) -> tuple[float, int]:
    """asyncio.gather 一次性提交 N 个协程。"""
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=10) as client:

        async def one() -> int:
            r = await client.get(f"{base_url}/slow", params={"delay": DELAY})
            r.raise_for_status()
            return 1

        results = await asyncio.gather(*(one() for _ in range(N)))
        # 📌 *(generator) 是"解包"语法：gather 接收的是多个位置参数，不是一个列表。
        #    写成 gather([one() for _ in range(N)]) 会报错。
    return time.perf_counter() - t0, sum(results)


# ═════════════════════════════════════════════════════════════
# D · 并发 + 信号量限流
# ═════════════════════════════════════════════════════════════
async def bench_d_semaphore(base_url: str, limit: int = 5) -> tuple[float, int]:
    """Semaphore 限制同时在飞的请求数。

    📌 限流不是"拖后腿"，是**保护下游和钱包**：
        · 打别人的 API：并发太高会被 429 甚至封号
        · 打 LLM API：并发太高会触发 RPM/TPM 限流，反而更慢（要退避重试）
        · 打自己的数据库：连接池就那么大，超了会排队甚至超时
        阶段 1 模块 01 的多模型客户端、阶段 2 的批量灌库，都靠这个模式。
    """
    sem = asyncio.Semaphore(limit)
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=10) as client:

        async def one() -> int:
            async with sem:                # 拿到令牌才能进；满了就在这里等（不占 CPU）
                r = await client.get(f"{base_url}/slow", params={"delay": DELAY})
                r.raise_for_status()
                return 1

        results = await asyncio.gather(*(one() for _ in range(N)))
    return time.perf_counter() - t0, sum(results)


# ═════════════════════════════════════════════════════════════
# E · 事件循环阻塞（★ 灾难演示）
# ═════════════════════════════════════════════════════════════
async def bench_e_blocking(n: int = 10) -> tuple[float, int]:
    """在协程里用 time.sleep 而不是 await asyncio.sleep。

    time.sleep 是**同步阻塞**调用，它阻塞的是整个线程 —— 而事件循环就跑在这个线程上。
    所以 10 个"并发"任务实际变成 10×0.5=5s 串行，事件循环完全停摆。

    真实后果（比慢更可怕）：
        · FastAPI 服务里一个接口用了 requests/time.sleep，**所有其他用户的请求都卡住**
        · 心跳发不出去 → 连接被判定死亡
        · 看起来是"服务偶发卡顿"，极难排查
    正确做法：
        · 用异步库（httpx.AsyncClient 替代 requests，aiofiles 替代 open）
        · 不得不用同步库时：await asyncio.to_thread(blocking_fn, args)
    """
    t0 = time.perf_counter()

    async def bad() -> int:
        time.sleep(DELAY)                  # ❌ 阻塞整个事件循环
        return 1

    async def good() -> int:
        await asyncio.sleep(DELAY)         # ✅ 让出控制权，别人可以跑
        return 1

    # 先测"正确写法"作为对照
    t_good = time.perf_counter()
    await asyncio.gather(*(good() for _ in range(n)))
    good_elapsed = time.perf_counter() - t_good

    results = await asyncio.gather(*(bad() for _ in range(n)))
    bad_elapsed = time.perf_counter() - t0

    print(f"  对照：await asyncio.sleep × {n} 并发 → {good_elapsed:.2f}s（应该 ≈ {DELAY}s）")
    print(f"  错误：time.sleep          × {n} 并发 → {bad_elapsed:.2f}s（≈ {n}×{DELAY}s，完全串行）")

    # 演示 asyncio.to_thread 的正确救法
    t_thread = time.perf_counter()
    await asyncio.gather(*(asyncio.to_thread(time.sleep, DELAY) for _ in range(n)))
    print(f"  救法：asyncio.to_thread   × {n} 并发 → {time.perf_counter() - t_thread:.2f}s"
          f"（丢进线程池，事件循环不被阻塞）")
    return bad_elapsed, sum(results)


# ═════════════════════════════════════════════════════════════
# F · 客户端复用 vs 每次新建
# ═════════════════════════════════════════════════════════════
async def bench_f_client_reuse(base_url: str) -> tuple[float, int]:
    """每个请求新建一个 AsyncClient → 每次都要重新 TCP 握手 + 连接池初始化。"""
    t0 = time.perf_counter()

    async def one() -> int:
        async with httpx.AsyncClient(timeout=10) as client:    # ❌ 每次都新建
            r = await client.get(f"{base_url}/slow", params={"delay": DELAY})
            r.raise_for_status()
            return 1

    results = await asyncio.gather(*(one() for _ in range(N)))
    return time.perf_counter() - t0, sum(results)


# ═════════════════════════════════════════════════════════════
# G · 服务端阻塞（对照：问题在服务端时长什么样）
# ═════════════════════════════════════════════════════════════
async def bench_g_server_blocking(base_url: str, n: int = 10) -> tuple[float, int]:
    """客户端写法完全正确（全并发），但服务端用了 time.sleep → 一样慢。

    📌 教学点：慢不一定是你的锅。
        排查延迟要先分清"客户端并发不够"还是"服务端本身串行"。
        方法：看服务端框架的 worker 数、看它有没有在 async 接口里写阻塞代码。
    """
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=30) as client:

        async def one() -> int:
            r = await client.get(f"{base_url}/slow-blocking", params={"delay": DELAY})
            r.raise_for_status()
            return 1

        results = await asyncio.gather(*(one() for _ in range(n)))
    return time.perf_counter() - t0, sum(results)


# ═════════════════════════════════════════════════════════════
# 汇总
# ═════════════════════════════════════════════════════════════
async def main() -> int:
    p = argparse.ArgumentParser(description="串行 vs 并发对照实验")
    p.add_argument("--base-url", default="http://127.0.0.1:8899")
    p.add_argument("--only", default="", help="只跑指定的实验，如 AC 或 BDE")
    p.add_argument("--save", default="", help="把结果写成 JSON（供 README 引用）")
    args = p.parse_args()

    only = set(args.only.upper()) or set("ABCDEFG")
    rows: list[dict[str, Any]] = []

    async def run(key: str, name: str, factory: Callable[[], Awaitable[Any]],
                  n: int, note: str = "") -> None:
        """📌 为什么传 factory（lambda）而不是直接传协程对象？
           如果直接传协程，那么"不在这个 only 集合里"的实验也会【先被创建】，
           而没被 await 的协程会触发 RuntimeWarning: coroutine was never awaited。
           传工厂函数就能做到"选中了才创建、才执行"。这是异步编程的一个通用技巧。"""
        if key not in only:
            return
        _hr(f"实验 {key} · {name}")
        elapsed, ok = await factory()
        speedup = (n * DELAY) / elapsed if elapsed else 0
        print(f"  {n} 个请求（每个服务端延迟 {DELAY}s）→ 总耗时 {elapsed:.2f}s，成功 {ok}")
        print(f"  理论串行耗时 {n * DELAY:.1f}s → 实际提速 {speedup:.2f}×")
        if note:
            print(f"  📌 {note}")
        rows.append({"exp": key, "name": name, "n": n, "elapsed_s": round(elapsed, 2),
                     "ok": ok, "speedup": round(speedup, 2), "note": note})

    url = args.base_url
    await run("A", "同步串行 for + httpx.Client",
              lambda: asyncio.to_thread(bench_a_sync, url), N,
              "基准线：20 × 0.5s = 10s")
    await run("B", "异步但串行 for + await", lambda: bench_b_async_serial(url), N,
              "★ async 关键字不会让代码变快！await 在循环里 = 逐个等待")
    await run("C", "asyncio.gather 全并发", lambda: bench_c_gather(url), N,
              "总耗时 ≈ 单个请求耗时 + 一点调度开销")
    await run("D", "gather + Semaphore(5) 限流", lambda: bench_d_semaphore(url, 5), N,
              "20/5 = 4 批 × 0.5s ≈ 2s。慢一点，但不会打爆下游")
    await run("E", "协程里用 time.sleep（阻塞事件循环）", lambda: bench_e_blocking(10), 10,
              "★ 10 个'并发'变成 5s 串行，且期间整个事件循环停摆")
    await run("F", "每次请求新建 AsyncClient", lambda: bench_f_client_reuse(url), N,
              "对比 C，多出来的时间就是 TCP 握手 + 连接池初始化")
    await run("G", "服务端阻塞（/slow-blocking）", lambda: bench_g_server_blocking(url, 10), 10,
              "客户端写法完全正确也一样慢 → 排查延迟要先分清是谁的锅")

    # ── 汇总表 ──
    _hr("汇总（把这张表贴进 README，面试时直接引用）")
    print(f"{'实验':<6}{'方案':<34}{'请求数':>7}{'耗时':>9}{'提速':>8}")
    print("-" * 70)
    for r in rows:
        print(f"{r['exp']:<6}{r['name']:<34}{r['n']:>7}{r['elapsed_s']:>8.2f}s{r['speedup']:>7.2f}×")

    if args.save:
        import json
        from pathlib import Path
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✅ 结果已保存 → {args.save}")

    print("\n═══ 三个必须能口头回答的问题 ═══")
    print("1. 为什么 B 不比 A 快？")
    print("   → await 的语义是'在这里等它完成'。for 循环里逐个 await 就是串行。")
    print("     并发的前提是【先创建多个任务，再一起等】(gather / TaskGroup / create_task)。")
    print("2. D 存在的意义是什么？")
    print("   → 限流不是拖后腿，是保护下游和钱包。打 LLM API 时并发过高会触发 RPM 限流，")
    print("     结果是大量 429 + 退避重试，反而更慢更贵。")
    print("3. 协程里为什么绝对不能出现 time.sleep？")
    print("   → 事件循环跑在单个线程上，同步阻塞调用会霸占这个线程，")
    print("     导致【所有】其他协程都无法推进。在 FastAPI 里，一个这样的接口能拖垮整个服务。")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
