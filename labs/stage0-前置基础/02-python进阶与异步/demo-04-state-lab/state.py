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

# ── 标准库 ─────────────────────────────────────────────
import operator                              # operator.add 就是 `lambda a, b: a + b`
from typing import (
    Annotated,       # ★ 核心：给类型附加"元数据"，reducer 就藏在这里
    Any,             # 表示任意类型
    TypedDict,       # "给 dict 加类型标注"的语法糖，运行时就是普通 dict
    get_args,        # 拆开 Annotated[...] 里的内容
    get_origin,      # 判断"外层容器"是不是 Annotated
    get_type_hints,  # ★ 从类里读出所有字段的类型标注
)


# ═════════════════════════════════════════════════════════════
# 1. 定义 State（和 LangGraph 的写法一模一样）
# ═════════════════════════════════════════════════════════════
def add_messages(old: list[dict], new: list[dict]) -> list[dict]:
    """LangChain 的 add_messages 的极简版：按 id 更新，无 id 则追加。

    📌 真实的 add_messages 还支持 RemoveMessage(id=x) 来删除历史消息，
       以及自动补 id。这里实现"按 id 更新"就够体会 reducer 的语义了。

    reducer 的签名约定：**接收 (旧值, 新值)，返回合并后的值**。
    LangGraph 只要求它是可调用对象，不强制签名，但事实约定就是 (old, new)。
    """
    # 先复制一份旧值，避免原地修改污染原 state（函数式风格，副作用最小化）
    merged = list(old)

    # 建立 "id → 下标" 的索引，后续按 id 查找要 O(1)
    # 只索引有 id 的消息；没有 id 的消息无法定位，只能追加
    index_by_id = {m["id"]: i for i, m in enumerate(merged) if "id" in m}

    for m in new:
        mid = m.get("id")
        if mid is not None and mid in index_by_id:
            # 情况 1：新消息带 id，且旧列表里已有同 id → 更新
            # {**旧值, **新值}：新字段覆盖旧字段，未提供的字段保留
            merged[index_by_id[mid]] = {**merged[index_by_id[mid]], **m}
        else:
            # 情况 2：无 id 或 id 没见过 → 追加到末尾
            merged.append(m)

    return merged


class AgentState(TypedDict):
    """Agent 的共享状态。

    📌 TypedDict vs dataclass vs BaseModel：
        · TypedDict 只是"给 dict 加类型标注"，运行时它就是普通 dict（零开销）
        · LangGraph 选它是因为 state 要频繁序列化进 checkpoint，dict 最省事
        · 代价：运行时【不做任何校验】，写错 key 不会报错 → 所以要靠 mypy
    """

    # ★ 关键字段：Annotated[真实类型, reducer 函数]
    #   - 第 0 个参数 list[dict] 是"真实类型"
    #   - 第 1 个参数 add_messages 是"元数据"，LangGraph 约定把它当 reducer
    #   语义：当节点返回新的 messages 时，不是覆盖，而是 add_messages(旧, 新)
    messages: Annotated[list[dict], add_messages]

    # 同理，logs 用标准库的 operator.add 做累加
    # operator.add(["a"], ["b"]) → ["a", "b"]
    logs: Annotated[list[str], operator.add]

    # ⚠️ 注意：没有 Annotated = 没有 reducer = 覆盖式更新
    # 每次节点返回 step_count，旧值会被直接丢掉
    step_count: int
    done: bool
    final_answer: str


# ═════════════════════════════════════════════════════════════
# 2. 手写 reduce_state（LangGraph 的核心机制）
# ═════════════════════════════════════════════════════════════
class UnknownKeyError(KeyError):
    """节点返回了 State 里没声明的 key。

    自定义异常类而不是直接用 KeyError，是为了让调用方可以精确捕获。
    LangGraph 遇到这种情况也会报错（InvalidUpdateError）。
    """
    pass


