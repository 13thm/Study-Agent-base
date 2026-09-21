#!/usr/bin/env python3
"""LLM 输出守门员 —— Demo 02-3 的驱动脚本。

三个实验：
    ① 脏数据清洗：20 条样本过一遍 Pydantic，统计一次通过率，打印人话版错误
    ② 错误回喂：把 ValidationError.errors() 拼成修复 prompt（阶段 1 模块 03 的雏形）
    ③ JSON Schema 导出：看 Function Calling 的 parameters 从哪来

跑法：python guard.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from models import AgentTrace, ToolCall, tool_call_schema
from pydantic import ValidationError

HERE = Path(__file__).parent
SAMPLES = HERE / "samples.jsonl"


# ═════════════════════════════════════════════════════════════
# 实验 ① 脏数据清洗
# ═════════════════════════════════════════════════════════════
#: 常见错误类型的中文翻译（Pydantic 的 msg 是英文，给用户看要翻译）
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
    out = []
    for err in e.errors():
        loc = ".".join(str(x) for x in err["loc"]) or "<root>"
        etype = err["type"]
        zh = TYPE_ZH.get(etype, err["msg"])
        raw_input = err.get("input")
        # 输入值太长会刷屏（比如整条 steps），截断到 80 字符
        inp_str = repr(raw_input)
        if len(inp_str) > 80:
            inp_str = inp_str[:80] + f"...(共{len(inp_str)}字符)"
        inp = f"（收到 {inp_str}）" if raw_input is not None else ""
        # 自定义校验器抛的 ValueError，msg 里已经是我们写的中文，直接用它
        detail = err["msg"].replace("Value error, ", "") if etype == "value_error" else ""
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
        return AgentTrace.model_validate(raw), []
    except ValidationError as e:
        return None, humanize_errors(e)


def exp1_clean() -> None:
    print("═" * 72)
    print("实验 ① 脏数据清洗：20 条样本（12 条设计成合法，8 条设计成非法）")
    print("═" * 72)

    rows = [json.loads(ln) for ln in SAMPLES.read_text(encoding="utf-8").splitlines() if ln.strip()]
    ok, failed = 0, 0
    type_counter: Counter[str] = Counter()

    for r in rows:
        obj, errs = parse_agent_trace(r["raw"])
        if obj is not None:
            ok += 1
            # 展示"归一化"的效果：模型给的脏值被洗成了什么
            notes = []
            st = obj.steps[0]
            if isinstance(r["raw"]["steps"][0].get("latency_ms"), str):
                notes.append(f"latency_ms {r['raw']['steps'][0]['latency_ms']!r} → {st.latency_ms}")
            act = r["raw"]["steps"][0].get("action")
            if isinstance(act, dict) and isinstance(act.get("args"), str):
                notes.append(f"args 字符串 → dict {st.action.args}")  # type: ignore[union-attr]
            if isinstance(act, dict) and act.get("args") is None:
                notes.append("args null → {}")
            if isinstance(act, dict) and "`" in str(act.get("name", "")):
                notes.append(f"name 去反引号 → {st.action.name!r}")  # type: ignore[union-attr]
            note = f"   🔧 {'; '.join(notes)}" if notes else ""
            print(f"  ✅ {r['id']} [{r['kind']}]{note}")
        else:
            failed += 1
            print(f"  ❌ {r['id']} [{r['kind']}]")
            for m in errs:
                print(f"       · {m}")
                # 统计错误类型分布，这就是"LLM 最常犯哪些错"的数据
                type_counter[m.split("[type=")[-1].rstrip("]")] += 1

    print(f"\n一次通过 {ok}/{len(rows)} = {ok / len(rows):.0%}   失败 {failed}")
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
    return REPAIR_PROMPT.format(
        raw=json.dumps(raw, ensure_ascii=False, indent=2),
        errors="\n".join(f"- {e}" for e in errs),
        schema=json.dumps(AgentTrace.model_json_schema(), ensure_ascii=False)[:1200],
    )


def exp2_repair() -> None:
    print("\n" + "═" * 72)
    print("实验 ② 错误回喂：把结构化错误拼成修复 prompt（阶段 1 模块 03 的雏形）")
    print("═" * 72)

    rows = [json.loads(ln) for ln in SAMPLES.read_text(encoding="utf-8").splitlines() if ln.strip()]
    # 挑一条"缺字段"的失败样本演示
    target = next(r for r in rows if r["id"] == "s16")
    obj, errs = parse_agent_trace(target["raw"])
    assert obj is None
    prompt = build_repair_prompt(target["raw"], errs)
    print(f"样本 {target['id']}（{target['kind']}）的修复 prompt：\n")
    print("─" * 72)
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
    print("ToolCall 的 schema（注意 description 字段，那是【写给模型看的提示词】）：")
    print(json.dumps(ToolCall.model_json_schema(), ensure_ascii=False, indent=2)[:700], "...\n")
    print("包装成 OpenAI tools 数组的一个元素：")
    print(json.dumps(tool_call_schema(), ensure_ascii=False, indent=2)[:520], "...\n")
    print("""📌 三个要点：
   ① Field(description=...) 不是给人看的注释，是**给模型看的提示词**。
      写"工具名，动词开头如 read_file"比只写"工具名"能显著降低误调用。
   ② Literal / Enum 会转成 schema 里的 enum 约束，
      这比在 prompt 里写"只能是 a 或 b"强 100 倍（约束解码层面就限死了）。
   ③ 嵌套模型会变成 $defs + $ref。⚠️ 部分厂商的 strict 模式不支持 $ref，
      阶段 1 模块 03 的 Demo 3-3 会写一个 flatten_refs() 把嵌套展开。""")


if __name__ == "__main__":
    exp1_clean()
    exp2_repair()
    exp3_schema()
