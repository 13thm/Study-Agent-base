# Demo 01-5 · 虚拟环境与依赖复现实验

> **对应文档**：[01-Python基础.md → Demo 01-5](../../../../my-docs/study01/stage0-前置基础/01-Python基础.md)
> **依赖**：`python3 -m venv`（自带）、可选 `uv` / `conda`　**预计耗时**：1 小时
> **练什么**：环境隔离的本质、依赖锁定、版本冲突、现代工具链

## 一、这个 Demo 没有代码，只有 5 个实验
面试问「你怎么管理依赖」，答"用 pip install"是不够的。
你要能说出：**为什么要锁版本、lock 文件解决了什么、uv 比 pip 快在哪、什么时候用 conda**。
这 5 个实验就是把这些变成你亲眼见过的事实。

## 二、怎么做
```bash
bash env_experiments.sh all     # 跑全部 5 个实验（在 /tmp 下建临时目录，跑完自动清理）
bash env_experiments.sh A       # 只跑实验 A
```
> ⚠️ **强烈建议先自己手敲一遍**（学习效果差 10 倍），再用脚本对照输出。
> 脚本里的每条命令都先用 `$ ...` 打印出来了，照着敲即可。

## 三、5 个实验与你要记录的东西

### 实验 A · venv 复现（必做）
```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
which python                       # ← 必须指向 .venv 内部
pip install "pydantic>=2,<3"
pip freeze > requirements.txt
deactivate && rm -rf .venv         # 删掉环境
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt    # 只靠 requirements.txt 重建
python -c "import pydantic; print(pydantic.VERSION)"
```
**记录**：重建后的版本号 = ____（应与删除前一致）
**思考**：`pip freeze` 输出的是**精确版本**（`pydantic==2.13.5`），
而你安装时写的是**范围**（`>=2,<3`）。这就是"声明"与"锁定"的区别。

### 实验 B · 污染验证
在 venv 外能 import 的包，激活 venv 后 import 不到 → 理解**隔离不是继承**。
**思考**：`python3 -m venv --system-site-packages .venv` 会发生什么？什么时候需要它？

### 实验 C · 依赖地狱
构造一个 `requirements.txt`：`pydantic<2` + `fastapi>=0.111`（后者要 pydantic v2）。
**记录**：pip 报的错原文（`ResolutionImpossible` / `Cannot install ... because these package versions have conflicting dependencies`）
**结论**：这就是 lock 文件（`uv.lock` / `poetry.lock`）存在的理由 ——
它记录的是**已解出的一组兼容版本**，而不是各自声明的范围。

### 实验 D · uv vs pip 速度
**记录**：两种方式各装 `pydantic httpx fastapi` 的秒数
```
venv + pip : ____ s
uv venv + uv pip : ____ s     （通常快 5~20 倍）
```
**为什么快**：Rust 实现 + 全局硬链接缓存（同一个包版本在磁盘上只存一份）。

### 实验 E · conda vs venv
| | venv | conda |
|---|---|---|
| 隔离范围 | 只有 Python 包 | Python 解释器 + 非 Python 依赖（CUDA/MKL/gcc/ffmpeg） |
| Python 版本 | 用系统的 | 可以自己装任意版本 |
| 镜像体积 | 小 | 大（+1GB 起） |
| 速度 | 快（uv 更快） | 慢（要解 SAT） |
| 适用 | Web/Agent 服务、Docker、CI | 数据科学、需要 CUDA 的训练环境 |

**我们的项目全程用 venv/uv**，因为要上 Docker（镜像里塞 conda 体积爆炸）。

## 四、本 lab 仓库自己是怎么做的（照着学）
```
labs/stage0-前置基础/
├── pyproject.toml      ← 依赖声明（范围）+ ruff/mypy/pytest 配置，一个文件搞定
├── requirements.txt    ← 备用，给不用 uv 的人
└── .venv/              ← 已 gitignore，绝不提交
```
```bash
cd labs/stage0-前置基础
uv venv .venv && uv pip install -r requirements.txt      # 30 秒装完全部依赖
source .venv/bin/activate
# 或者不激活，直接用绝对路径调用：
.venv/bin/python 01-python基础/demo-01-cli-toolbox/toolbox.py freq
```

## 五、验收清单
- [ ] 5 个实验全部亲手做过（不只是看脚本输出）
- [ ] 实验 A 的重建版本号记录在案
- [ ] 实验 C 的 pip 报错原文贴进下面的表格
- [ ] 实验 D 的两个秒数记录在案
- [ ] 能口头答：`pip freeze` 和 `pyproject.toml` 的区别、lock 文件解决什么问题、什么时候用 conda
- [ ] 换一台机器（或删掉 `.venv`）能在 5 分钟内把整个 lab 环境重建起来

## 六、实验记录（自己填）
| 实验 | 我的实测数据 | 结论 |
|---|---|---|
| A 重建 | pydantic 版本 ____ | |
| B 隔离 | venv 内包数量 ____ | |
| C 冲突 | 报错关键词 ____ | |
| D 速度 | pip ____s / uv ____s | 快 ____ 倍 |
| E conda | 是否安装 ____ | |

## 七、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
| | | | |
