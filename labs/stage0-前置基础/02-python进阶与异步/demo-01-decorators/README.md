# Demo 02-1 · 装饰器三连

> **任务书**：[02-Python进阶与异步编程.md → Demo 02-1](../../../../my-docs/study01/stage0-前置基础/02-Python进阶与异步编程.md)
> **依赖**：无　**耗时**：2 小时　**练什么**：闭包、`functools.wraps`、三层嵌套、sync/async 双支持

## 一、这三个装饰器以后真的会一直用
| 装饰器 | Agent 场景 | 后续在哪复用 |
|---|---|---|
| `@timer` | 定位哪一步最慢 | 阶段 3 的 RuntimeProfiler |
| `@retry(times, exceptions=...)` | LLM 429 / 超时 | 阶段 1 多模型客户端、阶段 3 工具八件套 |
| `@log_calls` | 工具调用审计 | 阶段 5 的审计日志 |

## 二、跑
```bash
bash run.sh          # 7 个场景，含 3 个"必须验证的现象"
```

## 三、7 个场景与你要记住的结论
| 场景 | 现象 | 结论 |
|---|---|---|
| 1 `@timer` 同步+异步 | `slow_sync 1.010s` / `slow_async 0.501s` | 用 `inspect.iscoroutinefunction` 分叉，返回不同 wrapper |
| 2 `@retry` 白名单 | 前 2 次失败第 3 次成功；`ZeroDivisionError` **一次都没重试** | 只重试瞬时错误；参数错/逻辑错重试是纯浪费 |
| 3 `@log_calls` | 长返回值被截断成 `...(共 90 字符)` | 审计日志必须截断，否则一条日志几 MB |
| 4 叠加顺序 | A 进入 → B 进入 → 原函数 → B 退出 → A 退出 | **由外向内包装，由内向外执行**（洋葱模型） |
| 5 `functools.wraps` | 无 wraps 时 `__name__='wrapper'`、`__doc__=None` | 丢元信息 → 日志分不清、`inspect.signature` 失效、pytest 漏测 |
| 6 普通装饰器装 async | 耗时 `0.000002s`（假的），返回 `coroutine` 对象 | **装饰 async 必须用 async wrapper 并 await** |
| 7 白板题 | 手写带参 + 支持 async 的 `@retry` | 8 步口诀见脚本输出 |

## 四、白板题口诀（面试真的会考）
```
三层嵌套 + wraps + iscoroutinefunction 判断 + 异常白名单 + 指数退避(+jitter) + 抛最后一次异常
```

## 五、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 给 `@retry` 加 `max_total_time` 参数：累计耗时超过它就放弃（生产必备，防止重试拖垮 SLA） |
| 2 | ⭐⭐ | 写 `@cache_result(ttl=60)`：用 dict + 时间戳做内存缓存，键是参数元组。思考：参数里有 list/dict 怎么办？（不可哈希） |
| 3 | ⭐⭐ | 写 `@deprecated(reason)`：调用时打 WARNING，并在 `__doc__` 前面加标记 |
| 4 | ⭐⭐⭐ | 写 `@circuit_breaker(fail_threshold=3, reset_timeout=60)` 实现三态熔断（CLOSED/OPEN/HALF_OPEN）。这是阶段 3 模块 03 Demo 3-2 的核心 |
| 5 | ⭐⭐⭐ | 写 `class RateLimiter` 用**类**实现装饰器（`__call__`），支持令牌桶。对比函数式装饰器的差别 |

## 六、验收清单
- [ ] 7 个场景输出与本文表格一致
- [ ] 能白板写出支持 async 的带参 `@retry`（不看参考，10 分钟内）
- [ ] 能说出 `functools.wraps` 不加的三个后果
- [ ] 能说出为什么 `@retry` 必须有异常白名单（并引用 Demo 01-4 的 `--retry 2` 对照实验）
- [ ] 练习 1、2、4 完成

## 七、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
| | | | |
