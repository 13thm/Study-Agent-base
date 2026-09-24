# Demo 03-5 · Nginx 反向代理与负载均衡

> **任务书**：[03-后端基础与Linux和Git.md → Demo 03-5](../../../../my-docs/study01/stage0-前置基础/03-后端基础与Linux和Git.md)
> **依赖**：Docker（要起 nginx + 两个 api 实例）　**耗时**：1.5 小时

## 一、跑
```bash
docker compose up -d          # 起 api1 + api2 + nginx（首次要装依赖，约 1~2 分钟）
docker compose ps             # 等三个都 healthy
bash verify.sh                # 5 组验证
docker compose down           # 收工
# 访问：http://127.0.0.1:8080/docs   http://127.0.0.1:8080/static/sse.html
```

## 二、nginx.conf 里的 4 个教学重点（都有注释）
| 配置 | 作用 | 不配会怎样 |
|---|---|---|
| `upstream api_pool { server api1; server api2; keepalive 32; }` | 负载均衡 + 复用上游长连接 | 单点、每次新建连接 |
| `location ~ ^/api/chat/stream$ { proxy_buffering off; gzip off; proxy_read_timeout 3600s; }` | **SSE 穿透** | 流式变一次性返回；长任务 60s 被掐断 |
| `limit_req_zone $binary_remote_addr zone=api_per_ip:10m rate=10r/s;` + `burst=20 nodelay` | 限流 | 被刷爆 |
| `client_max_body_size 50m;` | 大文件上传 | 上传 PDF 直接 413 |

另外三个容易漏的：
- `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` —— **不传的话应用看到的所有请求 IP 都是 nginx 的**，按 IP 限流会把全站限成一个桶
- `proxy_set_header X-Request-ID $request_id;` —— 与应用的 request_id 打通，一条 id 串起 nginx 日志和应用日志
- WS 的 `Upgrade` / `Connection "upgrade"` 头 —— 缺了握手直接失败

## 三、必做的对照实验（★ 本 Demo 的价值所在）
```bash
# ① 正常状态：SSE 逐帧到达
bash verify.sh                # 看第 2 步的时间戳是递增的

# ② 注释掉 proxy_buffering off
sed -i.bak 's/proxy_buffering off;/# proxy_buffering off;/' nginx.conf
docker compose restart nginx
bash verify.sh                # → 所有帧的时间戳【完全相同】= 被缓冲成一次性返回 ❌

# ③ 恢复
mv nginx.conf.bak nginx.conf && docker compose restart nginx
```
把这个对照的两次输出贴进下面的表格 —— 阶段 5 模块 01 会用它讲"TTFB 8.4s → 0.62s"。

## 四、我的验证记录（换成你的）
| 验证项 | 结果 |
|---|---|
| 负载均衡（10 次请求分布） | api1 ___ 次 / api2 ___ 次 |
| SSE 逐帧到达（有 buffering off） | 帧间隔 ___ ms |
| SSE 被缓冲（注释掉后） | 帧间隔 ___ ms（全部同时到达） |
| 限流（60 次快速请求） | 200 ___ 次 / 503 ___ 次 |
| 5MB 上传 | 状态码 ___（不是 413 即通过） |

## 五、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 把 `limit_req_status` 改成 429（更符合语义），并加 `Retry-After` 头 |
| 2 | ⭐⭐ | 按 API Key 而不是 IP 限流：用 `map $http_authorization $limit_key` 提取 |
| 3 | ⭐⭐ | 配自签 HTTPS 证书 + 80→443 跳转 + HSTS，用 `curl -k https://...` 验证 |
| 4 | ⭐⭐⭐ | 把 `upstream` 改成 `least_conn`，用并发压测对比两种策略的 P95 延迟 |

## 六、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
