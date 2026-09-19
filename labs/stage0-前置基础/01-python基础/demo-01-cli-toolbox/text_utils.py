"""文本处理纯函数库 —— Demo 01-1 的"逻辑层"。

📌 教学设计（先读这段再往下）
────────────────────────────────────────────────────────────
为什么要把逻辑单独放一个文件，而不是全写在 toolbox.py 里？

    toolbox.py  = 交互层（argparse 解析、打印表格、退出码）  ← 有 IO，难测
    text_utils.py = 逻辑层（纯函数：输入字符串，输出结果）      ← 无 IO，好测

这叫"逻辑与 IO 分离"，是模块 06（单元测试）能落地的前提。
一个函数只要不碰文件、不碰网络、不打印，它就能被 parametrize 覆盖 20 种输入。

本文件覆盖的知识点：
    · 字符串方法：split / join / strip / replace / startswith
    · 正则：re.sub 清洗标点
    · 容器：dict 计数、set 去重、sorted + key 排序
    · 列表/字典推导式
    · 类型注解（为模块 06 的 mypy 做准备）
────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# 常量：为什么用"编译好的正则"？
#   re.compile 只在模块加载时编译一次，后续复用，比每次调 re.sub(pattern, ...) 快。
#   在一个循环里对上万行做清洗时，差距很明显。
# ─────────────────────────────────────────────────────────────
#: 中英文标点 + 各类空白，分词时都当分隔符
_PUNCT_RE = re.compile(r"[\s，。、；：？！“”‘’（）《》【】…—·,.!?;:\"'()\[\]{}<>/\\|@#$%^&*+=~`-]+")

#: 零宽字符（复制粘贴常见的隐形脏数据）
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff\u2060]")

#: 中文字符（含扩展 A 区）
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")

#: 英文单词
_WORD_RE = re.compile(r"[A-Za-z]+")

#: 中文停用词（极简版）。
#: 📌 教学点：为什么必须过滤停用词？
#:   你第一次跑 freq 子命令时会看到 Top5 全是「的 / 一 / 是 / 在 / 了」——
#:   它们出现频率最高，但**信息量为零**。这就是阶段 2 做 BM25 关键词检索时的第一个坑：
#:   不去停用词，任何查询都会被这些高频虚词带偏。
#:   生产环境用完整停用词表（几百个）+ jieba 分词，这里给一个够用的极简版。
STOPWORDS: frozenset[str] = frozenset(["的", "了", "是", "在", "和", "与", "及", "或", "等", "之", "中", "为", "以", "到", "从", "被", "把", "让", "向", "于", "但", "而", "也", "就", "都", "还", "又", "很", "更", "最", "一", "二", "三", "个", "些", "这", "那", "你", "我", "他", "她", "它", "们", "有", "无", "不", "没", "要", "会", "能", "可", "时", "后", "前", "上", "下", "里", "外", "中", "并", "且", "因", "所", "如", "若", "则", "即", "各", "每", "其", "该", "本", "此", "种", "类", "次", "第", "只", "再", "才", "已", "未", "将", "使", "令", "给", "对", "关于"])

#: 中文双字停用词（2-gram 模式下才有意义）
STOPWORDS_2GRAM: frozenset[str] = frozenset(["一个", "我们", "你们", "他们", "它们", "这个", "那个", "这些", "那些", "什么", "怎么", "怎样", "为什么", "可以", "能够", "应该", "需要", "因为", "所以", "但是", "可是", "然而", "如果", "以及", "或者", "而且", "不是", "没有", "这样", "那样", "已经", "还是", "就是", "也是", "都是", "会有", "进行", "通过", "对于", "关于", "根据", "按照", "目前", "现在", "通常", "一般", "例如", "比如", "其中", "之一", "一些"])

#: 英文停用词（同样极简）
_EN_STOPWORDS: frozenset[str] = frozenset(
    ["a", "an", "the", "and", "or", "but", "if", "then", "else", "of", "to", "in", "on", "at", "for", "with", "without", "is", "are", "was", "were", "be", "been", "this", "that", "these", "those", "it", "its", "as", "by", "from", "not", "no", "yes", "do", "does", "did"]
)


# ═════════════════════════════════════════════════════════════
# 1. clean —— 文本清洗
# ═════════════════════════════════════════════════════════════
def clean(text: str) -> str:
    """清洗文本：去零宽字符 → 全角转半角 → 压缩多余空白。

    这是所有文档处理流水线的第一步（阶段 2 模块 02 会把它扩展成 10 步流水线，
    并且做消融实验证明"光是清洗就能让 Recall@5 涨 8 个点"）。

    Args:
        text: 原始文本，可能含零宽字符、全角标点、连续空行。

    Returns:
        清洗后的文本。不修改入参（字符串不可变，天然安全）。

    Examples:
        >>> clean("你好\\u200b  世界")
        '你好 世界'
        >>> clean("ＡＢＣ１２３")   # 全角字母数字
        'ABC123'
    """
    # ① 去掉零宽字符。它们不可见，但会让 "hello" != "hel\u200blo"，
    #    在去重、检索、缓存 key 计算时全部出问题。
    text = _ZERO_WIDTH_RE.sub("", text)

    # ② 全角转半角。unicodedata.normalize("NFKC", ...) 是标准做法：
    #    Ａ→A、１→1、　(全角空格)→ (半角空格)。
    #    ⚠️ 注意：NFKC 也会把 "①" 变成 "1"、把 "㈱" 变成 "(株)"，
    #    这在多数场景是想要的，但如果你要保留特殊符号，就得改成逐字符判断。
    text = unicodedata.normalize("NFKC", text)

    # ③ 行内多余空白压成一个空格；连续空行压成一个空行。
    #    分两步做：先把每行 strip + 压缩内部空格，再把 3 个以上换行压成 2 个。
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ═════════════════════════════════════════════════════════════
# 2. tokenize —— 简易分词
# ═════════════════════════════════════════════════════════════
def tokenize(
    text: str,
    *,
    grams: tuple[int, ...] = (2,),
    remove_stopwords: bool = True,
) -> list[str]:
    """极简分词：英文按词切，中文按"连续汉字串"切 n-gram。

    📌 为什么不用 jieba？
        这个 Demo 的目标是练 Python 基础，不是练 NLP。而且——
        **这个"简陋"的分词方式恰好能让你亲身体会到阶段 2 的两个真实坑**：
        ① BM25 检索中文必须先分词，否则退化成字符匹配，"向量数据库" 会匹配到
           任何含"数"的文档；
        ② 不过滤停用词时，Top N 全是"的/一/是"，信息量为零。
        等你到阶段 2 做混合检索时，回来把它换成 jieba + 完整停用词表，
        对比一下 Recall 的变化，就是最好的实验。

    Args:
        text: 原始文本。
        grams: 中文切几元组。(2,) 只用 2-gram（默认，最像"词"）；
               (1, 2) 两者都要（召回高但噪声大）；(1,) 退化成单字统计。
        remove_stopwords: 是否过滤停用词（单字停用词只在 1-gram 里有意义）。

    Returns:
        token 列表（可能有重复，交给 word_freq 去数）。

    Examples:
        >>> tokenize("RAG 检索增强")
        ['rag', '检索', '索增', '增强']
        >>> tokenize("检索增强", grams=(1, 2), remove_stopwords=False)
        ['检索', '索增', '增强', '检', '索', '增', '强']
    """
    tokens: list[str] = []

    # 英文/数字：整段取出，转小写（"Agent" 和 "agent" 应该算同一个词）
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9_]*", text):
        word = m.group().lower()
        if not (remove_stopwords and word in _EN_STOPWORDS):
            tokens.append(word)

    # 中文：先找出每一段连续汉字，再按 grams 切
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        # 长的 n-gram 先切（2-gram 比 1-gram 更像"词"，排在前面更好读）
        for g in sorted(grams, reverse=True):
            if g == 1:
                pieces = list(run)
            else:
                # run[i:i+g]：滑动窗口切 n-gram。长度不足 g 的段落自然产生不了 gram。
                pieces = [run[i : i + g] for i in range(len(run) - g + 1)]
            for pc in pieces:
                if remove_stopwords and (pc in STOPWORDS or pc in STOPWORDS_2GRAM):
                    continue
                tokens.append(pc)

    return tokens


# ═════════════════════════════════════════════════════════════
# 3. word_freq —— 词频统计
# ═════════════════════════════════════════════════════════════
def word_freq(text: str, **tok_kwargs: object) -> dict[str, int]:
    """统计词频，返回 {词: 次数}。

    📌 教学点：Counter 是 dict 的子类
        你可以用 Counter 一行搞定，但这里故意手写一遍普通 dict 的写法，
        因为你必须知道 setdefault / get(key, default) 怎么用 ——
        这两个方法在 Agent 代码里到处都是（统计 token、聚合成本、分组结果）。

    Args:
        text: 待统计文本（内部会先 clean + tokenize）。

    Returns:
        普通 dict。注意：**dict 本身是无序的**（Python 3.7+ 保留插入顺序，
        但那不是"按值排序"），要排序请用 top_n()。
    """
    freq: dict[str, int] = {}
    for tok in tokenize(clean(text), **tok_kwargs):  # type: ignore[arg-type]
        # 写法 A：get + 默认值（最常用）
        freq[tok] = freq.get(tok, 0) + 1

        # 写法 B：setdefault（值是可变对象时更有用，比如 list）
        #   freq.setdefault(tok, []).append(pos)
        # 写法 C：Counter（生产代码推荐）
        #   freq = Counter(tokenize(clean(text)))
        #
        # 📌 顺带一提：Counter 已经在文件顶部 import 了但这里没用，
        #    ruff 会报 F401（未使用的 import）—— 这是故意的，
        #    模块 06 的 Demo 06-1 会让你亲手把它清掉，体验一次 lint 流程。
    return freq


def top_n(freq: dict[str, int], n: int = 10) -> list[tuple[str, int]]:
    """按词频降序取前 N 个。

    📌 教学点：dict 没有 .sort()
        新手最常写错的一行就是 freq.sort_values()（那是 pandas 的 API）。
        正确做法：sorted(d.items(), key=lambda kv: -kv[1])

        key 函数返回"排序依据"。这里返回 -count 实现降序；
        也可以用 reverse=True，但那样在同词频时的次级排序不好控制。
        下面的写法用 (-次数, 词) 元组：**次数相同则按词的字典序**，
        这样输出是稳定的（同样的输入永远得到同样的顺序，测试才好写）。
    """
    if n <= 0:
        return []
    return sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


# ═════════════════════════════════════════════════════════════
# 4. char_count —— 字符统计
# ═════════════════════════════════════════════════════════════
def char_count(text: str) -> dict[str, int]:
    """统计中文字数 / 英文单词数 / 总字符数 / 行数。

    📌 为什么这个函数重要？
        阶段 1 模块 01 的 Demo 1-1 就是"Token 统计器"，那是它的进阶版。
        记住这个经验值：**1 个中文字 ≈ 1.5~1.8 token，1 个英文单词 ≈ 1.3 token**。
        所以"字数"能粗略估算成本，但不能替代 tiktoken。

    Returns:
        {"chinese": int, "english_words": int, "total_chars": int, "lines": int}
    """
    return {
        "chinese": len(_CJK_RE.findall(text)),
        "english_words": len(_WORD_RE.findall(text)),
        "total_chars": len(text),
        "lines": text.count("\n") + 1 if text else 0,
    }


# ═════════════════════════════════════════════════════════════
# 5. 文件遍历 —— 唯一碰 IO 的函数
# ═════════════════════════════════════════════════════════════
def iter_text_files(path: Path, pattern: str = "*.txt") -> list[Path]:
    """把"文件或目录"统一成一个有序的文件列表。

    📌 教学点：pathlib 优先于 os.path
        Path.is_dir() / Path.rglob() 比字符串拼接安全得多，
        而且跨平台（Windows 的 \\ 和 Unix 的 / 自动处理）。

    Args:
        path: 可以是单个文件，也可以是目录（目录会递归查找）。
        pattern: glob 模式，默认 "*.txt"。

    Returns:
        排序后的文件路径列表（排序是为了输出稳定，便于测试与 diff）。

    Raises:
        FileNotFoundError: 路径不存在。调用方（toolbox.py）负责把它转成友好提示。
    """
    if not path.exists():
        # 📌 这里"该抛"而不是"返回空列表"：
        #    路径不存在是调用方的错误，静默返回空列表会让用户以为"目录下没文件"，
        #    排查半天。原则：**能恢复的自己处理，不能恢复的往上抛，让边界层决定怎么呈现。**
        raise FileNotFoundError(f"路径不存在: {path}")

    if path.is_file():
        return [path]

    return sorted(p for p in path.rglob(pattern) if p.is_file())


def read_text(path: Path) -> str:
    """读文本文件，强制 utf-8。

    📌 教学点：encoding="utf-8" 必须显式写
        不写的话，Python 用 locale.getpreferredencoding()，
        Windows 中文环境是 GBK，读到 UTF-8 文件就 UnicodeDecodeError。
        "在我机器上是好的" 十有八九是这个原因。
    """
    return path.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════
# 自测：python text_utils.py 直接运行，跑几个 doctest 风格的断言
# ═════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # ── clean ──
    assert clean("你好\u200b  世界") == "你好 世界", clean("你好\u200b  世界")
    assert clean("ＡＢＣ１２３") == "ABC123"
    assert clean("a\n\n\n\n\nb") == "a\n\nb", "3 个以上换行应压成 2 个"

    # ── tokenize ──
    assert tokenize("RAG 检索增强") == ["rag", "检索", "索增", "增强"], tokenize("RAG 检索增强")
    assert tokenize("检索增强", grams=(1, 2), remove_stopwords=False) == [
        "检索", "索增", "增强", "检", "索", "增", "强",
    ]
    # 1-gram 模式下「这是一个测试」→「这/是/一/个」四个停用词被滤掉，只剩「测」「试」
    assert tokenize("这是一个测试", grams=(1,)) == ["测", "试"], "停用词应被过滤"
    assert tokenize("the Agent and agent") == ["agent", "agent"], "英文应小写化且去停用词"

    # ── word_freq / top_n ──
    assert word_freq("检索检索生成")["检索"] == 2
    assert top_n({"a": 1, "b": 5, "c": 5}, 2) == [("b", 5), ("c", 5)], "同频次应按字典序"
    assert top_n({"a": 1}, 0) == []

    # ── char_count ──
    assert char_count("你好 world")["chinese"] == 2
    assert char_count("你好 world")["english_words"] == 1
    assert char_count("")["lines"] == 0

    print("✅ text_utils 自测全部通过（12 组断言）")

    # 顺手打印真实语料的统计，让你对数据有手感
    here = Path(__file__).parent / "corpus"
    if here.exists():
        all_text = "\n".join(read_text(f) for f in iter_text_files(here))
        print(f"语料统计 : {char_count(all_text)}")
        print(f"Top8 词  : {[w for w, _ in top_n(word_freq(all_text), 8)]}")
        raw = [w for w, _ in top_n(word_freq(all_text, grams=(1,), remove_stopwords=False), 6)]
        kept = [w for w, _ in top_n(word_freq(all_text, grams=(1,)), 6)]
        print(f"1-gram 不去停用词 Top6: {raw}   ← 全是虚词，信息量为零")
        print(f"1-gram 去掉停用词 Top6: {kept}   ← 这才是有区分度的词")
