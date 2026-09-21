"""Pydantic v2 模型定义 —— Demo 02-3 的"LLM 输出守门员"。

📌 这个文件的真实身份
    阶段 1 模块 03「结构化输出专项」的地基，也是阶段 3 Agent 的
    Action / Observation / Plan 模型的写法模板。

覆盖的知识点：
    · Field 的约束参数（ge/le/min_length/max_length/description）
    · Literal / Enum 枚举约束（比在 prompt 里写"只能是 a 或 b"强 100 倍）
    · @field_validator(mode="before") 做宽松归一化
    · @model_validator(mode="after") 做跨字段校验
    · ConfigDict(extra="forbid") 拒绝未声明字段
    · model_json_schema() → 这就是 Function Calling 的 parameters 来源
    · ValidationError.errors() 的结构（loc / msg / type）→ 自动修复的原料
"""
from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ═════════════════════════════════════════════════════════════
# 枚举：用 Literal 或 Enum 都行，Enum 在需要"带方法的常量"时更好
# ═════════════════════════════════════════════════════════════
class Risk(StrEnum):
    """工具风险等级。

    📌 用 StrEnum（3.11+）而不是 (str, Enum)：
       ruff 的 UP042 会提示这个升级。StrEnum 的成员直接就是 str，
       JSON 序列化、== 比较、f-string 都更符合直觉。
    """
    SAFE = "safe"
    SENSITIVE = "sensitive"
    DANGEROUS = "dangerous"


class ToolCall(BaseModel):
    """一次工具调用意图（对应 OpenAI 的 message.tool_calls[i]）。"""

    model_config = ConfigDict(extra="forbid")   # 多出来的字段直接报错，不静默丢弃

    name: str = Field(
        min_length=1, max_length=64,
        description="工具名，必须是注册表里存在的名字，动词开头如 read_file",
    )
    args: dict[str, Any] = Field(default_factory=dict, description="工具参数，键值对")
    call_id: str | None = Field(default=None, description="对应 API 返回的 tool_call_id")

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, v: Any) -> Any:
        """LLM 常犯的错：名字前后带空格、带引号、带 markdown 反引号。"""
        if isinstance(v, str):
            return v.strip().strip("`'\"")
        return v

    @field_validator("args", mode="before")
    @classmethod
    def _args_from_string(cls, v: Any) -> Any:
        """★ 高频坑：OpenAI 的 tool_calls[].function.arguments 是【JSON 字符串】不是 dict。
        很多模型/SDK 会直接给你 '{"path": "a.txt"}' 这样的字符串。
        另外模型也常输出 "args": null（本该省略却写了 null）。
        这里统一兼容：null → {}，字符串 → json.loads，失败则报清晰的错。"""
        if v is None:
            return {}
        if isinstance(v, str):
            import json
            s = v.strip()
            if not s:
                return {}
            try:
                return json.loads(s)
            except json.JSONDecodeError as e:
                raise ValueError(f"args 是字符串但不是合法 JSON: {e.msg} (位置 {e.pos})") from e
        return v


class AgentStep(BaseModel):
    """Agent 的一步：思考 → (可选)动作 → (可选)观察。"""

    model_config = ConfigDict(extra="forbid")

    thought: str = Field(min_length=1, description="这一步的推理，一句话")
    action: ToolCall | None = Field(default=None, description="允许只思考不调工具")
    observation: str | None = Field(default=None, description="工具返回结果")
    latency_ms: Annotated[int, Field(ge=0, le=600_000)] = 0
    risk: Risk = Risk.SAFE

    @field_validator("latency_ms", mode="before")
    @classmethod
    def _coerce_latency(cls, v: Any) -> Any:
        """LLM 常把数字写成字符串："120"、"120ms"、"1,200"、"0.12s"。
        这里统一归一成 int 毫秒。**在 before 阶段做，才能救回本来会失败的校验。**"""
        if v is None or v == "":
            return 0
        if isinstance(v, str):
            s = v.strip().replace(",", "").lower()
            mult = 1
            if s.endswith("ms"):
                s = s[:-2]
            elif s.endswith("s"):
                s, mult = s[:-1], 1000
            try:
                return int(float(s.strip()) * mult)
            except ValueError:
                raise ValueError(f"latency_ms 无法解析为数字: {v!r}") from None
        return v

    @field_validator("observation", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Any:
        """空字符串统一成 None，避免下游到处写 if obs == "" or obs is None。"""
        return None if isinstance(v, str) and not v.strip() else v


class AgentTrace(BaseModel):
    """一次完整的 Agent 执行轨迹。"""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    steps: list[AgentStep] = Field(min_length=1, description="至少一步")
    total_cost_tokens: int = Field(default=0, ge=0)
    finished: bool = False
    mode: Literal["react", "plan_execute", "supervisor"] = "react"

    @model_validator(mode="after")
    def check_action_observation(self) -> AgentTrace:
        """跨字段校验：有 action 就必须有 observation（否则说明工具没执行或结果丢了）。

        📌 mode="after" 拿到的是【已校验完成的模型实例】，可以访问所有字段；
           mode="before" 拿到的是原始 dict，适合做归一化。
        """
        for i, s in enumerate(self.steps):
            if s.action is not None and s.observation is None:
                raise ValueError(f"steps[{i}] 有 action 但缺 observation（工具结果未回填）")
            if s.action is None and s.observation is not None:
                raise ValueError(f"steps[{i}] 有 observation 但没有 action（凭空出现的工具结果）")
        return self

    @property
    def tool_names(self) -> list[str]:
        """用了哪些工具（@property 让方法看起来像属性，调用方不用加括号）。"""
        return [s.action.name for s in self.steps if s.action]


# ═════════════════════════════════════════════════════════════
# 导出 JSON Schema —— 这就是 Function Calling 里 parameters 的来源
# ═════════════════════════════════════════════════════════════
def tool_call_schema() -> dict[str, Any]:
    """把 ToolCall 转成 OpenAI tools 数组里的一个元素。"""
    schema = ToolCall.model_json_schema()
    return {
        "type": "function",
        "function": {
            "name": "agent_step_action",
            "description": "Agent 的一步动作。name 必须是已注册工具，args 是它的参数。",
            "parameters": {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", []),
                "additionalProperties": False,
            },
        },
    }


if __name__ == "__main__":
    import json
    print("═══ ToolCall 的 JSON Schema（Function Calling 的 parameters 就长这样）═══")
    print(json.dumps(ToolCall.model_json_schema(), ensure_ascii=False, indent=2))
    print("\n═══ 包装成 OpenAI tools 数组元素 ═══")
    print(json.dumps(tool_call_schema(), ensure_ascii=False, indent=2)[:600], "...")
