#!/usr/bin/env python3
"""记账本演示脚本 —— 对应任务书里"跑起来应该长这样"的那段输出。

用法：
    python ledger_demo.py            # 造数据 → 报表 → 存盘 → 重新加载 → 校验往返一致
"""
from __future__ import annotations

from pathlib import Path

from ledger import Expense, Income, Ledger, Refund

HERE = Path(__file__).parent
OUT = HERE / "data" / "ledger.json"


def build_sample_ledger() -> Ledger:
    """造一份贴近真实的月度账本。"""
    led = Ledger(owner="小明")
    led.add(Income("9月工资", 12000, source="公司", tags=["主业"]))
    led.add_all(
        Expense("房租", 2400, category="住房"),
        Expense("火锅聚餐", 380.5, category="餐饮", tags=["社交"]),
        Expense("外卖", 820, category="餐饮"),
        Expense("地铁公交", 120.5, category="交通"),
        Expense("打车", 299.9, category="交通"),
        Expense("RTX 4070 显卡", 3980, category="数码", tags=["跑模型"]),
        Refund("退货：机械键盘", 400, original_category="数码"),
    )
    return led


def main() -> int:
    led = build_sample_ledger()

    print("=" * 62)
    print(f"  {led.owner} 的 9 月账本    （{len(led)} 条记录）")
    print("=" * 62)
    for r in led:                      # 靠 __len__ + __getitem__ 协议直接 for
        print("  " + r.describe())     # describe() 是多态调用，Ledger 不关心具体类型

    print("-" * 62)
    print(f"  总收入 {Ledger.money(led.income_total()):>12}")
    print(f"  总支出 {Ledger.money(led.expense_total()):>12}")
    print(f"  结　余 {Ledger.money(led.total()):>12}")

    print("\n分类支出：")
    for cat, amt in led.by_category().items():
        bar = "█" * int(abs(amt) / 200)          # 顺手做个 ASCII 柱状图
        print(f"  {cat:<6}{amt:>10.2f}  {bar}")

    print(f"\n支出 Top3：{[r.title for r in led.top_expense(3)]}")
    print(f"标签 '跑模型' 相关：{[r.title for r in led.filter_by_tag('跑模型')]}")

    # ── 存盘 → 重新加载 → 验证往返一致 ──
    led.save(OUT)
    led2 = Ledger.load(OUT)
    ok = (len(led2) == len(led) and led2.total() == led.total()
          and [type(r).__name__ for r in led2] == [type(r).__name__ for r in led])
    print(f"\n已保存到 {OUT.relative_to(HERE)}，重新加载后条目数 = {len(led2)} "
          f"{'✅ 往返一致' if ok else '❌ 不一致'}")

    # ── 演示"新增类型不改 Ledger"（开闭原则）──
    print("\n★ 开闭原则验证：Refund 类是后加的，Ledger 一行代码都没改，")
    print(f"  但它已被正确统计进结余：{[r.title for r in led2 if type(r).__name__ == 'Refund']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
