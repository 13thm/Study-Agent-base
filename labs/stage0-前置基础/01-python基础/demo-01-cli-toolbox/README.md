# Demo 01-1 · 命令行文本工具箱

> **对应文档**：[01-Python基础.md → Demo 01-1](../../../../my-docs/study01/stage0-前置基础/01-Python基础.md)
> **依赖**：无（纯标准库，`python3 toolbox.py` 直接跑）
> **预计耗时**：1.5~2 小时（含练习题）
> **练什么**：字符串方法、正则、容器（dict/list/set）、文件遍历、argparse、异常边界、退出码

---

## 一、这个 Demo 在训练什么

不是"学会 argparse"，而是养成三个后面每个模块都要用的习惯：

| 习惯 | 在本 Demo 里的体现 | 以后在哪用 |
|------|------------------|-----------|
| **逻辑与 IO 分离** | `text_utils.py`（纯函数）+ `toolbox.py`（打印/参数） | 模块 06 能写单测的前提 |
| **异常在边界层翻译** | 底层抛 `FileNotFoundError`，CLI 层转成"❌ 路径不存在" + 退出码 1 | Agent 工具的错误回填（阶段 3） |
| **输出可预测** | 排序用 `(-count, word)` 保证同输入同输出 | 黄金用例回归测试（模块 06） |

---

## 二、目录结构

```
demo-01-cli-toolbox/
├── README.md          ← 你在这里
├── run.sh             ← 一键演示（6 个场景，含 2 个错误场景）
├── text_utils.py      ← 逻辑层：5 个纯函数 + 12 组自测断言
├── toolbox.py         ← 交互层：argparse 子命令 dispatch
├── corpus/            ← 3 份真实语料（我写的 Agent 学习笔记，不是 lorem ipsum）
│   ├── a.txt          大模型与 Agent 基础
│   ├── b.txt          向量数据库与检索优化
│   └── c.txt          工程化与可观测性
└── out/               ← clean 子命令的输出目录（运行时自动创建，已 gitignore）
```

---

## 三、一步一步做（推荐顺序）

### 第 1 步：先跑起来，看到输出
```bash
bash run.sh
```
`run.sh` 会依次演示 6 个场景，包括**两个故意制造错误的场景**（路径不存在、参数类型错）。
先看一遍输出，心里有个"这东西能干什么"的印象。

### 第 2 步：读 `text_utils.py`（30 分钟）
按顺序读，每个函数头部的 `📌 教学点` 注释是重点：

| 函数 | 重点看什么 |
|------|----------|
| `clean()` | 为什么零宽字符是隐形炸弹；`unicodedata.normalize("NFKC")` 干了什么 |
| `tokenize()` | n-gram 切分；**为什么必须过滤停用词**（跑一次 `--keep-stopwords` 就懂了） |
| `word_freq()` | `dict.get(k, 0)` vs `setdefault` vs `Counter` 三种写法 |
| `top_n()` | **dict 没有 `.sort()`**；`sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))` |
| `iter_text_files()` | `pathlib` 的 `rglob`；为什么"路径不存在"要抛而不是返回空列表 |

读完跑一次自测：
```bash
python3 text_utils.py     # 应该输出 "✅ text_utils 自测全部通过（12 组断言）"
```

### 第 3 步：读 `toolbox.py`（20 分钟）
重点看三处：
- `build_parser()` 里的 `add_subparsers` + `set_defaults(func=...)` 模式
- `cmd_freq()` 里的异常边界（`print(..., file=sys.stderr)` 而不是 stdout）
- `if __name__ == "__main__"` 里的 `KeyboardInterrupt` 处理与退出码 130

### 第 4 步：自己敲一遍（★ 最重要，别跳过）
**关掉这两个文件**，新建 `my_toolbox.py`，凭记忆实现 `stat` 子命令。
写不出来的地方就是没学会的地方 —— 回去看，再关掉，再写。

### 第 5 步：做下面的练习题

---

## 四、预期输出（跑 `bash run.sh` 应该看到）

