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

# ── 标准库 ─────────────────────────────────────────────
import argparse                          # 命令行参数解析
import asyncio                           # 异步运行时（事件循环、Task、Semaphore）
import json                              # 读写 JSONL、构造请求体
import os                                # 读环境变量
import signal                            # 处理 Ctrl+C / SIGTERM
import sys                               # sys.path、sys.exit
import time                              # perf_counter 计时
from collections import Counter          # 重试统计
from pathlib import Path                 # 路径操作
from typing import Any                   # 类型标注

import httpx                             # 异步 HTTP 客户端（支持 HTTP/2、连接池）

# ── 复用 Demo 02-1 的装饰器 ────────────────────────────────────
# 📌 这里用 sys.path 插入兄弟目录，是"教学仓库"的权宜做法。
#    真实项目应该做成可安装的包（阶段 1 的 prompt-toolbox 就是 pip install -e 进来用的）。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "demo-01-decorators"))

# noqa: E402 —— ruff 的告警码，意思是"允许 import 出现在非文件顶部"
# 因为要先改 sys.path 才能 import，所以这个 import 必须放在中间
from decorators import retry  # noqa: E402

HERE = Path(__file__).parent

# ── 价格表（元 / 百万 token）──────────────────────────────────
# 📌 绝不硬编码在逻辑里，抽成常量（阶段 1 会挪进 YAML 配置）
# 键是模型名，值是 (输入单价, 输出单价)，单位：元 / 百万 token
PRICE = {"mock-llm": (1.0, 2.0), "deepseek-chat": (1.0, 2.0), "gpt-4o-mini": (0.15, 0.6)}


# ── 自定义异常：区分"该重试"和"不该重试" ──────────────────
# 这是重试机制设计的核心：不是所有错误都值得重试
class RateLimited(Exception):
    """429 —— 应该重试。"""
    pass


class UpstreamError(Exception):
    """5xx —— 应该重试。"""
    pass


class BadRequest(Exception):
    """400 —— ★ 绝不重试（重试只是浪费钱，结果一定一样）。"""
    pass


# ═════════════════════════════════════════════════════════════
# 单次调用（含重试与超时）
# ═════════════════════════════════════════════════════════════

#: 重试统计（用回调收集，不逐条打印 —— 见 decorators.retry 的 on_retry 说明）
# Counter 是"计数器"：统计每种异常各重试了多少次
RETRY_STATS: Counter[str] = Counter()


def _on_retry(name: str, attempt: int, exc: BaseException, wait: float) -> None:
    """重试回调：每次重试触发一次。

    为什么不在 retry 装饰器里直接 print？
      因为每条都打印会让日志爆炸（几百条并发，重试可能上千次）。
      这里默认只"计数"，想看细节才用 VERBOSE_RETRY 环境变量打开。

    参数：
      name    —— 被调用的函数名（这里是 "call_once"）
      attempt —— 第几次尝试失败（从 1 开始）
      exc     —— 触发的异常对象
      wait    —— 下次重试前会等多少秒（退避 + jitter 后的结果）
    """
    RETRY_STATS[type(exc).__name__] += 1
    if os.environ.get("VERBOSE_RETRY"):      # 想看细节时 VERBOSE_RETRY=1 python batch_call.py
        print(f"  [retry] {name} 第{attempt}次失败 {type(exc).__name__}: {exc}，等 {wait:.2f}s")


