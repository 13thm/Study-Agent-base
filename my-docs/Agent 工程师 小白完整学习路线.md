# Agent 工程师 · 小白完整学习路线

> **前置假设**：零基础小白，只会电脑基础操作，不懂 Python、AI、后端。
>
> **岗位定位**：Agent 应用开发工程师（最容易入职，市场需求量最大），不是底层大模型算法岗。
>
> **核心目标**：独立完成 3 个高质量 GitHub 项目，简历可投递，面试能讲清原理 + 踩坑，能手写核心代码。
>
> **用到的核心开源库**：Python、FastAPI、SQLAlchemy、Celery、LangChain、LangGraph、LlamaIndex、PydanticAI、Chroma/Qdrant/Milvus/PGVector、AutoGen、CrewAI、MetaGPT、MCP、Ollama、Docker、LangSmith

---

## 重要区分：Agent 工程师分两类

1. **Agent 应用开发**（本路线主攻方向，社招/校招岗位最多，门槛适中）：用 LLM + 框架搭建智能体、RAG、工具调用、多智能体、工程部署、可观测；不需要训练大模型。
2. **Agent 底层算法岗**：需要深度学习、微调、RL，门槛极高，本路线不主攻。

---

## 整体阶段总览

| 阶段 | 主题 | 核心内容 |
|------|------|---------|
| 0 | 前置基础 | Python + 计算机基础 + 后端框架 + 数据库 + Git |
| 1 | 大模型基础 & Prompt 工程 | LLM 原理、提示词、结构化输出 |
| 2 | RAG 检索增强生成 | RAG 全链路、向量库、召回优化，**第一个完整项目** |
| 3 | 单 Agent 核心 | ReAct、Function Calling、LangGraph，**第二个项目** |
| 4 | Multi-Agent + MCP 协议 | 角色化多 Agent、MCP，**第三个项目** |
| 5 | 工程化、可观测、安全、评测 | 生产化改造，Docker/K8s/CI-CD、可观测性、提示注入防护 |
| 6 | 项目打磨、简历、面试投递 | 简历 + 面试复盘，投递岗位 |

---

## 阶段 0：前置基础 —— Python + 后端框架 + 数据库 + Linux/Git

> **目标**：能写规范且带单元测试的 Python，会用 Git，懂 Linux 基础，能写生产级接口（含 SSE / WebSocket / 异步任务）。不要跳过，跳过后面完全看不懂。

### 模块一：Python 基础

**学习内容：**

1. 变量、数据类型、列表、字典、集合
2. 函数、类、面向对象（**重点**，Agent 框架大量用到类和继承）
3. 异常捕获 `try-except`（Agent 工具调用必备，处理 LLM 报错）
4. 文件读写、JSON 处理（LLM 输出大量 JSON）
5. 虚拟环境 `venv` / `conda`，`pip` 包管理

**实操任务：**

- 完成 100 道基础 Python 练习题
- 写脚本：读取本地 `.txt` 文档，解析成 JSON，保存文件
- 学会 `pip install xxx`，会创建和激活虚拟环境

**验收标准**：能独立写脚本读取文件、解析 JSON、处理异常。

### 模块二：Python 进阶 + 异步编程

**学习内容：**

1. 装饰器（理解 `@decorator` 语法，框架中大量使用）
2. 异步编程 `async/await`、`asyncio`（流式 SSE、LLM 异步调用必备）
3. Pydantic（**超级重要**，结构化输出校验，PydanticAI 底层依赖）

**实操任务：**

- 写异步函数，并发调用 2 个 API
- 用 Pydantic 定义数据模型，校验 JSON，捕获字段异常

**验收标准**：会写 `async` 代码，会用 Pydantic 做数据校验。

### 模块三：后端基础 + Linux + Git

**学习内容：**

1. **FastAPI 核心**：路由、Pydantic 请求/响应模型、依赖注入（Dependency Injection）、中间件、异常处理器
2. **流式输出两种方案**：SSE（大模型逐 Token 吐字首选）、WebSocket（多轮实时对话、双向推送）
3. **接口健壮性设计**：幂等（防重复提交）、超时重试、限流、熔断降级 —— JD 高频硬性要求
4. **Flask 了解即可**：部分老项目仍用 Flask，能看懂并能改就行
5. **Nginx 反向代理**：Agent 服务上线的标配，懂反向代理、负载均衡、HTTPS 配置
6. **API 文档**：FastAPI 自动生成的 OpenAPI / Swagger，以及用 Postman 调接口

