"""三个 Agent 开发里会反复用到的装饰器 —— Demo 02-1。

📌 为什么这三个？
────────────────────────────────────────────────────────────
    @timer      → 定位 Agent 哪一步最慢（阶段 3 的 RuntimeProfiler 的雏形）
    @retry      → LLM API 的 429 / 超时（阶段 1 模块 01 的多模型客户端靠它）
    @log_calls  → 工具调用审计日志（阶段 5 模块 03 的审计能力靠它）

本文件覆盖的知识点：
    · 闭包与 nonlocal
    · functools.wraps（不加会怎样，代码里有实验）
    · 带参数的装饰器 = 三层嵌套（ decorator_factory → decorator → wrapper ）
    · 同时支持同步和异步函数（inspect.iscoroutinefunction）
    · 多装饰器叠加的执行顺序
────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

log = logging.getLogger("decorators")


# ═════════════════════════════════════════════════════════════
# ① @timer —— 计时（同时支持 sync / async）
# ═════════════════════════════════════════════════════════════
def timer(func: F) -> F:
    """打印函数耗时。

    📌 教学点：为什么必须区分 sync 和 async？
        如果你写一个普通装饰器去装饰 async 函数：
            @functools.wraps(func)
            def wrapper(*a, **kw):
                t0 = time.perf_counter()
                result = func(*a, **kw)      # ← 这里拿到的是【协程对象】，不是结果！
                print(time.perf_counter() - t0)   # ← 打印出来接近 0
                return result
        因为调用 async 函数只会创建协程对象，**不 await 就完全不执行**。
        计时会显示 0.000s，而且更糟：返回的协程可能永远不会被 await（RuntimeWarning）。

        正确做法：用 inspect.iscoroutinefunction 判断，分别返回同步/异步的 wrapper。
    """
    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)                      # ★ 保留 __name__ / __doc__ / __wrapped__
        async def awrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                # 📌 放 finally：即使函数抛异常也要打印耗时（异常路径的耗时往往最有价值）
                print(f"[timer] {func.__qualname__} 耗时 {time.perf_counter() - t0:.3f}s")

        return awrapper  # type: ignore[return-value]

    @functools.wraps(func)
    def swrapper(*args: Any, **kwargs: Any) -> Any:
        t0 = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            print(f"[timer] {func.__qualname__} 耗时 {time.perf_counter() - t0:.3f}s")

    return swrapper  # type: ignore[return-value]


# ═════════════════════════════════════════════════════════════
# ② @retry(...) —— 指数退避重试（带参数的装饰器 = 三层嵌套）
# ═════════════════════════════════════════════════════════════
def retry(
    times: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    jitter: bool = True,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    on_retry: Callable[[str, int, BaseException, float], None] | None = None,
) -> Callable[[F], F]:
    """指数退避重试。

    Args:
        times: 最多尝试几次（含第一次）。times=3 表示"1 次正常 + 2 次重试"。
        delay: 首次退避秒数。
        backoff: 退避倍数。delay=1, backoff=2 → 等待 1s, 2s, 4s...
        jitter: 是否加随机抖动。**生产必须开** —— 否则一批请求同时失败会同时重试，
                把刚恢复的下游再次打死（这叫"重试风暴"/thundering herd）。
        exceptions: 只重试这些异常类型。
        on_retry: 重试回调 (函数名, 第几次, 异常, 等待秒数)。默认打印到 stdout。
                  📌 为什么要留这个口子？批量跑 200 条时，每条失败都 print 会刷屏，
                     你根本看不到进度。生产做法是**收集起来最后汇总**
                     （"共重试 47 次，其中 429 占 38 次"），而不是逐条打印。

    📌 教学点：三层嵌套的结构
        retry(...)          ← 装饰器工厂：接收配置，返回真正的装饰器
          └─ decorator      ← 装饰器：接收函数，返回 wrapper
               └─ wrapper   ← 包装函数：接收调用参数

        记法：**@retry(times=3) 等价于 func = retry(times=3)(func)**，两次调用。

    📌 教学点：exceptions 白名单是生产级重试的灵魂
        阶段 3 模块 03 的规则：只重试瞬时错误（网络超时、429、5xx），
        **绝不重试 400 参数错、401/403 鉴权错、业务逻辑错** ——
        重试它们只是浪费钱和时间，结果一定还是一样。
        Demo 01-4 的 --retry 2 对照实验已经证明过这件事。
    """

    def decorator(func: F) -> F:
        async def aretry_once(args: tuple, kwargs: dict, attempt: int) -> Any:
            return await func(*args, **kwargs)

        def _notify(name: str, attempt: int, exc: BaseException, wait: float) -> None:
            if on_retry is not None:
                on_retry(name, attempt, exc, wait)
            else:
                print(f"[retry] {name} 第 {attempt}/{times} 次失败："
                      f"{type(exc).__name__}: {exc}，等待 {wait:.2f}s 后重试")

        def _sleep_seconds(attempt: int) -> float:
            """第 attempt 次失败后该等多久（attempt 从 1 开始）。"""
            base = delay * (backoff ** (attempt - 1))
            if jitter:
                # 全抖动（full jitter）：在 [0.5*base, 1.5*base] 之间随机
                return base * (0.5 + random.random())
            return base

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def awrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: BaseException | None = None
                for attempt in range(1, times + 1):
                    try:
                        return await aretry_once(args, kwargs, attempt)
                    except exceptions as e:                 # ← 只捕获白名单里的
                        last_exc = e
                        if attempt >= times:
                            break
                        wait = _sleep_seconds(attempt)
                        _notify(func.__qualname__, attempt, e, wait)
                        await asyncio.sleep(wait)           # ★ 异步版必须 await asyncio.sleep
                raise last_exc  # type: ignore[misc]
            return awrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def swrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt >= times:
                        break
                    wait = _sleep_seconds(attempt)
                    _notify(func.__qualname__, attempt, e, wait)
                    time.sleep(wait)
            raise last_exc  # type: ignore[misc]

        return swrapper  # type: ignore[return-value]

    return decorator


# ═════════════════════════════════════════════════════════════
# ③ @log_calls(...) —— 入参/返回/耗时/异常 全记录
# ═════════════════════════════════════════════════════════════
def log_calls(level: str = "INFO", log_result: bool = True, max_len: int = 200) -> Callable[[F], F]:
    """记录函数调用（工具调用审计日志的原型）。

    Args:
        level: 日志级别名。
        log_result: 是否记录返回值（返回值可能很大或含敏感信息，要能关）。
        max_len: 值转字符串后的截断长度。**不截断的话一条日志可能几 MB**。

    📌 教学点：为什么审计日志要截断 + 脱敏？
        阶段 5 模块 02 的日志规范里有两条硬要求：
        ① 超长内容只记 size + sha256 前 8 位
        ② 敏感字段（api_key / Authorization / 手机号）自动替换成 [REDACTED]
        这里先实现①，②在模块 06 的 demo-02 里配合 FastAPI 中间件一起做。
    """
    lvl = getattr(logging, level.upper(), logging.INFO)

    def _short(v: Any) -> str:
        s = repr(v)
        return s if len(s) <= max_len else f"{s[:max_len]}...(共 {len(s)} 字符)"

    def decorator(func: F) -> F:
        def _fmt_args(args: tuple, kwargs: dict) -> str:
            parts = [_short(a) for a in args] + [f"{k}={_short(v)}" for k, v in kwargs.items()]
            return ", ".join(parts)

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def awrapper(*args: Any, **kwargs: Any) -> Any:
                argstr = _fmt_args(args, kwargs)
                log.log(lvl, "→ %s(%s)", func.__qualname__, argstr)
                t0 = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                except Exception as e:
                    log.log(lvl, "✗ %s 抛异常 %s: %s（耗时 %.3fs）",
                            func.__qualname__, type(e).__name__, e, time.perf_counter() - t0)
                    raise                       # ★ 记录完必须重新抛出，不能吞
                else:
                    log.log(lvl, "← %s 返回 %s（耗时 %.3fs）", func.__qualname__,
                            _short(result) if log_result else "<省略>", time.perf_counter() - t0)
                    return result
            return awrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def swrapper(*args: Any, **kwargs: Any) -> Any:
            argstr = _fmt_args(args, kwargs)
            log.log(lvl, "→ %s(%s)", func.__qualname__, argstr)
            t0 = time.perf_counter()
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                log.log(lvl, "✗ %s 抛异常 %s: %s（耗时 %.3fs）",
                        func.__qualname__, type(e).__name__, e, time.perf_counter() - t0)
                raise
            else:
                log.log(lvl, "← %s 返回 %s（耗时 %.3fs）", func.__qualname__,
                        _short(result) if log_result else "<省略>", time.perf_counter() - t0)
                return result
        return swrapper  # type: ignore[return-value]

    return decorator


# ═════════════════════════════════════════════════════════════
# 附：一个"不加 wraps"的对照装饰器（用于演示差异，不要在生产用）
# ═════════════════════════════════════════════════════════════
def timer_no_wraps(func: Callable) -> Callable:
    """故意不写 @functools.wraps 的版本，用来演示后果。"""
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        return await func(*args, **kwargs)
    return wrapper
