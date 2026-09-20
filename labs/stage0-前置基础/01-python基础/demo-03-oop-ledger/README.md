# Demo 01-3 · 面向对象记账本

> **对应文档**：[01-Python基础.md → Demo 01-3](../../../../my-docs/study01/stage0-前置基础/01-Python基础.md)
> **依赖**：无　**预计耗时**：2 小时
> **练什么**：ABC 抽象基类、dataclass、继承与多态、`@property/@classmethod/@staticmethod`、魔术方法、序列化往返

## 一、它的真实身份
这是 **LangChain `BaseTool` 设计模式的复刻**：

```
Record(ABC)            ←→   BaseTool
  ├─ Income                   ├─ SearchTool
  ├─ Expense                  ├─ CalculatorTool
  └─ Refund（后加的）          └─ 你后来新加的工具

Ledger.add(record: Record)  ←→  AgentExecutor 拿到一堆 tool
  只依赖抽象类型，不关心具体实现
```
面试问「框架怎么做到加新工具不用改核心代码」，拿这个 Demo 答（**开闭原则**），比背概念有说服力。

## 二、目录
```
demo-03-oop-ledger/
├── ledger.py         ← 核心：Record(ABC) + 3 个子类 + Ledger（约 300 行，含教学注释）
├── ledger_demo.py    ← 账本报表演示（对应任务书的预期输出）
├── run.sh            ← 4 个场景，含"可变默认参数陷阱"的现场复现
└── data/ledger.json  ← 运行后生成
```

## 三、一步一步做
1. `bash run.sh` —— 4 个场景：
   - ① 自测（抽象基类生效 / default_factory 生效 / 多态 / 往返一致）
   - ② 账本报表
   - ③ 生成的 JSON（注意 `_kind` 类型标签）
   - ④ **现场复现可变默认参数 bug**（`Wrong` vs `Right` 两个 dataclass 对比）
2. 读 `ledger.py`，重点看 5 个 `📌 教学点`：
   - `Record` 的 ABC 作用不是少写代码，而是**让错误在实例化时就暴露**
   - `Expense.amount()` 返回负数 —— 把类型判断封装在子类里，Ledger 不用 `isinstance`
   - `field(default_factory=list)` 为什么不能写成 `= []`
   - `to_dict()` 里的 `_kind` **类型标签**（Pydantic 的 discriminator、JSON 的 @type 都是这个套路）
   - `@classmethod load()` 是工厂方法，`@staticmethod money()` 只是命名空间归属
3. **动手加一个新子类**（这是本 Demo 的核心练习，见下）

## 四、预期输出
```
✅ 抽象基类生效：Record() → TypeError: Can't instantiate abstract class Record
   without an implementation for abstract methods 'amount', 'describe'
✅ default_factory 生效：a.tags 修改不影响 b.tags

==============================================================
  小明 的 9 月账本    （8 条记录）
==============================================================
  收入 + 12000.00  9月工资（公司） [主业]
  支出   -2400.00  房租（住房）
  ...
  退款 +   400.00  退货：机械键盘（原分类 数码）
--------------------------------------------------------------
  总收入    12,400.00
  总支出    -8,000.90
  结　余     4,399.10

分类支出：
  数码      -3580.00  █████████████████
  住房      -2400.00  ████████████
  ...
已保存到 data/ledger.json，重新加载后条目数 = 8 ✅ 往返一致

★ 开闭原则验证：Refund 类是后加的，Ledger 一行代码都没改，
  但它已被正确统计进结余：['退货：机械键盘']
```

## 五、跑出来的两个反直觉现象（都已写进代码注释）

### ① `@dataclass` 会**主动禁止**可变默认值
```python
@dataclass
class Wrong:
    tags: list = []     # ValueError: mutable default <class 'list'> for field tags
                        #             is not allowed: use default_factory
```
报错发生在**定义类的那一刻**，不是实例化时。所以 dataclass 比手写 `__init__` 更安全。
而普通函数的 `def f(x=[])` 和普通类属性 `items = []` **Python 完全不拦你** —— `run.sh` 场景 4
用三种写法做了对照：函数默认参数会累积（`['a']` → `['a','b']`），类属性会被所有实例共享。

### ② 自定义 `__repr__` 不生效
`Record.__repr__` **不生效**：`@dataclass` 默认自己生成 `__repr__`，子类的覆盖了父类的。
打印出来是 `Expense(title='房租', value=2400, ...)` 而不是我写的 `Expense(-2400.00, '房租')`。
想用自己的版本要写 `@dataclass(repr=False)`。而 `__str__` 不会被 dataclass 生成，所以它生效了。
→ **这类"我以为覆盖了其实没有"的行为，只有真跑一次才会发现。**

## 六、练习题
| # | 难度 | 题目 | 验收 |
|---|---|---|---|
| 1 | ⭐⭐ | 新增 `Investment(Record)` 子类（基金定投，有收益率），**不许改 Ledger 一行代码** | `total()` 自动包含它 |
| 2 | ⭐⭐ | 给 `Ledger` 加 `monthly_report()` 返回按月分组的 dict，用 `defaultdict(list)` | 覆盖跨月数据 |
| 3 | ⭐⭐ | 把金额从 `float` 换成 `decimal.Decimal`，验证 `0.1+0.2` 的精度问题被解决 | `Decimal("0.1")+Decimal("0.2") == Decimal("0.3")` |
| 4 | ⭐⭐⭐ | 用 `Protocol` 重写 `Record`（结构化子类型，不需要显式继承），对比两种方式的差别 | 能说出 Protocol 是"鸭子类型的静态版" |
| 5 | ⭐⭐⭐ | 给 `save/load` 加版本号 `schema_version`，并让 `load` 能读旧版本文件（向后兼容） | 造一个 v1 的 JSON 能被 v2 代码读出 |

## 七、验收清单
- [ ] `Record()` 直接实例化抛 `TypeError`
- [ ] 新增 `Refund` / 练习 1 的 `Investment` 都**不需要改 Ledger**
- [ ] `save` → `load` 往返一致（条目数、金额、**类型**都不丢）
- [ ] 能说出 `tags: list = []` 为什么是 bug（并现场复现过）
- [ ] 能区分 `@property` / `@classmethod` / `@staticmethod` 各自的使用场景
- [ ] 能口头答：`__str__` 和 `__repr__` 的区别，以及为什么这里 `__repr__` 没生效

## 八、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
| | | | |
