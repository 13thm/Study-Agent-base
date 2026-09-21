# Demo 02-2 · 串行 vs 并发对照实验

> **任务书**：[02-Python进阶与异步编程.md → Demo 02-2](../../../../my-docs/study01/stage0-前置基础/02-Python进阶与异步编程.md)
> **依赖**：`fastapi` `uvicorn` `httpx`　**耗时**：1.5 小时　**练什么**：asyncio、gather、Semaphore、事件循环阻塞

## 一、这个 Demo 的唯一目的：**拿到数字**
面试说"我懂异步"没有说服力；说"20 个请求串行 10.16s、并发 0.56s，提速 17.8 倍"才有。

## 二、跑
```bash
bash run.sh                       # 自动起 mock 服务 → 跑 7 组实验 → 关服务
bash run.sh --only CE             # 只跑指定实验
bash run.sh --base-url http://x   # 打你自己的服务
```
`run.sh` 会做三件事：启动 `slow_server.py`（后台）→ 等 `/health` 就绪 → 跑 `bench.py` → trap 清理。

## 三、我的实测结果（换成你的数字）
```
实验  方案                              请求数   耗时     提速
A    同步串行 for + httpx.Client          20    10.16s   0.98×
B    异步但串行 for + await               20    10.19s   0.98×   ★ async ≠ 并发
C    asyncio.gather 全并发               20     0.56s  17.81×
D    gather + Semaphore(5) 限流          20     2.05s   4.87×   ★ 保护下游
E    协程里用 time.sleep                  10     5.58s   0.90×   ★ 事件循环卡死
F    每次请求新建 AsyncClient             20     0.64s  15.67×   （比 C 慢 14%）
G    服务端阻塞 /slow-blocking            10     5.16s   0.97×   ★ 慢不一定是你的锅
```
E 的三方对照（脚本会打印）：
```
await asyncio.sleep × 10 并发 → 0.50s   ✅
time.sleep          × 10 并发 → 5.58s   ❌ 完全串行
asyncio.to_thread   × 10 并发 → 0.51s   ✅ 救法：丢进线程池
```

## 四、三个必须能口头回答的问题
1. **为什么 B 不比 A 快？** → `await` 的语义是"在这里等它完成"，for 循环里逐个 await 就是串行。
   并发的前提是**先创建多个任务，再一起等**（`gather` / `TaskGroup` / `create_task`）。
2. **D（限流）存在的意义？** → 不是拖后腿，是保护下游和钱包。打 LLM API 时并发过高会触发
   RPM/TPM 限流，结果是大量 429 + 退避重试，**反而更慢更贵**（Demo 02-5 会亲眼看到）。
3. **协程里为什么绝对不能出现 `time.sleep`？** → 事件循环跑在单线程上，同步阻塞调用霸占线程，
   导致**所有**其他协程无法推进。在 FastAPI 里，一个这样的接口能拖垮整个服务（实验 G 就是服务端版本）。

## 五、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 把 `Semaphore(5)` 改成 1/2/5/10/20，画出"并发度 - 总耗时"曲线，找出拐点 |
| 2 | ⭐⭐ | 用 `asyncio.TaskGroup`（3.11+）重写实验 C，对比 `gather` 的差异（异常处理语义不同：TaskGroup 会取消同组其他任务） |
| 3 | ⭐⭐ | 给实验 C 加"任意一个失败就整体失败"和"失败也继续"两种语义，分别用 `gather(return_exceptions=?)` 实现 |
| 4 | ⭐⭐⭐ | 实现一个 `async def fetch_all(urls, concurrency, on_error)` 通用函数，支持超时、重试、进度回调 —— 这就是阶段 2 批量灌库的核心 |
| 5 | ⭐⭐⭐ | 用 `asyncio.to_thread` 把一个同步库（如 `sqlite3` 查询）并发化，测出线程池大小对吞吐的影响 |

## 六、验收清单
- [ ] 7 组数字都拿到了，贴进上面第三节（换成你的实测值）
- [ ] 能口头解释 B、D、E 三个现象
- [ ] `out/bench_result.json` 生成了（可被 README 引用）
- [ ] 练习 1、2、4 完成

## 七、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
| | | | |
| 我写 run.sh 时 | `bash: BASE\xef: unbound variable` | `set -u` 下 `$BASE）`（后跟全角括号）被当成变量名的一部分 | 写成 `${BASE}）`；**变量后紧跟多字节字符时一律加花括号** |
