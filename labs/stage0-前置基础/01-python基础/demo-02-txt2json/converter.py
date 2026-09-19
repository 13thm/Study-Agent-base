#!/usr/bin/env python3
"""文本 → JSON 转换器 —— Demo 01-2。

📌 这个 Demo 的真实身份
────────────────────────────────────────────────────────────
它看起来是"解析一个聊天记录文本"，实际上是 **LLM 应用里 output parsing 的手写版**：
    · 输入是不可信的、脏的、格式不完全统一的文本
    · 输出必须是结构良好、能被下游 json.load 的 JSON
    · 单条失败不能拖垮整批（要有 errors 列表）
    · 容错而不是崩溃（缺字段填 null，而不是 KeyError）

等你到阶段 1 模块 03 做「容错 JSON 解析器」时，会发现思路一模一样，
只是脏数据从"缺分隔符"变成了"带 ```json 围栏 / 尾逗号 / 被截断"。

用法：
    python converter.py                                  # 用默认的 data/raw/chat_log.txt
    python converter.py --src 某文件.txt --dst out/x.json
    python converter.py --strict                         # 遇到脏行就退出（对照用）
────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ═════════════════════════════════════════════════════════════
# 第一步：定义"什么算合法"
#   📌 好习惯：先把规则写清楚（甚至写成常量），再动手解析。
#   新手常见错误是边写边猜规则，最后代码里散落着魔法数字。
# ═════════════════════════════════════════════════════════════
SEPARATOR = "|"
EXPECTED_FIELDS = 3          # user | timestamp | text
TIME_FORMATS = (             # 允许的时间写法，按顺序尝试
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M",
)


def normalize_ts(raw: str) -> str | None:
    """把各种时间写法归一成 'YYYY-MM-DD HH:MM:SS'，无法识别返回 None。

    📌 教学点：容错 ≠ 崩溃
        缺时间字段的行（"王五 | 2024-01-06 | xxx"）应该被接受，ts 填 None，
        而不是让整批数据失败。这就是"部分成功优于全部失败"。

    📌 教学点：for-else 的真实用法
        循环正常结束（没有 break）时执行 else。这里表示"所有格式都没匹配上"。
        很多人以为 for-else 是语法垃圾，其实这种"尝试多个候选，全失败则兜底"
        的场景它最简洁。
    """
    raw = raw.strip()
    if not raw:
        return None
    for fmt in TIME_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        # 只有日期的补上 00:00:00，保证输出格式统一
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    else:  # noqa: PLW0120  ← 循环没 break 才进这里
        return None


def parse_line(line: str, line_no: int) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """解析单行。

    Returns:
        (record, error) —— 二者必有一个是 None。
        📌 为什么返回元组而不是抛异常？
            因为"某一行是脏的"在这里是**预期内的正常情况**，不是异常。
            用异常做控制流会让主循环写成一堆 try/except，性能和可读性都差。
            原则：**异常用于"意外"，返回值用于"预期内的失败"**。
            （对比 Demo 01-4：那里"文件损坏"是意外，所以用异常更合适。）
    """
    stripped = line.strip()
    if not stripped:
        # 空行直接跳过，不算错误（文件末尾常有换行）
        return None, None

    parts = [p.strip() for p in stripped.split(SEPARATOR)]
    # ⚠️ 坑点：split 之后每个字段还要再 strip 一次！
    #    "李四|2024-01-05 09:30| 有没有路线图" → ["李四", "2024-01-05 09:30", " 有没有路线图"]
    #    不再 strip 的话 text 前面会带一个空格，后续做 Embedding 时就是噪声。

    if len(parts) < EXPECTED_FIELDS:
        return None, {
            "line_no": line_no,
            "raw": stripped[:120],          # 截断，避免脏数据把报告撑爆
            "reason": f"分隔符数量不足，期望 {EXPECTED_FIELDS - 1} 个 '{SEPARATOR}'，"
                      f"实际 {len(parts) - 1} 个",
        }

    user, ts_raw, text = parts[0], parts[1], SEPARATOR.join(parts[2:])
    # 📌 如果正文里本身就含 '|'，join 回去能保住原文（比只取 parts[2] 更稳）

    if not user:
        return None, {"line_no": line_no, "raw": stripped[:120], "reason": "用户名为空"}
    if not text:
        return None, {"line_no": line_no, "raw": stripped[:120], "reason": "正文为空"}

    return {
        "user": user,
        "ts": normalize_ts(ts_raw),        # 可能是 None，合法
        "ts_raw": ts_raw or None,          # 保留原始值，方便事后排查
        "text": text,
        "char_len": len(text),
    }, None


# ═════════════════════════════════════════════════════════════
# 第二步：主流程
# ═════════════════════════════════════════════════════════════
def convert(src: Path, dst: Path, *, strict: bool = False) -> dict[str, Any]:
    """读 src，逐行解析，写出结构化 JSON 到 dst，返回统计信息。"""
    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    total = 0

    # 📌 with 语句 = 上下文管理器，保证文件一定被关闭（哪怕中途抛异常）。
    #    encoding="utf-8" 必须显式写，否则 Windows 中文环境会用 GBK 解码 UTF-8 文件 → 乱码。
    with src.open(encoding="utf-8") as fh:
        # 📌 逐行迭代而不是 fh.read()：
        #    大文件（几百 MB 的日志）一次性读进内存会 OOM。逐行迭代是惰性的，内存恒定。
        for line_no, line in enumerate(fh, start=1):   # enumerate 从 1 开始，行号才对得上
            if not line.strip():
                continue                                  # 空行不计入 total
            total += 1
            rec, err = parse_line(line, line_no)
            if err:
                errors.append(err)
                if strict:
                    # strict 模式：一遇错就停，用于"数据必须干净"的导入场景
                    raise ValueError(f"第 {line_no} 行解析失败: {err['reason']}")
            if rec:
                records.append(rec)

    result = {
        "source": str(src),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "valid": len(records),
        "invalid": len(errors),
        "records": records,
        "errors": errors,
        # 顺手做个聚合，让输出更有用（也是练 dict 推导式）
        "users": sorted({r["user"] for r in records}),     # set 推导式去重 + 排序
        "missing_ts": sum(1 for r in records if r["ts"] is None),
    }

    # 📌 坑点：dst 的父目录不存在时 open() 直接 FileNotFoundError。
    #    parents=True 连带创建多级目录，exist_ok=True 表示已存在不报错。
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as fh:
        # ensure_ascii=False → 中文正常显示，不是 \u4e2d\u6587
        # indent=2          → 人类可读；生产环境传输时反而要去掉（省带宽）
        json.dump(result, fh, ensure_ascii=False, indent=2)
        fh.write("\n")   # 文件末尾留一个换行，是 Unix 的好习惯（git diff 更干净）

    return result


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).parent
    p = argparse.ArgumentParser(description="文本 → JSON 转换器（Demo 01-2）")
    p.add_argument("--src", type=Path, default=here / "data/raw/chat_log.txt")
    p.add_argument("--dst", type=Path, default=here / "data/out/chat_log.json")
    p.add_argument("--strict", action="store_true", help="遇到脏行立即失败（默认容错并记录）")
    p.add_argument("--show", type=int, default=2, help="打印前 N 条记录预览")
    args = p.parse_args(argv)

    if not args.src.is_file():
        print(f"❌ 输入文件不存在: {args.src}", file=sys.stderr)
        return 1

    try:
        r = convert(args.src, args.dst, strict=args.strict)
    # ⚠️ 顺序极其重要：UnicodeDecodeError 是 ValueError 的**子类**！
    #    如果先写 except ValueError，编码错误会被它吃掉，永远进不到下面那个分支。
    #    规则：**多个 except 时，子类必须写在父类前面。**
    #    （我第一次写就写反了，退出码变成 2，查了 10 分钟才发现是继承关系。）
    except UnicodeDecodeError as e:
        print(f"❌ 文件不是 UTF-8 编码: {e}", file=sys.stderr)
        print("   提示：用 chardet 探测编码，或 iconv -f GBK -t UTF-8 转换", file=sys.stderr)
        return 3
    except ValueError as e:                  # strict 模式的预期失败
        print(f"❌ {e}", file=sys.stderr)
        return 2

    print(f"解析完成：共 {r['total']} 行，成功 {r['valid']}，失败 {r['invalid']}")
    print(f"涉及用户：{', '.join(r['users'])}   缺时间戳：{r['missing_ts']} 条")
    print(f"输出文件：{args.dst}")

    for rec in r["records"][: args.show]:
        print(f"  · [{rec['ts'] or '无时间'}] {rec['user']}: {rec['text']} ({rec['char_len']} 字)")

    if r["errors"]:
        print("失败详情（前 3 条）：")
        for e in r["errors"][:3]:
            print(f"  第 {e['line_no']} 行: {e['reason']}  |  原文: {e['raw']}")

    # 📌 自我验证：写出去的 JSON 必须能被读回来。
    #    这一步很多人省了，结果下游 json.load 才发现文件是坏的。
    json.loads(args.dst.read_text(encoding="utf-8"))
    print("✅ 输出文件已通过 json.loads 回读校验")
    return 0


if __name__ == "__main__":
    sys.exit(main())
