#!/usr/bin/env python3
"""生成 100 个"脏配置文件"作为测试夹具 —— 别手写，用代码造。

分布（合计 100 个 = 成功 60 + 失败 40，与任务书的预期输出完全对齐）：
    60 个正常
    15 个 JSON 语法错
    10 个缺 version 字段
     5 个空文件
     5 个非 UTF-8 二进制
     5 个顶层类型错（是数组/字符串而不是对象）

用法：python make_fixtures.py [--dir data/configs] [--n 100] [--seed 42]
📌 为什么要固定 seed？→ 每次生成的数据完全一样，测试才能断言"成功 60 失败 40"。
   这叫**可复现的测试数据**，比随机数据有用得多。
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

PLAN = [
    ("ok", 60), ("bad_syntax", 15), ("missing_field", 10),
    ("empty", 5), ("binary", 5), ("wrong_type", 5),
]


def make_one(kind: str, idx: int, rng: random.Random) -> bytes:
    if kind == "ok":
        return json.dumps({
            "version": rng.choice(["1.0", "1.1", "2.0"]),
            "name": f"service-{idx:03d}",
            "replicas": rng.randint(1, 8),
            "tags": rng.sample(["rag", "agent", "web", "worker", "cache"], k=2),
            "enabled": rng.random() > 0.2,
        }, ensure_ascii=False, indent=2).encode("utf-8")
    if kind == "bad_syntax":
        # 三种典型语法错：缺右括号 / 尾逗号 / 单引号
        return rng.choice([
            b'{"version": "1.0", "name": "broken"',        # 缺 }
            b'{"version": "1.0", "name": "broken",}',       # 尾逗号
            b"{'version': '1.0', 'name': 'broken'}",        # 单引号
        ])
    if kind == "missing_field":
        return json.dumps({"name": f"no-version-{idx:03d}", "replicas": 1}).encode("utf-8")
    if kind == "empty":
        return b""
    if kind == "wrong_type":
        # 合法 JSON，但顶层不是对象 → 校验时必须挡住（否则 data["version"] 直接 TypeError）
        return rng.choice([b'[1, 2, 3]', b'"just a string"', b'42', b'null'])
    if kind == "binary":
        # 前两个字节就非法 UTF-8（0xff 不是合法的 UTF-8 起始字节）
        return b"\xff\xfe\x00\x01binary-garbage" + bytes(rng.randint(0, 255) for _ in range(40))
    raise ValueError(f"未知类型 {kind}")


def main() -> int:
    p = argparse.ArgumentParser(description="生成脏配置夹具")
    p.add_argument("--dir", type=Path, default=Path(__file__).parent / "data/configs")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    rng = random.Random(args.seed)
    args.dir.mkdir(parents=True, exist_ok=True)
    for old in args.dir.glob("*.json"):          # 先清空，保证可重复
        old.unlink()
    for old in args.dir.glob("*.bin"):
        old.unlink()

    total = 0
    for kind, count in PLAN:
        for _i in range(count):
            total += 1
            ext = "bin" if kind == "binary" else "json"
            name = f"{total:03d}_{kind}.{ext}"
            (args.dir / name).write_bytes(make_one(kind, total, rng))
        print(f"  {kind:<14} {count:>3} 个")
    print(f"✅ 共生成 {total} 个文件 → {args.dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
