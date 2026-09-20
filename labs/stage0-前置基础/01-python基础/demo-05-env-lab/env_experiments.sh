#!/usr/bin/env bash
# Demo 01-5 · 虚拟环境与依赖复现 —— 5 个实验的自动化脚本
#
# ⚠️ 这个脚本会在 /tmp 下创建临时目录做实验，不会污染你的项目。
#    建议：先自己手敲一遍（学习效果最好），再用这个脚本对照输出。
#
# 用法：bash env_experiments.sh [A|B|C|D|E|all]
set -uo pipefail
WORK=$(mktemp -d /tmp/envlab.XXXXXX)
PY=${PY:-python3}
trap 'rm -rf "$WORK"' EXIT
hr()  { printf '\n\033[36m══════ %s ══════\033[0m\n' "$1"; }
say() { printf '\033[33m$ %s\033[0m\n' "$1"; }

exp_A() {
  hr "实验 A · venv 创建 → 装包 → freeze → 删掉 → 只靠 requirements.txt 重建"
  cd "$WORK"
  say "python3 -m venv venv_a"
  $PY -m venv venv_a
  say "source venv_a/bin/activate && which python"
  # shellcheck disable=SC1091
  source venv_a/bin/activate
  which python
  echo "  → 必须指向 venv_a 内部，说明隔离生效"
  say 'pip install "pydantic>=2,<3" (只显示最后 2 行)'
  pip install -q "pydantic>=2,<3" 2>&1 | tail -2
  say "pip freeze > requirements.txt && head -3 requirements.txt"
  pip freeze > requirements.txt && head -3 requirements.txt
  deactivate

  say "rm -rf venv_a && python3 -m venv venv_a2 && pip install -r requirements.txt"
  rm -rf venv_a
  $PY -m venv venv_a2
  # shellcheck disable=SC1091
  source venv_a2/bin/activate
  pip install -q -r requirements.txt 2>&1 | tail -1
  say "python -c 'import pydantic; print(pydantic.VERSION)'"
  python -c "import pydantic; print('  pydantic', pydantic.VERSION, '← 新环境重建成功 ✅')"
  deactivate
  echo "✅ 结论：requirements.txt + venv 就能在任何机器上复现环境（前提是把版本钉死）"
}

exp_B() {
  hr "实验 B · 污染验证：venv 外的包，venv 内看不到"
  cd "$WORK"
  $PY -m venv venv_b
  say "系统 python 能看到 sqlalchemy 吗？"
  $PY -c "import importlib.util as u; print('  系统 python: sqlalchemy =', bool(u.find_spec('sqlalchemy')))"
  # shellcheck disable=SC1091
  source venv_b/bin/activate
  say "venv 内 python 能看到 sqlalchemy 吗？"
  python -c "import importlib.util as u; print('  venv  python: sqlalchemy =', bool(u.find_spec('sqlalchemy')))"
  say "pip list | wc -l  （venv 里只有 pip/setuptools）"
  echo "  venv 内已装包数量: $(pip list --format=freeze 2>/dev/null | wc -l | tr -d ' ')"
  deactivate
  echo "✅ 结论：venv 是【隔离】不是【继承】—— 系统装的包在里面看不见（除非建 venv 时加 --system-site-packages）"
}

exp_C() {
  hr "实验 C · 依赖地狱：A 要 pydantic<2，B 要 pydantic>=2"
  cd "$WORK"
  cat > requirements_conflict.txt <<'EOF'
pydantic<2
fastapi>=0.111
EOF
  $PY -m venv venv_c
  # shellcheck disable=SC1091
  source venv_c/bin/activate
  say "pip install -r requirements_conflict.txt （截取关键报错）"
  pip install -r requirements_conflict.txt 2>&1 | grep -iE "conflict|incompatible|error|cannot" | head -6
  echo "  ↑ pip 会报 ResolutionImpossible / 依赖冲突"
  deactivate
  echo "✅ 结论：这就是为什么要有 lock 文件（uv.lock / poetry.lock）——"
  echo "   它记录的是【已解出的一组兼容版本】，而不是各自声明的范围。"
}

exp_D() {
  hr "实验 D · uv vs venv+pip 的速度对比"
  if ! command -v uv >/dev/null 2>&1; then
    echo "⚠️  未安装 uv，跳过。安装：curl -LsSf https://astral.sh/uv/install.sh | sh"
    return
  fi
  cd "$WORK"
  say "计时 1：venv + pip install pydantic httpx fastapi"
  T0=$(date +%s.%N)
  $PY -m venv venv_d1 && ./venv_d1/bin/pip install -q pydantic httpx fastapi >/dev/null 2>&1
  T1=$(date +%s.%N)
  echo "  耗时: $(echo "$T1 - $T0" | bc)s"

  say "计时 2：uv venv + uv pip install pydantic httpx fastapi"
  T0=$(date +%s.%N)
  uv venv venv_d2 >/dev/null 2>&1 && uv pip install -q --python venv_d2/bin/python pydantic httpx fastapi >/dev/null 2>&1
  T1=$(date +%s.%N)
  echo "  耗时: $(echo "$T1 - $T0" | bc)s"
  echo "✅ 结论：uv 通常快 5~20 倍（Rust 实现 + 全局硬链接缓存）。把秒数记进 README。"
}

exp_E() {
  hr "实验 E · conda vs venv 的本质差别（只做说明，不实际创建）"
  if command -v conda >/dev/null 2>&1; then
    say "conda --version && conda env list | head -5"
    conda --version; conda env list 2>/dev/null | head -5
  else
    echo "  （未安装 conda，下面是结论）"
  fi
  cat <<'EOF'
  本质差别：
    venv  = 只隔离【Python 包】，Python 解释器本身来自系统
    conda = 隔离【整个环境】，包括 Python 解释器版本 + 非 Python 依赖
            （CUDA、MKL、gcc、ffmpeg、libpq 这些 C 库都能装）
  什么时候用 conda：
    · 需要特定 Python 版本且不想动系统
    · 要装带 C/CUDA 依赖的包（torch、tensorflow、rapids）
    · 数据科学场景（numpy/scipy 的 MKL 优化版）
  什么时候用 venv/uv：
    · 纯 Python 的 Web/Agent 服务（我们的项目就是）
    · 要上 Docker（镜像里装 conda 会让体积暴涨 1GB+）
    · CI 环境（uv 快得多）
EOF
}

case "${1:-all}" in
  A) exp_A ;; B) exp_B ;; C) exp_C ;; D) exp_D ;; E) exp_E ;;
  all) exp_A; exp_B; exp_C; exp_D; exp_E ;;
  *) echo "用法: bash env_experiments.sh [A|B|C|D|E|all]" ; exit 2 ;;
esac
hr "实验目录 $WORK 已自动清理"
