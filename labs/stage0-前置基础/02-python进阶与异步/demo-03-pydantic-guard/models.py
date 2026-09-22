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

# StrEnum 是 Python 3.11+ 标准库引入的，配合 __future__ import annotations
# 在旧版本也能写出 "str 语义的枚举"
from enum import StrEnum

# typing 里的三个工具：
#   Annotated → 给类型附加元数据（这里用来给 int 附上 Field 约束）
#   Any       → 表示"任意类型"，多用于 validator 的入参
#   Literal   → 字面量类型，取值只能是列出的那几个字符串
from typing import Annotated, Any, Literal

# Pydantic v2 的核心组件：
#   BaseModel       → 所有模型的基类
#   ConfigDict      → 模型级配置（extra="forbid" 之类）
#   Field           → 字段级约束与元数据（description/ge/le/...）
#   field_validator → 单字段校验钩子（before/after 两种时机）
#   model_validator → 整模型校验钩子（跨字段、跨步骤逻辑）
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
    # 三个成员都是字符串字面量，等价于 Literal["safe", "sensitive", "dangerous"]
    # 但 Enum 的好处是可以挂方法、可以迭代、名字更语义化
    SAFE = "safe"
    SENSITIVE = "sensitive"
    DANGEROUS = "dangerous"


class ToolCall(BaseModel):
    """一次工具调用意图（对应 OpenAI 的 message.tool_calls[i]）。"""

    # extra="forbid"：出现未声明字段时直接报错，而不是静默丢弃
    # 为什么要 forbid？因为"模型自己加字段"往往是幻觉的信号，静默忽略会掩盖问题
    model_config = ConfigDict(extra="forbid")

    # ── 字段定义：名字、类型、约束、给模型的提示词 ──────────
    name: str = Field(
        min_length=1, max_length=64,
        # description 不是注释！它会进入导出的 JSON Schema，
        # 最终成为 Function Calling 里给模型看的提示词，影响调用准确率
        description="工具名，必须是注册表里存在的名字，动词开头如 read_file",
    )
    # default_factory=dict：每个实例拿一个全新的空 dict，避免可变默认值共享的坑
    args: dict[str, Any] = Field(default_factory=dict, description="工具参数，键值对")
    # str | None 表示可省略；default=None 让它真的可选
    call_id: str | None = Field(default=None, description="对应 API 返回的 tool_call_id")

    # ── 校验钩子 1：规范化 name ────────────────────────────
    # mode="before" → 在 Pydantic 跑类型/约束校验【之前】先跑这个函数
    # 用途是"归一化"：把模型的脏写法修成标准写法，从而救回本会失败的样本
    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, v: Any) -> Any:
        """LLM 常犯的错：名字前后带空格、带引号、带 markdown 反引号。"""
        if isinstance(v, str):
            # strip() 去首尾空白；strip("`'\"") 再去首尾的三种引号字符
            # 例如 "`read_file`" → "read_file"，"\"read_file\"" → "read_file"
            return v.strip().strip("`'\"")
        return v  # 非字符串原样返回，让 Pydantic 后面给出真正的类型错误

    # ── 校验钩子 2：把 args 从"字符串形式"救回来 ─────────
    @field_validator("args", mode="before")
    @classmethod
    def _args_from_string(cls, v: Any) -> Any:
        """★ 高频坑：OpenAI 的 tool_calls[].function.arguments 是【JSON 字符串】不是 dict。
        很多模型/SDK 会直接给你 '{"path": "a.txt"}' 这样的字符串。
        另外模型也常输出 "args": null（本该省略却写了 null）。
        这里统一兼容：null → {}，字符串 → json.loads，失败则报清晰的错。"""
        # 情况 1：None（模型本该省略却写了 null）→ 统一成 {}
        if v is None:
            return {}

        # 情况 2：字符串 → 尝试当 JSON 解析
        if isinstance(v, str):
            # 局部 import：json 在这个函数里才用到，放局部减少顶层依赖
            import json
            s = v.strip()
            if not s:
                # 空字符串也当成 {}（模型经常输出 ""）
                return {}
            try:
                # 把 '{"path": "a.txt"}' 解析成 {"path": "a.txt"}
                return json.loads(s)
            except json.JSONDecodeError as e:
                # 解析失败 → 抛带位置信息的 ValueError
                # from e 保留原始异常链，便于调试
                raise ValueError(f"args 是字符串但不是合法 JSON: {e.msg} (位置 {e.pos})") from e

        # 情况 3：已经是 dict（或别的类型），交给 Pydantic 后续处理
        return v