**另外必须掌握的 Linux 与 Git：**

1. **Linux 命令**：`cd`、`ls`、`pwd`、`mkdir`、`rm`、`vim`、日志排查（`tail -f`、`grep`、`less`）、进程与端口（`ps`、`lsof`、`kill`）、权限（`chmod`）、`systemctl` 服务管理、`ssh` 远程登录
2. **Git 进阶**：`commit`、`branch`、`merge`、`rebase`、`cherry-pick`、`stash`、`push`、`pull`、`clone`；GitHub 建仓库、**Pull Request 与代码评审流程**；`.gitignore` 的正确使用

**实操任务：**

- 用 FastAPI 写一个流式 SSE 接口，返回逐段文本（模拟大模型打字机效果）
- 用 WebSocket 写一个实时对话回声服务
- 给某个「下单/扣费」接口加幂等键，重复请求只生效一次
- 用 Nginx 把 FastAPI 服务代理到 80 端口，本地跑通
- 在 GitHub 新建仓库，提交代码，提一个 PR 并自查 diff

**验收标准**：能本地跑 FastAPI 服务（含 SSE + WebSocket），能用 Nginx 代理，能把代码提交到 GitHub 并走 PR 流程。

### 模块四：数据库与存储

**学习内容：**

1. **MySQL 基础**：库表设计、索引、增删改查、多表关联查询、事务
2. **PostgreSQL 同样高频**：很多 Agent 项目直接用 PG（配合 **PGVector** 扩展可同时存业务数据和向量，一套库搞定），了解它与 MySQL 的差异
3. **SQLAlchemy 2.0 ORM**（重要）：Agent 项目不会手写 SQL，声明式模型 + Session + 异步查询是主流写法
4. **Redis 缓存**：五大数据类型、TTL 过期、**会话记忆 / 短期记忆存储**、分布式锁、用 `redis-stack` 做轻量向量检索
5. **MongoDB 了解**：对话记录、文档元信息这类半结构化数据常用它存
6. **MinIO / 阿里云 OSS 对象存储**：上传的 PDF / Word / 图片不能塞进数据库，必须走对象存储，RAG 项目第一步就是它

> 不用深入数据库内核与调优，会设计表、会 CRUD、会用 ORM、懂索引为什么快即可。

**实操任务：**

- 用 SQLAlchemy 定义 `User` / `Session` / `Message` 三张表，跑通增删改查
- 写 FastAPI 接口，把对话历史存入 Redis 并设置 30 分钟过期
- 搭建 MinIO，写一个文件上传接口，存完把访问地址回写数据库

### 模块五：异步任务与消息队列

**为什么学**：文档向量化、批量灌库、长耗时 Agent 任务，绝不能放在 HTTP 请求里同步跑 —— 一灌几千个 chunk 就直接超时，这是新手最容易踩的生产坑。

**学习内容：**

1. **Celery + Redis Broker**：生产者/消费者模型、Task 定义、异步派发、结果回查、失败重试、定时任务（Beat）
2. **RabbitMQ 了解**：Exchange / Queue / 死信队列基本概念，知道它和 Redis 作为 Broker 的差别
3. **任务进度上报**：用 Redis 存进度百分比，前端轮询或走 SSE 推送（「文档解析中 60%」这种体验）

**实操任务：** 上传文档接口立即返回 `task_id`，后台 Celery 跑解析 + 向量化，再用 `/progress/{task_id}` 查进度。

### 模块六：代码规范与单元测试（JD 明确要求，很多人忽视）

**学习内容：**

1. **规范工具**：`ruff`（Lint + 格式化，替代 Flake8 + Black）、`mypy` 静态类型检查
2. **pytest**：fixture、`parametrize` 参数化、`monkeypatch` mock 掉 LLM API（**关键技能**，否则每次跑测试都在烧钱）
3. **测试覆盖率** `pytest-cov`，理解「核心链路必须有测试」
4. **项目结构分层**：`api` / `service` / `repository` / `agent` / `tools` / `config`，别把几千行代码全堆在 `main.py`
5. 用 `uv` 或 `poetry` 管依赖，提交 `pyproject.toml` 而不是手抄 `requirements.txt`

**实操任务：** 给上面的对话接口写 5 个以上 pytest 用例，mock 掉 LLM 调用，覆盖率跑到 80%。

