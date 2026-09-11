# M0 Revision 状态机

```mermaid
stateDiagram-v2
  [*] --> draft
  draft --> pending_review: submit
  pending_review --> approved: approve (review record)
  pending_review --> rejected: reject (comment required)
  rejected --> draft: resubmit
  approved --> release_pending: publish (SoD + gates)
  release_pending --> released: promotion complete + activation
  release_pending --> release_failed: promotion error
  release_failed --> release_pending: retry_publish (idempotent)
  released --> obsolete: retire (reference gate)
  approved --> draft: withdraw
  draft --> [*]: delete (owner, no refs)
  obsolete --> [*]
```

每次转移均要求 `If-Match`，非法转移返回 `409 STATE_TRANSITION_INVALID` 并回显 `current_state` 与 `allowed_actions`。发布事务锁定 Part/BOM，写入审核、ReleaseActivation、审计和效力区间；任何门禁失败保持零业务写入。`release_failed` 重试不得创建第二组发布对象。
