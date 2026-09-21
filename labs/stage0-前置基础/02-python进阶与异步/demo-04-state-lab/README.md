# Demo 02-4 · TypedDict + Annotated 模拟 LangGraph State

> **任务书**：[02-Python进阶与异步编程.md → Demo 02-4](../../../../my-docs/study01/stage0-前置基础/02-Python进阶与异步编程.md)
> **依赖**：无（纯标准库）　**耗时**：1 小时　**练什么**：`TypedDict`、`Annotated`、`get_type_hints(include_extras=True)`

## 一、为什么现在就要练这个
阶段 3 写 LangGraph 时，90% 的新手卡壳不是图逻辑，而是这两行语法看不懂：
```python
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]   # ← 这行在干什么？
    step_count: int
```
本 Demo 用 **60 行纯标准库代码**把 reducer 机制手写实现一遍。
之后再看 LangGraph 源码，你会发现它就是这套东西的工业版。

## 二、跑
```bash
bash run.sh      # ① 8 个内置用例 ② pytest 跑同一批 ③ mypy 静态检查
```
两种跑法都支持：`python state.py`（内置断言）/ `pytest state.py -v`

## 三、8 个用例分别验证什么
| # | 用例 | 验证点 |
|---|---|---|
| ① | `test_reducer_registered` | `Annotated` 里的 reducer 被正确提取（靠 `get_type_hints(include_extras=True)`） |
| ② | `test_messages_accumulate` | **messages 累加**（核心行为） |
| ③ | `test_scalar_overwrite` | 无 Annotated 的字段是**覆盖**（step_count 1→2，不是 3） |
| ④ | `test_messages_update_by_id` | `add_messages` 支持按 id **更新**而非无脑追加 |
| ⑤ | `test_unknown_key_raises` | 未声明的 key 报错（拼写错误不会静默失效） |
| ⑥ | `test_no_reducer_would_lose_data` | ★ **对照实验**：忘了写 Annotated，第一条消息就被覆盖丢了 |
| ⑦ | `test_full_graph_run` | 完整跑一遍"图"，验证 state 演变 |
| ⑧ | `test_typed_dict_is_plain_dict` | TypedDict 运行时就是普通 dict，**不做任何校验** |

## 四、LangGraph 为什么需要 reducer（3 句话，背下来）
1. 节点返回的是**部分更新** dict，不是完整 state
2. 默认合并语义是**覆盖**，所以 list 字段会被整个替换掉
3. **并行节点**同时写同一个 key 时，覆盖会导致"只能有一个值"的错误（LangGraph 直接抛 `InvalidUpdateError`）

→ 结论：所有需要"累积"的字段（messages / logs / 工具调用记录）**都必须挂 reducer**。

## 五、我写这个 Demo 时踩的两个坑（已修，留着当教材）
| 坑 | 现象 | 原因 |
|---|---|---|
| 断言数错 | `test_full_graph_run` 期望 4 条 messages，实际 3 条 | 4 个节点里只有 3 个写了 messages，我自己数错了。**教训：写测试时先手算一遍期望值** |
| mypy 报错 | `Incompatible types in assignment (AgentState vs dict[str, object])` | `state = dict(init)` 后再 `state = reduce_state(...)` 类型不一致 → 显式标注 `state: dict[str, Any]` |

## 六、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 加一个 `tool_calls: Annotated[list, operator.add]` 字段，跑通累加 |
| 2 | ⭐⭐ | 实现"并行节点"模拟：两个 patch 同时到达，验证有 reducer 的字段能合并、没有的抛错（对应 LangGraph 的 `InvalidUpdateError`） |
| 3 | ⭐⭐ | 给 `reduce_state` 加 `max_size` 参数：messages 超过 N 条时自动丢最早的（滑动窗口记忆的雏形） |
| 4 | ⭐⭐⭐ | 把 State 从 TypedDict 换成 `pydantic.BaseModel`，对比两种方式的差别（BaseModel 有运行时校验但要 `model_copy(update=...)`） |
| 5 | ⭐⭐⭐ | 实现 `checkpoint(state)` / `restore(cp)`，把每步 state 存 JSON —— 这就是阶段 3 Checkpointer 的最小版 |

## 七、验收清单
- [ ] 8 个用例全绿（`python state.py` 和 `pytest state.py` 都跑过）
- [ ] `mypy state.py` 零报错
- [ ] 能默写出 `get_reducers()` 的核心 5 行（`get_type_hints` → `get_origin is Annotated` → `get_args`）
- [ ] 能背出"LangGraph 为什么需要 reducer"的 3 句话
- [ ] 练习 1~3 完成

## 八、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
| | | | |
