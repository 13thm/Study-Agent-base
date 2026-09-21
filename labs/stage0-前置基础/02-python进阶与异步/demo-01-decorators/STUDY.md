## 装饰器 
哈哈哈，第一次看道Python里面的装饰器，其实就是在数据外部包裹了一次在这个包裹里面在执行一次。
```
        ┌─────────────────────────┐
        │  wrapper（壳）           │
        │  ┌───────────────────┐  │
调用 →  │  │ 计时开始           │  │
        │  │   ↓               │  │
        │  │  原 add(a, b)     │  │  ← 核心逻辑还在，没被改
        │  │   ↓               │  │
        │  │ 打印耗时           │  │
        │  └───────────────────┘  │
        └─────────────────────────┘
```
```python
import functools

def timer(func):
    @functools.wraps(func)          # 关键
    def swrapper(*args, **kwargs):
        ...
    return swrapper

@timer
def add(a, b):
    """两数相加"""
    return a + b

print(add.__name__)    # add        ✅ 名字对了
print(add.__doc__)     # 两数相加    ✅ 文档回来了
print(add.__module__)  # 原函数所在模块 ✅
```
⚠️这里写了优化的方法 分了同步和异步的情况：
```python
F = TypeVar("F", bound=Callable[..., Any])

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
```

## 衍生到了重试

retry 是一个装饰器工厂：接收配置返回装饰器，装饰器接收函数返回 wrapper。
wrapper 里循环尝试 times 次，只捕获 exceptions 白名单里的异常，失败后按指数退避 + 随机抖动等待再试，期间用 _notify 通知。
分 sync / async 两套，异步版用 await + asyncio.sleep，同步版用 time.sleep。
全部失败后把最后一次异常抛给调用方。

```python
def retry(
    times: int = 3,                                     # 最多尝试几次（含第一次）。times=3 表示 1 次正常 + 2 次重试
    delay: float = 1.0,                                 # 首次退避秒数（第一次失败后等多久）
    backoff: float = 2.0,                               # 退避倍数。delay=1, backoff=2 → 等 1s, 2s, 4s...
    jitter: bool = True,                                # 是否加随机抖动。生产必须开，否则一批请求同时重试会打垮下游（重试风暴）
    exceptions: tuple[type[BaseException], ...] = (Exception,),  # 只重试这些异常类型，其他异常直接抛出
    on_retry: Callable[[str, int, BaseException, float], None] | None = None,  # 重试回调（函数名, 第几次, 异常, 等待秒数）；None 则默认 print
) -> Callable[[F], F]:                                  # 返回一个装饰器（接收函数 F，返回函数 F）
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

    def decorator(func: F) -> F:                        # 第 2 层：接收被装饰的函数，返回 wrapper
        async def aretry_once(args: tuple, kwargs: dict, attempt: int) -> Any:
            return await func(*args, **kwargs)          # 异步版调用原函数（必须 await 才会真正执行）

        def _notify(name: str, attempt: int, exc: BaseException, wait: float) -> None:
            """重试通知：有回调用回调，否则默认打印。"""
            if on_retry is not None:
                on_retry(name, attempt, exc, wait)      # 调用方自定义（如收集起来最后汇总）
            else:
                print(f"[retry] {name} 第 {attempt}/{times} 次失败："
                      f"{type(exc).__name__}: {exc}，等待 {wait:.2f}s 后重试")

        def _sleep_seconds(attempt: int) -> float:
            """第 attempt 次失败后该等多久（attempt 从 1 开始）。"""
            base = delay * (backoff ** (attempt - 1))   # 指数退避：delay, delay*backoff, delay*backoff^2...
            if jitter:
                # 全抖动（full jitter）：在 [0.5*base, 1.5*base] 之间随机，错开重试时间
                return base * (0.5 + random.random())
            return base                                  # 不加抖动就返回固定值

        if inspect.iscoroutinefunction(func):            # 判断原函数是不是 async def，是则走异步分支

            @functools.wraps(func)                       # 保留原函数的 __name__ / __doc__ / __wrapped__
            async def awrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: BaseException | None = None    # 记录最后一次异常，循环结束后抛出
                for attempt in range(1, times + 1):      # 尝试 times 次（1 到 times）
                    try:
                        return await aretry_once(args, kwargs, attempt)  # 成功就直接返回
                    except exceptions as e:              # 只捕获白名单里的异常，其他直接抛出
                        last_exc = e                     # 记下异常
                        if attempt >= times:             # 已经是最后一次尝试
                            break                        # 不再等待，跳出循环
                        wait = _sleep_seconds(attempt)   # 算这次要等多久
                        _notify(func.__qualname__, attempt, e, wait)  # 通知
                        await asyncio.sleep(wait)        # ★ 异步版必须 await asyncio.sleep（用 time.sleep 会阻塞事件循环）
                raise last_exc  # type: ignore[misc]     # 全部失败，抛出最后一次异常
            return awrapper  # type: ignore[return-value]

        @functools.wraps(func)                           # 同步分支同样保留原函数身份
        def swrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)         # 同步直接调用
                except exceptions as e:
                    last_exc = e
                    if attempt >= times:
                        break
                    wait = _sleep_seconds(attempt)
                    _notify(func.__qualname__, attempt, e, wait)
                    time.sleep(wait)                     # 同步版用 time.sleep（阻塞等待）
            raise last_exc  # type: ignore[misc]

        return swrapper  # type: ignore[return-value]

    return decorator                                     # 第 1 层返回装饰器
```

## 日志
我看了和之前的重试差不多，只是里面也包含了一些，func.__qualname__ 这些需要注意一下
func.__qualname__：代码里面的完整路径；
__name__：函数名字
type(e).__name__：拿到异常的函数名字


## 我看了多层的包裹

```python
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
```

这个就是想洋葱一样包裹。
```python
def stacked() -> None:
    print("  → 原函数执行")

stacked = deco_a(deco_b(stacked))
```