def get_reducers(state_cls: type) -> dict[str, Any]:
    """从类型标注里把 reducer 提取出来。

    📌 这段是本 Demo 的技术核心，看懂它就懂了 Annotated：
        get_type_hints(cls, include_extras=True)  →  拿到 {'messages': Annotated[list, fn], ...}
        get_origin(t) is Annotated                →  判断这个标注是不是 Annotated
        get_args(t)                               →  (list[dict], fn)  第 0 个是类型，第 1+ 个是元数据
    """
    # ★ include_extras=True 是必须的！
    #   默认 False 时，get_type_hints 会把 Annotated[T, x] 里的 x 剥掉，只返回 T
    #   我们要的恰恰是那个 x（reducer），所以必须显式打开
    hints = get_type_hints(state_cls, include_extras=True)

    reducers: dict[str, Any] = {}
    for name, hint in hints.items():
        # get_origin(Annotated[int, "x"]) → Annotated
        # get_origin(list[int])           → list
        # 所以这一句精确识别"这个字段是不是挂了 Annotated"
        if get_origin(hint) is Annotated:
            # get_args(Annotated[list[dict], fn]) → (list[dict], fn)
            # args[0] 是真实类型，args[1:] 是元数据列表
            args = get_args(hint)

            # 约定：元数据里第一个【可调用的】就是 reducer
            # 为什么要判 callable？因为 Annotated 允许挂任意元数据（字符串、数字都行）
            # LangGraph 的约定是"第一个 callable 就是 reducer"
            for meta in args[1:]:
                if callable(meta):
                    reducers[name] = meta
                    break   # 找到一个就停

    return reducers


# 模块加载时算一次并缓存。
# 为什么不每次调 reduce_state 都算？
#   因为类型标注在运行期不会变，重复解析纯属浪费。
#   和 Pydantic 编译 schema、Django 缓存 ORM 元数据是一个思路。
_REDUCERS = get_reducers(AgentState)


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
    # 拿到 State 声明的所有字段名，用于校验 patch 里的 key 是否合法
    declared = set(get_type_hints(AgentState, include_extras=True).keys())

    # ★ 关键防护：patch 里出现未声明的 key → 报错
    #   为什么必须报错？因为拼错字段名（step_count → step_counter）
    #   如果不报错，就会静默写入一个"没人读"的 key，bug 极难排查
    unknown = set(patch) - declared
    if unknown:
        raise UnknownKeyError(
            f"节点返回了 State 未声明的字段: {sorted(unknown)}；已声明: {sorted(declared)}"
        )

    # 从旧 state 复制一份新 dict，避免原地修改（不可变更新）
    new: dict[str, Any] = dict(old)

    for key, value in patch.items():
        reducer = _REDUCERS.get(key)

        if reducer is not None:
            # ── 有 reducer：合并而不是覆盖 ─────────────
            current = old.get(key)

            # 📌 第一次更新时，旧值可能还不存在
            #   用"空值"兜底：列表字段用 []，其他字段用新值本身
            #   这样 reducer([], [x]) 才能正常工作
            if current is None:
                current = [] if isinstance(value, list) else value

            new[key] = reducer(current, value)
        else:
            # ── 无 reducer：直接覆盖 ────────────────────
            new[key] = value

    # type ignore：TypedDict 的返回类型很难让类型检查器满意，
    # 因为 dict(...) 构造出的是普通 dict，不是 TypedDict 类型
    return new  # type: ignore[return-value]


def run_graph(nodes: list[tuple[str, dict[str, Any]]], init: AgentState) -> list[dict[str, Any]]:
    """模拟 LangGraph 的执行：按顺序跑节点，每个节点返回 patch，合并进 state。

    返回每一步的快照，方便测试断言。

    📌 参数 nodes 是 (节点名, patch) 的列表。
       真实 LangGraph 里"节点"是个函数，返回 patch；这里用预置的 patch 模拟，
       避免引入复杂度，把焦点放在 reducer 机制上。
    """
    state: dict[str, Any] = dict(init)

    # trace 记录每一步的快照（包括初始态），方便回溯与断言
    trace: list[dict[str, Any]] = [{"node": "<init>", "state": dict(state)}]

    for name, patch in nodes:
        # ★ 核心：每个节点返回的 patch 都过一遍 reduce_state
        #   dict(...) 再复制一次是防御性编程，防止外部持有引用后被改
        state = dict(reduce_state(state, patch))   # type: ignore[arg-type]

        # 快照保存 patch 和合并后的完整 state
        trace.append({"node": name, "patch": patch, "state": dict(state)})

    return trace


# ═════════════════════════════════════════════════════════════
# 3. 测试用例（8 个，既能直接跑也能被 pytest 收集）
# ═════════════════════════════════════════════════════════════
def initial() -> AgentState:
    """返回一个干净的初始 state。

    为什么写成函数而不是常量？
      dict 是可变对象，如果写成模块级常量 INITIAL = {...}，
      每个测试共享同一个对象，一个测试改了会影响另一个。
      返回函数每次调用生成新对象，隔离更彻底。
    """
    return {"messages": [], "logs": [], "step_count": 0, "done": False, "final_answer": ""}


