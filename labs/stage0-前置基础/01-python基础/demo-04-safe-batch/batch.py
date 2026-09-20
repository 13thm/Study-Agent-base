#!/usr/bin/env python3
"""异常防护批处理器 —— Demo 01-4。

📌 这个 Demo 的真实身份
────────────────────────────────────────────────────────────
**Agent 工具调用的核心能力就是"出错不能崩"。**

LLM 会调你的工具，工具的入参是模型编的（可能是错的路径、不存在的 ID）。
如果工具一遇到异常就把整个 Agent 进程炸掉，用户看到的就是 500。
正确做法：捕获 → 转成结构化的错误对象 → 回填给模型让它自己纠正。

本 Demo 就是这个模式的最小训练场：100 个文件，40 个是坏的，
主流程一次都不能崩，最后还要给出一份能看懂的报告。

用法：
    python batch.py --dir data/configs/
    python batch.py --dir data/configs/ --strict    # 一遇错就退出（对照）
    python batch.py --dir data/configs/ --retry 2   # 失败重试（体会"重试无用错误"的浪费）
────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any


# ═════════════════════════════════════════════════════════════
# 第一步：自定义异常层次
#   📌 为什么要自定义？
#     1. 让调用方能精确捕获（except MissingFieldError 只处理缺字段）
#     2. 错误信息可以带上业务上下文（文件名、字段名），不是干巴巴的 KeyError
#     3. 阶段 1 模块 01 的 LLMError → RateLimitError/TimeoutError 就是这个套路
# ═════════════════════════════════════════════════════════════
class ConfigError(Exception):
    """配置加载失败的基类。"""

    kind = "unknown"          # 报告里用来分类统计


class EncodingError(ConfigError):
    kind = "非 UTF-8 编码"


class EmptyFileError(ConfigError):
    kind = "空文件"


class SyntaxError_(ConfigError):   # 加下划线避免和内置 SyntaxError 撞名（好习惯）
    kind = "JSON 语法错"


class WrongTypeError(ConfigError):
    kind = "顶层类型错"


class MissingFieldError(ConfigError):
    kind = "缺 version 字段"

    def __init__(self, msg: str, field: str = "version") -> None:
        super().__init__(msg)
        self.field = field


REQUIRED_FIELDS = ("version", "name")


# ═════════════════════════════════════════════════════════════
# 第二步：单个文件的加载（会抛异常，交给上层处理）
# ═════════════════════════════════════════════════════════════
def load_one(path: Path) -> dict[str, Any]:
    """加载并校验一个配置文件。

    📌 教学点：raise ... from e 保留异常链
        `from e` 会把原异常挂到新异常的 __cause__ 上，traceback 里会打印
        "The above exception was the direct cause of ..."。
        不加 from 的话，Python 会显示 "During handling of the above exception,
        another exception occurred"，语义完全不同（那是"处理时又出错了"）。
        **排查线上问题时，这个区别能省你半小时。**
    """
    raw = path.read_bytes()

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise EncodingError(f"{path.name}: 非 UTF-8 编码（前 4 字节 {raw[:4].hex()}）") from e

    if not text.strip():
        raise EmptyFileError(f"{path.name}: 空文件（{len(raw)} 字节）")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        # e.lineno / e.colno / e.msg 是 JSONDecodeError 自带的定位信息，一定要用上
        raise SyntaxError_(f"{path.name}: JSON 语法错 line {e.lineno} col {e.colno}: {e.msg}") from e

    if not isinstance(data, dict):
        # 📌 这个检查不能省！如果顶层是 list，后面 data["version"] 会抛 TypeError，
        #    而 TypeError 不在我们捕获的 ConfigError 里 → 整个批处理崩掉。
        #    教训：**永远不要假设外部数据的结构，先验证类型再取字段。**
        raise WrongTypeError(f"{path.name}: 顶层不是对象，是 {type(data).__name__}")

    for f in REQUIRED_FIELDS:
        if f not in data:
            raise MissingFieldError(f"{path.name}: 缺字段 '{f}'", field=f)

    return data


# ═════════════════════════════════════════════════════════════
# 第三步：批处理主流程（一个都不能崩）
# ═════════════════════════════════════════════════════════════
def run_batch(directory: Path, *, strict: bool = False, retry: int = 0) -> dict[str, Any]:
    files = sorted(p for p in directory.iterdir() if p.is_file())
    if not files:
        raise FileNotFoundError(f"目录里没有文件: {directory}")

    ok_items: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    kind_counter: Counter[str] = Counter()
    attempts = 0
    t0 = time.perf_counter()

    for path in files:
        # 📌 关键设计：把"可能炸的部分"关在最小的 try 块里。
        #    try 块越大越容易吞掉真正的 bug（比如你统计代码里的 NameError 也会被吃掉）。
        data: dict[str, Any] | None = None
        last_err: Exception | None = None

        for attempt in range(retry + 1):
            attempts += 1
            try:
                data = load_one(path)
                break                                   # 成功就跳出重试循环
            except ConfigError as e:                    # ← 只捕获我们预期的业务异常
                last_err = e
                # 📌 这里体现一个真实教训：**ConfigError 全是"确定性错误"，重试没有意义**。
                #    文件坏了，重试 100 次还是坏的。真正该重试的是网络超时、429 这类瞬时错误。
                #    所以下面用 --retry 跑一次，你会看到"多花了 N 倍时间，结果完全一样"。
                if attempt < retry:
                    continue
            # ⚠️ 注意：这里【不】写 except Exception。
            #    意料之外的异常（比如权限问题的 PermissionError）应该炸出来让你知道，
            #    而不是被静默计入"失败"。裸 except: 更糟 —— 它连 Ctrl+C 都吞。

        if data is not None:
            ok_items.append({"file": path.name, **data})
        else:
            assert last_err is not None
            kind_counter[type(last_err).kind] += 1
            failures.append({
                "file": path.name,
                "error_type": type(last_err).__name__,
                "error_kind": type(last_err).kind,
                "message": str(last_err),
                # 📌 异常链取证：把 __cause__ 的原始信息也记下来
                "cause": (f"{type(last_err.__cause__).__name__}: {last_err.__cause__}"
                          if last_err.__cause__ else None),
            })
            if strict:
                print(f"❌ --strict 模式：第 {len(ok_items) + len(failures)} 个文件失败，立即退出",
                      file=sys.stderr)
                print(f"   {last_err}", file=sys.stderr)
                sys.exit(2)

    elapsed = time.perf_counter() - t0
    return {
        "directory": str(directory),
        "total": len(files),
        "success": len(ok_items),
        "failed": len(failures),
        "attempts": attempts,
        "elapsed_s": round(elapsed, 3),
        "failure_kinds": dict(kind_counter.most_common()),
        "failures": failures,
        "items": ok_items,
    }


def print_report(r: dict[str, Any]) -> None:
    print(f"处理 {r['total']} 个文件：成功 {r['success']}，失败 {r['failed']}"
          f"（尝试 {r['attempts']} 次）")
    if r["failure_kinds"]:
        print("失败原因分布：")
        for kind, cnt in r["failure_kinds"].items():
            print(f"  {kind:<18}{cnt:>4}   {'█' * cnt}")
    # 按分类聚合一下成功的数据，证明"部分成功"的结果依然可用
    versions: Counter[str] = Counter(str(i["version"]) for i in r["items"])
    print(f"成功文件的 version 分布：{dict(versions)}")
    print(f"耗时 {r['elapsed_s']}s")


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).parent
    p = argparse.ArgumentParser(description="异常防护批处理器（Demo 01-4）")
    p.add_argument("--dir", type=Path, default=here / "data/configs")
    p.add_argument("--out", type=Path, default=here / "data/out/batch_report.json")
    p.add_argument("--strict", action="store_true", help="一遇错立即退出（退出码 2）")
    p.add_argument("--retry", type=int, default=0, help="每个文件最多重试次数（用来验证重试无用错误的浪费）")
    p.add_argument("--show-traceback", action="store_true", help="打印第一个失败的完整异常链")
    args = p.parse_args(argv)

    if not args.dir.is_dir():
        print(f"❌ 目录不存在: {args.dir}", file=sys.stderr)
        print("   先运行: python make_fixtures.py", file=sys.stderr)
        return 1

    try:
        r = run_batch(args.dir, strict=args.strict, retry=args.retry)
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    print_report(r)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"详细报告 → {args.out}")

    if args.show_traceback and r["failures"]:
        # 演示 raise ... from 的效果：重新触发一次，打印完整异常链
        first = Path(args.dir) / r["failures"][0]["file"]
        print(f"\n── 完整异常链演示（{first.name}）──")
        try:
            load_one(first)
        except ConfigError:
            traceback.print_exc()

    return 0


if __name__ == "__main__":
    sys.exit(main())
