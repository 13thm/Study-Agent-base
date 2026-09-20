# Demo 01-4 · 异常防护批处理器

> **对应文档**：[01-Python基础.md → Demo 01-4](../../../../my-docs/study01/stage0-前置基础/01-Python基础.md)
> **依赖**：无　**预计耗时**：2 小时
> **练什么**：自定义异常层次、`raise ... from e`、最小 try 块、`Counter` 聚合、退出码

## 一、它的真实身份
**Agent 工具调用的核心能力就是"出错不能崩"。**
LLM 会调你的工具，参数是它编的（可能是错的路径、不存在的 ID）。工具一炸整个 Agent 就 500。
正确姿势：`捕获 → 转成结构化错误 → 回填给模型让它自纠`。这个 Demo 是这套模式的最小训练场。

## 二、目录
```
demo-04-safe-batch/
├── make_fixtures.py   ← 用代码造 100 个脏文件（seed=42 可复现）
├── batch.py           ← 批处理主流程 + 异常层次 + 报告
├── run.sh             ← 7 个场景（含 2 个反例演示）
└── data/
    ├── configs/       ← 100 个夹具（60 好 + 40 坏）
    └── out/batch_report.json
```
夹具分布（合计 100 = 成功 60 + 失败 40，**与任务书预期输出完全对齐**）：
`ok 60` / `bad_syntax 15` / `missing_field 10` / `empty 5` / `binary 5` / `wrong_type 5`

## 三、一步一步做
1. `bash run.sh` 看全部 7 个场景
2. 读 `batch.py`，重点看 5 处：
   - 自定义异常层次（`ConfigError` → 4 个子类，每个带 `kind` 用于分类统计）
   - `load_one()` 里的 **`raise ... from e`**（异常链，跑 `--show-traceback` 看效果）
   - `run_batch()` 里的 **最小 try 块**（try 范围越大越容易吞掉真 bug）
   - **为什么不写 `except Exception`**（意外异常应该炸出来让你知道）
   - `--strict` 与退出码约定
3. 跑对照实验：`--retry 2`（重试确定性错误）
4. 做练习题

## 四、预期输出
```
$ python3 batch.py --dir data/configs/
处理 100 个文件：成功 60，失败 40（尝试 100 次）
失败原因分布：
  JSON 语法错            15   ███████████████
  缺 version 字段        10   ██████████
  空文件                  5   █████
  非 UTF-8 编码           5   █████
  顶层类型错               5   █████
成功文件的 version 分布：{'2.0': 21, '1.0': 26, '1.1': 13}
耗时 0.002s
详细报告 → data/out/batch_report.json
```

## 五、三个必须亲手验证的反例（run.sh 里都做了）
| 反例 | 现象 | 正确做法 |
|---|---|---|
| **裸 `except:`** | 连 `KeyboardInterrupt` 都吞掉 → 用户按 Ctrl+C 停不下来 | 至少写 `except Exception`，让系统级异常穿透 |
| **`finally` 里 `return`** | 把 `try` 里的返回值覆盖掉 | `finally` 只做清理，绝不 return |
| **重试确定性错误** | `--retry 2` → 尝试次数 100→180，结果完全一样，纯浪费 | **只重试瞬时错误**（网络超时/429/5xx），参数错、文件坏绝不重试 |

> 第三条是阶段 3 模块 03「工具重试白名单」的思想源头。跑一次 `--retry 2`，
> 你会对"哪些错误值得重试"有肌肉记忆。

## 六、练习题
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 报告里加 `success_rate` 字段和每类错误的占比百分比 |
| 2 | ⭐⭐ | 加 `--fail-fast-n 5`：失败超过 5 个就停止（说明"数据源整体坏了"，不该继续浪费时间） |
| 3 | ⭐⭐ | 把失败文件**复制到 `data/quarantine/`**（隔离区）并保留原目录结构，方便人工排查 |
| 4 | ⭐⭐⭐ | 加自动修复：`bad_syntax` 里"缺右括号"和"尾逗号"两类用正则修复后重试，统计修复成功率（这就是阶段 1 模块 03 的 `repair_syntax` 雏形） |
| 5 | ⭐⭐⭐ | 用 `concurrent.futures.ThreadPoolExecutor` 并发处理，测 1/4/8 线程的耗时（为模块 02 的异步做铺垫） |

## 七、验收清单
- [ ] 100 个文件里 40 个是坏的，**主流程从没崩过**
- [ ] 报告 JSON 里每个失败项有：文件名、错误类型、错误分类、消息、**`cause`（异常链原文）**
- [ ] `--show-traceback` 能看到 "The above exception was the direct cause of..."
- [ ] `--strict` 生效，退出码 2
- [ ] 统计用 `Counter`，没有手写一堆 if
- [ ] 能口头答：`except Exception` 和 `except:` 的区别、`raise X from e` 和不加 `from` 在 traceback 上的差别、哪些错误不该重试

## 八、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
| | | | |
