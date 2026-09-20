#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"

# ── 自动定位 lab 的 .venv 与共享函数（hr / need_pkgs / wait_http）──
_d="$(pwd)"
while [ "$_d" != "/" ]; do
  [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }
  _d="$(dirname "$_d")"
done
hr() { printf '\n\033[36m── %s ──\033[0m\n' "$1"; }

hr "1. 生成 100 个脏配置夹具（seed=42，可复现）"
python3 make_fixtures.py

hr "2. 批处理：40 个坏文件，主流程一次都没崩"
python3 batch.py --dir data/configs/

hr "3. 看完整异常链（raise ... from e 的效果）"
python3 batch.py --dir data/configs/ --show-traceback 2>&1 | tail -22

hr "4. 对照实验：--retry 2 重试确定性错误 → 多花 3 倍时间，结果一模一样"
python3 batch.py --dir data/configs/ --retry 2 | head -3

hr "5. 对照实验：--strict 一遇错就退出（退出码 2）"
python3 batch.py --dir data/configs/ --strict ; echo "退出码 = $?"

hr "6. 反例演示：裸 except: 会连 Ctrl+C 都吞掉"
python3 - <<'EOF'
def bad():
    try:
        raise KeyboardInterrupt        # 模拟用户按 Ctrl+C
    except:                            # ❌ 裸 except（ruff 会报 E722）
        return "被吞了"
def good():
    try:
        raise KeyboardInterrupt
    except Exception:                  # ✅ 只捕获 Exception，KeyboardInterrupt 能穿透
        return "被吞了"
print(f"裸 except     : {bad()}   ← 用户按 Ctrl+C 都停不下来，这是生产事故")
try:
    good()
except KeyboardInterrupt:
    print("except Exception: KeyboardInterrupt 正常穿透 ✅")
EOF

hr "7. 反例演示：finally 里 return 会吞掉 try 里的 return"
python3 - <<'EOF'
def f1():
    try:
        return "try 的返回值"
    finally:
        return "finally 的返回值"      # ❌ 把 try 的返回值覆盖了
def f2():
    try:
        return "try 的返回值"
    finally:
        print("  (finally 做清理，不 return)")
print(f"f1() → {f1()}   ← finally 的 return 赢了，try 的结果被丢弃")
print(f"f2() → {f2()}")
EOF
