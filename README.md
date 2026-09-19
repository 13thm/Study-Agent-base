# Study-Agent-base · Agent 工程师零基础到求职的完整学习工程

> 一套**任务书 + 可运行代码**双轨制的学习工程：
> `my-docs/` 回答「学什么、做到什么程度算过关」，`labs/` 回答「代码长什么样、怎么跑、跑出来应该看到什么」。

---

## 一、仓库结构

```
Study-Agent-base/
├── README.md                 ← 你在这里
├── my-docs/                  规划层（任务书）
│   ├── Agent 工程师 小白完整学习路线.md      7 个阶段的完整路线图
│   ├── Agent 工程师招聘要求汇总.md           97 条 JD 要求（编号被任务书全程引用）
│   ├── GitHub 热门 Agent 开源项目.md         29 个开源项目 + 求职价值分析
│   └── study01/              ★ 执行层文档（33 个模块任务书 + 7 份阶段说明书）
│       ├── README.md                     使用说明与硬规矩
│       ├── 00-进度看板.md                 每天从这里开始（33 模块打卡表）
│       ├── stage0-前置基础/               6 个模块
│       ├── stage1-大模型与Prompt工程/      5 个模块
│       ├── stage2-RAG检索增强生成/         5 个模块 → ⭐ 项目 1
│       ├── stage3-单Agent开发/            6 个模块 → ⭐⭐ 项目 2
│       ├── stage4-MultiAgent与MCP/        4 个模块 → ⭐ 项目 3
│       ├── stage5-工程化与可观测安全/       3 个模块
│       └── stage6-项目打磨与求职/           4 个模块
│
└── labs/                     ★ 代码层（可运行教学 Demo）
    ├── README.md             lab 的组织约定与设计原则
    ├── stage0-前置基础/       ✅ 已完成：29 个 Demo 全部跑通
    └── stage1-大模型与Prompt工程/  ✅ 模块 01 完成（5 Demo + prompt-toolbox）
```

---

## 二、两层文档怎么配合用

| | `my-docs/study01/` | `labs/` |
|---|---|---|
| **是什么** | 任务书：知识点清单、Demo 规格、验收标准、面试考点 | 实现：可运行代码、一键演示脚本、预期输出、练习题 |
| **怎么用** | 每天开工先看 `00-进度看板.md`，找到当前模块，读任务书知道目标 | `cd` 到对应 Demo 目录 `bash run.sh`，看输出 → 读 `📌` 注释 → **关掉代码自己写一遍** |
| **完成标志** | 任务书里「四、模块完成判定」全部打勾 | Demo 的验收清单全部打勾 + 练习题做完 |

> **⚠️ 最重要的一条规矩**：看懂 ≠ 会写。每个 Demo 都必须**关掉参考代码自己重做一遍**，
> 写不出来的地方才是真正没学会的地方。

---

## 三、当前进度

| 阶段 | 任务书 | 配套代码 | 状态 |
|---|---|---|---|
| 阶段 0 · 前置基础 | 6 模块 ✅ | [`labs/stage0-前置基础/`](./labs/stage0-前置基础/) | ✅ **29 个 Demo 全部跑通**<br>104 pytest / 覆盖率 86% / ruff+mypy 零报错 |
| 阶段 1 · 大模型与 Prompt | 5 模块 ✅ | [`labs/stage1-大模型与Prompt工程/`](./labs/stage1-大模型与Prompt工程/) | ✅ 模块 01 完成（5 Demo）<br>48 pytest / 覆盖率 80% / mock 冒烟 6/6<br>⬜ 模块 02~05 待建 |
| 阶段 2 · RAG | 5 模块 ✅ | — | ⬜ 任务书就绪 |
| 阶段 3 · 单 Agent | 6 模块 ✅ | — | ⬜ 任务书就绪 |
| 阶段 4 · Multi-Agent + MCP | 4 模块 ✅ | — | ⬜ 任务书就绪 |
| 阶段 5 · 工程化 | 3 模块 ✅ | — | ⬜ 任务书就绪 |
| 阶段 6 · 项目打磨与求职 | 4 模块 ✅ | — | ⬜ 任务书就绪（含 120 道面试题库） |

**文档层已 100% 完成**（33 个模块任务书 + 7 份阶段说明书 + 进度看板，共 40 份、约 59 万字）。
代码层按阶段推进，目前完成阶段 0 全部 + 阶段 1 模块 01。

---

## 四、5 分钟上手

```bash
# ── 阶段 0（Python / 后端 / 数据库 / 异步任务 / 测试）──
cd labs/stage0-前置基础
make setup                    # 建 .venv + 装依赖（uv 约 30 秒）
make m1                       # 跑模块 01 的 5 个 Demo
make all                      # 跑全部 29 个 Demo（约 6 分钟）
make check                    # ruff + mypy + 104 个测试
cd fastapi-chat-backend && make serve    # 起服务，打开 http://127.0.0.1:8000/docs

# ── 阶段 1（LLM 基础与 API 调用）──
cd ../stage1-大模型与Prompt工程
make setup
make mock                     # 启动 OpenAI 兼容的 mock LLM（不需要 API Key）
make m1                       # 跑模块 01 的 5 个 Demo
make check                    # lint + mypy + 48 测试 + mock 冒烟 6 项
```

