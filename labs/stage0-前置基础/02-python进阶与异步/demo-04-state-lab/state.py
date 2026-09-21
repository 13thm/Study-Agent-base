#!/usr/bin/env python3
"""TypedDict + Annotated 模拟 LangGraph 的 State 与 Reducer —— Demo 02-4。

📌 为什么要在这里练？
    阶段 3 模块 02 写 LangGraph 时，90% 的"新手卡壳"不是图逻辑，而是这两行语法：

        class AgentState(TypedDict):
            messages: Annotated[list[AnyMessage], add_messages]
            step_count: int

    看不懂 Annotated 在干什么，就永远不明白"为什么我的 messages 每次都被清空了"。
    本 Demo 用**纯标准库**把 reducer 机制手写实现一遍（60 行），
    之后再看 LangGraph 的源码，你会发现它就是这套东西的工业版。

跑法：python state.py            （内置 8 个测试用例，无需 pytest）
     pytest state.py -v          （也能被 pytest 收集）
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict, get_args, get_origin, get_type_hints


# ═════════════════════════════════════════════════════════════
# 1. 定义 State（和 LangGraph 的写法一模一样）
# ═════════════════════════════════════════════════════════════
def add_messages(old: list[dict], new: list[dict]) -> list[dict]:
    """LangChain 的 add_messages 的极简版：按 id 更新，无 id 则追加。

    📌 真实的 add_messages 还支持 RemoveMessage(id=x) 来删除历史消息，
       以及自动补 id。这里实现"按 id 更新"就够体会 reducer 的语义了。
    """
    merged = list(old)
    index_by_id = {m["id"]: i for i, m in enumerate(merged) if "id" in m}
    for m in new:
        mid = m.get("id")
        if mid is not None and mid in index_by_id:
            merged[index_by_id[mid]] = {**merged[index_by_id[mid]], **m}   # 更新
        else:
            merged.append(m)                                               # 追加
    return merged


class AgentState(TypedDict):
    """Agent 的共享状态。

    📌 TypedDict vs dataclass vs BaseModel：
        · TypedDict 只是"给 dict 加类型标注"，运行时它就是普通 dict（零开销）
        · LangGraph 选它是因为 state 要频繁序列化进 checkpoint，dict 最省事
        · 代价：运行时【不做任何校验】，写错 key 不会报错 → 所以要靠 mypy
    """

    messages: Annotated[list[dict], add_messages]   # ← 增量合并（reducer）
    logs: Annotated[list[str], operator.add]        # ← 也是增量合并，用标准库的 operator.add
    step_count: int                                 # ← 无 Annotated = 覆盖式更新
    done: bool
    final_answer: str


# ═════════════════════════════════════════════════════════════
# 2. 手写 reduce_state（LangGraph 的核心机制）
# ═════════════════════════════════════════════════════════════
class UnknownKeyError(KeyError):
    """节点返回了 State 里没声明的 key。"""


def get_reducers(state_cls: type) -> dict[str, Any]:
    """从类型标注里把 reducer 提取出来。

    📌 这段是本 Demo 的技术核心，看懂它就懂了 Annotated：
        get_type_hints(cls, include_extras=True)  →  拿到 {'messages': Annotated[list, fn], ...}
        get_origin(t) is Annotated                →  判断这个标注是不是 Annotated
        get_args(t)                               →  (list[dict], fn)  第 0 个是类型，第 1+ 个是元数据
    """
    hints = get_type_hints(state_cls, include_extras=True)
    reducers: dict[str, Any] = {}
    for name, hint in hints.items():
        if get_origin(hint) is Annotated:
            args = get_args(hint)
            # Annotated[T, x, y] 里 x、y 都是元数据，LangGraph 约定第一个可调用的是 reducer
            for meta in args[1:]:
                if callable(meta):
                    reducers[name] = meta
                    break
    return reducers


_REDUCERS = get_reducers(AgentState)          # 模块加载时算一次，缓存起来


def reduce_state(old: AgentState, patch: dict[str, Any]) -> AgentState:
    """把节点返回的"部分更新"合并进 state。

    规则（和 LangGraph 完全一致）：
        · 字段登记了 reducer → 用 reducer(旧值, 新值) 合并
        · 没登记           → 直接覆盖
        · patch 里有 State 未声明的 key → 抛 UnknownKeyError（LangGraph 也是报错）

    📌 LangGraph 为什么需要 reducer？三句话说清：
        ① 节点返回的是"部分更新"（dict），不是完整 state
        ② 默认的合并语义是【覆盖】，所以 list 字段会被整个替换掉
        ③ 并行节点同时写同一个 key 时，覆盖会导致"只能有一个值"的错误
           （LangGraph 会直接抛 InvalidUpdateError）
        → 结论：所有需要"累积"的字段（messages、logs、工具调用记录）都必须挂 reducer。
    """
    declared = set(get_type_hints(AgentState, include_extras=True).keys())
    unknown = set(patch) - declared
    if unknown:
        raise UnknownKeyError(
            f"节点返回了 State 未声明的字段: {sorted(unknown)}；已声明: {sorted(declared)}"
        )

    new: dict[str, Any] = dict(old)
    for key, value in patch.items():
        reducer = _REDUCERS.get(key)
        if reducer is not None:
            # 📌 旧值可能还不存在（第一次更新），用类型的"空值"兜底
            current = old.get(key)
            if current is None:
                current = [] if isinstance(value, list) else value
            new[key] = reducer(current, value)
        else:
            new[key] = value
    return new  # type: ignore[return-value]


def run_graph(nodes: list[tuple[str, dict[str, Any]]], init: AgentState) -> list[dict[str, Any]]:
    """模拟 LangGraph 的执行：按顺序跑节点，每个节点返回 patch，合并进 state。

    返回每一步的快照，方便测试断言。
    """
    state: dict[str, Any] = dict(init)
    trace: list[dict[str, Any]] = [{"node": "<init>", "state": dict(state)}]
    for name, patch in nodes:
        state = dict(reduce_state(state, patch))   # type: ignore[arg-type]
        trace.append({"node": name, "patch": patch, "state": dict(state)})
    return trace


# ═════════════════════════════════════════════════════════════
# 3. 测试用例（8 个，既能直接跑也能被 pytest 收集）
# ═════════════════════════════════════════════════════════════
def initial() -> AgentState:
    return {"messages": [], "logs": [], "step_count": 0, "done": False, "final_answer": ""}


def test_reducer_registered() -> None:
    """① Annotated 里的 reducer 被正确识别出来。"""
    assert set(_REDUCERS) == {"messages", "logs"}, _REDUCERS
    assert _REDUCERS["logs"] is operator.add


def test_messages_accumulate() -> None:
    """② messages 累加（这是最核心的行为）。"""
    s = reduce_state(initial(), {"messages": [{"role": "user", "content": "hi"}]})
    s = reduce_state(s, {"messages": [{"role": "assistant", "content": "hello"}]})
    assert len(s["messages"]) == 2, f"应该累加成 2 条，实际 {len(s['messages'])}"
    assert s["messages"][1]["content"] == "hello"


def test_scalar_overwrite() -> None:
    """③ 无 reducer 的字段是覆盖式更新。"""
    s = reduce_state(initial(), {"step_count": 1})
    s = reduce_state(s, {"step_count": 2})
    assert s["step_count"] == 2, "step_count 应该被覆盖成 2，而不是累加成 3"


def test_messages_update_by_id() -> None:
    """④ add_messages 支持按 id 更新（不是无脑追加）。"""
    s = reduce_state(initial(), {"messages": [{"id": "m1", "role": "assistant", "content": "v1"}]})
    s = reduce_state(s, {"messages": [{"id": "m1", "content": "v2"}]})
    assert len(s["messages"]) == 1, "同 id 应该是更新，不是追加"
    assert s["messages"][0]["content"] == "v2"
    assert s["messages"][0]["role"] == "assistant", "更新时应保留未提供的字段"


def test_unknown_key_raises() -> None:
    """⑤ 未声明的 key 必须报错（否则拼写错误会静默失效，极难排查）。"""
    try:
        reduce_state(initial(), {"step_counter": 1})     # 拼错了：count → counter
    except UnknownKeyError as e:
        assert "step_counter" in str(e)
    else:
        raise AssertionError("应该抛 UnknownKeyError 但没有")


def test_no_reducer_would_lose_data() -> None:
    """⑥ 对照实验：如果 messages 没挂 reducer，数据会被覆盖丢失。

    这就是 LangGraph 新手第一大坑的复现。
    """
    class BadState(TypedDict):
        messages: list[dict]        # ← 忘了写 Annotated

    def reduce_bad(old: dict, patch: dict) -> dict:
        return {**old, **patch}     # 默认合并语义 = 覆盖

    s: dict = {"messages": []}
    s = reduce_bad(s, {"messages": [{"role": "user", "content": "hi"}]})
    s = reduce_bad(s, {"messages": [{"role": "assistant", "content": "hello"}]})
    assert len(s["messages"]) == 1, "没有 reducer 时应该只剩 1 条（第一条被覆盖了）"
    assert s["messages"][0]["role"] == "assistant"


def test_full_graph_run() -> None:
    """⑦ 完整跑一遍"图"，验证 state 演变过程。"""
    trace = run_graph([
        ("agent",   {"messages": [{"role": "user", "content": "1+1=?"}], "step_count": 1}),
        ("tools",   {"messages": [{"role": "tool", "content": "2"}], "logs": ["调用 calculator"]}),
        ("agent",   {"messages": [{"role": "assistant", "content": "等于 2"}], "step_count": 2}),
        ("finish",  {"done": True, "final_answer": "等于 2", "logs": ["任务完成"]}),
    ], initial())

    final = trace[-1]["state"]
    # 4 个节点里有 3 个写了 messages（agent/tools/agent），finish 只改标量字段
    assert len(final["messages"]) == 3, f"messages 应累加成 3 条，实际 {len(final['messages'])}"
    assert final["step_count"] == 2, "step_count 应该是最后的 2（覆盖）"
    assert final["logs"] == ["调用 calculator", "任务完成"], "logs 用 operator.add 累加"
    assert final["done"] is True
    assert [t["node"] for t in trace] == ["<init>", "agent", "tools", "agent", "finish"]


def test_typed_dict_is_plain_dict() -> None:
    """⑧ TypedDict 运行时就是普通 dict（零开销，但也不做校验）。"""
    s = initial()
    assert isinstance(s, dict)
    assert type(s) is dict, "TypedDict 不会创建新类型，运行时就是 dict"
    # ⚠️ 证明它不做运行时校验：写错类型也不报错（只有 mypy 会拦）
    bad: Any = {"step_count": "不是数字"}
    merged = reduce_state(s, bad)
    assert merged["step_count"] == "不是数字", "TypedDict 不做运行时类型校验！"


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    passed = 0
    print("═" * 68)
    print(f"TypedDict + Annotated reducer 实验（{len(tests)} 个用例）")
    print("═" * 68)
    for name, fn in tests:
        try:
            fn()
        except AssertionError as e:
            print(f"  ❌ {name}: {e}")
        else:
            passed += 1
            print(f"  ✅ {name}   {fn.__doc__.strip().splitlines()[0]}")

    print(f"\n{passed}/{len(tests)} 通过")

    # 演示一次完整的 state 演变
    print("\n═══ 一次完整执行的 state 演变 ═══")
    for step in run_graph([
        ("agent",  {"messages": [{"role": "user", "content": "1+1=?"}], "step_count": 1}),
        ("tools",  {"messages": [{"role": "tool", "content": "2"}], "logs": ["调用 calculator"]}),
        ("finish", {"done": True, "final_answer": "等于 2"}),
    ], initial()):
        st = step["state"]
        print(f"  [{step['node']:<7}] messages={len(st['messages'])} logs={len(st['logs'])} "
              f"step={st['step_count']} done={st['done']}")

    print("\n═══ LangGraph 为什么需要 reducer（3 句话，背下来）═══")
    print("  ① 节点返回的是【部分更新】dict，不是完整 state")
    print("  ② 默认合并语义是【覆盖】，所以 list 字段会被整个替换掉")
    print("  ③ 并行节点同时写同一个 key 时，覆盖会导致「只能有一个值」的错误")
    print("  → 所有需要累积的字段（messages / logs / 工具调用记录）都必须挂 reducer")
    raise SystemExit(0 if passed == len(tests) else 1)
