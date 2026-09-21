#!/usr/bin/env bash
# Demo 02-5 一键演示：起 mock 服务 → 造 200 条 prompt → 并发跑 → 中断续跑 → 并发度对照
set -uo pipefail
cd "$(dirname "$0")"

# ── 自动定位 lab 的 .venv 与共享函数（hr / need_pkgs / wait_http）──
_d="$(pwd)"
while [ "$_d" != "/" ]; do
  [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }
  _d="$(dirname "$_d")"
done
PORT="${PORT:-8898}"
BASE="http://127.0.0.1:${PORT}"
hr() { printf '\n\033[36m══════ %s ══════\033[0m\n' "$1"; }

hr "0. 启动 mock LLM 服务（带故障注入：8% 429 / 4% 超时 / 8% 脏 JSON）"
${PYBIN} mock_llm_server.py > /tmp/mock_llm.log 2>&1 &
SRV=$!
trap 'kill ${SRV} 2>/dev/null; echo "▶ mock 服务已停止"' EXIT
for i in $(seq 1 40); do curl -sf "${BASE}/health" >/dev/null 2>&1 && break; sleep 0.25; done
curl -sf "${BASE}/health" >/dev/null || { echo "❌ mock 服务启动失败，看 /tmp/mock_llm.log"; exit 1; }
head -2 /tmp/mock_llm.log
echo "✅ mock 服务就绪 (pid=${SRV})"

hr "1. 生成 200 条 prompt（seed=42，可复现）"
${PYBIN} make_prompts.py --n 200
head -3 data/prompts.jsonl

hr "2. 并发 5 跑全量 200 条（观察进度、成本、脏 JSON 容错）"
rm -f data/results.jsonl data/results.failed.jsonl
${PYBIN} batch_call.py --concurrency 5 --report-every 40

hr "3. 结果文件检查：每行都是合法 JSON 吗？"
${PYBIN} - <<'EOF'
import json
from pathlib import Path
lines = Path("data/results.jsonl").read_text(encoding="utf-8").splitlines()
ok = bad = 0
for ln in lines:
    try: json.loads(ln); ok += 1
    except json.JSONDecodeError: bad += 1
print(f"  共 {len(lines)} 行，合法 JSON {ok} 行，损坏 {bad} 行 {'✅' if bad == 0 else '❌'}")
print(f"  第一条样例：{json.dumps(json.loads(lines[0]), ensure_ascii=False)[:220]}...")
EOF

hr "4. ★ 断点续跑演示：跑到一半按 Ctrl+C，再 --resume 接着跑"
rm -f data/resume_demo.jsonl data/resume_demo.failed.jsonl
${PYBIN} batch_call.py --in data/prompts.jsonl --out data/resume_demo.jsonl \
        --failed-out data/resume_demo.failed.jsonl --concurrency 5 --report-every 200 &
BGPID=$!
sleep 2.5
echo "  → 发送 SIGINT（等价于 Ctrl+C）..."
kill -INT ${BGPID} 2>/dev/null
wait ${BGPID} 2>/dev/null
DONE1=$(wc -l < data/resume_demo.jsonl | tr -d ' ')
echo "  中断时已落盘 ${DONE1} 条（这就是「边跑边 flush」的价值）"
echo "  → 现在用 --resume 继续："
${PYBIN} batch_call.py --in data/prompts.jsonl --out data/resume_demo.jsonl \
        --failed-out data/resume_demo.failed.jsonl --concurrency 5 --resume --report-every 100 2>&1 | head -6
DONE2=$(wc -l < data/resume_demo.jsonl | tr -d ' ')
echo "  续跑后总计 ${DONE2} 条（中断前的 ${DONE1} 条【没有】被重复处理）"

hr "5. 对照实验：并发度 1 / 5 / 10 的耗时与失败率"
for C in 1 5 10; do
  rm -f data/bench_c${C}.jsonl data/bench_c${C}.failed.jsonl
  head -60 data/prompts.jsonl > data/bench_in.jsonl
  OUT=$(${PYBIN} batch_call.py --in data/bench_in.jsonl --out data/bench_c${C}.jsonl \
          --failed-out data/bench_c${C}.failed.jsonl --concurrency ${C} --report-every 1000 2>&1 | grep -E "耗时|完成：")
  echo "  并发 ${C}: $(echo "${OUT}" | tr '\n' ' ')"
done

hr "6. 服务端统计（证明请求真的打过去了，且故障是服务端注入的）"
curl -s "${BASE}/stats" | ${PYBIN} -m json.tool

hr "7. 失败项单独重跑（把 failed 文件当输入）"
if [ -s data/results.failed.jsonl ]; then
  echo "  失败 $(wc -l < data/results.failed.jsonl | tr -d ' ') 条，重跑一次："
  ${PYBIN} batch_call.py --in data/results.failed.jsonl --out data/retry.jsonl \
          --failed-out data/retry.failed.jsonl --concurrency 3 --report-every 100 2>&1 | tail -8
else
  echo "  本次没有失败项（mock 的故障率是概率性的，多跑几次会遇到）"
fi