### ✅ 阶段 0 产出

GitHub 仓库：**对话后端 Demo** —— FastAPI（SSE + WebSocket）+ SQLAlchemy + Redis 会话记忆 + MinIO 上传 + Celery 异步任务 + pytest 测试，全程走 Git 分支与 PR 流程。

---

## 阶段 1：大模型基础 & Prompt 工程

> **目标**：理解 LLM 能力边界，精通提示词工程，掌握结构化输出，看懂 Token、上下文窗口等核心概念。

### 模块一：LLM 基础理论

**学习内容：**

1. Transformer 通俗原理（不用啃数学，理解注意力机制的直觉即可）
2. 核心概念：Token、上下文窗口、Token 计费方式、**长文本截断与滑窗策略**
3. 推理参数：`temperature`、`top_p`、`top_k`、`max_tokens`、`frequency_penalty` 的含义与调参技巧
4. LLM 幻觉：产生原因与基础抑制方法
5. 主流大模型 API 调用：OpenAI、**Claude**、通义千问、**文心一言**、DeepSeek、Qwen
   - **OpenAI 兼容协议**是工程上最重要的抽象：国内大部分模型（DeepSeek / Qwen / Kimi）都兼容，改一个 `base_url` 就能切模型
   - 掌握**多模型降级**：主模型超时/限流时自动切备用模型
6. **本地模型推理 —— Ollama 部署开源模型**（企业内网、数据不能外发的刚需场景，JD 高频要求）

**实操任务：**

- 写 Python 脚本调用 LLM API，修改 `temperature` 观察输出变化
- 写代码统计输入文本的 Token 数量
- 用 Ollama 本地拉起 Qwen2.5，用同一套 OpenAI 兼容客户端分别调云端和本地模型

### 模块二：Prompt Engineering 提示工程

**学习内容：**

1. Zero-shot、Few-shot 提示范式
2. CoT 思维链、ToT 思维树、ReAct 提示词模板
3. 系统提示词（System Prompt）与用户提示词（User Prompt）的分离策略
4. 提示词版本管理与 A/B 测试思路

**实操任务：**

- 写提示词让 LLM 固定输出 JSON 格式
- 实现 CoT，解决简单推理问题
- 写一个角色提示词：AI 文档助手

### 模块三：结构化输出专项

**学习内容：**

1. 强制 JSON 输出，处理 LLM 输出 JSON 残缺、乱码等常见问题
2. 使用 Pydantic + LLM 自动校验输出格式
3. 提示词注入（Prompt Injection）基础概念（后续安全章节深入）

### 模块四：多模态基础能力

**为什么学**：纯文本 Agent 已经不满足业务需求，表单 OCR、截图理解、语音助手背后都是多模态，JD 里“了解多模态大模型基础能力”出现频率在上升。

**学习内容：**

1. 主流多模态模型：GPT-4o、Claude、Qwen-VL、Gemini
2. **图片输入两种形式**：Base64 编码 vs 图片 URL，理解 messages 里的 `image_url` 结构
3. 典型落地：表单 / 发票 / 截图 OCR、UI 设计图转代码、**扫描件直接喂图代替传统 OCR**（效果往往更好）
4. **语音链路**：ASR 转文字（Whisper）→ LLM 处理 → TTS 合成，串起语音 Agent
5. **多模态 Embedding（CLIP）**：以图搜图的原理

**实操任务：** 写一个脚本，把发票图片转成结构化 JSON（金额 / 日期 / 商家），用 Pydantic 校验。

### 模块五：上下文工程 Context Engineering

**为什么单独拎出来**：提示词工程已经卷到头了，现在面试更爱问「上下文工程」。模型能力固定，**你往上塞什么、塞多少、什么顺序，直接决定效果**。

**学习内容：**

1. 上下文窗口预算分配：System Prompt / 工具描述 / 历史对话 / RAG 结果 / 当前问题各占多少
2. 长上下文的**「中间遗忘」（Lost in the Middle）**：重要信息放开头和结尾
3. 上下文压缩：历史对话摘要、工具返回结果剪裁、只保留必要字段
4. **Prompt Caching / KV Cache 复用**：把静态的 System Prompt 和工具描述前置，能省 50%+ Token 成本（面试聊成本必说）
5. 多轮对话拼装策略：滑动窗口 vs 摘要窗口 vs 混合

### ✅ 阶段 1 产出

