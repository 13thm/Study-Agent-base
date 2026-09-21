#!/usr/bin/env python3
"""装饰器三连的演示与验证 —— 对应任务书的"跑起来应该长这样"。

跑法：python demo_decorators.py       （7 个场景，含 3 个必须验证的现象）
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time

from decorators import log_calls, retry, timer, timer_no_wraps

# 📌 stream=sys.stdout：logging 默认写 stderr，而 print 写 stdout。
#    管道重定向时 stdout 是块缓冲、stderr 是无缓冲，两者会乱序（日志跑到最前面）。
#    统一到 stdout 就能保证输出顺序与代码执行顺序一致。
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", stream=sys.stdout)

# 用一个全局计数器模拟"前两次失败、第三次成功"的下游
_call_count = {"n": 0}


# ═════════════════════════════════════════════════════════════
# 场景 1：@timer 同时装饰同步与异步函数
# ═════════════════════════════════════════════════════════════
@timer
def slow_sync() -> str:
    time.sleep(1.0)
    return "sync done"


@timer
async def slow_async() -> str:
    await asyncio.sleep(0.5)
    return "async done"


# ═════════════════════════════════════════════════════════════
# 场景 2：@retry 只重试白名单异常
# ═════════════════════════════════════════════════════════════
class FakeNetworkError(Exception):
    """模拟网络抖动（应该被重试）。"""


@retry(times=3, delay=0.2, backoff=2, exceptions=(FakeNetworkError, TimeoutError))
async def flaky_llm_call() -> str:
    _call_count["n"] += 1
    if _call_count["n"] < 3:
        raise FakeNetworkError("模拟网络错误")
    return "第 3 次成功 ✅"


@retry(times=3, delay=0.1, exceptions=(FakeNetworkError,))
def bad_math() -> float:
    """抛的是 ZeroDivisionError，不在白名单里 → 必须直接往外抛，一次都不重试。"""
    _call_count["zero"] = _call_count.get("zero", 0) + 1  # type: ignore[typeddict-item]
    return 1 / 0


# ═════════════════════════════════════════════════════════════
# 场景 3：@log_calls 记录入参与返回
# ═════════════════════════════════════════════════════════════
@log_calls(level="INFO", max_len=60)
async def call_llm(model: str, prompt: str) -> str:
    await asyncio.sleep(0.05)
    return "这是一个模拟的模型回复" * 8      # 故意返回长文本，看截断效果


# ═════════════════════════════════════════════════════════════
# 场景 4：装饰器叠加顺序（★ 必须验证的现象之一）
# ═════════════════════════════════════════════════════════════
def deco_a(func):
    def wrapper(*a, **kw):
        print("  A 进入（前）")
        r = func(*a, **kw)
        print("  A 退出（后）")
        return r
    return wrapper


def deco_b(func):
    def wrapper(*a, **kw):
        print("  B 进入（前）")
        r = func(*a, **kw)
        print("  B 退出（后）")
        return r
    return wrapper


@deco_a          # 外层
@deco_b          # 内层（更靠近函数）
def stacked() -> None:
    print("  → 原函数执行")


# ═════════════════════════════════════════════════════════════
# 场景 5：functools.wraps 的作用（★ 必须验证的现象之二）
# ═════════════════════════════════════════════════════════════
@timer                 # 有 wraps
async def with_wraps() -> None:
    """我是 docstring。"""


@timer_no_wraps        # 没有 wraps
async def without_wraps() -> None:
    """我是 docstring。"""


async def main() -> int:
    print("=" * 68)
    print("场景 1 · @timer 同时支持同步与异步")
    print("=" * 68)
    slow_sync()
    await slow_async()

    print("\n" + "=" * 68)
    print("场景 2 · @retry 指数退避 + 异常白名单")
    print("=" * 68)
    _call_count["n"] = 0
    print(await flaky_llm_call())
    print(f"  实际调用次数 = {_call_count['n']}（前 2 次失败，第 3 次成功）")

    print("\n  ▼ 白名单外的异常（ZeroDivisionError）：")
    t0 = time.perf_counter()
    try:
        bad_math()
    except ZeroDivisionError as e:
        print(f"  直接抛出，未重试 ✅  异常={type(e).__name__}  "
              f"调用次数={_call_count.get('zero')}  耗时={time.perf_counter() - t0:.3f}s")
        print("  → 如果它被重试了 3 次，耗时会 >= 0.3s（0.1+0.2 退避）")

    print("\n" + "=" * 68)
    print("场景 3 · @log_calls 审计日志（注意长返回值被截断）")
    print("=" * 68)
    await call_llm(model="deepseek-chat", prompt="用一句话解释 RAG")

    print("\n" + "=" * 68)
    print("场景 4 · 装饰器叠加顺序（★ 必须验证）")
    print("=" * 68)
    print("  代码写法：@deco_a 在上，@deco_b 在下（更靠近函数）")
    stacked()
    print("  结论：**由外向内包装，由内向外执行** —— 等价于 deco_a(deco_b(stacked))，")
    print("        所以 A 先进入、B 后进入；返回时 B 先退出、A 后退出（洋葱模型）")

    print("\n" + "=" * 68)
    print("场景 5 · functools.wraps 的作用（★ 必须验证）")
    print("=" * 68)
    print(f"  有 wraps : __name__={with_wraps.__name__!r}  __doc__={with_wraps.__doc__!r}")
    print(f"  无 wraps : __name__={without_wraps.__name__!r}  __doc__={without_wraps.__doc__!r}")
    print("  → 不加 wraps 会丢函数元信息，后果：")
    print("     ① 日志/追踪里全叫 'wrapper'，分不清是哪个函数")
    print("     ② inspect.signature() 拿不到真实签名 → FastAPI/Pydantic 的参数推导直接崩")
    print("     ③ pytest 收集测试函数时按 __name__ 匹配 test_*，会漏测")
    print(f"  额外能力：wraps 还会设置 __wrapped__，可用 inspect.unwrap() 拿回原函数："
          f"{getattr(with_wraps, '__wrapped__', None) is not None}")

    print("\n" + "=" * 68)
    print("场景 6 · 装饰 async 函数时，普通装饰器的灾难（★ 必须验证）")
    print("=" * 68)

    def naive_timer(func):
        """错误示范：不区分 sync/async 的装饰器。"""
        def wrapper(*a, **kw):
            t0 = time.perf_counter()
            result = func(*a, **kw)          # ← 拿到协程对象，函数根本没执行！
            print(f"  [naive] 耗时 {time.perf_counter() - t0:.6f}s   ← 接近 0，假的")
            return result
        return wrapper

    @naive_timer
    async def work() -> str:
        await asyncio.sleep(0.3)
        return "done"

    coro = work()
    print(f"  返回值类型 = {type(coro).__name__}  ← 不是 str，是协程对象")
    print(f"  await 之后 = {await coro!r}")
    print("  → 结论：装饰 async 函数必须用 async wrapper 并 await 原函数，")
    print("    否则①计时是假的 ②函数可能永远不执行（RuntimeWarning: coroutine was never awaited）")

    print("\n" + "=" * 68)
    print("场景 7 · 白板题：手写一个支持 async 的带参 @retry（参考答案在 decorators.py）")
    print("=" * 68)
    print("""
  def retry(times=3, delay=1.0, exceptions=(Exception,)):     # ① 装饰器工厂
      def decorator(func):                                    # ② 装饰器
          @functools.wraps(func)                              # ③ 保留元信息
          async def wrapper(*a, **kw):                        # ④ async wrapper
              last = None
              for i in range(1, times + 1):
                  try:
                      return await func(*a, **kw)             # ⑤ 必须 await
                  except exceptions as e:                     # ⑥ 只捕白名单
                      last = e
                      if i < times:
                          await asyncio.sleep(delay * 2 ** (i - 1))   # ⑦ 指数退避
              raise last                                      # ⑧ 重试用尽抛最后一次异常
          return wrapper
      return decorator
  记忆口诀：三层嵌套 + wraps + iscoroutinefunction 判断 + 白名单 + 指数退避 + 抛最后一次异常
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
