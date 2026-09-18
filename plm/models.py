import uuid, hashlib, json
from django.db import models
from django.contrib.postgres.fields import DateTimeRangeField
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeOperators
from django.db.models.expressions import RawSQL

class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    major_code = models.CharField(max_length=2)
    minor_code = models.CharField(max_length=2)
    name = models.CharField(max_length=120)
    major_name = models.CharField(max_length=120, blank=True)
    path = models.CharField(max_length=255, blank=True)
    attribute_group = models.CharField(max_length=255, blank=True)
    parent_code = models.CharField(max_length=2, blank=True)
    parent_name = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    aliases = models.CharField(max_length=500, blank=True)
    standard_references = models.CharField(max_length=500, blank=True)
    is_selectable = models.BooleanField(default=True)
    part_nature = models.CharField(max_length=32, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    catalog_version = models.CharField(max_length=32, blank=True)
    is_enabled = models.BooleanField(default=True)
    is_leaf = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['major_code','minor_code'], name='uniq_category_code')]
        ordering = ['major_code','minor_code']
    @property
    def code(self): return f'{self.major_code}{self.minor_code}'

class Unit(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    dimension = models.CharField(max_length=32, default='each')
    base_unit_code = models.CharField(max_length=32, blank=True)
    factor_to_base = models.DecimalField(max_digits=24, decimal_places=12, default=1)
    is_active = models.BooleanField(default=True)
    row_version = models.PositiveIntegerField(default=1)
    def __str__(self): return self.name

class NumberSource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    url = models.URLField(unique=True)
    is_enabled = models.BooleanField(default=True)

class NumberRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(NumberSource, on_delete=models.PROTECT)
    source_request_id = models.CharField(max_length=150)
    operation_key = models.CharField(max_length=150, unique=True)
    returned_part_code = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=20, default='draft')

class Part(models.Model):
    STATUS_CHOICES = [('draft','Draft'),('pending_review','Pending review'),('approved','Approved'),('released','Released'),('obsolete','Obsolete')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.CharField(max_length=64, default='default')
    part_code = models.CharField(max_length=32)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, null=True, blank=True, related_name='parts')
    number_request = models.ForeignKey(NumberRequest, on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    row_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['part_code']
        constraints = [models.UniqueConstraint(fields=['tenant_id', 'part_code'], name='uniq_part_tenant_code')]
    @property
    def part_number(self): return self.part_code

class PartRevision(models.Model):
    REVISION_STATES = [('draft','Draft'),('pending_review','Pending review'),('rejected','Rejected'),('approved','Approved'),('release_pending','Release pending'),('released','Released'),('release_failed','Release failed'),('obsolete','Obsolete')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    part = models.ForeignKey(Part, related_name='revisions', on_delete=models.PROTECT)
    revision = models.CharField(max_length=8, default='A')
    revision_seq = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=32, default='standard')
    business_lifecycle = models.CharField(max_length=20, default='active')
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, null=True, blank=True)
    standard_code = models.CharField(max_length=64, blank=True)
    material = models.CharField(max_length=128, blank=True)
    manufacturer = models.CharField(max_length=128, blank=True)
    manufacturer_part_number = models.CharField(max_length=128, blank=True)
    is_customized = models.BooleanField(default=False)
    rohs_standard = models.CharField(max_length=128, blank=True)
    # Category controlled technical parameters (key/value JSON).  Keeping the
    # values on the revision makes every engineering change auditable.
    parameters = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    revision_state = models.CharField(max_length=20, choices=REVISION_STATES, default='draft')
    submitter = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.PROTECT, related_name='submitted_part_revisions')
    reviewer = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.PROTECT, related_name='reviewed_part_revisions')
    publisher = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.PROTECT, related_name='published_part_revisions')
    row_version = models.PositiveIntegerField(default=1)
    effective_range = DateTimeRangeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['part','revision'], name='unique_part_revision'),
            models.CheckConstraint(
                condition=RawSQL("effective_range IS NULL OR (NOT isempty(effective_range) AND lower_inc(effective_range) AND NOT upper_inc(effective_range))", (), output_field=models.BooleanField()),
                name='partrevision_effective_range_half_open',
            ),
            ExclusionConstraint(
                name='partrevision_part_effective_range_excl',
                expressions=[('part', RangeOperators.EQUAL), ('effective_range', RangeOperators.OVERLAPS)],
            ),
        ]
        ordering = ['part','revision_seq']

