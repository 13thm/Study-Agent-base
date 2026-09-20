#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"

# ── 自动定位 lab 的 .venv 与共享函数（hr / need_pkgs / wait_http）──
_d="$(pwd)"
while [ "$_d" != "/" ]; do
  [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }
  _d="$(dirname "$_d")"
done
hr() { printf '\n\033[36m── %s ──\033[0m\n' "$1"; }

hr "1. 自测：抽象基类 / 可变默认参数陷阱 / 多态 / 序列化往返"
python3 ledger.py

hr "2. 账本报表演示"
python3 ledger_demo.py

hr "3. 生成的 JSON 长什么样（注意 _kind 类型标签）"
head -30 data/ledger.json

hr "4. 反例演示：可变默认参数陷阱（三种写法对照）"
python3 - <<'EOF'
from dataclasses import dataclass, field

# ── 写法 1：普通函数默认参数 —— 经典 bug，Python 不拦你 ──
def add_tag_bad(tag, tags=[]):        # ❌ 默认值在【函数定义时】只求值一次
    tags.append(tag)
    return tags
print("写法1 普通函数默认参数:")
print(f"  第1次调用 add_tag_bad('a') → {add_tag_bad('a')}")
print(f"  第2次调用 add_tag_bad('b') → {add_tag_bad('b')}   ← 竟然带着上次的 'a'！")
print(f"  默认值对象 id = {id(add_tag_bad.__defaults__[0])}，所有调用共享同一个 list")

# ── 写法 2：普通类属性 —— 同样不拦你 ──
class CartBad:
    items = []                        # ❌ 类属性，所有实例共享
    def add(self, x): self.items.append(x)
c1, c2 = CartBad(), CartBad()
c1.add("苹果")
print(f"\n写法2 普通类属性: c1.items={c1.items}  c2.items={c2.items}   ← c2 被污染！")

# ── 写法 3：dataclass —— Python 主动帮你拦住（★ 很多人不知道）──
print("\n写法3 @dataclass 的行为:")
try:
    @dataclass
    class Wrong:
        tags: list = []               # ❌ dataclass 直接拒绝
    print("  没报错？不可能")
except ValueError as e:
    print(f"  定义类的那一刻就抛 ValueError ✅\n    {e}")
print("  → dataclass 明确禁止 list/dict/set 作默认值，这是它比手写 __init__ 更安全的地方之一")

# ── 正确写法 ──
@dataclass
class Right:
    tags: list = field(default_factory=list)   # ✅ 每次实例化都调 list() 造新对象
def add_tag_good(tag, tags=None):              # ✅ None 哨兵
    if tags is None: tags = []
    tags.append(tag); return tags

a, b = Right(), Right()
a.tags.append("only-a")
print(f"\n正确写法: a.tags={a.tags}  b.tags={b.tags}   ← 各自独立 ✅")
print(f"          add_tag_good 两次调用: {add_tag_good('x')} / {add_tag_good('y')} ✅")
print("\n📌 一句话总结：默认值必须是【不可变】的（None/数字/字符串/元组）；")
print("   要可变对象就用 default_factory（dataclass）或 None 哨兵（普通函数）。")
EOF
