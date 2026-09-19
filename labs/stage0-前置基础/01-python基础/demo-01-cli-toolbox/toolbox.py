#!/usr/bin/env python3
"""命令行文本工具箱 —— Demo 01-1 的"交互层"。

用法（三个子命令）：
    python toolbox.py freq  --path corpus/ --top 5     # 词频 Top N
    python toolbox.py stat  --path corpus/             # 每个文件的字符统计
    python toolbox.py clean --in corpus/a.txt --out out/a.clean.txt   # 清洗并另存

📌 教学设计
────────────────────────────────────────────────────────────
本文件只做三件事：解析参数 → 调用 text_utils 的纯函数 → 格式化打印。
不写任何业务逻辑。这样做的三个好处：
  1. 逻辑层可单测（模块 06 会给 text_utils 写 parametrize 测试）
  2. 换 UI 不用重写逻辑（明天想做成 FastAPI 接口，只换这一层）
  3. 出错时容易定位（是解析错了、算错了、还是打印错了）

覆盖的知识点：
  · argparse 的 subparsers（子命令）、type、default、help、required
  · sys.exit 的退出码约定（0 成功 / 1 一般错误 / 2 参数错误）
  · 异常边界：把底层的 FileNotFoundError 转成"人话"，不给用户看 traceback
  · f-string 的对齐与宽度（{:>5} {:<12} 这种，做终端表格必备）
────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import text_utils as tu


# ═════════════════════════════════════════════════════════════
# 三个子命令的处理函数
#   约定：每个 cmd_xxx(args) -> int，返回进程退出码。
#   这样 main() 只负责 dispatch，也方便测试时直接调用 cmd_stat()。
# ═════════════════════════════════════════════════════════════
def cmd_freq(args: argparse.Namespace) -> int:
    """freq 子命令：统计词频并打印 Top N。"""
    try:
        files = tu.iter_text_files(Path(args.path))
    except FileNotFoundError as e:
        # 📌 异常边界层：底层抛的异常在这里"翻译"成用户能懂的话。
        #    print 到 stderr（不是 stdout），这样 `... > out.txt` 不会把错误写进结果文件。
        print(f"❌ {e}", file=sys.stderr)
        print("   提示：--path 可以是单个文件，也可以是目录", file=sys.stderr)
        return 1

    if not files:
        print(f"⚠️  {args.path} 下没有找到 {args.pattern} 文件", file=sys.stderr)
        return 1

    # 📌 教学点：argparse 的 type=int 只校验"能转成 int"，语义校验要自己写。
    #    传 --top -5 不会报错，但 top_n 已经处理了 n<=0 返回空列表 —— 边界要在底层守住。
    grams = tuple(int(g) for g in args.gram.split(",") if g.strip())
    tok_kwargs: dict[str, object] = {"grams": grams, "remove_stopwords": not args.keep_stopwords}

    merged: dict[str, int] = {}
    total_chars = 0
    for f in files:
        text = tu.read_text(f)
        total_chars += len(text)
        # 📌 合并多个文件的词频：dict 不能直接相加，要逐 key 累加
        for word, cnt in tu.word_freq(text, **tok_kwargs).items():
            merged[word] = merged.get(word, 0) + cnt

    if args.min_count > 1:
        merged = {w: c for w, c in merged.items() if c >= args.min_count}

    print(f"文件数: {len(files)}   总字符: {total_chars}   去重词数: {len(merged)}")
    # 表头：用 f-string 的宽度对齐做出"表格感"
    #   {:<4} 左对齐占 4 位；{:<12} 左对齐占 12 位；{:>6} 右对齐占 6 位
    print(f"{'rank':<4}  {'word':<12}  {'count':>6}")
    print("-" * 28)
    for i, (word, cnt) in enumerate(tu.top_n(merged, args.top), 1):
        print(f"{i:<4}  {word:<12}  {cnt:>6}")
    return 0


def cmd_stat(args: argparse.Namespace) -> int:
    """stat 子命令：逐文件打印字符统计。"""
    try:
        files = tu.iter_text_files(Path(args.path), args.pattern)
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    if not files:
        print("⚠️  没有匹配的文件", file=sys.stderr)
        return 1

    print(f"{'file':<16}{'中文':>8}{'英文词':>8}{'总字符':>9}{'行数':>7}")
    print("-" * 48)
    totals = {"chinese": 0, "english_words": 0, "total_chars": 0, "lines": 0}
    for f in files:
        s = tu.char_count(tu.read_text(f))
        # 📌 中文字符是"宽字符"，终端里占 2 列，所以对齐会看起来偏一点。
        #    想精确对齐要用 wcwidth 库或手动补空格 —— 这里不折腾，知道有这回事就行。
        print(f"{f.name:<16}{s['chinese']:>8}{s['english_words']:>8}"
              f"{s['total_chars']:>9}{s['lines']:>7}")
        for k in totals:
            totals[k] += s[k]
    print("-" * 48)
    print(f"{'合计':<15}{totals['chinese']:>8}{totals['english_words']:>8}"
          f"{totals['total_chars']:>9}{totals['lines']:>7}")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """clean 子命令：清洗单个文件并写出。"""
    src, dst = Path(args.input), Path(args.out)
    if not src.is_file():
        print(f"❌ 输入文件不存在: {src}", file=sys.stderr)
        return 1

    raw = tu.read_text(src)
    cleaned = tu.clean(raw)

    # 📌 坑点：目标目录不存在时 open() 会抛 FileNotFoundError。
    #    parents=True 会连带创建多级父目录，exist_ok=True 表示已存在不报错。
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(cleaned + "\n", encoding="utf-8")

    saved = len(raw) - len(cleaned)
    print(f"✅ 清洗完成: {src} → {dst}")
    print(f"   原始 {len(raw)} 字符 → 清洗后 {len(cleaned)} 字符"
          f"（{'减少' if saved >= 0 else '增加'} {abs(saved)}，"
          f"{abs(saved) / max(len(raw), 1):.1%}）")
    return 0


# ═════════════════════════════════════════════════════════════
# argparse 装配
# ═════════════════════════════════════════════════════════════
def build_parser() -> argparse.ArgumentParser:
    """构建参数解析器。

    📌 抽成独立函数而不是写在 main() 里，是为了测试时能直接构造 parser 验证参数解析。
    """
    p = argparse.ArgumentParser(
        prog="toolbox.py",
        description="文本工具箱 · 阶段0 模块01 Demo 01-1（练字符串/容器/文件/argparse）",
        # RawDescriptionHelpFormatter 让 epilog 里的换行原样显示
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  python toolbox.py freq  --path corpus/ --top 5
  python toolbox.py stat  --path corpus/
  python toolbox.py clean --in corpus/a.txt --out out/a.clean.txt
""",
    )
    sub = p.add_subparsers(dest="command", required=True, metavar="<子命令>")

    # ---- freq ----
    sp = sub.add_parser("freq", help="统计词频 Top N", description="递归读取目录下所有文本文件，合并统计词频")
    sp.add_argument("--path", default="corpus/", help="文件或目录路径（默认 corpus/）")
    sp.add_argument("--pattern", default="*.txt", help="glob 匹配模式（默认 *.txt）")
    sp.add_argument("--top", type=int, default=10, help="显示前 N 个（默认 10）")
    sp.add_argument("--gram", default="2", help="中文 n-gram，逗号分隔，如 1,2（默认 2）")
    sp.add_argument("--min-count", type=int, default=1, help="只显示出现 >= N 次的词（默认 1）")
    sp.add_argument("--keep-stopwords", action="store_true",
                    help="保留停用词（默认过滤）—— 加上它看看 Top5 会变成什么样")
    sp.set_defaults(func=cmd_freq)

    # ---- stat ----
    sp = sub.add_parser("stat", help="逐文件字符统计", description="打印每个文件的中文字数/英文词数/总字符/行数")
    sp.add_argument("--path", default="corpus/", help="文件或目录路径")
    sp.add_argument("--pattern", default="*.txt", help="glob 匹配模式")
    sp.set_defaults(func=cmd_stat)

    # ---- clean ----
    sp = sub.add_parser("clean", help="清洗文本并另存", description="去零宽字符、全角转半角、压缩空白")
    sp.add_argument("--in", dest="input", required=True, help="输入文件（必填）")
    sp.add_argument("--out", required=True, help="输出文件（目录会自动创建）")
    sp.set_defaults(func=cmd_clean)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # 📌 set_defaults(func=...) 是 argparse 子命令的经典写法：
    #    每个子命令把自己的处理函数挂在 args.func 上，这里一行 dispatch。
    #    比写一堆 if args.command == "freq": ... 干净得多，加子命令也不用改 main。
    return args.func(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        # 📌 Ctrl+C 不该打印一屏 traceback，那是给开发者看的，不是给用户的。
        print("\n⚠️  已被用户中断", file=sys.stderr)
        sys.exit(130)  # 128 + SIGINT(2) 是 Unix 约定