GitHub 项目：**提示词工具箱** —— 支持多提示词模板切换、结构化 JSON 输出、**云端 API 与本地 Ollama 一键切换**，带发票图片转 JSON 的多模态小工具。

**面试考点**：Token 计算、`temperature` 作用、幻觉成因与应对、CoT 原理、提示词注入、**OpenAI 兼容协议怎么切模型**、**Prompt Caching 怎么降本**。

---

## 阶段 2：RAG 检索增强生成

> **目标**：掌握 RAG 完整链路：文档解析 → 分块 → 向量化 → 向量库存储 → 检索 → 重排 → 生成；独立搭建 RAG 知识库系统。
>
> **为什么重要**：没有 RAG 的 Agent 很难落地，几乎所有企业级 Agent 都带知识库。RAG 是 JD 中出现频率最高的技能要求之一。

### 模块一：Embedding & 向量数据库

**学习内容：**

1. Embedding 嵌入模型原理：文本转向量、向量相似度计算（余弦相似度）
2. 向量库：**Chroma**（本地原型首选）、**Qdrant**（生产主流，带过滤与水平扩展）、**PGVector**（与业务同一个 PG，运维成本低）、**Milvus**（大规模分布式场景）
3. 检索策略：向量检索、BM25 关键词检索、**混合检索**（效果最好）

**实操任务：** 用 Chroma 加载本地文档，向量化后做相似度检索。

### 模块二：文档解析 & Chunk 分块策略

**学习内容：**

1. 文档解析库：PyPDF、Markdown 读取，Unstructured（解析复杂 PDF/Word），**Playwright / trafilatura 抓网页正文**，**openpyxl 解析 Excel 表格**
2. 文本分块策略：固定长度分块、重叠分块、**语义分块**（效果最佳）
3. 文档清洗：去除多余换行、空格、脏数据

**实操任务：** 解析 PDF 文档，做语义分块，存入向量库。

### 模块三：RAG 优化 —— 重排、过滤、召回

**学习内容：**

1. **Rerank 重排模型**（如 BGE-reranker），显著提升检索准确率
2. 元数据过滤：按文档来源、时间等维度过滤检索结果
3. RAG 常见问题与优化方案：召回污染、上下文丢失、幻觉
4. **知识库增量更新**（实际运维必须）：文档改 / 删时对应向量同步更新 —— 靠 `文档ID + chunk hash` 做去重与增量写入，而不是全量重灌
5. **RAG 效果量化评估**：构构建问答对测试集，算 **Recall@K / 命中率 / 答案忠实度（Faithfulness）**，用 **RAGAS** 框架自动打分 —— 能拿出调优前后数据对比，面试含金量极高

### 模块四：多模态 RAG 与先期检索优化

**学习内容：**

1. **图文混合知识库**：图片转描述文本入库（caption）vs 直接用多模态 Embedding，两种路线的取舍
2. **Query Rewriting 查询改写**：用户提问口语化、多轮指代不清时，先用 LLM 把问题改写/拆分再检索
3. **HyDE**：让 LLM 先生成一段假设答案，再拿它去检索，小样本场景提升明显
4. **表格与结构化数据问答（Text2SQL）**：比向量检索更适合 BI 类需求，企业高频真实需求

### 模块五：完整 RAG 项目开发

使用 **LlamaIndex** 或 **LangChain** 搭建企业知识库 RAG 系统。

**功能清单：**

1. 上传 PDF / Markdown 文档
2. 自动解析、分块、向量化存入 Chroma
3. 用户提问 → 混合检索 + Rerank → LLM 生成答案
4. 记录对话历史（支持多轮问答）
5. 增加简单前端：用 **Gradio** 快速搭建（演示最快），或用 **Streamlit / Next.js** 做更像产品的界面（简历加分）

### ✅ 阶段 2 产出

GitHub 项目 1：**私有知识库 RAG 系统**（重点项目，简历核心项目）。

**面试高频**：RAG 全链路、Chunk 策略对比、混合检索原理、Rerank 机制、RAG 幻觉怎么解决。

---

## 阶段 3：单 Agent 开发 —— 整个学习路线最重要部分

> **目标**：理解 Agent 三大核心能力（Planning 规划、Memory 记忆、Tool 调用）；熟练使用 LangGraph，手写 ReAct 循环，实现带断点和 HITL 人机介入的 Agent。
>
> **为什么最重要**：这是招聘核心考点，JD 权重最高的部分。