class AgentStep(BaseModel):
    """Agent 的一步：思考 → (可选)动作 → (可选)观察。"""

    model_config = ConfigDict(extra="forbid")

    # ── 字段 ─────────────────────────────────────────────
    # thought 必填，且至少 1 个字符（空思考是无意义的）
    thought: str = Field(min_length=1, description="这一步的推理，一句话")

    # action 可以为 None：允许"只思考、不调工具"的一步（比如准备结束）
    action: ToolCall | None = Field(default=None, description="允许只思考不调工具")

    # observation 是工具返回值，也可以为 None（还没执行）
    observation: str | None = Field(default=None, description="工具返回结果")

    # Annotated[int, Field(ge=0, le=600_000)]：
    #   - 类型是 int
    #   - 附加约束：0 <= 值 <= 600000（毫秒，最长 10 分钟）
    # 用 Annotated 而不是 Field(ge=...) 直接写在赋值里，是为了让"类型 + 约束"更紧凑
    latency_ms: Annotated[int, Field(ge=0, le=600_000)] = 0

    # risk 是枚举，默认 SAFE；传入值必须是 safe/sensitive/dangerous 之一
    risk: Risk = Risk.SAFE

    # ── 校验钩子 1：把各种"数字写法"统一成 int 毫秒 ──────
    @field_validator("latency_ms", mode="before")
    @classmethod
    def _coerce_latency(cls, v: Any) -> Any:
        """LLM 常把数字写成字符串："120"、"120ms"、"1,200"、"0.12s"。
        这里统一归一成 int 毫秒。**在 before 阶段做，才能救回本来会失败的校验。**"""
        # None 或空字符串 → 视为 0（模型省略了耗时）
        if v is None or v == "":
            return 0

        if isinstance(v, str):
            # 去空白、去千分位逗号、转小写（统一 "MS"/"ms"、"S"/"s"）
            s = v.strip().replace(",", "").lower()
            mult = 1  # 单位换算因子，默认按毫秒
            if s.endswith("ms"):
                # "120ms" → "120"
                s = s[:-2]
            elif s.endswith("s"):
                # "0.12s" → "0.12"，且换算因子变 1000
                s, mult = s[:-1], 1000
            try:
                # 先转 float 再转 int，兼容 "0.12" 这种小数
                return int(float(s.strip()) * mult)
            except ValueError:
                # 转不成数字 → 抛带原文的 ValueError
                # from None 表示不保留原始 ValueError 链，让错误信息更干净
                raise ValueError(f"latency_ms 无法解析为数字: {v!r}") from None
        return v  # 已经是数字类型，原样交给 Pydantic

    # ── 校验钩子 2：空字符串统一成 None ──────────────────
    @field_validator("observation", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Any:
        """空字符串统一成 None，避免下游到处写 if obs == "" or obs is None。"""
        # 注意这里是三元表达式：只有当 v 是"全空白字符串"时才换成 None
        return None if isinstance(v, str) and not v.strip() else v


class AgentTrace(BaseModel):
    """一次完整的 Agent 执行轨迹。"""

    model_config = ConfigDict(extra="forbid")

    # ── 顶层字段 ─────────────────────────────────────────
    session_id: str = Field(min_length=1)
    # steps 至少 1 步；min_length 对 list 表示"元素个数最少 1"
    steps: list[AgentStep] = Field(min_length=1, description="至少一步")
    # 非负整数，默认 0
    total_cost_tokens: int = Field(default=0, ge=0)
    finished: bool = False
    # Literal 限定取值只能是这三个字符串之一；
    # 导出 schema 时会变成 enum 约束，模型层面就被限死了
    mode: Literal["react", "plan_execute", "supervisor"] = "react"

    # ── 跨字段校验：单字段校验做不到的事 ──────────────────
    # mode="after"：拿到的是【已经过完所有字段校验的模型实例】，
    # 因此可以直接 s.action / s.observation 访问属性（而不是 raw dict）
    @model_validator(mode="after")
    def check_action_observation(self) -> AgentTrace:
        """跨字段校验：有 action 就必须有 observation（否则说明工具没执行或结果丢了）。

        📌 mode="after" 拿到的是【已校验完成的模型实例】，可以访问所有字段；
           mode="before" 拿到的是原始 dict，适合做归一化。
        """
        # enumerate 给出 (索引, 元素)，索引用于报错时指出是第几步
        for i, s in enumerate(self.steps):
            # 规则 1：有 action 却没 observation → 工具调了但结果没回填
            if s.action is not None and s.observation is None:
                raise ValueError(f"steps[{i}] 有 action 但缺 observation（工具结果未回填）")
            # 规则 2：有 observation 却没有 action → 凭空出现的工具结果（幻觉）
            if s.action is None and s.observation is not None:
                raise ValueError(f"steps[{i}] 有 observation 但没有 action（凭空出现的工具结果）")

        # 注意：model_validator(mode="after") 必须返回 self
        # 返回别的对象会替换掉最终实例，所以这里务必返回 self
        return self

    # ── 派生属性：从已有数据算出来的便捷访问 ──────────────
    @property
    def tool_names(self) -> list[str]:
        """用了哪些工具（@property 让方法看起来像属性，调用方不用加括号）。"""
        # 列表推导：遍历每一步，跳过没 action 的，取 action.name
        # 调用方写 trace.tool_names 而不是 trace.tool_names()
        return [s.action.name for s in self.steps if s.action]


# ═════════════════════════════════════════════════════════════
# 导出 JSON Schema —— 这就是 Function Calling 里 parameters 的来源
# ═════════════════════════════════════════════════════════════
def tool_call_schema() -> dict[str, Any]:
    """把 ToolCall 转成 OpenAI tools 数组里的一个元素。"""
    # model_json_schema() 是 Pydantic v2 提供的：根据模型定义自动生成 JSON Schema
    # 里面会包含 description、约束（minimum/minLength/enum）、required 等
    schema = ToolCall.model_json_schema()

    # 按 OpenAI Chat Completions API 的 tools 参数格式组装
    return {
        "type": "function",  # 固定值，OpenAI 用这个字段区分工具类型
        "function": {
            # 工具名（这是"函数名"，不是模型里的字段名），可以任取
            "name": "agent_step_action",
            # 给模型的整体说明，帮助它判断何时调用
            "description": "Agent 的一步动作。name 必须是已注册工具，args 是它的参数。",
            # parameters 就是模型要"填充"的参数结构，直接复用 ToolCall 的 properties/required
            "parameters": {
                "type": "object",
                # schema.get(..., {})：如果模型没有属性就返回空对象，避免 KeyError
                "properties": schema.get("properties", {}),
                "required": schema.get("required", []),
                # additionalProperties=False：明确告诉模型"不要加额外字段"
                # 与模型层 extra="forbid" 相呼应，双保险
                "additionalProperties": False,
            },
        },
    }


if __name__ == "__main__":
    # 直接 `python models.py` 时，打印两份 schema 方便肉眼检查
    import json
    print("═══ ToolCall 的 JSON Schema（Function Calling 的 parameters 就长这样）═══")
    print(json.dumps(ToolCall.model_json_schema(), ensure_ascii=False, indent=2))
    print("\n═══ 包装成 OpenAI tools 数组元素 ═══")
    # 只打印前 600 字符，避免长输出刷屏
    print(json.dumps(tool_call_schema(), ensure_ascii=False, indent=2)[:600], "...")