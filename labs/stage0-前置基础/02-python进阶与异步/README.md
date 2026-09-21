# 模块 02 · Python 进阶与异步编程 —— 教学 Demo 目录

> **任务书**：[my-docs/study01/stage0-前置基础/02-Python进阶与异步编程.md](../../../my-docs/study01/stage0-前置基础/02-Python进阶与异步编程.md)
> **依赖**：`pydantic` `httpx` `fastapi` `uvicorn`（见仓库根 `pyproject.toml`，`uv pip install -r requirements.txt` 一次装完）
> **预计投入**：10~12 小时（5 个 Demo）
> **完成标志**：能白板写出支持 async 的带参 `@retry`；手里有并发对照实验的真实数字

---

## 一、这个模块是分水岭

模块 01 让你"会写脚本"，模块 02 让你**能看懂 Agent 框架的源码**。
LangChain / LangGraph / PydanticAI 的核心抽象，全部建立在这四样东西上：

| 框架里的东西 | 本模块对应的 Demo |
|-------------|-----------------|
| `@tool` / `@traceable` / `@observe` 装饰器 | Demo 02-1 |
| 批量调 LLM、并发灌库 | Demo 02-2、02-5 |
| `create_structured_output` / 输出校验与自动修复 | Demo 02-3 |
| `class AgentState(TypedDict)` + `Annotated[..., add_messages]` | Demo 02-4 |

**跳过这个模块，阶段 3 会 100% 卡死**（任务书原话）。

---

## 二、目录结构

```
02-python进阶与异步/
├── README.md                       ← 你在这里
├── demo-01-decorators/             ① 装饰器三连          [闭包/wraps/三层嵌套/sync+async]
│   ├── README.md  run.sh
│   ├── decorators.py               @timer @retry @log_calls（约 250 行，含教学注释）
│   └── demo_decorators.py          7 个场景（含 3 个"必须验证的现象"）
├── demo-02-concurrency-lab/        ② 串行 vs 并发对照     [asyncio/gather/Semaphore/事件循环阻塞]
│   ├── README.md  run.sh
│   ├── slow_server.py              Mock 慢服务（含"服务端阻塞"反面教材端点）
│   ├── bench.py                    7 组实验 A~G
│   └── out/bench_result.json       运行后生成
├── demo-03-pydantic-guard/         ③ LLM 输出守门员       [Pydantic v2 全套]
│   ├── README.md  run.sh
│   ├── models.py                   ToolCall / AgentStep / AgentTrace + Schema 导出
│   ├── guard.py                    3 个实验
│   └── samples.jsonl               20 条样本（12 合法 / 8 脏）
├── demo-04-state-lab/              ④ LangGraph State 预演 [TypedDict/Annotated/reducer]
│   ├── README.md  run.sh
│   └── state.py                    手写 reduce_state + 8 个用例（纯标准库）
└── demo-05-batch-caller/           ⑤ 异步批量调用器 ★集大成 [限流/重试/超时/续跑/成本]
    ├── README.md  run.sh
    ├── mock_llm_server.py          OpenAI 兼容 mock，故意注入 429/超时/脏JSON
    ├── make_prompts.py             造 200 条 prompt
    ├── batch_call.py               主程序（8 个工程要点）
    └── data/                       prompts / results / results.failed
```

---

## 三、学习路径

```
Day 1 上午 ── Demo 02-1 装饰器三连
   ① bash run.sh 看 7 个场景                (15 min)
   ② 读 decorators.py，重点看 iscoroutinefunction 分叉  (30 min)
   ③ 关掉代码，白板写支持 async 的带参 @retry  (40 min) ★ 面试必考
   ④ 练习 1、2、4（熔断器）                  (90 min)

Day 1 下午 ── Demo 02-2 并发对照
   ① bash run.sh，把 7 组数字记进 README     (20 min)
   ② 读 bench.py，重点看 B（async 串行）和 E（time.sleep 阻塞）  (30 min)
   ③ 练习 1（并发度曲线）、练习 4（fetch_all 通用函数）  (90 min)

Day 2 上午 ── Demo 02-3 Pydantic 守门员
   ① bash run.sh 看 3 个实验                (15 min)
   ② 读 models.py，逐个 validator 理解它救回了哪条样本  (40 min)
   ③ 读 samples.jsonl，自己再造 10 条脏样本   (40 min)
   ④ 练习 2、3（auto_repair）                (60 min)

Day 2 下午 ── Demo 02-4 State Lab
   ① bash run.sh（8 个用例 + pytest + mypy）  (10 min)
   ② 读 state.py 的 get_reducers()，这是技术核心  (30 min)
   ③ 背下"LangGraph 为什么需要 reducer"三句话  (5 min)
   ④ 练习 2（并行冲突）、练习 5（简易 checkpoint） (60 min)

Day 3 全天 ── Demo 02-5 批量调用器 ★ 集大成
   ① bash run.sh 看 7 步完整演示             (20 min)
   ② 读 batch_call.py 的 8 个工程要点         (60 min)
   ③ 亲手 Ctrl+C 一次，再 --resume，确认不重复  (15 min) ★ 任务书最重要的一条
   ④ 练习 2（成本护栏）、3（语义缓存）、5（接 Pydantic 校验）  (150 min)

Day 4 上午 ── 收尾
   ① 5 个 Demo 的验收清单逐条打勾
   ② 任务书"知识点清单"逐条打勾
   ③ 把并发实验数字、批量调用成本数字整理成一段"面试用素材"
   ④ 回 my-docs 打勾，进模块 03
```

