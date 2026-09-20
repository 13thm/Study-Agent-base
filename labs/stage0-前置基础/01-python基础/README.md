# 模块 01 · Python 基础 —— 教学 Demo 目录

> **任务书**：[my-docs/study01/stage0-前置基础/01-Python基础.md](../../../my-docs/study01/stage0-前置基础/01-Python基础.md)
> **依赖**：**零依赖**，`python3 xxx.py` 直接跑（本模块全部用标准库）
> **预计投入**：8~10 小时（5 个 Demo）
> **完成标志**：5 个 Demo 的 `run.sh` 全部跑通 + 每个 Demo 的验收清单打满勾 + 练习题至少做完 ⭐⭐ 及以下

---

## 一、这个模块在解决什么问题

不是"学会 Python 语法"。而是让你写出**能被后面 5 个阶段复用**的三样东西：

| 能力 | 对应 Demo | 后面在哪用 |
|------|----------|-----------|
| 脏文本 → 结构化数据 | 01-1、01-2 | 阶段 2 的文档解析、阶段 1 的 JSON 容错解析 |
| 用抽象基类做可扩展设计 | 01-3 | 阶段 3 的工具体系（`BaseTool` 就是这套） |
| 出错不崩 + 结构化错误 | 01-4 | 阶段 3 的工具异常处理与错误回填 |
| 环境可复现 | 01-5 | 阶段 5 的 Docker 化与 CI |

**所以本模块的代码不是练习完就扔**：`text_utils.py` 的 `clean()` 会变成阶段 2 的清洗流水线第一步，
`ledger.py` 的抽象基类模式会变成阶段 3 的 `Tool` 基类，`batch.py` 的异常层次会变成阶段 1 的 `LLMError`。

---

## 二、目录结构

```
01-python基础/
├── README.md                    ← 你在这里（学习地图）
├── demo-01-cli-toolbox/         ① 命令行文本工具箱      [字符串/容器/文件/argparse]
│   ├── README.md  run.sh
│   ├── text_utils.py            逻辑层：5 个纯函数 + 12 组自测
│   ├── toolbox.py               交互层：3 个子命令
│   └── corpus/{a,b,c}.txt       3 份真实语料（Agent 学习笔记）
├── demo-02-txt2json/            ② 文本转 JSON 转换器    [文件IO/json/容错/for-else]
│   ├── README.md  run.sh  converter.py
│   └── data/{raw,edge,out}/     12 行脏数据 + 3 个边界样本
├── demo-03-oop-ledger/          ③ 面向对象记账本        [ABC/dataclass/继承/魔术方法]
│   ├── README.md  run.sh
│   ├── ledger.py                Record(ABC) + 3 子类 + Ledger
│   ├── ledger_demo.py           账本报表
│   └── data/ledger.json         运行后生成
├── demo-04-safe-batch/          ④ 异常防护批处理器      [自定义异常/异常链/Counter]
│   ├── README.md  run.sh
│   ├── make_fixtures.py         造 100 个脏配置（60 好 + 40 坏）
│   ├── batch.py                 批处理主流程
│   └── data/{configs,out}/
└── demo-05-env-lab/             ⑤ 虚拟环境实验          [venv/pip/uv/conda]
    ├── README.md
    └── env_experiments.sh       5 个实验的自动化脚本（在 /tmp 下跑，自动清理）
```

---

## 三、学习路径（严格按顺序，别跳）

```
Day 1 上午 ── Demo 01-1 命令行工具箱
   ① bash run.sh 看输出           (10 min)
   ② 读 text_utils.py 的教学点     (30 min)
   ③ 跑停用词对比实验              (10 min)
   ④ 关掉代码自己写 stat 子命令     (40 min) ★ 最重要
   ⑤ 练习 1~3                     (60 min)

Day 1 下午 ── Demo 01-2 文本转 JSON
   ① bash run.sh（7 个场景）       (10 min)
   ② 读 converter.py，重点看 except 顺序的坑  (30 min)
   ③ 自己写 parse_line()           (40 min)
   ④ 练习 1~3                     (60 min)

Day 2 上午 ── Demo 01-3 面向对象记账本
   ① bash run.sh（含默认参数陷阱复现）(10 min)
   ② 读 ledger.py 的 5 个教学点     (40 min)
   ③ 练习 1：加 Investment 子类，不许改 Ledger  (40 min) ★ 开闭原则的肌肉记忆
   ④ 练习 2~3                     (60 min)

Day 2 下午 ── Demo 01-4 异常防护批处理
   ① bash run.sh（7 个场景含 3 个反例）(15 min)
   ② 跑 --retry 2 对照实验，体会"重试无用错误"  (10 min)
   ③ 读 batch.py 的异常层次设计      (30 min)
   ④ 练习 2、4                    (80 min)

Day 3 上午 ── Demo 01-5 环境实验
   ① 自己手敲 5 个实验（别只看脚本）  (60 min)
   ② 填 README 的实验记录表         (15 min)
   ③ 把整个 lab 的 .venv 删掉重建一次 (10 min)

Day 3 下午 ── 收尾
   ① 5 个 Demo 的验收清单逐条打勾
   ② 任务书的"知识点清单"逐条打勾（发现不会的立刻回来补）
   ③ 关掉所有代码，30 分钟内重做一遍 Demo 01-2 ★ 任务书硬性要求
   ④ 回 my-docs 把模块 01 的状态改成 ✅，进度看板同步
```

