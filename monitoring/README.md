# M3 监控与告警基线

应用通过 `/health/ready/`（存活）和 `/admin/health`（依赖详情）暴露状态。Prometheus 采集应用请求延迟、5xx、Celery 队列深度、数据库连接、Redis 命中率、MinIO 5xx、磁盘/inode 使用率、multipart 孤儿数和对象版本增长。

建议告警阈值：

- API 5xx >2%（5 分钟）或 p95 超过接口基线 2 倍：页面告警。
- 任一依赖 unavailable、WAL 归档中断、审计链断裂：立即阻断写操作并通知安全负责人。
- 磁盘 >80% 预警、>90% 暂停新上传/promotion；inode >80% 同理。
- Celery dead-letter >0、multipart 孤儿超过保留周期：通知运维并暂停 GC。

每条告警必须关联 Owner、值班渠道和对应 Runbook；日志保留 30 天，审计保留按策略执行。所有阈值通过环境变量或监控系统配置注入。
