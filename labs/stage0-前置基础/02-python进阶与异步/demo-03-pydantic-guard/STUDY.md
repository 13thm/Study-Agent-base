## 了解一下注释 

### @model_validator(mode="after")
所有等所有字段都校验完了，我再插手查一遍跨字段规则"

```python
@model_validator(mode="after")
# └──────┬──────┘ └──┬──┘
#  管整个模型     什么时候跑
```
### @field_validator("observation", mode="before")
这个就是在使用的使用需要检验这个observation值
### @property
没有 @property 时:
```python
class AgentTrace(BaseModel):
    steps: list[AgentStep]

    def tool_names(self) -> list[str]:
        return [s.action.name for s in self.steps if s.action]
## 调用：
trace = AgentTrace(...)
trace.tool_names()          # ← 注意括号
```
它是个"方法"，调用方得记得加 ()。

加了 @property 后
```python
class AgentTrace(BaseModel):
    steps: list[AgentStep]

    @property
    def tool_names(self) -> list[str]:
        return [s.action.name for s in self.steps if s.action]
## 调用：

trace = AgentTrace(...)
trace.tool_names            # ← 没有括号！
```
看起来像读一个属性，实际上每次访问都在跑一个函数。


## 学习相关的框架

这个就是对LLM 的一些校验的规则。统一进行了校验规则，使用一些类定义和注解的方式来实现的。