### 模块一：Agent 基础概念 + LangChain 基础

**学习内容：**

1. Agent 核心范式：ReAct（Reasoning + Acting）、Plan-and-Solve
2. Agent 三大组件：**Planning**（规划）、**Memory**（记忆）、**Tool Use**（工具调用）
3. LangChain 核心组件：Chain、PromptTemplate、Memory（ConversationBufferMemory、SummaryMemory）
4. Function Calling 原理：工具描述 JSON Schema，LLM 判断何时调用工具
5. **不依赖任何框架，用原生 API + while 循环手写一个 ReAct Agent**（JD 明确要求，面试区分度最高的题）
6. 理解 **Agent Runtime 运行时原理**：一次请求完整经历哪些阶段 —— 加载记忆 → 拼上下文 → 模型推理 → 解析工具调用 → 执行 → 回填结果 → 循环或结束，搞清楚 Token 花在哪、延迟出在哪
7. **Reflection 自我反思机制**：Agent 输出后自己当批评者 review 一遍再修正，或失败后重规划；了解 Reflexion / Self-Critique 思路

**实操任务：** 用 LangChain 写一个简单 Agent，集成搜索工具。

### 模块二：LangGraph 状态机（重中之重！生产首选）

**学习内容：**

1. LangGraph 核心概念：State 状态定义、节点（Node）、边（Edge）、条件分支
2. 状态持久化与断点保存
3. **HITL（Human-in-the-Loop）**：Agent 执行到一半暂停，等待人工确认再继续
4. 用 LangGraph 实现 ReAct 多轮循环

**实操任务：** 手写 LangGraph ReAct Agent，支持断点恢复。

### 模块三：自定义工具开发

**学习内容：**

1. 自定义 Function Calling 工具，编写工具 JSON Schema
2. 工具调用异常处理：超时、重试、结果校验
3. 工具幂等设计，防止重复执行危险操作（如支付、删除）
4. 工具沙箱概念
5. **工具权限控制与最小权限原则**：只给 Agent 当前任务必需的工具，读写分离，高危操作必须走 HITL 审批
6. **接入内部业务系统**（企业真实场景）：调内部 REST / gRPC 接口、查业务数据库、按当前用户身份透传鉴权 Token
7. **接入第三方工具**：搜索（Tavily / Serper）、邮件、日历、文件读写、代码执行
8. **工具选择逻辑**：工具超过 20 个时全部塞进上下文会降效果 —— 需要工具分组路由、向量召回候选工具、分层调度
9. **工具返回结果校验与剪裁**：过滤无效/空返回，长结果只取相关片段，防止上下文被工具输出堵死

**实操任务：** 自定义工具：查询本地文件、查询 Redis、安全计算器；再加一个带鉴权透传的内部业务 API 工具。

### 模块四：Agent 高级机制

**学习内容：**

1. **任务拆解与子任务分发**：复杂需求如何拆成可执行步骤，怎么判断「该拆还是不该拆」
2. **路由与委派**：Supervisor（主管）模式、Router 根据意图分流到不同 Agent
3. **循环控住**：`max_iterations`、连续失败熔断、重复动作检测 —— **Agent 死循环是面试必问坑点**
4. **结构化输出在 Agent 中的应用**：用 Pydantic 定义 Agent 的 action / observation / final answer
5. **推理模型新趋势**：o1 / o3、DeepSeek-R1 类思考模型已内置 CoT，**不再需要写 ReAct 提示词**，直接用原生 reasoning + tool calling

### 模块五：Agent 记忆系统

**学习内容：**

- 短期记忆（当前对话上下文）
- 会话记忆（多轮对话保持）
- 长期记忆（跨会话持久化）
- 记忆压缩与摘要记忆（解决长上下文 Token 爆炸问题）

**实操任务：** 给 LangGraph Agent 增加长期记忆，实现对话历史摘要压缩。

### 模块六：完整单 Agent 项目开发

**项目：个人任务规划 Agent**（简历核心项目 2）

**功能清单：**

1. 用户输入复杂任务 → Agent 自动拆解为子任务（Planning）
2. 可调用工具：计算器、本地文件读写、搜索
3. LangGraph 实现状态流转，断点保存，HITL 人工审批关键步骤
4. 记忆模块，记住历史对话偏好
5. LangSmith 链路追踪：每一步思考、工具调用、Token 消耗可视化
6. 幻觉校验与输出结果校验机制
7. **Reflection 环节**：产出前先自检一轮，发现矛盾自动重试修正
8. **不依赖框架的降级模式**：能切到手写 ReAct 循环跑同一套工具

