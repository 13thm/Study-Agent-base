# Demo 02-3 · Pydantic 校验器（LLM 输出守门员）

> **任务书**：[02-Python进阶与异步编程.md → Demo 02-3](../../../../my-docs/study01/stage0-前置基础/02-Python进阶与异步编程.md)
> **依赖**：`pydantic>=2.7`　**耗时**：2.5 小时　**练什么**：Pydantic v2 全套、`ValidationError.errors()`、JSON Schema 导出

## 一、真实身份
这是**阶段 1 模块 03「结构化输出专项」的地基**，也是阶段 3 Agent 的
`Action / Observation / Plan` 模型的写法模板。所有"让 LLM 输出合法结构"的努力都从这里开始。

## 二、文件
```
demo-03-pydantic-guard/
├── models.py       ← 3 个模型（ToolCall / AgentStep / AgentTrace）+ Schema 导出
├── guard.py        ← 3 个实验的驱动脚本
├── samples.jsonl   ← 20 条样本（12 合法 / 8 脏，每条都标注了 kind）
└── run.sh
```

## 三、跑
```bash
bash run.sh
```

## 四、预期输出（我的实测）
```
实验 ① 脏数据清洗：20 条样本
  ✅ s02 [合法-数字是字符串]   🔧 latency_ms '120' → 120
  ✅ s03 [合法-args是JSON字符串] 🔧 latency_ms '340ms' → 340; args 字符串 → dict {'q': 'RAG'}
  ✅ s07 [合法-工具名带反引号]  🔧 name 去反引号 → 'read_file'
  ✅ s08 [合法-latency带单位]   🔧 latency_ms '1.5s' → 1500
  ✅ s09 [合法-千分位]         🔧 latency_ms '1,240' → 1240
  ✅ s12 [合法-args为null]     🔧 args null → {}
  ❌ s13 steps: 列表长度不足（收到 []）                     [type=too_short]
  ❌ s14 steps.0.latency_ms: 数值小于允许的最小值（收到 -5）    [type=greater_than_equal]
  ❌ s15 steps.0.extra_info: 存在未声明字段（extra="forbid"）  [type=extra_forbidden]
  ❌ s16 steps.0.thought: 缺少必填字段                        [type=missing]
  ❌ s17 <root>: 自定义校验未通过 → steps[0] 有 action 但缺 observation
  ❌ s18 steps.0.risk: 取值不在允许的枚举内（收到 'super_dangerous'）
  ❌ s19 session_id: 缺少必填字段
  ❌ s20 steps.0.action.args: 自定义校验未通过 → args 是字符串但不是合法 JSON

一次通过 12/20 = 60%   失败 8
错误类型分布：{'missing': 2, 'value_error': 2, 'too_short': 1, ...}
```

## 五、三个实验各自证明什么
| 实验 | 证明了什么 |
|---|---|
| ① 脏数据清洗 | `field_validator(mode="before")` **救回 6 条**本来会失败的样本（字符串数字/带单位/千分位/args 是 JSON 字符串/工具名带反引号/args 为 null）；`extra="forbid"` 发现"模型自己加字段"；`model_validator(mode="after")` 抓到"有 action 没 observation"这种**单字段校验永远发现不了的逻辑错误** |
| ② 错误回喂 | 把 `e.errors()` 的 `loc`+`type`+`msg` 拼进修复 prompt。为什么有效：给了**具体字段路径**、**错误类型**、**目标 Schema** 三样东西。笼统说"格式不对请重试"，模型会重复犯同样的错。（真实提升数据在阶段 1 模块 03：63.3% → 86.7%） |
| ③ Schema 导出 | `model_json_schema()` 的输出**就是** Function Calling 里 `parameters` 字段。`Field(description=...)` 不是给人看的注释，是**给模型看的提示词** |

## 六、必记的 6 个 Pydantic v2 知识点
1. `mode="before"` 拿到**原始值**（做归一化）；`mode="after"` 拿到**已校验的模型实例**（做跨字段检查）
2. `extra="forbid"` 拒绝未声明字段；`"ignore"` 静默丢弃；`"allow"` 收进 `model_extra`
3. `Literal["a","b"]` / `Enum` → schema 里的 `enum` 约束，**比在 prompt 里写"只能是 a 或 b"强 100 倍**
4. `ValidationError.errors()` 每条含 `type / loc / msg / input / url` —— 这是自动修复的原料
5. `model_validate(dict)` vs `model_validate_json(str)`（后者容错更强，能处理部分类型转换）
6. 嵌套模型会生成 `$defs` + `$ref`，⚠️ 部分厂商的 strict 模式不支持 `$ref`（阶段 1 模块 03 会写 flatten）

## 七、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 加一个 `Budget` 模型：`total_tokens` / `used` / `limit`，用 `model_validator` 校验 `used <= limit` |
| 2 | ⭐⭐ | 给 `AgentStep` 加 `@field_validator("thought")`：长度 < 5 字时报错（防止模型敷衍输出"好的"） |
| 3 | ⭐⭐ | 实现 `auto_repair(raw, model_cls, fake_llm)`：校验失败 → 拼修复 prompt → 调"假 LLM"（就用规则修）→ 再校验，统计修复成功率 |
| 4 | ⭐⭐⭐ | 把 samples.jsonl 扩到 100 条（用代码生成各种脏形态），统计"哪类脏数据最常见"，据此决定优先写哪个 validator |
| 5 | ⭐⭐⭐ | 用 `TypeAdapter(list[AgentStep])` 校验裸列表（不是 BaseModel），说明什么时候需要 TypeAdapter |

## 八、验收清单
- [ ] 20 条样本：12 通过 / 8 失败，与任务书预期一致
- [ ] 能指出 6 条被 `mode="before"` 救回的样本分别是哪个
- [ ] 能说出 `errors()` 的 5 个字段及其用途
- [ ] `python models.py` 能打印出完整 JSON Schema
- [ ] 练习 1~3 完成

## 九、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
| | | | |