---

## 四、一键跑全部（自检用）

```bash
cd labs/stage0-前置基础
for d in 01-python基础/demo-*/; do
  [ -f "$d/run.sh" ] && echo "═══ $d ═══" && (cd "$d" && bash run.sh > /tmp/out.log 2>&1 && echo "  ✅ OK" || echo "  ❌ FAIL，看 /tmp/out.log")
done
bash 01-python基础/demo-05-env-lab/env_experiments.sh all
```

或在仓库根目录用 Makefile：`make m1`

---

## 五、四个必须口头答出的问题（任务书要求）

| 问题 | 答案要点 | 在哪个 Demo 验证过 |
|------|---------|------------------|
| 为什么 `tags: list = []` 是 bug？ | 默认值在**函数定义时只求值一次**，所有实例共享同一个对象；`a.tags.append()` 会污染 `b.tags`。正确写法 `field(default_factory=list)`，普通函数则是 `x=None` + 内部创建 | 01-3 `run.sh` 场景 4 现场复现 |
| 为什么不能用裸 `except:`？ | 它捕获 `BaseException`，连 `KeyboardInterrupt`（Ctrl+C）和 `SystemExit` 都吞掉 → 程序杀不死。至少要写 `except Exception` | 01-4 `run.sh` 场景 6 |
| dict 怎么按值排序？ | dict 没有 `.sort()`（那是 list 的），也没有 `sort_values()`（那是 pandas 的）。用 `sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))`，元组第二项保证同值时顺序稳定 | 01-1 `top_n()` |
| 异常什么时候捕获、什么时候往上抛？ | **能恢复的自己处理，不能恢复的往上抛，让边界层决定怎么呈现给用户**。预期内的失败用返回值（01-2 的 `(record, error)`），意外用异常（01-4 的 `ConfigError`） | 01-2 vs 01-4 对照 |

---

## 六、常见报错速查

| 报错 | 原因 | 解法 |
|------|------|------|
| `ModuleNotFoundError: No module named 'text_utils'` | 没在 demo 目录里运行 | `cd` 进 demo 目录再跑，或用 `run.sh`（它会自动 cd） |
| `UnicodeDecodeError: 'utf-8' codec can't decode...` | 文件不是 UTF-8 / 没写 `encoding="utf-8"` | 显式指定编码；用 `iconv -f GBK -t UTF-8` 转换 |
| `FileNotFoundError: [Errno 2] ... 'data/out'` | 输出目录不存在 | `dst.parent.mkdir(parents=True, exist_ok=True)` |
| 中文打印成 `\u4e2d\u6587` | `json.dump` 默认 `ensure_ascii=True` | 加 `ensure_ascii=False` |
| `TypeError: Can't instantiate abstract class Record` | 子类没实现全部 `@abstractmethod` | 这不是 bug，是 ABC 在保护你 —— 去实现 `amount()` 和 `describe()` |
| 词频 Top5 全是"的/一/是" | 没过滤停用词 + 用了 1-gram | 默认配置已过滤；跑 `--gram 1 --keep-stopwords` 故意复现一次 |

---

## 七、完成后做什么

1. 回 [任务书](../../../my-docs/study01/stage0-前置基础/01-Python基础.md) 把「四、模块完成判定」和「二、知识点清单」逐条打勾
2. 更新 [00-进度看板.md](../../../my-docs/study01/00-进度看板.md)：`⬜` → `✅`
3. 把 5 个 Demo 的代码 `git commit`（commit message 用 `feat(m01): demo-01-3 增加 Investment 子类`）
4. 进入 [模块 02 · Python 进阶与异步编程](../02-python进阶与异步/)

> **⚠️ 不许跳过练习直接进模块 02。** 本模块的 5 个 Demo 看懂只要 2 小时，
> 但"关掉代码自己写出来"需要 8 小时 —— **后面那 6 小时才是真正学会的部分。**