class BOM(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.CharField(max_length=64, default='default')
    bom_code = models.CharField(max_length=64)
    bom_type = models.CharField(max_length=8, default='EBOM')
    name = models.CharField(max_length=200, blank=True)
    row_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['tenant_id', 'bom_code'], name='uniq_bom_tenant_code')]

class BOMRevision(models.Model):
    REVISION_STATES = PartRevision.REVISION_STATES
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bom = models.ForeignKey(BOM, related_name='revisions', on_delete=models.PROTECT)
    revision = models.CharField(max_length=8, default='A')
    root_part_revision = models.ForeignKey(PartRevision, on_delete=models.PROTECT)
    revision_state = models.CharField(max_length=20, choices=REVISION_STATES, default='draft')
    submitter = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.PROTECT, related_name='submitted_bom_revisions')
    reviewer = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.PROTECT, related_name='reviewed_bom_revisions')
    publisher = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.PROTECT, related_name='published_bom_revisions')
    row_version = models.PositiveIntegerField(default=1)
    effective_range = DateTimeRangeField(null=True, blank=True)
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=RawSQL("effective_range IS NULL OR (NOT isempty(effective_range) AND lower_inc(effective_range) AND NOT upper_inc(effective_range))", (), output_field=models.BooleanField()),
                name='bomrevision_effective_range_half_open',
            ),
            ExclusionConstraint(
                name='bomrevision_bom_effective_range_excl',
                expressions=[('bom', RangeOperators.EQUAL), ('effective_range', RangeOperators.OVERLAPS)],
            ),
        ]

class BOMItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bom_revision = models.ForeignKey(BOMRevision, related_name='items', on_delete=models.PROTECT)
    parent_item = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.PROTECT)
    line_no = models.PositiveIntegerField()
    child_part_revision = models.ForeignKey(PartRevision, null=True, blank=True, on_delete=models.PROTECT, related_name='bom_items')
    child_bom_revision = models.ForeignKey(BOMRevision, null=True, blank=True, on_delete=models.PROTECT, related_name='parent_items')
    quantity = models.DecimalField(max_digits=18, decimal_places=6)
    quantity_entered = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    unit_entered = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.PROTECT, related_name='entered_bom_items')
    conversion_factor = models.DecimalField(max_digits=24, decimal_places=12, default=1)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, null=True, blank=True)
    position = models.CharField(max_length=128, default='__NO_POSITION__')
    no_position_reason = models.CharField(max_length=255, blank=True)
    alternative_group_id = models.UUIDField(null=True, blank=True)
    alternative_role = models.CharField(max_length=16, choices=[('primary','Primary'),('alternate','Alternate')], default='primary')
    priority = models.PositiveIntegerField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['bom_revision','line_no'], name='uniq_bom_line'),
        ]

class UploadSession(models.Model):
    STATES = [('created','Created'),('uploaded','Uploaded'),('verified','Verified'),('failed','Failed'),('expired','Expired'),('cancelled','Cancelled')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    object_key = models.CharField(max_length=512, unique=True)
    bucket = models.CharField(max_length=128)
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=255, blank=True)
    size = models.BigIntegerField()
    total_chunks = models.PositiveIntegerField(default=1)
    declared_sha256 = models.CharField(max_length=64, blank=True)
    state = models.CharField(max_length=20, choices=STATES, default='created')
    upload_id = models.CharField(max_length=255, blank=True)
    s3_version_id = models.CharField(max_length=255, blank=True)
    tenant_id = models.CharField(max_length=64, default='default')
    owner = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.PROTECT, related_name='owned_upload_sessions')
    purpose = models.CharField(max_length=32, default='attachment')
    generation = models.PositiveIntegerField(default=1)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

class PartAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(PartRevision, related_name='attachments', on_delete=models.PROTECT)
    upload_session = models.ForeignKey(UploadSession, related_name='part_attachments', on_delete=models.PROTECT)
    attachment_type = models.CharField(max_length=32, default='drawing')
    filename = models.CharField(max_length=255)
    description = models.CharField(max_length=500, blank=True)
    # ``transparent`` means the client-side enterprise encryption layer leaves
    # ciphertext on the wire/storage.  ClamAV cannot inspect that ciphertext;
    # it must never be reported as a clean scan.
    ENCRYPTION_MODES = [('unknown','Unknown encryption'),('none','No encryption'),('transparent','Transparent enterprise encryption'),('client_decrypted','Client decrypted before upload')]
    encryption_mode = models.CharField(max_length=24, choices=ENCRYPTION_MODES, default='unknown')
    SECURITY_STATES = [('pending','Pending scan'),('scanning','Scanning'),('available','Available'),('quarantined','Quarantined'),('unscannable','Encrypted/opaque - client scan required'),('error','Scan error')]
    security_state = models.CharField(max_length=20, choices=SECURITY_STATES, default='pending')
    scan_generation = models.CharField(max_length=64, blank=True)
    scanner_engine_version = models.CharField(max_length=128, blank=True)
    scanner_signature_version = models.CharField(max_length=128, blank=True)
    scan_error = models.TextField(blank=True)
    scanned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class AttachmentScan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attachment = models.ForeignKey(PartAttachment, related_name='scans', on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default='queued')
    generation = models.CharField(max_length=64, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    engine_version = models.CharField(max_length=128, blank=True)
    signature_version = models.CharField(max_length=128, blank=True)
    result = models.CharField(max_length=255, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=80)
    resource_type = models.CharField(max_length=80, blank=True)
    resource_id = models.CharField(max_length=80, blank=True)
    success = models.BooleanField(default=True)
    details = models.JSONField(default=dict, blank=True)
    # Correlators and a tamper-evident chain are part of the persisted audit
    # contract.  ``entry_hash`` is SHA-256 over the canonical row payload and
    # the previous entry hash; the append-only trigger is installed by the
    # 0014 migration for PostgreSQL deployments.
    request_id = models.CharField(max_length=128, blank=True, db_index=True)
    job_id = models.CharField(max_length=128, blank=True, db_index=True)
    prev_hash = models.CharField(max_length=64, blank=True)
    entry_hash = models.CharField(max_length=64, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def save(self, *args, **kwargs):
        # All application paths (including legacy modules that create an
        # AuditEvent directly) receive the same chain metadata as record_audit.
        # The PostgreSQL trigger makes later mutation impossible.
        if self._state.adding and not self.entry_hash:
            previous = type(self).objects.order_by('-created_at', '-id').first()
            self.prev_hash = self.prev_hash or ((previous.entry_hash or '') if previous else '')
            payload = {'id': str(self.id), 'actor': self.actor, 'action': self.action,
                       'resource_type': self.resource_type, 'resource_id': self.resource_id,
                       'success': bool(self.success), 'details': self.details or {},
                       'request_id': self.request_id or '', 'job_id': self.job_id or '',
                       'prev_hash': self.prev_hash or ''}
            self.entry_hash = hashlib.sha256(json.dumps(payload, sort_keys=True,
                separators=(',', ':'), default=str).encode()).hexdigest()
        return super().save(*args, **kwargs)
    class Meta:
        ordering = ['-created_at']

class ImportJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=32, choices=[('category','category'),('part','part'),('bom','bom')])
    upload_session = models.ForeignKey(UploadSession, on_delete=models.PROTECT)
    status = models.CharField(max_length=32, default='queued')
    business_state = models.CharField(max_length=16, default='none')
    summary = models.JSONField(default=dict, blank=True)
    error_report_key = models.CharField(max_length=512, blank=True)
    tenant_id = models.CharField(max_length=64, default='default', db_index=True)
    actor = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.PROTECT, related_name='import_jobs')
    input_hash = models.CharField(max_length=64, blank=True)
    preview_hash = models.CharField(max_length=64, blank=True)
    catalog_version = models.CharField(max_length=32, blank=True)
    permission_version = models.PositiveIntegerField(default=1)
    confirm_token_hash = models.CharField(max_length=64, blank=True)
    confirm_expires_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=200, blank=True)
    parent_job = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='retries')
    row_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ExportJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=32)
    format = models.CharField(max_length=16, default='csv')
    status = models.CharField(max_length=20, default='queued')
    object_key = models.CharField(max_length=512, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    tenant_id = models.CharField(max_length=64, default='default', db_index=True)
    actor = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.PROTECT, related_name='export_jobs')
    template_version = models.CharField(max_length=32, default='v1.6')
    snapshot_at = models.DateTimeField(null=True, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    artifact_sha256 = models.CharField(max_length=64, blank=True)
    artifact_expires_at = models.DateTimeField(null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)
    idempotency_key = models.CharField(max_length=200, blank=True)
    row_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class FinalizeJob(models.Model):
    """Durable asynchronous upload finalization handle."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    upload_session = models.ForeignKey(UploadSession, on_delete=models.PROTECT, related_name='finalize_jobs')
    parts = models.JSONField(default=list)
    status = models.CharField(max_length=20, default='queued')
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ReleasePublication(models.Model):
    """Durable publication record for an immutable released revision.

    A revision has at most one publication.  Keeping this record in the
    control plane makes release retries idempotent and gives operators a
    durable audit handle without exposing MinIO credentials to clients.
    """
    STATUS_CHOICES = [('pending','Pending'),('published','Published'),('failed','Failed')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.OneToOneField('PartRevision', related_name='release_publication', on_delete=models.PROTECT)
    operation_key = models.CharField(max_length=180, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    canonical_release_key = models.CharField(max_length=512, blank=True)
    version_id = models.CharField(max_length=255, blank=True)
    content_sha256 = models.CharField(max_length=64, blank=True)
    error = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class RevisionReview(models.Model):
    """Immutable review decision and snapshot for a revision submission."""
    DECISIONS = [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.CharField(max_length=64, default='default')
    revision = models.ForeignKey(PartRevision, related_name='reviews', on_delete=models.PROTECT)
    reviewer = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='revision_reviews')
    decision = models.CharField(max_length=16, choices=DECISIONS, default='pending')
    comment = models.TextField(blank=True)
    content_sha256 = models.CharField(max_length=64)
    attachment_set_sha256 = models.CharField(max_length=64, blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['revision'], condition=models.Q(decision='pending'), name='uniq_pending_revision_review')]
        ordering = ['-created_at']


class AttachmentVersion(models.Model):
    """Immutable content identity associated with an attachment upload."""
    SECURITY_STATES = [('scanning','Scanning'), ('available','Available'), ('quarantined','Quarantined'), ('rescanning','Rescanning'), ('rejected','Rejected'), ('unscannable','Unscannable')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.CharField(max_length=64, default='default')
    attachment = models.ForeignKey(PartAttachment, related_name='versions', on_delete=models.PROTECT)
    version_id = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    size_bytes = models.BigIntegerField()
    detected_mime = models.CharField(max_length=255, blank=True)
    security_state = models.CharField(max_length=16, choices=SECURITY_STATES, default='scanning')
    rescan_required = models.BooleanField(default=False)
    last_pass_policy_version = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['attachment','version_id'], name='uniq_attachment_version_id')]
        ordering = ['-created_at']


class ReleaseActivation(models.Model):
    """Revision-level visibility barrier for atomic publication."""
    STATUS_CHOICES = [('pending','Pending'), ('promoting','Promoting'), ('active','Active'), ('failed','Failed'), ('abandoned','Abandoned')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.CharField(max_length=64, default='default')
    revision = models.OneToOneField(PartRevision, related_name='release_activation', on_delete=models.PROTECT)
    operation_key = models.CharField(max_length=180, unique=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')
    error = models.TextField(blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AttachmentStoragePlacement(models.Model):
    """Object placement generated by promotion; release placement is immutable."""
    STATES = [('draft','Draft'), ('release','Release')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.CharField(max_length=64, default='default')
    version = models.ForeignKey(AttachmentVersion, related_name='placements', on_delete=models.PROTECT)
    activation = models.ForeignKey(ReleaseActivation, related_name='placements', null=True, blank=True, on_delete=models.PROTECT)
    storage_tier = models.CharField(max_length=16, choices=STATES, default='draft')
    bucket = models.CharField(max_length=128)
    object_key = models.CharField(max_length=512)
    s3_version_id = models.CharField(max_length=255, blank=True)
    visible = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['storage_tier','object_key'], name='uniq_storage_placement_key')]


class ReleasePromotion(models.Model):
    """Idempotent per-attachment promotion attempt within an activation."""
    STATES = [('pending','Pending'), ('promoted','Promoted'), ('failed','Failed')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.CharField(max_length=64, default='default')
    activation = models.ForeignKey(ReleaseActivation, related_name='promotions', on_delete=models.PROTECT)
    version = models.ForeignKey(AttachmentVersion, related_name='promotions', on_delete=models.PROTECT)
    status = models.CharField(max_length=16, choices=STATES, default='pending')
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['activation','version'], name='uniq_release_promotion')]



class UserSecurity(models.Model):
    user = models.OneToOneField('auth.User', primary_key=True, on_delete=models.CASCADE, related_name='security')
    permission_version = models.PositiveIntegerField(default=1)
    session_nonce = models.UUIDField(default=uuid.uuid4, editable=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
