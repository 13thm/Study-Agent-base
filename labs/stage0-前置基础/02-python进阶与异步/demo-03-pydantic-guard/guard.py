#!/usr/bin/env python3
"""LLM 输出守门员 —— Demo 02-3 的驱动脚本。

三个实验：
    ① 脏数据清洗：20 条样本过一遍 Pydantic，统计一次通过率，打印人话版错误
    ② 错误回喂：把 ValidationError.errors() 拼成修复 prompt（阶段 1 模块 03 的雏形）
    ③ JSON Schema 导出：看 Function Calling 的 parameters 从哪来

跑法：python guard.py
"""
from __future__ import annotations

# ── 标准库 ──────────────────────────────────────────────
import json                                  # 读写 JSONL 样本、拼修复 prompt 里的 JSON
from collections import Counter              # 统计"哪种错误出现最多"
from pathlib import Path                     # 跨平台路径处理（比 os.path 更现代）
from typing import Any                       # 类型注解里表示"任意类型"

# ── 本项目模块 ──────────────────────────────────────────
# models.py 里定义的"门"：AgentTrace 是整条轨迹，ToolCall 是单个工具调用
from models import AgentTrace, ToolCall, tool_call_schema
# Pydantic v2 的校验失败异常，异常对象里携带结构化错误列表
from pydantic import ValidationError

# 当前文件所在目录，用于定位同目录下的 samples.jsonl
HERE = Path(__file__).parent
SAMPLES = HERE / "samples.jsonl"


# ═════════════════════════════════════════════════════════════
# 实验 ① 脏数据清洗
# ═════════════════════════════════════════════════════════════

#: 常见错误类型的中文翻译（Pydantic 的 msg 是英文，给用户看要翻译）
#: 键是 Pydantic 内部错误类型字符串，值是中文解释。
#: 为什么要有这张表？因为 Pydantic 的 msg 是英文且措辞偏技术，
#: 而"给模型回喂的修复 prompt"里我们希望用清晰、无歧义的中文。
#: 没收录的类型会 fallback 到原始英文 msg（见 humanize_errors）。
TYPE_ZH = {
    "missing": "缺少必填字段",
    "extra_forbidden": "存在未声明字段（extra=\"forbid\"）",
    "too_short": "列表长度不足",
    "greater_than_equal": "数值小于允许的最小值",
    "less_than_equal": "数值大于允许的最大值",
    "string_too_short": "字符串过短",
    "string_too_long": "字符串过长",
    "enum": "取值不在允许的枚举内",
    "dict_type": "应为对象/字典",
    "list_type": "应为数组",
    "int_parsing": "无法解析为整数",
    "bool_parsing": "无法解析为布尔值",
    "value_error": "自定义校验未通过",
}


def humanize_errors(e: ValidationError) -> list[str]:
    """把 Pydantic 的结构化错误翻译成"人话"。

    📌 e.errors() 的每条结构：
        {"type": "greater_than_equal",     ← 错误类型（机器可读，用于分类统计）
         "loc": ("steps", 0, "latency_ms"),← 出错字段的完整路径（元组）
         "msg": "Input should be >= 0",    ← 英文消息
         "input": -5,                      ← 实际收到的值
         "url": "https://errors.pydantic.dev/..."}

    这两样东西（type 和 loc）是**自动修复的原料**：
    把它们回喂给模型，比笼统说"格式不对"有效得多。
    """
    out = []                                        # 收集每一条翻译后的人话错误

    # e.errors() 返回一个 list[dict]，每个 dict 描述一条错误
    for err in e.errors():

        # loc 是元组，例如 ("steps", 0, "latency_ms")，表示路径
        # 用 "." 连接成 "steps.0.latency_ms"，人读起来更直观
        # 如果是根级错误（loc 为空元组），用 "<root>" 占位
        loc = ".".join(str(x) for x in err["loc"]) or "<root>"

        # type 是机器可读的错误分类，用它去查中文表
        etype = err["type"]
        zh = TYPE_ZH.get(etype, err["msg"])         # 表里没有就退回英文 msg

        # input 是实际收到的值（可能不存在，比如某些 root 级错误）
        raw_input = err.get("input")

        # 输入值可能很长（比如整条 steps 列表），截断到 80 字符避免刷屏
        inp_str = repr(raw_input)
        if len(inp_str) > 80:
            inp_str = inp_str[:80] + f"...(共{len(inp_str)}字符)"

        # 只有确实有 input 时才附上"（收到 ...）"，否则留空
        inp = f"（收到 {inp_str}）" if raw_input is not None else ""

        # 自定义校验器抛的 ValueError，msg 里已经是我们写的中文，直接用它
        # Pydantic 会加前缀 "Value error, "，这里去掉它
        detail = err["msg"].replace("Value error, ", "") if etype == "value_error" else ""

        # 拼成一行：路径 + 中文类型 + 细节 + 实收值 + [type=...]
        # 末尾的 [type=xxx] 是刻意加的：实验①后面会用它做错误分布统计
        line = f"{loc}: {zh}" + (f" → {detail}" if detail else "") + f"{inp}  [type={etype}]"
        out.append(line)

    return out


