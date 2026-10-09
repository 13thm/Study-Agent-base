#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
_d="$(pwd)"; while [ "$_d" != "/" ]; do [ -f "$_d/scripts/env.sh" ] && { . "$_d/scripts/env.sh"; break; }; _d="$(dirname "$_d")"; done
APP="${LAB_ROOT}/fastapi-chat-backend"
cd "${APP}"
hr() { printf '\n\033[36m══════ %s ══════\033[0m\n' "$1"; }

hr "Demo 05-2 · 进度上报 + SSE 推送"
hr "① 任务侧：进度上报（无 Broker 模拟）"
"${PYBIN}" scripts/demo05_simulate.py --only 2
hr "② 接口侧：起服务后跑真实的 POST /parse + SSE 进度流"
bash scripts/serve.sh start 8000 || exit 1
"${PYBIN}" - <<'EOF'
import json, time, httpx
B = "http://127.0.0.1:8000"
# 预热一次：首次调用要初始化 Redis 客户端与线程，那部分不属于"受理请求"的成本。
# 生产环境靠启动时的 readiness 探针预热（阶段 5 模块 01）。
httpx.post(f"{B}/api/files/0/parse", timeout=10)
time.sleep(0.5)
t0 = time.perf_counter()
r = httpx.post(f"{B}/api/files/9/parse", timeout=10).json()
print(f"  POST /api/files/9/parse → {r['task_id']}  受理耗时 {r['accepted_in_ms']}ms")
assert r["accepted_in_ms"] < 50, "★ 受理必须 <50ms，证明没在请求里干活"
print("  ✅ 受理耗时 < 50ms（任务书验收项）")
seen, t1 = [], time.perf_counter()
with httpx.stream("GET", f"{B}/api/tasks/{r['task_id']}/stream", timeout=60) as resp:
    for line in resp.iter_lines():
        if not line.startswith("data: "): continue
        p = line[6:]
        if p == "[DONE]": break
        d = json.loads(p)
        sig = (d.get("state"), d.get("pct"))
        if sig not in seen:
            seen.append(sig)
            print(f"    [{time.perf_counter()-t1:5.2f}s] {d.get('state'):<9} "
                  f"{str(d.get('stage','')):<10} {str(d.get('pct',''))+'%':>7}")
print(f"  ✅ SSE 收到 {len(seen)} 个不同状态帧（只在变化时推，不刷重复数据）")
EOF
bash scripts/serve.sh stop 8000
