# M0 数据模型（ER 图）

```mermaid
erDiagram
  CATEGORY ||--o{ PART : classifies
  PART ||--o{ PART_REVISION : versions
  UNIT ||--o{ PART_REVISION : measures
  PART_REVISION ||--o{ BOM_REVISION : root
  BOM ||--o{ BOM_REVISION : versions
  BOM_REVISION ||--o{ BOM_ITEM : contains
  PART_REVISION ||--o{ BOM_ITEM : child
  UNIT ||--o{ BOM_ITEM : measures
  NUMBER_SOURCE ||--o{ NUMBER_REQUEST : provides
  NUMBER_REQUEST ||--o| PART : registers
  UPLOAD_SESSION ||--o{ PART_ATTACHMENT : stores
  PART_REVISION ||--o{ PART_ATTACHMENT : attaches
  UPLOAD_SESSION ||--o{ ATTACHMENT_VERSION : produces
  USER ||--o{ PART_REVISION : submits
  USER ||--o{ PART_REVISION : reviews
  USER ||--o{ PART_REVISION : publishes
  USER ||--o{ AUDIT_EVENT : acts
  UPLOAD_SESSION ||--o{ IMPORT_JOB : input

  CATEGORY { uuid id PK; string major_code; string minor_code; string catalog_version; boolean is_selectable }
  PART { uuid id PK; string tenant_id; string part_code UK; int row_version }
  PART_REVISION { uuid id PK; uuid part_id FK; string revision; string revision_state; int row_version; tstzrange effective_range }
  BOM { uuid id PK; string bom_code UK; string bom_type }
  BOM_REVISION { uuid id PK; uuid bom_id FK; uuid root_part_revision_id FK; string revision_state; int row_version }
  BOM_ITEM { uuid id PK; uuid bom_revision_id FK; uuid child_part_revision_id FK; int line_no; decimal quantity; string position }
  UNIT { uuid id PK; string code UK; string dimension }
  NUMBER_SOURCE { uuid id PK; string name; boolean is_enabled }
  NUMBER_REQUEST { uuid id PK; uuid source_id FK; string source_request_id UK; string operation_key UK }
  UPLOAD_SESSION { uuid id PK; string bucket; string object_key UK; bigint size; string state }
  ATTACHMENT_VERSION { uuid id PK; uuid upload_session_id FK; string s3_version_id; string sha256; string scan_status }
  PART_ATTACHMENT { uuid id PK; uuid revision_id FK; uuid upload_session_id FK; string attachment_type }
  AUDIT_EVENT { uuid id PK; string action; string request_id; string prev_hash; string hash }
  IMPORT_JOB { uuid id PK; uuid upload_session_id FK; string status; string confirm_token }
  USER { uuid id PK; string username; string role; int permission_version }
```

约束：所有业务写表含 `row_version`；租户隔离唯一键；BOMItem 父子复合外键；发布 Revision 的 `effective_range` 使用 PostgreSQL `tstzrange` 排他约束；附件对象通过 `s3_version_id` 固定读取。
