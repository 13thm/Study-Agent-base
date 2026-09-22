# state

我总结一下就是需要使用reduce 函数来保证多线程的一致性。看是否能不能停换或者替用的关系。

reducer = "当同一个字段被写入多次时，用什么规则合并。"

没 reducer → 默认覆盖，新值替换旧值（messages 会丢历史）

有 reducer → 调用 reducer(旧值, 新值)，按你定义的语义合并

Annotated[list[dict], add_messages] 拆开读就是：

"messages 的真实类型是 list[dict]；每次新值到来时，用 add_messages 和旧值合并，而不是覆盖。"

LangGraph 里所有需要累积的字段（messages、logs、工具调用记录）都必须挂 reducer，否则并行节点同时写会报错、串行写会丢数据。