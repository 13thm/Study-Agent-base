
按【核心开发框架｜多智能体｜RAG 知识库 Agent｜自主 Agent｜工具 / 记忆 / MCP｜代码 Agent｜垂直行业 Agent｜学习 & Awesome 清单】划分，附带 Star、核心能力、求职价值
一、核心 Agent 开发框架（面试最高频，JD 必提）
1. langchain-ai/langchain ⭐136k+ Python/JS 生态，Agent+Chain+RAG 全套组件；LangSmith 做可观测评测。招聘出现频率最高，用来构建单 Agent、工具调用、RAG 应用
2. langchain-ai/langgraph ⭐39.5k LangChain 官方图状态机框架，支持状态持久化、分支、HITL 人机介入、断点恢复；企业生产级 Agent 首选，复杂长任务、多轮编排必学
3. run-llama/llama_index ⭐51.6k 主打数据 + RAG+Agent，擅长文档、知识库检索增强智能体；适合企业内部知识库 Agent 场景
4. pydantic/pydantic-ai ⭐19.2k 类型安全 Agent 框架，Pydantic 做输出校验，强结构化输出，适合生产环境工具调用，减少幻觉、JSON 解析异常
5. huggingface/smolagents ⭐28.8k HF 官方极简 Agent 框架，代码少、易读，适合手写 ReAct，学习底层原理，不被重型框架封装绑架
6. openai/agents-sdk ⭐28.6k OpenAI 官方 Agent SDK，原生 Function Calling、工具、护栏，轻量，OpenAI 生态项目首选
7. microsoft/semantic-kernel ⭐28.4k 微软，Python/.NET 双语言，企业级，适合.NET/ 微软云业务对接 Agent
8. google/adk ⭐21.1k Google Agent 开发套件，Gemini 生态，图工作流、多模态 Agent
9. mastra-ai/mastra ⭐27.1k TypeScript 全栈 Agent 框架，前端 + 后端一体化，TS 技术栈开发 Agent 平台首选
二、多智能体 Multi-Agent 框架（团队 Agent、角色分工）
10. microsoft/autogen ⭐60.4k 微软多智能体，Agent 之间对话辩论、任务委派；经典多 Agent 教学项目，大量面试案例，现已进入维护模式
11. crewAIInc/crewAI ⭐56.9k 角色式多 Agent 团队，给每个 Agent 分配角色、目标、工具，快速搭建数字团队，上手简单，原型最快
12. geekan/MetaGPT ⭐67.5k 模拟软件公司多 Agent 团队：产品、架构、开发、测试，自动做完整软件项目；国内非常火，多 Agent 工程化标杆博客园
13. openclaw/openclaw ⭐380k+ 现象级自主 Agent，跨平台，可操作本地文件、浏览器、终端，支持 MCP 协议，2026 年热度爆炸，端侧 / 本地执行 Agent 代表稀土掘金
14. SuperAGI-AI/superagi ⭐17.6k 自主 Agent 平台，带 WebUI，可管理、调度多个自主 Agent，内置工具、内存、Agent 监控面板
三、经典自主 Agent（浏览器 / 网页可运行，Demo 标杆）
15. reworkd/AgentGPT ⭐36.3k 浏览器端自主 Agent，网页直接跑，输入目标自动拆解任务、调用工具，入门 Demo 首选，TypeScript 开发
16. Significant-Gravitas/AutoGPT ⭐187k 初代爆款自主 Agent，AutoGPT 开创自主 Agent 风潮，理解 ReAct、任务规划、自我反思的经典项目
四、工具协议、记忆、可观测、MCP 生态（生产工程化重点）
17. modelcontextprotocol/mcp Model Context Protocol 现在 Agent 行业新标准，Agent 统一调用外部工具的协议，大量 JD 开始要求懂 MCP
18. screenpipe/screenpipe ⭐21.4k Rust 本地屏幕录制，给 Agent 提供屏幕视觉上下文，电脑操作 Agent 必备，Rust 高性能
19. obra/superpowers ⭐216k Agent 技能 Skill 标准化仓库，大量可复用工具技能包，定义 Skill 开发规范稀土掘金
20. composiohq/composio 上千个预置工具集成，Agent 一键调用第三方 SaaS 工具（邮件、日历、Github、钉钉），企业 Agent 常用
五、代码 Agent / 编程智能体（开发岗高频）
21. anthropics/claude-code-sdk ⭐8.1k Anthropic 官方代码 Agent SDK，Claude Code 底层，内置沙箱、文件读写、代码执行钩子
22. codellama/CodeLlama 代码大模型，配合 Agent 做代码生成、审查
23. colbymchenry/codegraph MCP 服务，解析代码 AST 构建代码图谱，Agent 阅读大型代码库，减少 token 消耗，近期 Trending 热门
六、RAG & 知识库 Agent 相关
24. chroma-core/chroma 向量库，轻量本地向量数据库，Agent 知识库原型
25. milvus-io/milvus 企业级向量库，生产 RAG+Agent 常用
26. pgvector/pgvector Postgres 向量插件，业务系统直接复用 PG 存储向量，企业项目高频
七、垂直行业 Agent 项目（业务落地参考，简历加分）
27. AI4Finance-Foundation/FinRobot ⭐7.9k 金融多 Agent，分析师、会计、交易员角色，自动财报分析、研报生成，金融行业 Agent 标杆
28. OpenMinis/openminis ⭐4.3k 手机端本地私有 Agent，调用手机系统能力，端侧智能体参考
八、Awesome 清单 / 学习资料仓库（快速找案例、论文）
29. ai-agent-book/ai-agent-book 开源 Agent 工程书籍，从记忆、工具调用、评测、安全完整工程体系
30. agency-agents/agency-agents ⭐149k 300 + 预制 Agent 角色库，工程、安全、市场、医疗等大量角色定义，直接拿来做角色 Agent

求职建议（Agent 工程师）
✅ 简历优先写这 4 个（面试问的最多）
LangChain / LangGraph、LlamaIndex、AutoGen、CrewAI。最好自己写 Demo：LangGraph 实现带 HITL、断点的任务 Agent + RAG + Function Calling。
✅ 进阶加分项目（写在项目经历）
MetaGPT（多 Agent）、OpenClaw（MCP、本地工具执行）、smolagents（手写 ReAct，底层原理）
✅ 避坑提醒
AutoGPT、AgentGPT 适合理解概念，但不适合生产；面试区分：实验 Demo vs 企业生产级（LangGraph 为主）
✅ 学习路线建议
1. LangChain + LangGraph 搭建基础 Agent
2. 用 LlamaIndex 做 RAG 知识库 Agent
3. CrewAI/AutoGen 做多 Agent 角色协作
4. 学习 MCP 协议，接入 Composio 工具
5. 用 LangSmith 做 Agent 链路追踪 & 评测