# ★ 装饰器顺序很重要：@retry 在外，async 在内
#   @retry 装饰的是一个 async 函数，所以它必须支持 await（Demo 02-1 应该已经处理了）
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
    t0 = time.perf_counter()    # 高精度计时器（比 time.time 更适合测耗时）

    # ── 构造请求体（OpenAI Chat Completions 格式）────────────
    payload = {
        "model": model,
        "messages": [
            # system：告诉模型它的角色和输出格式
            # 这里强调"只输出 JSON"，是为了减少 markdown 围栏和解释文字
            {"role": "system", "content": "你是简洁的技术助手，只输出 JSON：{\"answer\": str, \"confidence\": float}"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,   # 0 = 尽量确定性输出，批量评测时不希望有随机性
    }

    try:
        # ★ asyncio.wait_for 给整个请求加"硬超时"
        #   注意：超时会取消底层请求，但服务端可能已经在执行了
        #   这就是为什么"超时"和"连不上"是两回事（见下面 except）
        resp = await asyncio.wait_for(
            client.post(f"{base_url}/v1/chat/completions",
                        json=payload,
                        headers={"Authorization": f"Bearer {api_key}"}),
            timeout=timeout,
        )
    except TimeoutError:
        # 📌 超时和"连不上"是两回事：超时说明请求可能已经在服务端执行了
        #    （阶段 3 的幂等设计就是为了解决这个"不知道成没成功"的问题）
        # 这里只是"原样抛出"，让 @retry 决定要不要重试
        raise

    # ── 按 HTTP 状态码分流：区分"该重试"和"不该重试" ────
    if resp.status_code == 429:
        # 429 Too Many Requests：限流，应该重试
        # Retry-After 是服务端建议的等待秒数（有就参考，没有就退避）
        raise RateLimited(f"429 限流（Retry-After={resp.headers.get('Retry-After', '?')}）")
    if resp.status_code >= 500:
        # 5xx：上游错误（服务端挂了/超时），应该重试
        raise UpstreamError(f"{resp.status_code} 上游错误")
    if resp.status_code >= 400:
        # 4xx（除 429）：参数错、鉴权错等，重试也没用，直接抛不重试的异常
        raise BadRequest(f"{resp.status_code} 请求有误: {resp.text[:200]}")

    # ── 解析响应 ──────────────────────────────────────────
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})

    return {
        "text": text,
        "finish_reason": data["choices"][0].get("finish_reason"),  # stop / length / ...
        "usage": usage,                                             # {prompt_tokens, completion_tokens, ...}
        "latency_ms": int((time.perf_counter() - t0) * 1000),       # 转成整数毫秒
        "model": model,
    }


def calc_cost(model: str, in_tok: int, out_tok: int) -> float:
    """按价格表算钱（元）。

    单价是按"每百万 token"给的，所以要除以 1_000_000。
    PRICE.get(model, (1.0, 2.0)) 的第二个参数是"未知模型的默认价"，
    防止新模型上线时 KeyError 崩掉整个批量任务。
    """
    pin, pout = PRICE.get(model, (1.0, 2.0))
    return in_tok / 1_000_000 * pin + out_tok / 1_000_000 * pout


# ═════════════════════════════════════════════════════════════
# 解析（脏 JSON 容错 —— 阶段 1 模块 03 的雏形）
# ═════════════════════════════════════════════════════════════
def parse_loose(text: str) -> tuple[dict[str, Any] | None, str]:
    """从可能很脏的输出里抠 JSON。返回 (dict 或 None, 状态标记)。

    mock 服务会故意返回三种脏输出：被截断 / 带 ```json 围栏 / 前后有解释文字。
    这里用最小代价处理它们；阶段 1 模块 03 会扩展成 7 层降级的完整解析器。

    返回的"状态标记"有三种：
      "clean"        —— 干净，直接 json.loads 成功
      "extracted"    —— 从文字里抠出了 JSON（前后有噪音）
      "unparseable"  —— 完全解析不出
    """
    s = text.strip()

    # ── 处理 markdown 围栏 ─────────────────────────────────
    # 形如：
    #   ```json
    #   {"answer": "..."}
    #   ```
    if s.startswith("```"):
        s = s.strip("`")                 # 去首尾的所有反引号
        if s.lower().startswith("json"): # 可能带 "json" 标记（大小写都可能有）
            s = s[4:]                    # 去掉这 4 个字符
        s = s.strip()                    # 再去一次空白

    # ── 第一次尝试：直接解析 ───────────────────────────────
    try:
        return json.loads(s), "clean"
    except json.JSONDecodeError:
        pass

    # ── 第二次尝试：抠出第一个 { 到最后一个 } 之间的内容 ──
    # 处理"前面有解释，后面有解释"的情况，例如：
    #   "好的，答案是：{"answer": "42"} 希望有帮助"
    i, j = s.find("{"), s.rfind("}")     # 第一个 { 和最后一个 }
    if i >= 0 and j > i:                 # 确保找到且位置合法
        try:
            return json.loads(s[i : j + 1]), "extracted"   # 切片是左闭右开，所以 j+1
        except json.JSONDecodeError:
            pass

    # ── 彻底失败 ───────────────────────────────────────────
    return None, "unparseable"


