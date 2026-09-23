#!/usr/bin/env python3
"""生成 prompts.jsonl（200 条，可复现）。

用法：python make_prompts.py --n 200 --out data/prompts.jsonl
"""
from __future__ import annotations

# ── 标准库 ─────────────────────────────────────────────
import argparse                          # 命令行参数解析
import json                              # 每条记录序列化成 JSON
import random                            # 随机选题材/模板（用 seed 保证可复现）
from pathlib import Path                 # 路径操作（跨平台）


# ═════════════════════════════════════════════════════════════
# 素材库：题材 × 模板，随机组合生成 prompt
# ═════════════════════════════════════════════════════════════

# 20 个题材，全部是"阶段 1～5 会反复出现的技术名词"
# 📌 为什么不直接写 200 条 prompt？
#    因为 20 题材 × 5 模板 = 100 种组合，随机生成 200 条，
#    既覆盖多话题，又不用手写 200 行 —— 教学 demo 用这个方法最省事
TOPICS = [
    "RAG 检索增强生成", "向量数据库", "Embedding 模型", "混合检索", "Rerank 重排",
    "Chunk 分块策略", "Function Calling", "ReAct 范式", "LangGraph 状态机", "HITL 人工审批",
    "Agent 记忆系统", "Prompt Caching", "上下文窗口", "提示注入防护", "多租户隔离",
    "Celery 异步任务", "SSE 流式输出", "Docker 多阶段构建", "Prometheus 指标", "评测集构建",
]

# 5 个问题模板，{} 是占位符，会被 topic 替换
# 📌 模板的多样性很重要：不同的问法会触发模型不同长度/风格的回答，
#    这正是"批量评测"需要的——如果全是"用一句话解释X"，评测就没区分度了
TEMPLATES = [
    "用一句话解释{}",                       # 简短回答
    "{} 解决了什么问题？",                   # 问题/动机型
    "在 Agent 项目里，{} 通常怎么用？",      # 应用型
    "{} 有哪些常见的坑？",                   # 经验型
    "对比一下 {} 与其他方案的优劣",          # 对比型
]


def main() -> int:
    # ── 命令行参数 ────────────────────────────────────────
    p = argparse.ArgumentParser()

    # --n：生成多少条。默认 200
    p.add_argument("--n", type=int, default=200)

    # --out：输出路径。默认是脚本同目录下的 data/prompts.jsonl
    # 📌 Path(__file__).parent 而不是 "./"：
    #    让脚本在任意工作目录下跑都能正确找到自己所在的位置
    p.add_argument("--out", type=Path, default=Path(__file__).parent / "data/prompts.jsonl")

    # --seed：随机种子。默认 42
    # 📌 这是"可复现"的关键：同一个 seed 生成的 200 条永远一样
    #    这样别人的评测结果和你的一致，调试时也不会变来变去
    p.add_argument("--seed", type=int, default=42)

    args = p.parse_args()

    # ── 初始化随机数生成器 ────────────────────────────────
    # 📌 用 random.Random(args.seed) 而不是 random.seed(args.seed)：
    #    - random.seed() 改的是"全局状态"，会影响别处调用 random 的代码
    #    - random.Random(seed) 造一个"独立的生成器"，互不干扰
    #    这是好习惯：需要可复现时，永远用独立实例
    rng = random.Random(args.seed)

    # ── 确保输出目录存在 ──────────────────────────────────
    # parents=True：递归创建父目录（比如 data/ 不存在就先建 data/）
    # exist_ok=True：已存在不报错（幂等，脚本可以重复跑）
    args.out.parent.mkdir(parents=True, exist_ok=True)

    # ── 逐条生成并写入 ────────────────────────────────────
    with args.out.open("w", encoding="utf-8") as fh:
        # i 从 1 开始，编号更符合人类直觉
        for i in range(1, args.n + 1):
            # rng.choice 从列表里等概率随机抽一个
            # 每次循环都重新抽，所以同一条 prompt 可能重复出现（没关系，本来就允许重复）
            topic = rng.choice(TOPICS)
            tmpl = rng.choice(TEMPLATES)

            # ── 构造一条记录 ──────────────────────────────
            # 📌 f"q{i:04d}" 是"补零格式化"：
            #    i=1    → "q0001"
            #    i=200  → "q0200"
            #    好处：按 id 排序时字典序 == 数字序，日志里对齐也好看
            #
            # 📌 tmpl.format(topic) 把模板里的 {} 替换成题材：
            #    "用一句话解释{}".format("RAG") → "用一句话解释RAG"
            rec = {"id": f"q{i:04d}", "prompt": tmpl.format(topic), "topic": topic}

            # ── 写一行 JSON ───────────────────────────────
            # ensure_ascii=False：中文直接输出，不转成 \uXXXX
            #   如果忘了这个参数，输出会是 "RAG \u68c0\u7d22..." 这种，人根本看不了
            # 结尾加 "\n"：JSONL 的约定——每行一个 JSON，行尾换行
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"✅ 已生成 {args.n} 条 → {args.out}")
    return 0


if __name__ == "__main__":
    # raise SystemExit(main()) 而不是 sys.exit(main())：
    #   两者等价，但 SystemExit 更"显式"——一眼看出这是"用返回值当退出码"
    #   0 = 成功，非 0 = 失败（UNIX 约定）
    raise SystemExit(main())