"""面向对象记账本 —— Demo 01-3 的核心模块。

📌 这个 Demo 的真实身份
────────────────────────────────────────────────────────────
它表面上是"记账本"，实际是 **LangChain `BaseTool` / `BaseChatModel` 的设计模式复刻**：

    Record (抽象基类)          ←→   BaseTool
      ├─ Income                   ├─ 你的搜索工具
      ├─ Expense                  ├─ 你的计算工具
      └─ Refund                   └─ 你后来新加的工具

    Ledger.add(record: Record)  ←→   AgentExecutor 拿到一堆 tool
      只依赖抽象类型，不关心具体是哪种

这就是**开闭原则**：新增一种 Record 子类，Ledger 一行代码都不用改。
面试问「框架怎么做到加新工具不用改核心代码」，拿这个 Demo 回答，比背概念有说服力。

本文件覆盖的知识点：
    · ABC 抽象基类 + @abstractmethod（实例化会抛 TypeError）
    · @dataclass 与 field(default_factory=...)
    · 实例属性 vs 类属性
    · @property / @classmethod / @staticmethod 的区别
    · 继承与 super().__init__()
    · __str__ vs __repr__
    · defaultdict 分组聚合
    · JSON 序列化/反序列化的"往返一致"（round-trip）
────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar


# ═════════════════════════════════════════════════════════════
# 抽象基类：所有记账条目的契约
# ═════════════════════════════════════════════════════════════
class Record(ABC):
    """记账条目的抽象基类（类比 LangChain 的 BaseTool）。

    📌 教学点：ABC 的作用不是"少写代码"，而是"提前报错"
        如果子类忘了实现 amount()，**实例化的那一刻**就抛 TypeError，
        而不是等到运行到 Ledger.total() 时才抛 AttributeError。
        错误越早暴露越好排查 —— 这是抽象基类的全部价值。

    📌 教学点：ClassVar 与类属性
        KIND 用 ClassVar 标注，表示"这是类级别的常量，不是实例字段"。
        dataclass 看到 ClassVar 会跳过它，不会当成 __init__ 的参数。
    """

    #: 子类必须覆盖：条目类型标识，用于序列化时区分类型
    KIND: ClassVar[str] = "base"

    @abstractmethod
    def amount(self) -> float:
        """返回带符号金额：收入为正，支出为负。"""

    @abstractmethod
    def describe(self) -> str:
        """返回人类可读的一行描述。"""

    # ── 通用实现（子类不用重写）─────────────────────────────
    def to_dict(self) -> dict[str, Any]:
        """序列化成 dict，额外带上 _kind 用于反序列化时分辨类型。

        📌 dataclasses.asdict() 会递归把嵌套 dataclass 也转成 dict，很方便。
           但它不知道"这是哪个子类"，所以要手动加 _kind 标记 —— 这叫**类型标签**，
           是所有序列化框架（Pydantic 的 discriminator、JSON 的 @type）都在用的套路。
        """
        d = asdict(self)  # type: ignore[call-overload]
        d["_kind"] = self.KIND
        return d

    def __repr__(self) -> str:
        """__repr__ 给开发者看：目标是"无歧义、可重建"。

        ⚠️ 实测发现：这个自定义 __repr__ **不会生效**！
           因为 @dataclass 默认会自己生成 __repr__（repr=True），子类里的覆盖了父类的。
           打印 Expense 实例看到的是 `Expense(title='房租', value=2400, ...)`。
           想用自己的版本要写 @dataclass(repr=False)，或改 __str__（dataclass 不生成它）。
           —— 这类"我以为覆盖了其实没有"的行为，只有真跑一次才会发现。
        """
        return f"{type(self).__name__}({self.amount():+.2f}, {getattr(self, 'title', '')!r})"

    def __str__(self) -> str:
        # __str__ 给用户看：目标是"可读"。print() 会优先用它。
        return self.describe()


# ═════════════════════════════════════════════════════════════
# 三个具体子类
# ═════════════════════════════════════════════════════════════
@dataclass
class Income(Record):
    """收入。"""

    KIND: ClassVar[str] = "income"

    title: str
    value: float
    source: str = "工资"
    tags: list[str] = field(default_factory=list)
    # ⚠️ 必须写 default_factory=list，不能写 tags: list = []
    #    原因：默认值在【函数定义时】只求值一次，所有实例会共享同一个 list！
    #    a = Income("x", 1); b = Income("y", 2)
    #    a.tags.append("t")  →  b.tags 也变成 ["t"]  ← 这就是著名的可变默认参数陷阱
    #    同样的坑也出现在 def f(x=[]) 上。

    def amount(self) -> float:
        return self.value

    def describe(self) -> str:
        tag_str = f" [{','.join(self.tags)}]" if self.tags else ""
        return f"收入 +{self.value:>9.2f}  {self.title}（{self.source}）{tag_str}"


@dataclass
class Expense(Record):
    """支出。注意 amount() 返回负数 —— 这样 total() 直接求和就行。"""

    KIND: ClassVar[str] = "expense"

    title: str
    value: float
    category: str = "其他"
    tags: list[str] = field(default_factory=list)

    def amount(self) -> float:
        # 📌 设计决策：把"支出记为负数"的逻辑封装在子类里，
        #    而不是让 Ledger.total() 去判断 if isinstance(r, Expense)。
        #    后者会让 Ledger 依赖具体类型，违反开闭原则。
        return -abs(self.value)

    def describe(self) -> str:
        return f"支出 {self.amount():>10.2f}  {self.title}（{self.category}）"


@dataclass
class Refund(Record):
    """退款 —— ★ 这个类是用来验证"开闭原则"的。

    📌 验收要点：新增这个类时，Ledger 的代码**一行都没改**，
       但它自动就被统计进 total()、出现在 describe 列表里。
       试着想象如果用 if/elif 判断类型来写 Ledger，加这个类要改几个地方。
    """

    KIND: ClassVar[str] = "refund"

    title: str
    value: float
    original_category: str = "其他"

    def amount(self) -> float:
        return abs(self.value)     # 退款是正向流入

    def describe(self) -> str:
        return f"退款 +{self.value:>9.2f}  {self.title}（原分类 {self.original_category}）"


# ═════════════════════════════════════════════════════════════
# Ledger：只依赖抽象类型 Record
# ═════════════════════════════════════════════════════════════
class Ledger:
    """记账本。注意它的所有方法签名里只有 `Record`，没有任何具体子类。"""

    #: 反序列化用的类型注册表（类属性，所有实例共享）
    _REGISTRY: ClassVar[dict[str, type[Record]]] = {
        "income": Income,
        "expense": Expense,
        "refund": Refund,
    }

    def __init__(self, owner: str = "我", records: list[Record] | None = None) -> None:
        self.owner = owner
        # 📌 又一个可变默认参数的正确写法：
        #    def __init__(self, records=[]) 是错的，None + 内部创建才对。
        self.records: list[Record] = records if records is not None else []
        self.created_at = datetime.now().isoformat(timespec="seconds")

    # ── 增 ────────────────────────────────────────────────
    def add(self, record: Record) -> None:
        """多态入口：任何 Record 子类都能进来，Ledger 不需要知道它是什么。"""
        if not isinstance(record, Record):
            # 📌 类型注解只是"提示"，运行时不强制。真要防呆得自己检查。
            #    mypy 会在写代码时就拦住，但动态传入的数据（如反序列化）需要运行时校验。
            raise TypeError(f"只接受 Record 子类，收到 {type(record).__name__}")
        self.records.append(record)

    def add_all(self, *records: Record) -> None:
        """练 *args：一次加多条。"""
        for r in records:
            self.add(r)

    # ── 查 ────────────────────────────────────────────────
    def total(self) -> float:
        """结余 = 所有条目带符号金额之和。

        📌 sum() 的第二个参数是初始值。浮点求和会有精度误差
           （0.1 + 0.2 = 0.30000000000000004），生产环境算钱要用 decimal.Decimal。
           这里用 round() 兜一下，够教学用。
        """
        return round(sum(r.amount() for r in self.records), 2)

    def income_total(self) -> float:
        return round(sum(r.amount() for r in self.records if r.amount() > 0), 2)

    def expense_total(self) -> float:
        return round(sum(r.amount() for r in self.records if r.amount() < 0), 2)

    def by_category(self) -> dict[str, float]:
        """按分类汇总支出，降序返回。

        📌 defaultdict(float) 的用法：访问不存在的 key 时自动创建 0.0，
           省掉 if key not in d: d[key] = 0 这两行。
        """
        agg: defaultdict[str, float] = defaultdict(float)
        for r in self.records:
            # 只有 Expense 有 category 属性 —— 这里用 getattr 做鸭子类型判断，
            # 而不是 isinstance(r, Expense)，这样未来任何"带分类的条目"都能被统计。
            cat = getattr(r, "category", None) or getattr(r, "original_category", None)
            if cat and r.amount() < 0 or cat and r.amount() > 0:
                agg[cat] += r.amount()
        return dict(sorted(agg.items(), key=lambda kv: kv[1]))

    def top_expense(self, n: int = 5) -> list[Record]:
        """支出金额最大的前 N 条（绝对值降序）。"""
        expenses = [r for r in self.records if r.amount() < 0]
        return sorted(expenses, key=lambda r: r.amount())[:n]   # 负数越小越靠前 = 花得越多

    def filter_by_tag(self, tag: str) -> list[Record]:
        """按标签过滤 —— 练 getattr + 列表推导式。"""
        return [r for r in self.records if tag in getattr(r, "tags", [])]

    # ── 魔术方法 ──────────────────────────────────────────
    def __len__(self) -> int:
        """让 len(ledger) 可用。"""
        return len(self.records)

    def __getitem__(self, idx: int) -> Record:
        """让 ledger[0] 和 for r in ledger 可用（后者靠 __len__ + __getitem__ 协议）。"""
        return self.records[idx]

    def __str__(self) -> str:
        return f"<Ledger {self.owner} · {len(self)} 条 · 结余 {self.total():.2f}>"

    # ── 存 / 取 ───────────────────────────────────────────
    def save(self, path: Path) -> None:
        """存成 JSON。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "owner": self.owner,
            "created_at": self.created_at,
            "records": [r.to_dict() for r in self.records],
            "summary": {
                "count": len(self),
                "total": self.total(),
                "by_category": self.by_category(),
            },
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Ledger:
        """从 JSON 恢复。

        📌 为什么是 @classmethod 而不是普通函数？
           因为它是"另一种构造方式"（工厂方法）。调用方写 Ledger.load(path)
           比写 load_ledger(path) 更直观，而且**子类继承它时会自动返回子类实例**
           （cls 是实际调用的类，不是硬编码的 Ledger）。
        """
        data = json.loads(path.read_text(encoding="utf-8"))
        records: list[Record] = []
        for raw in data.get("records", []):
            kind = raw.pop("_kind", None)
            klass = cls._REGISTRY.get(kind)
            if klass is None:
                # 📌 遇到未知类型不要崩，跳过并警告 —— 老版本的数据要能被新版本读
                print(f"⚠️  跳过未知条目类型: {kind!r}")
                continue
            records.append(klass(**raw))
        ledger = cls(owner=data.get("owner", "我"), records=records)
        ledger.created_at = data.get("created_at", ledger.created_at)
        return ledger

    # ── 静态方法 ──────────────────────────────────────────
    @staticmethod
    def money(x: float) -> str:
        """格式化金额。

        📌 @staticmethod 不接收 self 也不接收 cls —— 它只是"恰好放在这个类里"的普通函数。
           放在类里的意义是"命名空间归属"（Ledger.money(x) 一眼知道是记账相关的格式化）。
           判断标准：既不需要实例状态、也不需要类信息 → 用 staticmethod。
        """
        return f"{x:,.2f}"