### ✅ 阶段 3 产出

GitHub 项目 2：**LangGraph 任务规划 Agent**。

**面试必问**：LangGraph 状态机原理、HITL 设计、Function Calling 机制、Agent 记忆架构、ReAct 原理、**手写 ReAct 循环**、**Reflection 反思机制**、Agent 死循环怎么处理。

---

## 阶段 4：Multi-Agent 多智能体 + MCP 协议

> **目标**：学会角色化多 Agent 协作，理解 MCP 协议，让多个 Agent 分工完成复杂任务。

### 模块一：Multi-Agent 基础 —— AutoGen & CrewAI

**学习内容：**

1. 多 Agent 架构：角色定义、任务委派、Agent 间通信机制
2. **CrewAI**：角色（Role）、目标（Goal）、工具（Tool），串行/并行执行
3. **AutoGen**：Agent 辩论、代码执行 Agent
4. **MetaGPT**：软件公司范式（产品经理 / 架构师 / 工程师 / QA），了解 SOP 流程编排思想
5. **多 Agent 评审与冲突处理**：多个 Agent 结论不一致时怎么仲裁 —— 投票、评审 Agent 打分、上级 Agent 裁定、人工兜底

**实操任务：** 用 CrewAI 搭建多 Agent 团队（产品经理、文档撰写、审核），协作完成一篇调研报告。

### 模块二：MCP Model Context Protocol（招聘新热点）

**学习内容：**

1. MCP 协议原理：统一工具调用标准，实现 Agent 与外部工具/服务的标准化通信
2. 搭建 MCP 服务端，让 Agent 通过 MCP 协议调用工具

### 模块三：A2A 协议与低代码 Agent 平台

**学习内容：**

1. **A2A（Agent2Agent）协议**：MCP 解决「Agent 怎么调工具」，A2A 解决「**Agent 之间怎么互调**」，两个协议配合起来是未来的 Agent 互联标准；了解 Agent Card 能力声明机制
2. **Dify / Coze 低代码平台**（JD 经常要求）：会用它快速验证业务想法、做 Demo 给客户看
3. **为什么还要会写代码**：低代码平台到复杂逻辑、自定义编排、私有化部署就会碰壁 —— **面试要把这个取舍讲清楚**，这是高频加分项
4. 了解如何正在低代码平台上做二次开发（自定义插件、外挂 API）

**实操任务：** 搭建本地 MCP 文件服务，Agent 通过 MCP 协议读写本地文件。

### 模块四：多 Agent 完整项目开发

**项目：多 Agent 文档智能处理团队**（简历项目 3）

**角色设计：**

| Agent | 职责 |
|-------|------|
| 文档解析 Agent | 读取 PDF，提取结构化内容 |
| 摘要 Agent | 总结文档核心要点 |
| 审核 Agent | 校验摘要是否准确，检测幻觉 |
| 汇总 Agent | 合并输出最终报告 |

使用 **CrewAI + LangGraph** 混合编排，可接入 MCP 文件工具。

### ✅ 阶段 4 产出

GitHub 项目 3：**多 Agent 文档智能团队**。

**面试考点**：多 Agent 角色分工与通信方式、MCP 协议原理与价值、**MCP 和 A2A 的区别**、**多 Agent 什么时候不如单 Agent**（面试高频陷阱题）。

---

## 阶段 5：工程化、可观测、安全、评测

> **目标**：区分 Demo 选手 vs 生产级工程师的关键分水岭。很多人只会写 Demo 不会上线，学好这一段，面试碾压大部分候选人。

### 模块一：容器化部署

**学习内容：**