> **不需要 Docker、不需要 API Key、不需要联网**（除装依赖）。
> 所有外部依赖都做了自动降级：MySQL/PG→SQLite、Redis→fakeredis、MinIO→本地文件系统、
> LLM API→本地 mock 服务、Celery Broker→内置迷你运行时、Nginx→配置讲解模式。
> 想跑真实服务时 `docker compose up -d` 即可，**业务代码一行都不用改**。

---

## 五、这套工程的三个特点

### ① 每个 Demo 都自带「反例」
不只演示正确写法，还**现场复现错误写法会怎样**：
裸 `except:` 吞掉 Ctrl+C、`finally` 里 return 覆盖返回值、可变默认参数被所有实例共享、
`time.sleep` 卡死事件循环、`proxy_buffering` 让 SSE 变一次性返回、后过滤导致租户数据泄漏……

### ② 踩过的坑全部留在代码注释里
所有 `📌 踩坑记录` 都是**真实遇到并修好的 bug**，不是编的教材。例如：

| 坑 | 被谁抓出来的 |
|---|---|
| `UnicodeDecodeError` 是 `ValueError` 子类，except 顺序写反 | 手动测试发现退出码不对 |
| `get_redis()` 惰性初始化不是线程安全的 | `test_idempotency.py::并发10个只有一个成功` |
| SQLite 默认不强制外键 → 级联删除静默失效 | `test_db.py::级联删除` |
| ORM 级联依赖内存里的关系集合（陈旧快照） | `test_db.py::级联删除` |
| 多阶段任务的进度条会往回跳 | `test_tasks_api.py::进度单调递增` |
| Celery 的 `task.run` 被包过一层，`self` 不是你以为的那个 | 无限重试到 max_retries |
| 温度对照实验数据全是假的（相似度恒为 1.000） | 自查发现 mock 的 hash 没混入调用序号 |
| `prices.yaml` 加一个字符串字段就让整张价格表静默降级 | `test_tokens.py::价格表非空` |
| Makefile 里 `$$@` 被转义成 shell 的空 `$@` | `make m3` 打印"模块  的配套代码" |
| 测试起了后台线程没收尾，污染下一个测试 | `make check` 连跑时 pytest 偶发只跑 32/104 个用例 |
| pytest 结束时 terminate 掉 mock 服务，uvicorn 优雅关闭期间 /health 仍返回 200 | `make check` 的 smoke 步骤 6 项全红，但单跑 `make smoke` 永远绿 |

> 这些就是面试时最值钱的素材 —— 比"我做过一个 RAG 项目"有说服力得多。

### ③ 所有结论都有实测数字
不写"效果显著提升"，只写"Recall@5 从 0.78 → 0.91"、"并发 20 请求串行 10.16s → 并发 0.56s（17.8×）"、
"降级路由在云端全挂时 20/20 成功走本地兜底"。这些数字直接进阶段 6 的简历。

---

## 六、最终目标（阶段 6 结束时的交付物）

| 产出 | 来源 | 简历用途 |
|---|---|---|
| `fastapi-chat-backend` | 阶段 0 | ✅ 已完成 —— 证明后端基本功 |
| `prompt-toolbox` | 阶段 1 | 🔨 进行中 —— 证明懂 LLM 与提示词 |
| **项目 1：私有知识库 RAG 系统** | 阶段 2 | ⭐ 简历核心项目 1 |
| **项目 2：LangGraph 任务规划 Agent** | 阶段 3 | ⭐⭐ 简历核心项目 2 |
| **项目 3：多 Agent 文档智能团队** | 阶段 4 | ⭐⭐ 简历核心项目 3 |
| 部署 + 评测 + 安全加固 | 阶段 5 | 证明生产级能力（分水岭） |
| 简历 + 120 题面试题库自评 + 投递台账 | 阶段 6 | 面试直接背 |

---

## 七、需要我继续做什么

代码层按阶段推进，随时可以生成下一个 lab：

```
labs/stage1-大模型与Prompt工程/   模块 02~05（提示词注册表 / 结构化输出 / 多模态 / 上下文工程）
labs/stage2-RAG检索增强生成/      模块 01~05 + 项目 1 kb-rag-system
labs/stage3-单Agent开发/          模块 01~06 + 项目 2 task-planner-agent
labs/stage4-MultiAgent与MCP/      模块 01~04 + 项目 3 multi-agent-doc-team
labs/stage5-工程化与可观测安全/     模块 01~03（改造前三个项目）
```
说一句「继续做阶段 N 的模块 M」即可。每份任务书里已经写好了目录结构、接口签名、
预期输出与验收标准，所以生成的代码能**严格对齐文档**，不会跑偏。