def parse_agent_trace(raw: dict[str, Any]) -> tuple[AgentTrace | None, list[str]]:
    """解析一条 Agent 轨迹。返回 (对象 或 None, 人话错误列表)。

    📌 为什么返回元组而不是抛异常？
        批量处理 200 条时，你不想写 200 个 try/except。
        和 Demo 01-2 的 parse_line 是同一个设计原则：**预期内的失败用返回值**。
    """
    try:
        # model_validate 是 Pydantic v2 的推荐入口：从 dict 构造并校验
        # 成功返回 (对象, 空错误列表)
        return AgentTrace.model_validate(raw), []
    except ValidationError as e:
        # 失败返回 (None, 人话错误列表)，调用方按 errs 是否为空判断成败
        return None, humanize_errors(e)


def exp1_clean() -> None:
    print("═" * 72)
    print("实验 ① 脏数据清洗：20 条样本（12 条设计成合法，8 条设计成非法）")
    print("═" * 72)

    # 读取 JSONL：每行一个 JSON 对象
    # splitlines() 把整段文本按换行拆成行，if ln.strip() 跳过空行
    rows = [json.loads(ln) for ln in SAMPLES.read_text(encoding="utf-8").splitlines() if ln.strip()]

    ok, failed = 0, 0
    type_counter: Counter[str] = Counter()          # 统计"哪种错误出现最多"

    for r in rows:
        # 每条样本形如 {"id": "s01", "kind": "valid", "raw": {...LLM 输出...}}
        obj, errs = parse_agent_trace(r["raw"])

        if obj is not None:
            # ── 通过校验：打印归一化效果 ────────────────
            ok += 1

            # notes 收集"模型给的脏值被洗成了什么"，让人看到 before 钩子起了作用
            notes = []
            st = obj.steps[0]                        # 只展示第一步，样本设计上第一步就够

            # 如果原始 latency_ms 是字符串（如 "120ms"），说明归一化救回了一条
            if isinstance(r["raw"]["steps"][0].get("latency_ms"), str):
                notes.append(f"latency_ms {r['raw']['steps'][0]['latency_ms']!r} → {st.latency_ms}")

            act = r["raw"]["steps"][0].get("action")

            # 原始 args 是字符串（JSON 字符串），但已成功解析成 dict
            if isinstance(act, dict) and isinstance(act.get("args"), str):
                notes.append(f"args 字符串 → dict {st.action.args}")  # type: ignore[union-attr]

            # 原始 args 是 null，被统一成 {}
            if isinstance(act, dict) and act.get("args") is None:
                notes.append("args null → {}")

            # 原始 name 带反引号（markdown 风格），被 _strip_name 清掉
            if isinstance(act, dict) and "`" in str(act.get("name", "")):
                notes.append(f"name 去反引号 → {st.action.name!r}")  # type: ignore[union-attr]

            note = f"   🔧 {'; '.join(notes)}" if notes else ""
            print(f"  ✅ {r['id']} [{r['kind']}]{note}")

        else:
            # ── 校验失败：打印人话错误并统计类型 ────────
            failed += 1
            print(f"  ❌ {r['id']} [{r['kind']}]")
            for m in errs:
                print(f"       · {m}")
                # 从 "xxx [type=missing]" 里抽出 "missing" 并计数
                # m.split("[type=")[-1] → "missing]"；rstrip("]") → "missing"
                type_counter[m.split("[type=")[-1].rstrip("]")] += 1

    print(f"\n一次通过 {ok}/{len(rows)} = {ok / len(rows):.0%}   失败 {failed}")
    # most_common() 按出现次数降序返回 (类型, 次数) 列表
    print(f"错误类型分布：{dict(type_counter.most_common())}")
    print("""
📌 结论（把它写进 README）：
   · field_validator(mode="before") 救回了 5 条本来会失败的样本
     （字符串数字 / 带单位 / 千分位 / args 是 JSON 字符串 / 工具名带反引号）
   · extra="forbid" 帮我们发现了"模型自己加字段"这种行为（s15）
   · model_validator(mode="after") 抓到了"有 action 没 observation"（s17）——
     这类逻辑错误单字段校验永远发现不了""")


# ═════════════════════════════════════════════════════════════
# 实验 ② 错误回喂（自动修复的雏形）
# ═════════════════════════════════════════════════════════════

# 修复 prompt 的模板。三块内容缺一不可：
#   raw    → 让模型看到自己上次输出了什么
#   errors → 告诉它错在哪、错在哪一类
#   schema → 给它目标形状，避免瞎猜
# 开头强调"只输出 JSON、不要解释、不要围栏"，是为了让返回结果可直接 json.loads
REPAIR_PROMPT = """\
你上次输出的 JSON 未通过校验。请只输出修正后的完整 JSON，不要任何解释、不要 markdown 围栏。

【你上次的输出】
{raw}

【校验错误】
{errors}

【目标 JSON Schema】
{schema}
"""