1. Docker 基础，编写 Dockerfile 打包 Agent 服务（**多阶段构建 + `.dockerignore` 控制镜像体积**）
2. Docker Compose 本地编排：Agent 服务 + 向量库 + Redis + MySQL + Celery Worker 一键启动
3. **Kubernetes（K8s）基本概览**：JD 写「云原生部署优先」—— 知道 Pod / Deployment / Service / Ingress / ConfigMap 是什么，会写最简 YAML；**小白不必深挖，了解概念即可**
4. **CI/CD 自动化发布**（现在很普遍）：GitHub Actions 跑 ruff + mypy + pytest，测试过了再构建镜像推仓库、自动部署
5. **服务限流与流量控制**：单用户 QPS 限制、Token 配额限流、并发队列、排队与 429 返回 —— 防止 Agent 被刷、成本失控
6. **微服务拆分思路**：把 Agent 编排、RAG 检索、文档解析、用户服务拆开，用消息队列解耦；理解什么不该拆
7. **配置与密钥管理**：环境变量 / `.env` / 密钥不入库、多环境（dev / staging / prod）配置隔离
8. **模型推理服务部署**（了解）：**vLLM**（高吞吐、PagedAttention、OpenAI 兼容）、TGI、SGLang；模型量化 GPTQ / AWQ 的意义 —— 能本地免费跑大模型就靠这整套

**实操任务：** 把 LangGraph Agent 项目打包成 Docker 镜像，用 Docker Compose 一键拉起整套服务；配一个 GitHub Actions，推代码自动跑测试 + 构建镜像。

### 模块二：Agent 可观测性 + 评测体系

**学习内容：**

1. **LangSmith**：链路追踪，查看每一步思考、工具调用、Token 消耗、响应延迟
2. 核心指标定义：任务成功率、幻觉率、召回率、Token 成本、响应延迟
3. 构建评测数据集，自动化评估 Agent 效果，A/B 测试不同提示词策略

**实操任务：** 为 Agent 编写评测脚本，自动跑测试集，统计任务成功率。

### 模块三：安全、隐私、租户隔离

**学习内容：**

1. **Prompt Injection** 提示注入攻击与防护
2. 工具沙箱隔离，禁止高危命令执行
3. PII 敏感信息脱敏（姓名、手机号、身份证等）
4. 操作审计日志，记录 Agent 所有行为
5. 多租户隔离与知识库权限控制（**RAG 高危场景**：必须按用户/部门过滤向量库，否则会读到别人的文档）
6. **输出内容安全**：接内容审核 API 或 LLM 自审，过滤违规、违法违规、不适当输出
7. **合规意识**：生成式 AI 服务备案、用户数据跨境与留存要求、模型输出必须标识为 AI 生成

**实操任务：** 给 Agent 增加提示注入检测、敏感信息自动脱敏。

### ✅ 阶段 5 产出

给前面 3 个项目加上：Docker Compose 一键部署、GitHub Actions CI、LangSmith 追踪、安全防护、自动评测脚本。

**面试高频**：Agent 安全风险、提示注入防护、Agent 效果评估方法、API 成本控制。

---

## 阶段 6：项目打磨、简历、面试刷题 + 投递

### 模块一：项目打磨

1. **GitHub 仓库整理**：完善 README、架构图、演示 GIF、部署教程、技术难点 & 踩坑总结（面试官重点看）
2. 精简代码，清理冗余部分，补充关键注释
3. 录制简单演示视频（可选，简历加分）
4. **整理踩坑文档**：RAG 召回率低怎么调、LLM 输出 JSON 解析失败怎么办、Agent 死循环怎么排查

### 模块二：简历撰写

3 个项目放在项目经历，技术栈列表：

> **后端**：Python、FastAPI、SQLAlchemy、Redis、Celery、PostgreSQL/MySQL、WebSocket/SSE、Nginx
>
> **大模型与 Agent**：LangChain、LangGraph、LlamaIndex、CrewAI、AutoGen、Function Calling、MCP、Prompt Engineering、Ollama、Pydantic
>
> **RAG 与向量**：RAG 全链路、Chroma、Qdrant、Milvus、PGVector、混合检索、Rerank、RAGAS
>
> **工程化**：Docker、Docker Compose、K8s（了解）、GitHub Actions CI/CD、LangSmith、pytest
>
> ✅ 只写**你真的动手做过**的，写上去的每一项都会被现场追问；掌拙不深的标「了解」。

### 模块三：面试题库（Agent 工程师高频面试题，全部掌握）

按模块分类复习：