# ═════════════════════════════════════════════════════════════
# 主流程
# ═════════════════════════════════════════════════════════════
class Runner:
    """整个批量任务的协调者。

    为什么用类而不是一堆函数？
      因为要维护"跨任务的共享状态"（成功数、失败数、token 累计、锁……），
      类天然适合承载这些状态 + 行为。
    """

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.done_ids: set[str] = set()      # 断点续跑：已完成的 id 集合
        self.ok = self.fail = self.skipped = 0
        self.in_tok = self.out_tok = 0
        self.cost = 0.0
        self.parse_stats: dict[str, int] = {}
        # ★ 一把异步锁，保护"更新计数器 + 写文件"这两步的原子性
        #   详见 _write 的 docstring
        self._lock = asyncio.Lock()
        self._stop = False                    # 收到 Ctrl+C 时置 True，阻止新任务

    # ── 断点续跑：读已有结果，收集已完成的 id ──
    def load_done(self) -> None:
        """把上次跑到一半的结果文件读一遍，收集已完成的 id。

        为什么叫"断点续跑"？
          批量任务跑几小时，中途可能因为各种原因中断（Ctrl+C、断网、OOM）。
          如果每次都从头跑，浪费大量 token 和时间。
          断点续跑 = "接着上次跑"，只处理没完成的。
        """
        out = Path(self.args.out)
        # 只有 --resume 且输出文件存在时才读
        if out.exists() and self.args.resume:
            with out.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        # 结果文件的每一行都是一个 JSON，从里面取 id
                        self.done_ids.add(json.loads(line)["id"])
                    except (json.JSONDecodeError, KeyError):
                        # ★ 半截行容错：上次 Ctrl+C 时可能写了一半
                        #   直接把这种行跳过，不影响整体
                        continue
            print(f"▶ 断点续跑：已完成 {len(self.done_ids)} 条，将跳过")

    # ── 单条任务 ──
    async def one(self, client: httpx.AsyncClient, sem: asyncio.Semaphore,
                  rec: dict[str, Any], fh) -> None:
        """处理一条 prompt：限流 + 调用 + 解析 + 写盘。

        这个函数会被 create_task 包装成 N 个协程，并发跑。
        """
        # ★ 信号量限流：同时最多 concurrency 个任务能走到这里
        #   async with sem 会"阻塞"（异步地）直到拿到令牌
        async with sem:
            if self._stop:
                # 收到 Ctrl+C 后，正在排队的任务直接退出
                return

            # ── 调用模型（含重试）─────────────────────────
            try:
                result = await call_once(client, self.args.base_url, self.args.api_key,
                                         self.args.model, rec["prompt"], self.args.timeout)
            except BadRequest as e:
                # ★ 400 类错误：不重试，直接记失败
                #   注意这里写 error_type 是为了后续统计"哪种错最多"
                await self._write(fh, {"id": rec["id"], "ok": False, "error": str(e),
                                       "error_type": "BadRequest", "prompt": rec["prompt"]},
                                  failed=True)
                return
            except Exception as e:
                # ★ 其他错误：重试用尽后仍失败
                #   用 type(e).__name__ 记录异常类型（RateLimited / TimeoutError / ...）
                await self._write(fh, {"id": rec["id"], "ok": False, "error": str(e),
                                       "error_type": type(e).__name__, "prompt": rec["prompt"]},
                                  failed=True)
                return

            # ── 解析输出 ──────────────────────────────────
            parsed, status = parse_loose(result["text"])
            u = result["usage"]
            cost = calc_cost(result["model"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))

            # ── 写盘 ──────────────────────────────────────
            await self._write(fh, {
                "id": rec["id"], "ok": True, "prompt": rec["prompt"],
                # 解析成功存 answer 字段；失败则 answer 为 None
                "answer": parsed.get("answer") if parsed else None,
                # ★ 只在解析失败时存原文
                #   为什么？因为原文可能很大，全存会导致结果文件膨胀
                #   解析成功的 text 意义不大（已经提取成 answer 了）
                "raw_text": result["text"] if parsed is None else None,
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
            # ── 写结果文件 ────────────────────────────────
            # ensure_ascii=False：中文直接输出，不转成 \uXXXX
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()    # ★ 立刻刷到磁盘，避免崩溃时丢数据

            if failed:
                # ── 失败分支 ──────────────────────────────
                self.fail += 1
                # 失败项单独存一个文件，方便重跑
                # 用 "a" 模式：追加，不清空
                with Path(self.args.failed_out).open("a", encoding="utf-8") as ff:
                    ff.write(json.dumps(rec, ensure_ascii=False) + "\n")
            else:
                # ── 成功分支：更新统计 ────────────────────
                self.ok += 1
                u = rec.get("usage", {})
                self.in_tok += u.get("prompt_tokens", 0)
                self.out_tok += u.get("completion_tokens", 0)
                self.cost += rec.get("cost", 0.0)
                # 统计解析状态（clean / extracted / unparseable）
                st = rec.get("parse_status", "clean")
                self.parse_stats[st] = self.parse_stats.get(st, 0) + 1

            # ── 定期打印进度 ──────────────────────────────
            total_done = self.ok + self.fail
            # 每 report_every 条打印一次，或者全部完成时打印
            # total 是"本次要处理的总数"（不含跳过的）
            if total_done % self.args.report_every == 0 or total_done == self.args.total:
                print(f"  进度 {total_done}/{self.args.total}  成功 {self.ok}  失败 {self.fail}"
                      f"  累计成本 ¥{self.cost:.4f}")

    # ── 主入口 ──
    async def run(self) -> int:
        """协调整个批量任务：读输入 → 建任务 → 并发跑 → 打印汇总。"""
        # ── 读输入 ────────────────────────────────────────
        records = []
        with Path(self.args.input).open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    records.append(json.loads(line))

        # ── 断点续跑：过滤已完成的 ────────────────────────
        self.load_done()
        todo = [r for r in records if r["id"] not in self.done_ids]
        self.skipped = len(records) - len(todo)
        self.args.total = len(todo)   # ★ 把总数塞进 args，方便 _write 里访问

        if not todo:
            print("✅ 全部已完成，无事可做")
            return 0

        print(f"▶ 待处理 {len(todo)} 条（跳过 {self.skipped} 条已完成）"
              f"  并发 {self.args.concurrency}  模型 {self.args.model}")

        # ── 准备并发环境 ──────────────────────────────────
        # 信号量：同时最多 concurrency 个任务进入关键区
        sem = asyncio.Semaphore(self.args.concurrency)

        # 确保输出目录存在（parents=True 会递归创建，exist_ok=True 已存在不报错）
        Path(self.args.out).parent.mkdir(parents=True, exist_ok=True)

        # resume 时用追加模式，否则覆盖
        mode = "a" if self.args.resume else "w"

        # 不是续跑的话，先删掉上次的失败文件（避免累积旧数据）
        if not self.args.resume and Path(self.args.failed_out).exists():
            Path(self.args.failed_out).unlink()

        t0 = time.perf_counter()

        # ★ 连接池配置：直接影响并发性能
        #   max_connections：总连接数上限（设成并发数的 2 倍，留点余量）
        #   max_keepalive_connections：保持长连接的数量（复用 TCP，避免每次握手）
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
            # ★ create_task 把协程包装成"任务"，交给事件循环调度
            #   注意：create_task 不会立刻执行，而是"注册"到循环
            #   所有任务会由 gather 一起等待
            tasks = [asyncio.create_task(self.one(client, sem, r, fh)) for r in todo]

            # ── 优雅退出：处理 Ctrl+C ────────────────────
            # 目标：收到中断时，取消未完成的任务，已写入磁盘的结果不丢
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, self._on_signal, tasks)
                except NotImplementedError:
                    # Windows 不支持 add_signal_handler，忽略即可
                    pass

            # ★ gather 等待所有任务完成
            #   return_exceptions=True：任务抛异常时不中断其他任务，
            #   而是把异常当"结果"返回（我们已经在 one 里处理了异常，这里是双保险）
            await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.perf_counter() - t0
        self._print_summary(elapsed, todo)
        return 0

    def _on_signal(self, tasks: list[asyncio.Task]) -> None:
        """信号处理器：收到 Ctrl+C / SIGTERM 时调用。

        注意：这是"信号回调"，在事件循环里执行，不能阻塞。
        所以这里只做"置标志 + 取消任务"，不做 I/O。
        """
        print("\n⚠️  收到中断信号，取消未完成任务（已写入磁盘的结果不会丢）...")
        self._stop = True
        for t in tasks:
            if not t.done():     # 已完成的不用取消
                t.cancel()

    def _print_summary(self, elapsed: float, todo: list[dict]) -> None:
        """打印最终汇总，包括成本、耗时、吞吐、重试统计。"""
        print("\n" + "═" * 66)
        print(f"完成：成功 {self.ok}，失败 {self.fail}，跳过 {self.skipped}")

        # :, 是千分位格式化，1234567 → 1,234,567
        print(f"总 Token {self.in_tok + self.out_tok:,}（输入 {self.in_tok:,} / 输出 {self.out_tok:,}）")

        # 吞吐用 max(..., 0.01) 兜底，避免除零（极端情况 elapsed 为 0）
        print(f"预估成本 ¥{self.cost:.4f}，耗时 {elapsed:.1f}s，"
              f"平均 {elapsed / max(len(todo), 1):.2f}s/条，吞吐 {len(todo) / max(elapsed, 0.01):.1f} 条/s")

        # ── 重试统计 ──────────────────────────────────────
        if RETRY_STATS:
            print(f"重试统计（共 {sum(RETRY_STATS.values())} 次）：{dict(RETRY_STATS.most_common())}")
            print("  → 想逐条看每次重试，用 VERBOSE_RETRY=1 python batch_call.py ...")

        # ── 解析统计 ──────────────────────────────────────
        if self.parse_stats:
            print(f"输出解析情况：{self.parse_stats}")
            bad = self.parse_stats.get("unparseable", 0)
            if bad:
                print(f"  ⚠️ {bad} 条完全解析失败，原文已存在结果文件的 raw_text 字段里")

        # ── 失败项重跑提示 ────────────────────────────────
        if self.fail:
            print(f"失败项已写入 {self.args.failed_out}，可以直接把它当 --in 重跑：")
            print(f"  python batch_call.py --in {self.args.failed_out} --out data/retry.jsonl")

        # 换算成生产视角的数字（这是面试要讲的"成本意识"）
        if self.ok:
            per = self.cost / self.ok
            # :,.0f 表示"千分位 + 零小数"
            print(f"\n单条成本 ¥{per:.6f} → 10 万条约 ¥{per * 100_000:,.0f}，"
                  f"100 万条约 ¥{per * 1_000_000:,.0f}")
        print("═" * 66)


def main() -> int:
    """解析命令行参数，跑 Runner，返回退出码。"""
    p = argparse.ArgumentParser(description="异步 LLM 批量调用器（Demo 02-5）")

    # --in 的 dest="input" 是因为 "in" 是 Python 关键字，不能做属性名
    # default 用 HERE 拼路径，让脚本在任意目录下都能跑
    p.add_argument("--in", dest="input", default=str(HERE / "data/prompts.jsonl"))
    p.add_argument("--out", default=str(HERE / "data/results.jsonl"))
    p.add_argument("--failed-out", default=str(HERE / "data/results.failed.jsonl"))

    # 并发数：控制同时有多少个请求在飞
    p.add_argument("--concurrency", type=int, default=5)

    # base_url 和 api_key 优先从环境变量读，方便切真实 API
    p.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8898"))
    p.add_argument("--api-key", default=os.environ.get("LLM_API_KEY", "mock-key"))
    p.add_argument("--model", default="mock-llm")

    # 单次请求超时（秒）：会被 asyncio.wait_for 用
    p.add_argument("--timeout", type=float, default=5.0, help="单次请求超时（秒）")

    # --resume 是"开关型"参数：出现就是 True，不出现就是 False
    # action="store_true" 就是"不用接值"的意思
    p.add_argument("--resume", action="store_true", help="断点续跑：跳过 out 文件里已有的 id")

    # 每处理多少条打印一次进度
    p.add_argument("--report-every", type=int, default=20)

    args = p.parse_args()

    # ── 输入文件校验（早失败，给出友好提示）─────────────
    if not Path(args.input).is_file():
        print(f"❌ 输入文件不存在: {args.input}\n   先运行: python make_prompts.py", file=sys.stderr)
        return 1

    # asyncio.run 负责创建事件循环、跑协程、关闭循环
    return asyncio.run(Runner(args).run())


if __name__ == "__main__":
    # sys.exit 把 main 的返回值当退出码
    # 0 = 成功，非 0 = 失败（UNIX 约定，方便 CI 判断）
    sys.exit(main())