# ═════════════════════════════════════════════════════════════
# 自测
# ═════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # ① 抽象基类生效验证
    try:
        Record()  # type: ignore[abstract]
        raise AssertionError("❌ Record 竟然能被实例化，ABC 没生效")
    except TypeError as e:
        print(f"✅ 抽象基类生效：Record() → TypeError: {e}")

    # ② 可变默认参数陷阱验证（这是面试高频题）
    a = Income("测试A", 100)
    b = Income("测试B", 200)
    a.tags.append("only-a")
    assert b.tags == [], f"❌ 默认值被共享了！b.tags={b.tags}"
    print("✅ default_factory 生效：a.tags 修改不影响 b.tags")

    # ③ 多态与开闭原则
    led = Ledger(owner="小明")
    led.add(Income("9月工资", 12000, source="公司", tags=["主业"]))
    led.add_all(
        Expense("房租", 2400, category="住房"),
        Expense("火锅", 380.5, category="餐饮", tags=["社交"]),
        Expense("地铁", 120, category="交通"),
        Expense("显卡", 1480, category="数码"),
        Refund("退货：机械键盘", 200, original_category="数码"),
    )
    print(f"\n{led}")
    print(f"总收入 {led.income_total():.2f}  总支出 {led.expense_total():.2f}  结余 {led.total():.2f}")
    assert led.total() == 12000 - 2400 - 380.5 - 120 - 1480 + 200

    print("\n分类汇总：")
    for cat, amt in led.by_category().items():
        print(f"  {cat:<6}{amt:>10.2f}")

    print(f"\n支出 Top3：{[r.title for r in led.top_expense(3)]}")
    assert [r.title for r in led.top_expense(2)] == ["房租", "显卡"]

    print(f"标签 '社交' 过滤：{[r.title for r in led.filter_by_tag('社交')]}")
    print(f"len(led) = {len(led)}   led[0] = {led[0].title}")
    # ⚠️ 注意这里打印出来的是 @dataclass 自动生成的 __repr__，不是我自定义的那个
    #    （子类 dataclass 的 __repr__ 覆盖了父类 Record.__repr__）
    print(f"__repr__ (dataclass 生成): {led.records[1]!r}")
    print(f"__str__  (自定义生效)    : {led.records[1]}")

    # ④ 序列化往返一致
    out = Path(__file__).parent / "data" / "ledger.json"
    led.save(out)
    led2 = Ledger.load(out)
    assert len(led2) == len(led), "条目数不一致"
    assert led2.total() == led.total(), f"金额不一致 {led2.total()} vs {led.total()}"
    assert [type(r).__name__ for r in led2] == [type(r).__name__ for r in led], "类型丢失"
    print(f"\n✅ 序列化往返一致：{out}")
    print(f"   重新加载后 {len(led2)} 条，结余 {led2.total():.2f}，类型完整保留")