def build_repair_prompt(raw: dict[str, Any], errs: list[str]) -> str:
    """把原始输出 + 错误列表 + 目标 schema 拼成修复 prompt。"""
    return REPAIR_PROMPT.format(
        # ensure_ascii=False：保留中文，不转成 \uXXXX
        # indent=2：格式化，便于人读（也给模型更清晰的层次）
        raw=json.dumps(raw, ensure_ascii=False, indent=2),
        # 每条错误前加 "- "，形成 markdown 列表
        errors="\n".join(f"- {e}" for e in errs),
        # schema 可能很长，截断到 1200 字符（真实场景可按模型上下文调整）
        schema=json.dumps(AgentTrace.model_json_schema(), ensure_ascii=False)[:1200],
    )


def exp2_repair() -> None:
    print("\n" + "═" * 72)
    print("实验 ② 错误回喂：把结构化错误拼成修复 prompt（阶段 1 模块 03 的雏形）")
    print("═" * 72)

    rows = [json.loads(ln) for ln in SAMPLES.read_text(encoding="utf-8").splitlines() if ln.strip()]

    # 挑一条"缺字段"的失败样本演示
    # next(...) 取第一个匹配项；因为 samples.jsonl 里一定有 s16，所以不会 StopIteration
    target = next(r for r in rows if r["id"] == "s16")

    obj, errs = parse_agent_trace(target["raw"])
    # 断言：s16 是故意设计成失败的，这里必须拿到 None
    # 如果哪天样本改了导致它通过，assert 会立刻爆，提醒你换样本
    assert obj is None

    prompt = build_repair_prompt(target["raw"], errs)
    print(f"样本 {target['id']}（{target['kind']}）的修复 prompt：\n")
    print("─" * 72)
    # 只打印前 900 字符，避免整段 schema 刷屏
    print(prompt[:900] + "\n...(schema 部分已截断)")
    print("─" * 72)
    print("""
📌 为什么这样回喂有效？
   ① 给了【具体字段路径】steps.0.thought，模型知道改哪里
   ② 给了【错误类型】missing，模型知道是"缺"而不是"错"
   ③ 给了【目标 Schema】，模型有明确的形状可对齐
   笼统地说"你的输出格式不对，请重试"—— 模型大概率会重复犯同样的错。

📌 真实的提升数字在阶段 1 模块 03 的 Demo 3-2 里测：
   prompt 模式一次通过率 63.3% → 回喂修复一次后 86.7% → 最终 90%。
   本 Demo 只演示"怎么拼 prompt"，不真的调模型（不花钱、可离线）。""")


# ═════════════════════════════════════════════════════════════
# 实验 ③ JSON Schema 导出
# ═════════════════════════════════════════════════════════════
def exp3_schema() -> None:
    print("\n" + "═" * 72)
    print("实验 ③ JSON Schema 导出 —— Function Calling 的 parameters 从哪来")
    print("═" * 72)

    # ToolCall.model_json_schema() 会产出标准 JSON Schema：
    #   - Field(description=...) → description 字段（给模型看的提示词）
    #   - Field(ge/le/min_length/...) → minimum/maximum/minLength 等约束
    #   - Literal/Enum → enum 约束
    # 这里只打印前 700 字符，避免长输出
    print("ToolCall 的 schema（注意 description 字段，那是【写给模型看的提示词】）：")
    print(json.dumps(ToolCall.model_json_schema(), ensure_ascii=False, indent=2)[:700], "...\n")

    # tool_call_schema() 把上面那份 schema 包装成 OpenAI tools 数组里的一个元素
    # 也就是你平常手写的那一坨 {"type": "function", "function": {...}}
    print("包装成 OpenAI tools 数组的一个元素：")
    print(json.dumps(tool_call_schema(), ensure_ascii=False, indent=2)[:520], "...\n")

    print("""📌 三个要点：
   ① Field(description=...) 不是给人看的注释，是**给模型看的提示词**。
      写"工具名，动词开头如 read_file"比只写"工具名"能显著降低误调用。
   ② Literal / Enum 会转成 schema 里的 enum 约束，
      这比在 prompt 里写"只能是 a 或 b"强 100 倍（约束解码层面就限死了）。
   ③ 嵌套模型会变成 $defs + $ref。⚠️ 部分厂商的 strict 模式不支持 $ref，
      阶段 1 模块 03 的 Demo 3-3 会写一个 flatten_refs() 把嵌套展开。""")


# ═════════════════════════════════════════════════════════════
# 入口
# ═════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # 只有直接 `python guard.py` 时才跑三个实验；
    # 被 import 时不会执行（方便测试或复用其中函数）
    exp1_clean()    # 实验①：清洗 + 统计
    exp2_repair()   # 实验②：拼修复 prompt
    exp3_schema()   # 实验③：导出 schema