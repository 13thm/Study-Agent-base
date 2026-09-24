# Demo 04-3 · 对象存储上传全链路

> **任务书**：[04-数据库与存储.md](../../../../my-docs/study01/stage0-前置基础/04-数据库与存储.md)
> **代码位置**：`../fastapi-chat-backend/app/services/storage.py + scripts/demo04_3_minio.py`
> **依赖**：minio（无服务时降级本地文件系统，接口一致）　**耗时**：2 小时

## 一、跑
```bash
bash run.sh
```
要跑真实 MinIO：`cd .. && docker compose up -d minio`，控制台 http://localhost:9001（minioadmin/minioadmin）

## 二、这个 Demo 验证什么
7 个场景：

| # | 场景 | 期望 |
|---|---|---|
| ① | 上传 4 种文件（1.2MB pdf / md / png / txt） | 全部成功，返回 file_id + status=pending |
| ② | **sha256 秒传去重** | 重传同一文件 → `dedup=True`，记录数不变，多余对象被删 |
| ③ | 预签名 URL | 5 分钟有效；**篡改签名 → 拒**；**已过期 → 拒** |
| ④ | 路径穿越 | `../../etc/passwd`、`uploads/1/../../../secret` 全部被拒 |
| ⑤ | 类型/大小/空文件 | `.exe` 拒（415）、21MB 拒（413）、空文件拒（400） |
| ⑥ | 元数据入库 | `user_files` 表含 object_key/sha256/status，供模块 05 的解析任务用 |
| ⑦ | 存储挂了 | 先写对象再写库 → 对象存储失败时**数据库零脏数据** |

## 三、要读哪些代码（按顺序）
1. `app/services/storage.py`：`ObjectStorage` 抽象基类 + `LocalStorage` / `MinioStorage` 两个实现
   （**这就是"换云厂商只改一个文件"的落地**）；`_p()` 里的路径穿越防护；HMAC 预签名 URL 的原理
2. `scripts/demo04_3_minio.py`：`object_key()` 的命名规范为什么是 `uploads/{user_id}/{yyyy}/{mm}/{dd}/{uuid}.{ext}`
3. `tests/test_storage.py`：5 个安全用例（穿越 / 篡改 / 过期 / 缺参数 / sha256 去重）

## 四、练习
| # | 难度 | 题目 |
|---|---|---|
| 1 | ⭐ | 加 `GET /api/files`、`DELETE /api/files/{id}`（删对象 + 删记录，要保证一致性） |
| 2 | ⭐⭐ | 大文件分片上传：`initiate / upload_part / complete`，断点续传 |
| 3 | ⭐⭐ | 预签名 URL 加**下载计数**与**单用户并发下载数限制** |
| 4 | ⭐⭐⭐ | 实现"删对象成功但删记录失败"的补偿（对账脚本，找出孤儿对象与孤儿记录） |

## 五、验收清单
- [ ] 7 个场景全部通过
- [ ] 能答"文件为什么不进数据库"（三条理由）
- [ ] 能答"object key 为什么带 user_id 和日期分层"（租户隔离 + 避免单目录百万文件）
- [ ] 能答"预签名 URL 解决什么问题"（不把密钥给前端，给限时限对象的临时 URL）
- [ ] `tests/test_storage.py` 全绿；练习 1、4 完成

## 六、踩坑记录
| 日期 | 现象 | 原因 | 解法 |
|---|---|---|---|
