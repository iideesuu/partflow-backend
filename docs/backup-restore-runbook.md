# M3 备份恢复 Runbook（执行状态：待演练）

1. 设置 `PGHOST`、`PGPORT`、`PGUSER`、`PGDATABASE`、`PGPASSWORD`、`BACKUP_DIR` 和 `BACKUP_ENCRYPTION_KEY_FILE`（密钥文件由 Secret 管理，禁止提交仓库）。
2. 在后端容器执行 `scripts/backup_restore.sh`。脚本生成 `pg_dump -Fc` 后使用 AES-256-CBC 加密，写出 SHA-256 校验文件并删除明文。
3. 将加密备份复制到异地存储；MinIO 使用运维侧 `mc mirror --versions` 复制四个业务桶。记录对象版本映射，不得覆盖 release 对象。
4. 恢复时解密到临时文件，执行 `pg_restore --clean --if-exists --no-owner`；恢复对象及 VersionId 后运行数据库/对象对账。
5. 运行 Django `manage.py check`、审计哈希链校验，并随机抽取 10 个已发布附件计算 SHA-256，与 `AttachmentVersion.sha256` 比对。
6. 记录 UTC 开始/结束时间、数据集哈希、备份大小、RPO/RTO。验收要求 RPO ≤15 分钟、RTO ≤4 小时。
7. 演练失败时切换应用只读，保留故障实例供取证，从最近完整备份重做；禁止手工 SQL 绕过审计。
8. 运维与安全负责人将结果签署到 `artifacts/backup-restore/<timestamp>/signoff.md`。未完成实测前不得标记 V16-28 通过。