---

## 四、一键跑全部

```bash
cd labs/stage0-前置基础
export PYBIN=$PWD/.venv/bin/python
for d in 02-python进阶与异步/demo-*/; do
  echo "═══ $d ═══"
  (cd "$d" && bash run.sh > /tmp/m2.log 2>&1 && echo "  ✅ OK" || { echo "  ❌ FAIL"; tail -20 /tmp/m2.log; })
done
```
或 `make m2`（仓库根目录）。

---

## 五、必须口头答出的 6 个问题

| 问题 | 答案要点 | 在哪个 Demo 验证过 |
|------|---------|------------------|
| async 到底快在哪？ | 不是"更快"，是**等待时能让出控制权**给别的任务。CPU 密集型一点都不会快（要用多进程）。我的数字：20 个 IO 请求串行 10.16s → 并发 0.56s | 02-2 实验 A/C |
| 为什么加了 `async def` 没变快？ | `await` 在 for 循环里 = 逐个等待 = 串行。并发要"先建多个任务再一起等" | 02-2 实验 B（10.19s vs A 的 10.16s） |
| 协程里调同步库怎么办？ | `await asyncio.to_thread(fn, args)` 丢线程池；或换异步库（httpx 替 requests、aiofiles 替 open） | 02-2 实验 E 的"救法"对照 |
| `time.sleep` 在协程里的后果？ | 阻塞的是**整个线程**，事件循环停摆，所有协程都推不动。FastAPI 里一个这样的接口能拖垮整个服务 | 02-2 实验 E（10 并发变 5.58s 串行）+ 实验 G（服务端版） |
| Pydantic 的 `errors()` 有什么用？ | 返回 `[{type, loc, msg, input, url}]` 结构化错误 → 是**自动修复的原料**：把字段路径和错误类型回喂给模型，比"格式不对请重试"有效得多 | 02-3 实验 ② |
| LangGraph 的 State 为什么用 reducer？ | 节点返回部分更新；默认合并语义是覆盖，list 字段会被整个替换；并行节点写同一 key 会冲突 | 02-4 用例 ⑥（对照实验：不写 Annotated 就丢数据） |

---

## 六、常见报错速查

| 报错 | 原因 | 解法 |
|------|------|------|
| `ModuleNotFoundError: pydantic / httpx / fastapi` | 没用 lab 的 venv | `cd labs/stage0-前置基础 && uv venv .venv && uv pip install -r requirements.txt`，然后用 `.venv/bin/python` 或激活后跑 |
| `RuntimeWarning: coroutine 'xxx' was never awaited` | 调用了 async 函数但没 await（常见于用普通装饰器装饰 async） | 见 02-1 场景 6 |
| `TypeError: '_io.TextIOWrapper' object does not support the asynchronous context manager protocol` | `async with client, open(...) as fh` 混用 | 嵌套写：`async with client:` 里面再 `with open(...)` |
| `Address already in use` (8899/8898) | 上次的 mock 服务没关掉 | `lsof -i :8899` 找到 pid 后 `kill`；或 `PORT=9001 bash run.sh` |
| 重试后依然全部失败 | mock 的故障注入是确定性的（我已修） | 若你自己改过 `mock_llm_server.py`，检查 `dice` 是否用了 `hash(prompt)`（错误）而不是 `_rng.random()`（正确） |
| `pytest: no tests ran` | testpaths 指向了模块 06 | 显式指定：`pytest 02-python进阶与异步/demo-04-state-lab/state.py` |

---

## 七、完成后做什么

1. 回 [任务书](../../../my-docs/study01/stage0-前置基础/02-Python进阶与异步编程.md) 打勾「四、模块完成判定」
2. 更新 [00-进度看板.md](../../../my-docs/study01/00-进度看板.md)
3. **把这两组数字写进你的面试素材库**（阶段 6 简历要用）：
   - 并发对照：串行 ____s → 并发 ____s，提速 ____×
   - 批量调用：200 条，成本 ¥____，耗时 ____s，重试 ____ 次，解析失败 ____ 条
4. `git commit`（`feat(m02): demo-02-5 增加成本护栏与语义缓存`）
5. 进入 [模块 03 · 后端基础与 Linux/Git](../03-后端与linux-git/)

> **⚠️ Demo 02-5 的 `batch_call.py` 不要删。** 阶段 1 做提示词 A/B 评测时会直接复用它，
> 阶段 2 的批量灌库也是同一套模式（限流 + 重试 + 断点续跑 + 成本统计）。
