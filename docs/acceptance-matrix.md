# M0/M3 验收矩阵

| ID | 阶段 | 验证命令/证据 | 通过标准 |
|---|---|---|---|
| V16-01/02 | M0 | `scripts/minio_probe.sh` | API/Console 职责、TLS、CORS 原始响应归档 |
| V16-03/07/11/12/13/14 | M2 | `pytest -k attachment` + 浏览器上传 | 分片回执、校验、异步 finalize、扫描门禁、发布屏障、下载 mode 全通过 |
| V16-08/09/10 | M2 | `pytest -k import_export` | CSV/JSON dry-run→confirm、无损往返、公式注入转义 |
| V16-15/16 | M1 | `pytest -k auth_roles` | LDAP 只读、锁定、五角色及 SoD 矩阵 |
| V16-17/18/19 | M1 | `pytest -k part_catalog` | 编号、分类版本、旧取号 410 |
| V16-20/22/23/24 | M2 | `pytest -k bom_state` | EBOM 结构、废止传播、效力排他、幂等/ETag |
| V16-25/26/27 | M3 | `scripts/security_check.sh` | 无明文密钥、依赖故障 fail-closed、审计哈希链 |
| V16-28 | M3 | `scripts/backup_restore.sh` | 加密备份可恢复，RPO ≤15m、RTO ≤4h，对象 SHA 一致 |
| V16-29 | M3 | `scripts/perf_baseline.py` | 记录硬件/数据集/并发，API p95/p99 达标 |
| V16-30 | M3 | `frontend` capability probe | 支持浏览器完成 5GiB；不支持环境创建会话前提示 |

## 证据归档

将命令输出、原始 HTTP 响应、数据集 SHA-256、迁移前后数量、签字记录归档到 `artifacts/m0-m3/<timestamp>/`；该目录只存脱敏证据，不得包含域名、IP、Token 或密码。