- **Python 后端**：异步编程、装饰器、FastAPI、SSE vs WebSocket、Redis 使用场景、幂等/限流/熔断
- **RAG**：全链路、Chunk 策略、混合检索、Rerank、幻觉处理、**召回率低怎么排查**、增量更新
- **Agent 原理**：ReAct、Planning、Memory、Tool Use、HITL、Reflection、**手写一次 ReAct 循环**
- **LangGraph**：状态机、断点、条件分支、持久化
- **多 Agent**：角色分工、通信、CrewAI vs AutoGen、**什么时候不该用多 Agent**
- **协议**：MCP 解决什么问题、**MCP vs A2A vs Function Calling 的区别**
- **安全**：Prompt Injection、沙箱、PII 脱敏
- **工程化**：Docker/K8s、CI/CD、可观测、评测体系、**成本怎么控**
- **场景设计题**：让你从零设计一个客服 Agent / 内部知识库问答（考架构拆解能力，现在很流行）

### 模块四：投递策略

- **岗位关键词**：Agent 开发工程师、AI 应用开发工程师、大模型应用工程师、智能体开发工程师
- **投递平台**：BOSS 直聘、拉勾、猎聘、国聘、大厂官网
- **投递策略**：优先投递中小厂 AI 应用团队（门槛更低，容易拿 offer），再冲大厂

---

## 配套学习资源清单（全部免费）

| 资源 | 说明 |
|------|------|
| Python 菜鸟教程 + B 站入门 | 零基础入门首选 |
| **FastAPI 官方文档** | 后端框架首选，教程质量很高 |
| SQLAlchemy / Celery 文档 | ORM 与异步任务队列 |
| **Ollama 官网** | 本地部署开源模型，五分钟上手 |
| LangChain 官方文档 | **优先看官方文档**，比视频靠谱 |
| LangGraph 官方文档 | 状态机、HITL 讲得最清楚 |
| LlamaIndex 官方文档 | RAG 框架首选 |
| CrewAI / AutoGen / MetaGPT 官方文档 | 多 Agent 框架 |
| MCP 官方文档 | 工具调用协议标准 |
| **A2A 协议文档** | Agent 之间互联的新标准 |
| Dify / Coze 官方文档 | 低代码平台，快速出 Demo |
| LangSmith 官网文档 | 可观测性平台 |
| **RAGAS 文档** | RAG 自动化评测框架 |
| **MTEB 排行榜**（Hugging Face） | 选 Embedding 模型直接看它 |
| 论文（选读，面试加分） | ReAct、Toolformer、Reflexion、Self-RAG |

---

## 每周自查清单（防止摆烂）

每个学习模块结束必须完成：

- [ ] 代码提交 GitHub，有清晰的提交记录
- [ ] 写简短学习笔记（Markdown，存在仓库）
- [ ] 完成本模块实操任务，能本地成功运行

---

## 小白避坑指南（非常重要！）

1. ❌ **不要一上来啃论文**，不要直接学微调 SFT/QLoRA。先做 Agent 应用开发，微调是加分项，不是入职必需。
2. ❌ **不要只看视频不写代码**。Agent 岗位代码能力第一，看 10 小时视频不如写 1 小时代码。
3. ❌ **不要做太多小 Demo**。聚焦 3 个完整项目，深度优先，不要广度堆一堆玩具。
4. ❌ **不要跳过工程化章节**。只会 Demo 的候选人非常多；懂 Docker、监控、安全、评测，才能拉开差距。
5. ❌ **不要害怕报错**。LLM API 报错、JSON 解析失败、Agent 死循环都是常态，解决 Bug 的过程就是成长。
6. ❌ **不要只会调框架**。一定要自己手写一次 ReAct、写过一次工具 Schema，否则面试问「框架背后干了什么」就哑了。
7. ❌ **不要忽视后端基本功**。Agent 岗本质仍是后端岗，FastAPI、Redis、消息队列、Docker 不熟练，项目再花哨也过不了基础关。
8. ❌ **不要上来就搞多 Agent**。单 Agent + RAG 做好已经能过大部分面试；多 Agent 很容易失控，而且要能答出「什么时候不该用多 Agent」。

---

## 可选进阶路线（拿到 offer 之后再学）

- 模型量化（GPTQ / AWQ）、vLLM / TGI 高吞吐推理部署
- LoRA 微调、DPO 偏好优化
- 向量数据库内核优化
- Agent 仿真环境、Agent Benchmark 评测
- RAG 高级优化：Self-RAG、Agentic RAG、GraphRAG（知识图谱 + RAG）
- **Computer-Use / Browser-Use Agent**：让 Agent 直接操作浏览器和电脑，目前最火的方向
- **全栈 Agent 平台**：TypeScript / Next.js 写前端控制台，Go 写高并发网关
- 多模态 Agent：图像理解 + 语音交互 + 视频处理