```
── 1. freq：递归读目录，合并统计词频 Top 5 ──
文件数: 3   总字符: 1549   去重词数: 770
rank  word           count
----------------------------
1     模型                13
2     检索                 9
3     agent                5
4     召回                 5
5     向量                 5

── 2. stat：逐文件字符统计 ──
file                  中文     英文词      总字符     行数
------------------------------------------------
a.txt                346      15      515     18
b.txt                365      14      512     20
c.txt                336      17      522     21
------------------------------------------------
合计                 1047      46     1549     59

── 3. clean：清洗并另存 ──
✅ 清洗完成: corpus/a.txt → out/a.clean.txt
   原始 515 字符 → 清洗后 514 字符（减少 1，0.2%）

── 4. 异常边界：路径不存在 ──
❌ 路径不存在: 不存在的目录
   提示：--path 可以是单个文件，也可以是目录
退出码 = 1

── 5. 参数错误：--top abc ──
usage: toolbox.py freq [-h] ...
toolbox.py freq: error: argument --top: invalid int value: 'abc'
退出码 = 2
```

> 数字会随你改动 corpus 而变，**结构一致即可**。

### 停用词实验（本 Demo 最有教学价值的一步）
```bash
python3 toolbox.py freq --path corpus/ --top 6 --gram 1 --keep-stopwords
# → Top6: 的(30) 一(20) 是(18) 用(15) 模(14) 型(13)     ← 全是虚词，信息量为零

python3 toolbox.py freq --path corpus/ --top 6 --gram 1
# → Top6: 用 模 型 回 工 检                              ← 过滤后才有区分度

python3 toolbox.py freq --path corpus/ --top 6            # 默认 2-gram
# → Top6: 模型 检索 agent 召回 向量 工具                  ← 这才像"词"
```
**把这个现象记住**：阶段 2 做 BM25 混合检索时，中文不分词 + 不去停用词，
检索效果会烂得莫名其妙，而你会立刻知道原因。

---

## 五、练习题（做完才算过关）

| # | 难度 | 题目 | 提示 |
|---|------|------|------|
| 1 | ⭐ | 给 `freq` 加 `--out result.json`，把 Top N 写成 JSON 文件 | `json.dump(..., ensure_ascii=False, indent=2)`；记得 `dst.parent.mkdir(parents=True, exist_ok=True)` |
| 2 | ⭐ | 给 `stat` 加一列"预估 token 数"（中文字数×1.6 + 英文词数×1.3） | 阶段 1 模块 01 的 Token 统计器就是这个的进阶版 |
| 3 | ⭐⭐ | 新增 `grep` 子命令：`python toolbox.py grep --path corpus/ --kw 向量 --context 1`，打印命中行及上下各 1 行 | `enumerate(lines)` + 切片；注意第一行没有"上一行" |
| 4 | ⭐⭐ | 新增 `diff` 子命令：比较两个文件的词频差异，输出"只在 A 出现的词 / 只在 B 出现的词 / 频次差最大的词" | 用 `set` 的交并差；这就是文档去重的雏形 |
| 5 | ⭐⭐⭐ | 把 `tokenize` 换成 `jieba.cut_for_search`，对比 Top10 的差异，写进 README | `pip install jieba`；体会"分词质量决定检索质量" |
| 6 | ⭐⭐⭐ | 给 `text_utils.py` 补 5 个断言：`clean` 处理 `\r\n`、空字符串、只有标点、超长单行、混合 emoji | emoji 是 4 字节字符，`len()` 与视觉字符数不一致，试试 `"👨‍👩‍👧"` |

---

## 六、验收清单（对着打勾）

- [ ] `bash run.sh` 全部 6 个场景输出正常，无 traceback
- [ ] `python3 text_utils.py` 自测通过
- [ ] 传目录能递归读多个文件，传单个文件也能用（`--path corpus/a.txt` 试一下）
- [ ] 文件不存在 → 友好错误 + 退出码 1（`echo $?` 验证）
- [ ] `--help` 与 `freq --help` 输出清晰
- [ ] **关掉参考代码，30 分钟内独立写出 `stat` 子命令**
- [ ] 完成练习 1~4（5、6 选做）
- [ ] 能口头解释：为什么 `dict` 不能 `.sort()`、为什么必须写 `encoding="utf-8"`、
      为什么路径不存在要抛异常而不是返回空列表

---

## 七、踩坑记录（自己填）

| 日期 | 现象 | 原因 | 解法 |
|------|------|------|------|
| | | | |
