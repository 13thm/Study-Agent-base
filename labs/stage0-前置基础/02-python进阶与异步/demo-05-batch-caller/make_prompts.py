#!/usr/bin/env python3
"""生成 prompts.jsonl（200 条，可复现）。

用法：python make_prompts.py --n 200 --out data/prompts.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

TOPICS = [
    "RAG 检索增强生成", "向量数据库", "Embedding 模型", "混合检索", "Rerank 重排",
    "Chunk 分块策略", "Function Calling", "ReAct 范式", "LangGraph 状态机", "HITL 人工审批",
    "Agent 记忆系统", "Prompt Caching", "上下文窗口", "提示注入防护", "多租户隔离",
    "Celery 异步任务", "SSE 流式输出", "Docker 多阶段构建", "Prometheus 指标", "评测集构建",
]
TEMPLATES = [
    "用一句话解释{}",
    "{} 解决了什么问题？",
    "在 Agent 项目里，{} 通常怎么用？",
    "{} 有哪些常见的坑？",
    "对比一下 {} 与其他方案的优劣",
]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--out", type=Path, default=Path(__file__).parent / "data/prompts.jsonl")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    rng = random.Random(args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for i in range(1, args.n + 1):
            topic = rng.choice(TOPICS)
            tmpl = rng.choice(TEMPLATES)
            rec = {"id": f"q{i:04d}", "prompt": tmpl.format(topic), "topic": topic}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"✅ 已生成 {args.n} 条 → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
