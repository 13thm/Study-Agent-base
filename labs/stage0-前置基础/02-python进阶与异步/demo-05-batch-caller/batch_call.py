#!/usr/bin/env python3
"""异步 LLM 批量调用器 —— Demo 02-5（本模块的集大成者）。

📌 这个脚本以后会被反复复用
    阶段 1 的提示词 A/B 评测、阶段 2 的评测集跑分、阶段 5 的批量回归，
    本质都是"读一批 prompt → 并发调模型 → 落盘 → 统计成本"。
    所以这里把它写成**生产可用的样子**：限流、重试、超时、断点续跑、边跑边写、成本统计。

📌 默认打的是本地 mock 服务（mock_llm_server.py），不花钱、可离线、可复现故障。
    换成真实 API 只需要改 --base-url 和 --api-key（协议是 OpenAI 兼容的）。

用法：
    python batch_call.py --in data/prompts.jsonl --out data/results.jsonl --concurrency 5
    python batch_call.py --resume          # 断点续跑（跳过已完成的 id）
    python batch_call.py --concurrency 1   # 对照实验：串行要多久
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

# ── 复用 Demo 02-1 的装饰器 ────────────────────────────────────
# 📌 这里用 sys.path 插入兄弟目录，是"教学仓库"的权宜做法。
#    真实项目应该做成可安装的包（阶段 1 的 prompt-toolbox 就是 pip install -e 进来用的）。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demo-01-decorators"))
from decorators import retry  # noqa: E402  （放在 import 后面是因为要先改 sys.path）

HERE = Path(__file__).parent

# ── 价格表（元 / 百万 token）──────────────────────────────────
# 📌 绝不硬编码在逻辑里，抽成常量（阶段 1 会挪进 YAML 配置）
PRICE = {"mock-llm": (1.0, 2.0), "deepseek-chat": (1.0, 2.0), "gpt-4o-mini": (0.15, 0.6)}


class RateLimited(Exception):
    """429 —— 应该重试。"""


class UpstreamError(Exception):
    """5xx —— 应该重试。"""


class BadRequest(Exception):
    """400 —— ★ 绝不重试（重试只是浪费钱，结果一定一样）。"""


# ═════════════════════════════════════════════════════════════
# 单次调用（含重试与超时）
# ═════════════════════════════════════════════════════════════
#: 重试统计（用回调收集，不逐条打印 —— 见 decorators.retry 的 on_retry 说明）
RETRY_STATS: Counter[str] = Counter()


def _on_retry(name: str, attempt: int, exc: BaseException, wait: float) -> None:
    RETRY_STATS[type(exc).__name__] += 1
    if os.environ.get("VERBOSE_RETRY"):      # 想看细节时 VERBOSE_RETRY=1 python batch_call.py
        print(f"  [retry] {name} 第{attempt}次失败 {type(exc).__name__}: {exc}，等 {wait:.2f}s")


@retry(times=3, delay=0.3, backoff=2, jitter=True,
       exceptions=(RateLimited, UpstreamError, asyncio.TimeoutError),
       on_retry=_on_retry)
async def call_once(client: httpx.AsyncClient, base_url: str, api_key: str, model: str,
                    prompt: str, timeout: float) -> dict[str, Any]:
    """调一次 /v1/chat/completions，返回 {text, usage, latency_ms, retried?}。

    📌 三个设计点：
        ① @retry 的 exceptions 白名单里【没有 BadRequest】—— 400 参数错绝不重试
        ② asyncio.wait_for 包住整个请求，超时抛 TimeoutError（在白名单里 → 会重试）
        ③ 429 优先读 Retry-After 头（服务端告诉你等多久，比盲目退避更礼貌）
    """
    t0 = time.perf_counter()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是简洁的技术助手，只输出 JSON：{\"answer\": str, \"confidence\": float}"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }
    try:
        resp = await asyncio.wait_for(
            client.post(f"{base_url}/v1/chat/completions",
                        json=payload,
                        headers={"Authorization": f"Bearer {api_key}"}),
            timeout=timeout,
        )
    except TimeoutError:
        # 📌 超时和"连不上"是两回事：超时说明请求可能已经在服务端执行了
        #    （阶段 3 的幂等设计就是为了解决这个"不知道成没成功"的问题）
        raise

    if resp.status_code == 429:
        raise RateLimited(f"429 限流（Retry-After={resp.headers.get('Retry-After', '?')}）")
    if resp.status_code >= 500:
        raise UpstreamError(f"{resp.status_code} 上游错误")
    if resp.status_code >= 400:
        raise BadRequest(f"{resp.status_code} 请求有误: {resp.text[:200]}")

    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return {
        "text": text,
        "finish_reason": data["choices"][0].get("finish_reason"),
        "usage": usage,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
        "model": model,
    }


def calc_cost(model: str, in_tok: int, out_tok: int) -> float:
    """按价格表算钱（元）。"""
    pin, pout = PRICE.get(model, (1.0, 2.0))
    return in_tok / 1_000_000 * pin + out_tok / 1_000_000 * pout


# ═════════════════════════════════════════════════════════════
# 解析（脏 JSON 容错 —— 阶段 1 模块 03 的雏形）
# ═════════════════════════════════════════════════════════════
def parse_loose(text: str) -> tuple[dict[str, Any] | None, str]:
    """从可能很脏的输出里抠 JSON。返回 (dict 或 None, 状态标记)。

    mock 服务会故意返回三种脏输出：被截断 / 带 ```json 围栏 / 前后有解释文字。
    这里用最小代价处理它们；阶段 1 模块 03 会扩展成 7 层降级的完整解析器。
    """
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
        s = s.strip()
    try:
        return json.loads(s), "clean"
    except json.JSONDecodeError:
        pass
    # 抠出第一个 { 到最后一个 } 之间的内容（处理"前后有解释文字"）
    i, j = s.find("{"), s.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(s[i : j + 1]), "extracted"
        except json.JSONDecodeError:
            pass
    return None, "unparseable"


# ═════════════════════════════════════════════════════════════
# 主流程
# ═════════════════════════════════════════════════════════════
class Runner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.done_ids: set[str] = set()
        self.ok = self.fail = self.skipped = 0
        self.in_tok = self.out_tok = 0
        self.cost = 0.0
        self.parse_stats: dict[str, int] = {}
        self._lock = asyncio.Lock()          # ★ 保护共享计数器和文件写入
        self._stop = False

    # ── 断点续跑：读已有结果，收集已完成的 id ──
    def load_done(self) -> None:
        out = Path(self.args.out)
        if out.exists() and self.args.resume:
            with out.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self.done_ids.add(json.loads(line)["id"])
                    except (json.JSONDecodeError, KeyError):
                        continue       # 半截行（上次 Ctrl+C 时写坏的）直接跳过
            print(f"▶ 断点续跑：已完成 {len(self.done_ids)} 条，将跳过")

    # ── 单条任务 ──
    async def one(self, client: httpx.AsyncClient, sem: asyncio.Semaphore,
                  rec: dict[str, Any], fh) -> None:
        async with sem:                              # 限流：拿到令牌才发请求
            if self._stop:
                return
            try:
                result = await call_once(client, self.args.base_url, self.args.api_key,
                                         self.args.model, rec["prompt"], self.args.timeout)
            except BadRequest as e:                  # 不重试的错误
                await self._write(fh, {"id": rec["id"], "ok": False, "error": str(e),
                                       "error_type": "BadRequest", "prompt": rec["prompt"]},
                                  failed=True)
                return
            except Exception as e:                   # 重试用尽
                await self._write(fh, {"id": rec["id"], "ok": False, "error": str(e),
                                       "error_type": type(e).__name__, "prompt": rec["prompt"]},
                                  failed=True)
                return

            parsed, status = parse_loose(result["text"])
            u = result["usage"]
            cost = calc_cost(result["model"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
            await self._write(fh, {
                "id": rec["id"], "ok": True, "prompt": rec["prompt"],
                "answer": parsed.get("answer") if parsed else None,
                "raw_text": result["text"] if parsed is None else None,   # 只在解析失败时存原文
                "parse_status": status,
                "finish_reason": result["finish_reason"],
                "usage": u, "latency_ms": result["latency_ms"], "cost": round(cost, 6),
            })

    async def _write(self, fh, rec: dict[str, Any], *, failed: bool = False) -> None:
        """加锁写一行并 flush。

        📌 为什么每条都 flush？
            如果攒到最后一次性写，中途崩了（Ctrl+C / OOM / 断网）就全丢了。
            批量任务跑几小时，这种"白干"是最让人崩溃的事。
            flush 的代价是每条多一次系统调用，对 IO 密集型任务完全可以接受。

        📌 为什么要加锁？
            asyncio 是单线程的，但 await 会让出控制权。多个协程同时执行到
            `self.ok += 1` 和 `fh.write()` 之间时，虽然不会真的数据竞争（GIL + 单线程），
            但"计数 + 写入"这两步之间如果被切走，进度打印就可能与实际不符。
            加锁保证这两步是原子的 —— 这是好习惯，换到多线程就是必需的。
        """
        async with self._lock:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            if failed:
                self.fail += 1
                with Path(self.args.failed_out).open("a", encoding="utf-8") as ff:
                    ff.write(json.dumps(rec, ensure_ascii=False) + "\n")
            else:
                self.ok += 1
                u = rec.get("usage", {})
                self.in_tok += u.get("prompt_tokens", 0)
                self.out_tok += u.get("completion_tokens", 0)
                self.cost += rec.get("cost", 0.0)
                st = rec.get("parse_status", "clean")
                self.parse_stats[st] = self.parse_stats.get(st, 0) + 1

            total_done = self.ok + self.fail
            if total_done % self.args.report_every == 0 or total_done == self.args.total:
                print(f"  进度 {total_done}/{self.args.total}  成功 {self.ok}  失败 {self.fail}"
                      f"  累计成本 ¥{self.cost:.4f}")

    # ── 主入口 ──
    async def run(self) -> int:
        records = []
        with Path(self.args.input).open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    records.append(json.loads(line))
        self.load_done()
        todo = [r for r in records if r["id"] not in self.done_ids]
        self.skipped = len(records) - len(todo)
        self.args.total = len(todo)

        if not todo:
            print("✅ 全部已完成，无事可做")
            return 0

        print(f"▶ 待处理 {len(todo)} 条（跳过 {self.skipped} 条已完成）"
              f"  并发 {self.args.concurrency}  模型 {self.args.model}")

        sem = asyncio.Semaphore(self.args.concurrency)
        Path(self.args.out).parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if self.args.resume else "w"
        if not self.args.resume and Path(self.args.failed_out).exists():
            Path(self.args.failed_out).unlink()

        t0 = time.perf_counter()
        limits = httpx.Limits(max_connections=self.args.concurrency * 2,
                              max_keepalive_connections=self.args.concurrency)
        # 📌 踩坑记录：我一开始写成
        #      async with httpx.AsyncClient(...) as client, Path(...).open(...) as fh:
        #    结果报 TypeError: '_io.TextIOWrapper' object does not support the
        #    asynchronous context manager protocol
        #    原因：async with 要求对象实现 __aenter__/__aexit__，而普通文件对象只有
        #    __enter__/__exit__。**两种上下文管理器不能混在同一个 async with 里**，
        #    要么嵌套写，要么用 contextlib.ExitStack。
        async with httpx.AsyncClient(timeout=None, limits=limits) as client:
          # 📌 timeout=None：超时由 call_once 里的 asyncio.wait_for 控制。
          #    两处都设会导致"到底谁生效"的困惑 —— 只留一处。
          with Path(self.args.out).open(mode, encoding="utf-8") as fh:
            tasks = [asyncio.create_task(self.one(client, sem, r, fh)) for r in todo]

            # Ctrl+C 优雅退出：取消所有任务，已写入的结果不丢
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, self._on_signal, tasks)
                except NotImplementedError:
                    pass        # Windows 不支持 add_signal_handler

            await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.perf_counter() - t0
        self._print_summary(elapsed, todo)
        return 0

    def _on_signal(self, tasks: list[asyncio.Task]) -> None:
        print("\n⚠️  收到中断信号，取消未完成任务（已写入磁盘的结果不会丢）...")
        self._stop = True
        for t in tasks:
            if not t.done():
                t.cancel()

    def _print_summary(self, elapsed: float, todo: list[dict]) -> None:
        print("\n" + "═" * 66)
        print(f"完成：成功 {self.ok}，失败 {self.fail}，跳过 {self.skipped}")
        print(f"总 Token {self.in_tok + self.out_tok:,}（输入 {self.in_tok:,} / 输出 {self.out_tok:,}）")
        print(f"预估成本 ¥{self.cost:.4f}，耗时 {elapsed:.1f}s，"
              f"平均 {elapsed / max(len(todo), 1):.2f}s/条，吞吐 {len(todo) / max(elapsed, 0.01):.1f} 条/s")
        if RETRY_STATS:
            print(f"重试统计（共 {sum(RETRY_STATS.values())} 次）：{dict(RETRY_STATS.most_common())}")
            print("  → 想逐条看每次重试，用 VERBOSE_RETRY=1 python batch_call.py ...")
        if self.parse_stats:
            print(f"输出解析情况：{self.parse_stats}")
            bad = self.parse_stats.get("unparseable", 0)
            if bad:
                print(f"  ⚠️ {bad} 条完全解析失败，原文已存在结果文件的 raw_text 字段里")
        if self.fail:
            print(f"失败项已写入 {self.args.failed_out}，可以直接把它当 --in 重跑：")
            print(f"  python batch_call.py --in {self.args.failed_out} --out data/retry.jsonl")

        # 换算成生产视角的数字（这是面试要讲的"成本意识"）
        if self.ok:
            per = self.cost / self.ok
            print(f"\n单条成本 ¥{per:.6f} → 10 万条约 ¥{per * 100_000:,.0f}，"
                  f"100 万条约 ¥{per * 1_000_000:,.0f}")
        print("═" * 66)


def main() -> int:
    p = argparse.ArgumentParser(description="异步 LLM 批量调用器（Demo 02-5）")
    p.add_argument("--in", dest="input", default=str(HERE / "data/prompts.jsonl"))
    p.add_argument("--out", default=str(HERE / "data/results.jsonl"))
    p.add_argument("--failed-out", default=str(HERE / "data/results.failed.jsonl"))
    p.add_argument("--concurrency", type=int, default=5)
    p.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8898"))
    p.add_argument("--api-key", default=os.environ.get("LLM_API_KEY", "mock-key"))
    p.add_argument("--model", default="mock-llm")
    p.add_argument("--timeout", type=float, default=5.0, help="单次请求超时（秒）")
    p.add_argument("--resume", action="store_true", help="断点续跑：跳过 out 文件里已有的 id")
    p.add_argument("--report-every", type=int, default=20)
    args = p.parse_args()

    if not Path(args.input).is_file():
        print(f"❌ 输入文件不存在: {args.input}\n   先运行: python make_prompts.py", file=sys.stderr)
        return 1

    return asyncio.run(Runner(args).run())


if __name__ == "__main__":
    sys.exit(main())