def test_reducer_registered() -> None:
    """① Annotated 里的 reducer 被正确识别出来。"""
    # messages 和 logs 挂了 reducer；其他字段没有
    assert set(_REDUCERS) == {"messages", "logs"}, _REDUCERS
    # logs 用的是标准库 operator.add，验证解析出来的就是它
    assert _REDUCERS["logs"] is operator.add


def test_messages_accumulate() -> None:
    """② messages 累加（这是最核心的行为）。"""
    s = reduce_state(initial(), {"messages": [{"role": "user", "content": "hi"}]})
    s = reduce_state(s, {"messages": [{"role": "assistant", "content": "hello"}]})

    # 两次写入应该得到 2 条；如果忘了 reducer，只会剩 1 条
    assert len(s["messages"]) == 2, f"应该累加成 2 条，实际 {len(s['messages'])}"
    assert s["messages"][1]["content"] == "hello"


def test_scalar_overwrite() -> None:
    """③ 无 reducer 的字段是覆盖式更新。"""
    s = reduce_state(initial(), {"step_count": 1})
    s = reduce_state(s, {"step_count": 2})

    # ★ 注意语义：这里是覆盖，不是累加。2 覆盖了 1，结果还是 2
    #   如果 step_count 也挂了 operator.add，结果会是 3
    assert s["step_count"] == 2, "step_count 应该被覆盖成 2，而不是累加成 3"


def test_messages_update_by_id() -> None:
    """④ add_messages 支持按 id 更新（不是无脑追加）。"""
    s = reduce_state(initial(), {"messages": [{"id": "m1", "role": "assistant", "content": "v1"}]})
    s = reduce_state(s, {"messages": [{"id": "m1", "content": "v2"}]})

    # 同 id → 更新，不是追加，所以还是 1 条
    assert len(s["messages"]) == 1, "同 id 应该是更新，不是追加"
    assert s["messages"][0]["content"] == "v2"

    # ★ 关键：更新是"合并"而不是"替换"
    #   新消息只给了 content，没给 role；role 应该保留
    assert s["messages"][0]["role"] == "assistant", "更新时应保留未提供的字段"


def test_unknown_key_raises() -> None:
    """⑤ 未声明的 key 必须报错（否则拼写错误会静默失效，极难排查）。"""
    try:
        # 故意写错：step_count → step_counter
        reduce_state(initial(), {"step_counter": 1})
    except UnknownKeyError as e:
        # 验证错误信息里确实指出了错的那个 key
        assert "step_counter" in str(e)
    else:
        # ★ try/except/else 结构：
        #   没有异常时执行 else 分支，这里主动抛断言失败
        raise AssertionError("应该抛 UnknownKeyError 但没有")


def test_no_reducer_would_lose_data() -> None:
    """⑥ 对照实验：如果 messages 没挂 reducer，数据会被覆盖丢失。

    这就是 LangGraph 新手第一大坑的复现。

    📌 这个测试的意义：用"反例"证明 reducer 的必要性。
       看懂这条，比单纯记住"要写 Annotated"更有价值。
    """
    class BadState(TypedDict):
        # ⚠️ 忘了写 Annotated，就没有 reducer
        messages: list[dict]

    def reduce_bad(old: dict, patch: dict) -> dict:
        # 默认合并语义 = 直接覆盖（{**old, **patch} 是最朴素的实现）
        return {**old, **patch}

    s: dict = {"messages": []}
    s = reduce_bad(s, {"messages": [{"role": "user", "content": "hi"}]})
    s = reduce_bad(s, {"messages": [{"role": "assistant", "content": "hello"}]})

    # 第一条被第二条覆盖了，只剩 1 条
    assert len(s["messages"]) == 1, "没有 reducer 时应该只剩 1 条（第一条被覆盖了）"
    assert s["messages"][0]["role"] == "assistant"


