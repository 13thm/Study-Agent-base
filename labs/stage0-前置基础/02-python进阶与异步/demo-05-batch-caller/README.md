# Demo 02-5 · 异步 LLM 批量调用器

> **任务书**：[02-Python进阶与异步编程.md → Demo 02-5](../../../../my-docs/study01/stage0-前置基础/02-Python进阶与异步编程.md)
> **依赖**：`fastapi` `uvicorn` `httpx` + 复用 demo-01 的 `@retry`　**耗时**：3 小时
> **练什么**：把模块 02 的所有东西串成一个**生产可用的工具**

## 一、为什么要认真做这个 Demo
阶段 1 的提示词 A/B 评测、阶段 2 的评测集跑分、阶段 5 的批量回归，
本质都是同一件事：**读一批 prompt → 并发调模型 → 落盘 → 统计成本**。
现在把它写成能用的样子，后面直接复用（阶段 1 的 `prompt-toolbox` 就是从这类脚本长出来的）。

## 二、文件
```
demo-05-batch-caller/
├── mock_llm_server.py   ← OpenAI 兼容的 mock 服务，【故意注入故障】：8% 429 / 4% 超时 / 8% 脏JSON
├── make_prompts.py      ← 生成 200 条 prompt（seed=42 可复现）
├── batch_call.py        ← 主程序：限流/重试/超时/断点续跑/边跑边写/成本统计
├── run.sh               ← 7 步完整演示
└── data/                ← prompts.jsonl / results.jsonl / results.failed.jsonl
```

## 三、跑
```bash
bash run.sh          # 自动起 mock 服务 → 7 个步骤 → 关服务（约 2 分钟）
```
换真实 API（阶段 1 之后会这么用）：
```bash
python batch_call.py --base-url https://api.deepseek.com --api-key $DEEPSEEK_API_KEY \
                     --model deepseek-chat --concurrency 3
```

## 四、我的实测输出
```
▶ 待处理 200 条（跳过 0 条已完成）  并发 5  模型 mock-llm
  进度 40/200  成功 40  失败 0  累计成本 ¥0.0127
  ...
完成：成功 200，失败 0，跳过 0
总 Token 37,769（输入 12,172 / 输出 25,597）
预估成本 ¥0.0634，耗时 26.1s，平均 0.13s/条，吞吐 7.7 条/s
重试统计（共 39 次）：{'RateLimited': 29, 'TimeoutError': 10}
输出解析情况：{'clean': 191, 'extracted': 5, 'unparseable': 4}
单条成本 ¥0.000317 → 10 万条约 ¥32，100 万条约 ¥317

★ 断点续跑：跑到 2.5s 时发 SIGINT
  中断时已落盘 37 条（这就是「边跑边 flush」的价值）
  → --resume 继续：已完成 37 条，将跳过 → 待处理 163 条 → 总计 200 条
  ✅ 中断前的 37 条【没有】被重复处理

★ 并发度对照（60 条）
  并发 1 : 37.7s   1.6 条/s
  并发 5 :  9.5s   6.3 条/s   （3.97×）
  并发 10:  6.9s   8.7 条/s   （5.46×）

★ 服务端统计（证明请求真的打过去了，故障是服务端注入的）
  {"requests": 670, "429": 62, "timeout": 26, "badjson": 52}
```

## 五、8 个工程要点（每个都在代码里有对应注释）
| 要点 | 实现 | 不做会怎样 |
|---|---|---|
| 并发限流 | `asyncio.Semaphore(n)` | 打爆下游 / 触发 RPM 限流 / 更慢更贵 |
| 失败重试 | 复用 demo-01 的 `@retry(exceptions=(RateLimited, UpstreamError, TimeoutError))` | 偶发 429 直接丢数据 |
| **不重试 400** | `BadRequest` 不在白名单 | 参数错重试 3 次纯浪费钱 |
| 超时控制 | `asyncio.wait_for(coro, timeout)`；httpx 侧 `timeout=None` 只留一处 | 卡死的请求永远占着信号量 |
| **断点续跑** | 启动时读 out 文件收集已完成 id | 跑 3 小时崩了要从头再来 |
| **边跑边 flush** | 每条 `fh.write() + fh.flush()` | Ctrl+C 后全丢 |
| 加锁写 | `asyncio.Lock` 保护"计数 + 写入"两步 | 进度统计与实际不符 |
| 优雅中断 | `loop.add_signal_handler` + 取消未完成 task | Ctrl+C 后文件里出现半截 JSON |

## 六、我踩的两个坑（都已修，代码注释里留了记录）
| 坑 | 现象 | 根因 | 教训 |
|---|---|---|---|
| **mock 故障是确定性的** | 重试 3 次全部失败，成功率只有 88% | 我写 `dice = random.Random(hash(prompt)).random()`，同一 prompt 每次算出同一个 dice → 第一次 429，重试还是 429 | **"可复现的随机"要用进程级 seeded RNG**，不是对输入取 hash |
| **async with 混用文件对象** | `TypeError: '_io.TextIOWrapper' object does not support the asynchronous context manager protocol` | `async with client, open(...) as fh` —— 普通文件只有 `__enter__`，没有 `__aenter__` | 两种上下文管理器不能混在一个 `async with` 里，要嵌套或用 `ExitStack` |

## 七、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 加 `--limit N` 只跑前 N 条（调试时很有用） |
| 2 | ⭐⭐ | 加 `--max-cost 0.5`：累计成本超过就优雅停止（阶段 1 的成本护栏雏形） |
| 3 | ⭐⭐ | 加**语义缓存**：相同 prompt 直接返回上次结果，统计命中率与省下的钱 |
| 4 | ⭐⭐⭐ | 加 AIMD 并发自适应：遇 429 就把 Semaphore 减半，连续成功 10 次就 +1（阶段 1 模块 03 Demo 3-5 的要求） |
| 5 | ⭐⭐⭐ | 把 `parse_loose` 换成 demo-03 的 Pydantic 校验 + 失败自动回喂重试，统计一次通过率的变化 |

## 八、验收清单
- [ ] `bash run.sh` 7 步全部通过
- [ ] **中途 Ctrl+C 后 `--resume` 能续上，且不重复处理**（本 Demo 最重要的一条）
- [ ] `results.jsonl` 每行都是合法 JSON（脚本已自动校验）
- [ ] 并发 1 / 5 / 10 的耗时都记录了
- [ ] 失败项能单独重跑（`--in data/results.failed.jsonl`）
- [ ] 能说出 8 个工程要点各自防的是什么事故
- [ ] 练习 2、3、5 完成

## 九、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
| | | | |