def test_full_graph_run() -> None:
    """⑦ 完整跑一遍"图"，验证 state 演变过程。"""
    trace = run_graph([
        # 每个元组是 (节点名, 该节点返回的 patch)
        ("agent",   {"messages": [{"role": "user", "content": "1+1=?"}], "step_count": 1}),
        ("tools",   {"messages": [{"role": "tool", "content": "2"}], "logs": ["调用 calculator"]}),
        ("agent",   {"messages": [{"role": "assistant", "content": "等于 2"}], "step_count": 2}),
        ("finish",  {"done": True, "final_answer": "等于 2", "logs": ["任务完成"]}),
    ], initial())

    final = trace[-1]["state"]

    # 4 个节点里有 3 个写了 messages（agent/tools/agent），finish 只改标量字段
    # 所以最终 messages 长度是 3（reducer 累加的结果）
    assert len(final["messages"]) == 3, f"messages 应累加成 3 条，实际 {len(final['messages'])}"

    # step_count 被覆盖了两次（1 → 2），最终是 2
    assert final["step_count"] == 2, "step_count 应该是最后的 2（覆盖）"

    # logs 用 operator.add 累加两次，得到两条
    assert final["logs"] == ["调用 calculator", "任务完成"], "logs 用 operator.add 累加"

    assert final["done"] is True

    # 验证 trace 的节点顺序（第一个是 <init>）
    assert [t["node"] for t in trace] == ["<init>", "agent", "tools", "agent", "finish"]


def test_typed_dict_is_plain_dict() -> None:
    """⑧ TypedDict 运行时就是普通 dict（零开销，但也不做校验）。"""
    s = initial()
    assert isinstance(s, dict)

    # ★ 关键：type(s) 就是 dict，不是某个"AgentState 类"的实例
    #   TypedDict 是纯静态检查工具，运行时零开销也零校验
    assert type(s) is dict, "TypedDict 不会创建新类型，运行时就是 dict"

    # ⚠️ 证明它不做运行时校验：写错类型也不报错（只有 mypy 会拦）
    bad: Any = {"step_count": "不是数字"}     # 标成 Any 是为了让 mypy 也别拦，专注展示运行时行为
    merged = reduce_state(s, bad)

    # 字符串"不是数字"照样写进去了，没有校验
    assert merged["step_count"] == "不是数字", "TypedDict 不做运行时类型校验！"


# ═════════════════════════════════════════════════════════════
# 入口：不使用 pytest 时也能直接运行
# ═════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # 收集当前模块里所有 test_ 开头的可调用对象
    # sorted 保证执行顺序稳定（虽然测试之间无依赖）
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]

    passed = 0
    print("═" * 68)
    print(f"TypedDict + Annotated reducer 实验（{len(tests)} 个用例）")
    print("═" * 68)

    for name, fn in tests:
        try:
            fn()
        except AssertionError as e:
            # 断言失败：打印测试名和具体失败信息
            print(f"  ❌ {name}: {e}")
        else:
            # 通过：计数器 +1，并打印测试文档字符串的第一行
            passed += 1
            # fn.__doc__.strip().splitlines()[0] 取文档字符串第一行做简要说明
            print(f"  ✅ {name}   {fn.__doc__.strip().splitlines()[0]}")

    print(f"\n{passed}/{len(tests)} 通过")

    # ── 演示：一次完整执行的 state 演变 ────────────────
    print("\n═══ 一次完整执行的 state 演变 ═══")
    for step in run_graph([
        ("agent",  {"messages": [{"role": "user", "content": "1+1=?"}], "step_count": 1}),
        ("tools",  {"messages": [{"role": "tool", "content": "2"}], "logs": ["调用 calculator"]}),
        ("finish", {"done": True, "final_answer": "等于 2"}),
    ], initial()):
        st = step["state"]
        # :<7 是左对齐宽度 7，让输出列对齐
        print(f"  [{step['node']:<7}] messages={len(st['messages'])} logs={len(st['logs'])} "
              f"step={st['step_count']} done={st['done']}")

    # ── 收尾：三句话总结 reducer 的必要性 ──────────────
    print("\n═══ LangGraph 为什么需要 reducer（3 句话，背下来）═══")
    print("  ① 节点返回的是【部分更新】dict，不是完整 state")
    print("  ② 默认合并语义是【覆盖】，所以 list 字段会被整个替换掉")
    print("  ③ 并行节点同时写同一个 key 时，覆盖会导致「只能有一个值」的错误")
    print("  → 所有需要累积的字段（messages / logs / 工具调用记录）都必须挂 reducer")

    # 用退出码反映测试结果：全通过 0，否则 1
    # 这是 UNIX 工具约定，方便 CI 判断
    raise SystemExit(0 if passed == len(tests) else 1)