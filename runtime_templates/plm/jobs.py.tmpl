"""MinIO backed import/export jobs.

The API stores only an UploadSession and dispatches these tasks to Celery.  A
worker reads the object directly from MinIO; no input or output file is ever
written to the application container filesystem.  Import parsing is bounded
to the configured upload limit (5 GiB) and the worker keeps the decoded input
in memory only for the duration of a task.
"""
import csv
import io
import json
import os
import uuid
import socket
import struct
import hashlib
from decimal import Decimal, InvalidOperation

import boto3
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import secrets

from .models import (
    BOM, BOMItem, BOMRevision, Category, ImportJob, Part, PartRevision,
    Unit, UploadSession, ExportJob, FinalizeJob, PartAttachment, AttachmentScan,
    AttachmentVersion,
    UserSecurity,
)

MAX_BYTES = 5 * 1024 * 1024
MAX_ERRORS = 1000
CLAMAV_MAX_BYTES = int(os.getenv('CLAMAV_MAX_BYTES', str(4 * 1024 * 1024 * 1024)))

def _confirm_cache_key(job_id):
    return f'plm:import-confirm:{job_id}'

def _clamd_scan(body, timeout=1800):
    """Scan a stream with clamd INSTREAM; returns raw daemon verdict."""
    host, port = os.getenv('CLAMAV_HOST', 'clamav'), int(os.getenv('CLAMAV_PORT', '3310'))
    sock = socket.create_connection((host, port), timeout=min(timeout, 30)); sock.settimeout(timeout)
    try:
        sock.sendall(b'zINSTREAM\0')
        while True:
            chunk = body.read(1024 * 1024)
            if not chunk: break
            sock.sendall(struct.pack('!I', len(chunk)) + chunk)
        sock.sendall(struct.pack('!I', 0))
        return sock.recv(4096).decode('utf-8', 'replace').strip()
    finally:
        sock.close()

@shared_task(name='plm.scan_attachment')
def scan_attachment(attachment_id):
    """Fail-closed ClamAV gate.

    Transparent enterprise encryption is intentionally treated as opaque: the
    container only receives ciphertext, so a ClamAV ``OK`` verdict over those
    bytes would be meaningless. Opaque content remains quarantined until an
    explicit policy override is implemented by a trusted decryption service.
    """
    attachment = PartAttachment.objects.select_related('upload_session').get(pk=attachment_id)
    session = attachment.upload_session
    scan = AttachmentScan.objects.create(attachment=attachment, status='running', generation=uuid.uuid4().hex, started_at=timezone.now())
    version = attachment.versions.order_by('-created_at').first()
    attachment.security_state = 'scanning'; attachment.scan_generation = scan.generation; attachment.save(update_fields=['security_state','scan_generation'])
    if attachment.encryption_mode in ('transparent', 'unknown'):
        scan.status = 'opaque'; scan.result = 'OPAQUE_ENCRYPTED_CONTENT'; scan.error = 'encrypted or unknown content cannot be trusted as clean; upload authorized plaintext for container scanning or integrate a trusted decryption/scan service'; scan.finished_at = timezone.now()
        scan.save(update_fields=['status','result','error','finished_at'])
        # The container cannot inspect enterprise-transparent ciphertext. Keep
        # the object explicitly unscannable and fail all release/download gates.
        attachment.security_state = 'unscannable'; attachment.scan_error = scan.error; attachment.scanned_at = timezone.now()
        attachment.save(update_fields=['security_state','scan_error','scanned_at'])
        if version is not None:
            version.security_state = 'unscannable'; version.rescan_required = True
            version.save(update_fields=['security_state','rescan_required'])
        return {'status': 'opaque', 'code': 'OPAQUE_ENCRYPTED_CONTENT', 'attachment': str(attachment.id)}
    if session.size > CLAMAV_MAX_BYTES:
        scan.status='error'; scan.error='UPLOAD_SIZE_EXCEEDED: ClamAV publish limit is 4 GiB'; scan.finished_at=timezone.now(); scan.save(update_fields=['status','error','finished_at'])
        attachment.security_state='error'; attachment.scan_error=scan.error; attachment.scanned_at=timezone.now(); attachment.save(update_fields=['security_state','scan_error','scanned_at']); return {'status':'error','code':'UPLOAD_SIZE_EXCEEDED'}
    body = None
    try:
        body = s3_client().get_object(Bucket=session.bucket, Key=session.object_key)['Body']
        digest = hashlib.sha256()
        class Tee:
            def read(self, n=-1):
                data = body.read(n)
                if data: digest.update(data)
                return data
        verdict = _clamd_scan(Tee())
        scan.sha256 = digest.hexdigest(); scan.result = verdict
        normalized_verdict = verdict.rstrip('\x00\r\n ').upper()
        clean = normalized_verdict == 'OK' or normalized_verdict.endswith(': OK')
        scan.status = 'clean' if clean else 'infected'; scan.engine_version = os.getenv('CLAMAV_ENGINE_VERSION','unknown'); scan.signature_version = os.getenv('CLAMAV_DB_VERSION','unknown'); scan.finished_at=timezone.now(); scan.save(update_fields=['sha256','result','status','engine_version','signature_version','finished_at'])
        attachment.security_state = 'available' if clean else 'quarantined'; attachment.scanner_engine_version=scan.engine_version; attachment.scanner_signature_version=scan.signature_version; attachment.scanned_at=timezone.now(); attachment.save(update_fields=['security_state','scanner_engine_version','scanner_signature_version','scanned_at'])
        if version is not None:
            version.sha256 = scan.sha256
            version.security_state = 'available' if clean else 'quarantined'
            version.rescan_required = not clean
            version.last_pass_policy_version = os.getenv('CLAMAV_POLICY_VERSION', 'clamav-default') if clean else ''
            version.save(update_fields=['sha256','security_state','rescan_required','last_pass_policy_version'])
        return {'status': scan.status, 'attachment': str(attachment.id)}
    except Exception as exc:
        scan.status='error'; scan.error=str(exc); scan.finished_at=timezone.now(); scan.save(update_fields=['status','error','finished_at'])
        attachment.security_state='error'; attachment.scan_error=str(exc); attachment.scanned_at=timezone.now(); attachment.save(update_fields=['security_state','scan_error','scanned_at'])
        if version is not None:
            version.security_state='rejected'; version.rescan_required=True; version.save(update_fields=['security_state','rescan_required'])
        raise
    finally:
        if body is not None:
            try:
                body.close()
            except Exception:
                pass

# Spreadsheet formula injection guard mandated by V1.6 §6.5.4.  Prefix
# dangerous leading characters with a single quote while preserving the
# original text for all ordinary cells.  Apply to every generated CSV/JSON
# artifact because JSON is routinely converted to spreadsheets by users.
_DANGEROUS_PREFIXES = ('=', '+', '-', '@', '\t', '\r')

def _safe_cell(value):
    text = '' if value is None else str(value)
    return "'" + text if text.startswith(_DANGEROUS_PREFIXES) else text


def s3_client():
    return boto3.client(
        "s3", endpoint_url=settings.MINIO_ENDPOINT,
        aws_access_key_id=os.getenv("MINIO_ROOT_USER", ""),
        aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", ""),
        region_name="us-east-1",
    )


def _read_session(session):
    if session.state not in ("uploaded", "verified"):
        raise ValueError("upload session must be completed before importing")
    if session.size <= 0 or session.size > MAX_BYTES:
        raise ValueError("import file must not exceed 5 MiB")
    response = s3_client().get_object(Bucket=session.bucket, Key=session.object_key)
    # Keep the object as a streaming MinIO body.  CSV parsing below consumes
    # it incrementally; the worker never creates a temporary Linux file.
    content_length = response.get("ContentLength")
    if content_length is not None and content_length > MAX_BYTES:
        response["Body"].close()
        raise ValueError("import file must not exceed 5 MiB")
    return response["Body"]


def _rows(session, body):
    name = (session.filename or "").lower()
    content_type = (session.content_type or "").lower()
    if not (name.endswith(".csv") or name.endswith(".json") or "csv" in content_type or "json" in content_type):
        body.close()
        raise ValueError("only CSV and JSON import files are supported")
    if name.endswith(".json") or "json" in content_type:
        raw = body.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("JSON object exceeds the configured 5 GiB limit")
        value = json.loads(raw.decode("utf-8-sig"))
        if isinstance(value, dict):
            value = value.get("rows", value.get("data", []))
        if not isinstance(value, list):
            raise ValueError("JSON import must contain an array or rows array")
        if not all(isinstance(row, dict) for row in value):
            raise ValueError("every JSON row must be an object")
        return value
    # DictReader reads one physical line at a time from the MinIO streaming
    # body.  This keeps peak parser memory bounded by a row plus the decoded
    # domain objects being committed, rather than the complete upload.
    return csv.DictReader(io.TextIOWrapper(body, encoding="utf-8-sig", newline=""))


def _text(row, *names, default=""):
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


def _json_cell(row, name, *, default, expected):
    """Parse a JSON CSV cell while retaining a useful row-level error."""
    raw_value = row.get(name)
    if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
        return default
    if isinstance(raw_value, expected):
        return raw_value
    raw = str(raw_value).strip()
    try:
        value = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        # aliases/standard_references historically accepted free text. Keep
        # those rows importable while still rejecting cells that advertise a
        # JSON structure but are malformed. attribute_schema always requires
        # an object and therefore does not take this compatibility path.
        if expected is list and raw[:1] not in ('[', '{'):
            return raw
        raise ValueError(f"{name} must contain valid JSON: {exc}")
    if not isinstance(value, expected):
        expected_name = 'array' if expected is list else 'object'
        raise ValueError(f"{name} must contain a JSON {expected_name}")
    return value


def _category_json_text(row, name):
    value = row.get(name)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return _text(row, name)


def _category_ref(row):
    code = _text(row, "code", "category_code")
    if not code:
        code = _text(row, "major_code") + _text(row, "minor_code")
    code = code.replace("-", "")
    if len(code) not in (2, 4) or not code.isdigit():
        raise ValueError("category code must contain four digits")
    if len(code) == 2:
        return code, "00"
    return code[:2], code[2:]


def _validate_category(row, index):
    major, minor = _category_ref(row)
    if not _text(row, "name"):
        raise ValueError("name is required")
    if minor != "00" and _text(row, "parent_code", default=major).replace("-", "") != major:
        raise ValueError("minor category parent_code must match its major prefix")
    selectable = _text(row, "is_selectable", default="true").lower()
    if selectable not in ("true", "false", "1", "0", "yes", "no"):
        raise ValueError("is_selectable must be a boolean")
    try:
        sort_order = int(_text(row, "sort_order", default="0"))
        if sort_order < 0: raise ValueError
    except ValueError:
        raise ValueError("sort_order must be a non-negative integer")
    # Validate JSON cells at dry-run time.  aliases and standard references
    # remain text columns for backwards compatibility and byte-preserving CSV
    # round trips; attribute_schema is stored as structured JSON.
    _json_cell(row, "aliases", default=[], expected=list)
    _json_cell(row, "standard_references", default=[], expected=list)
    attribute_schema = _json_cell(row, "attribute_schema", default={}, expected=dict)
    active = _text(row, "is_active", "is_enabled", default="true").lower()
    if active not in ("true", "false", "1", "0", "yes", "no"):
        raise ValueError("is_active must be a boolean")
    return {"major_code": major, "minor_code": minor,
            "name": _text(row, "name"),
            "major_name": _text(row, "major_name", "parent_name", default=_text(row, "name")),
            "parent_code": _text(row, "parent_code"),
            "parent_name": _text(row, "parent_name"),
            "path": _text(row, "path", "full_path"),
            "description": _text(row, "description"),
            "aliases": _category_json_text(row, "aliases"),
            "standard_references": _category_json_text(row, "standard_references"),
            "attribute_schema": attribute_schema,
            "attribute_group": _text(row, "attribute_group", "attribute_groups"),
            "part_nature": _text(row, "part_nature"),
            "catalog_version": _text(row, "catalog_version"),
            "is_selectable": selectable in ("true", "1", "yes"),
            "is_enabled": active in ("true", "1", "yes"),
            "sort_order": sort_order,
            "is_leaf": minor != "00"}


def _complete_category_hierarchy(rows):
    """Fill parent-derived fields after all rows have been validated.

    CSV order is not a hierarchy contract; a child may precede its parent.
    Parents already in the catalog are accepted for incremental imports.
    """
    imported = {f"{row['major_code']}{row['minor_code']}": row for row in rows}
    existing_codes = set(
        Category.objects.filter(minor_code='00').values_list('major_code', flat=True)
    )
    existing = {
        row.major_code: row
        for row in Category.objects.filter(minor_code='00')
    }
    for row in rows:
        if row['minor_code'] == '00':
            row['major_name'] = row.get('major_name') or row['name']
            row['path'] = row.get('path') or row['name']
            row['parent_code'] = ''
            row['parent_name'] = ''
            continue
        parent_code = row.get('parent_code') or row['major_code']
        parent = imported.get(f"{parent_code}00") or existing.get(parent_code)
        if parent is None and parent_code not in existing_codes:
            raise ValueError(f"parent category not found: {parent_code}")
        parent_name = row.get('parent_name')
        major_name = row.get('major_name')
        parent_path = ''
        if parent is not None:
            if hasattr(parent, 'name'):
                parent_name = parent_name or parent.name
                major_name = parent.name
                parent_path = parent.path
            else:
                parent_name = parent_name or parent.get('name', '')
                major_name = parent.get('name', '')
                parent_path = parent.get('path', '')
        row['parent_code'] = parent_code
        row['parent_name'] = parent_name or ''
        row['major_name'] = major_name or row['parent_name']
        row['path'] = row.get('path') or (f"{parent_path}/{row['name']}" if parent_path else f"{row['parent_name']}/{row['name']}")
    return rows


def _validate_part(row, index):
    code = _text(row, "part_code", "part_number")
    if not code or len(code) != 10 or code[4] != "-" or not code[:4].isdigit() or not code[5:].isdigit():
        raise ValueError("part_code must match NNNN-NNNNN")
    major, minor = _category_ref(row)
    if minor == "00" or code[:4] != major + minor or code.endswith("-00000"):
        raise ValueError("part_code must use a selectable category prefix and nonzero sequence")
    if not _text(row, "name"):
        raise ValueError("name is required")
    return {"part_code": code, "category_code": major + minor,
            "name": _text(row, "name"), "revision": _text(row, "revision", default="A"),
            "kind": _text(row, "kind", default="standard"),
            "business_lifecycle": _text(row, "business_lifecycle", default="active"),
            "unit_code": _text(row, "unit_code", "unit"),
            "standard_code": _text(row, "standard_code"), "material": _text(row, "material"),
            "manufacturer": _text(row, "manufacturer"),
            "manufacturer_part_number": _text(row, "manufacturer_part_number"),
            "description": _text(row, "description"),
            "is_customized": _text(row, "is_customized", default="false").lower() in ("true", "1", "yes"),
            "rohs_standard": _text(row, "rohs_standard"),
            "catalog_version": _text(row, "catalog_version")}


def _validate_bom(row, index):
    bom_code = _text(row, "bom_code")
    root = _text(row, "root_part_code", "root_part", "parent_part_code")
    child = _text(row, "child_part_code", "child_part", "part_code")
    root_rev = _text(row, "root_part_revision", "root_revision")
    child_rev = _text(row, "child_part_revision", "child_revision")
    if not bom_code or not root or not child or not root_rev or not child_rev:
        raise ValueError("bom_code, root_part_code, root_part_revision, child_part_code and child_part_revision are required")
    if _text(row, "bom_type", default="EBOM").upper() != "EBOM":
        raise ValueError("only EBOM imports are supported")
    try:
        quantity = Decimal(_text(row, "quantity", default="1"))
        if quantity <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        raise ValueError("quantity must be a positive number")
    try:
        line_no = int(_text(row, "line_no", default=str(index + 1)))
    except ValueError:
        raise ValueError("line_no must be an integer")
    return {"bom_code": bom_code, "bom_type": "EBOM",
            "name": _text(row, "name"), "revision": _text(row, "revision", default="A"),
            "root": root, "root_revision": root_rev, "child": child, "child_revision": child_rev, "quantity": quantity,
            "line_no": line_no, "unit_code": _text(row, "unit_code", "unit"),
            "position": _text(row, "position", default="__NO_POSITION__"),
            "no_position_reason": _text(row, "no_position_reason")}


def _error_report(job, errors):
    if not errors:
        return ""
    prefix = f"imports/{job.tenant_id}/{job.id}/errors"
    rows = []
    for item in errors:
        raw = item.get('message', '') if isinstance(item, dict) else str(item)
        code, _, message = str(raw).partition(':')
        if not message:
            code, message = 'IMPORT_VALIDATION_ERROR', str(raw)
        data = item.get('data') if isinstance(item, dict) else None
        source_value = ''
        if isinstance(data, dict):
            source_value = next((str(value)[:200] for value in data.values() if value not in (None, '')), '')
        rows.append({'row_number': item.get('row', '') if isinstance(item, dict) else '', 'column': item.get('column', '') if isinstance(item, dict) else '', 'error_code': code.strip() or 'IMPORT_VALIDATION_ERROR', 'message': message.strip(), 'source_value': source_value})
    payload = json.dumps({'job_id': str(job.id), 'errors': rows}, ensure_ascii=False, separators=(',', ':')).encode()
    csv_out = io.StringIO(newline='')
    writer = csv.DictWriter(csv_out, fieldnames=['row_number','column','error_code','message','source_value'], quoting=csv.QUOTE_ALL, lineterminator='\r\n')
    writer.writeheader(); writer.writerows(rows)
    client = s3_client()
    client.put_object(Bucket=settings.MINIO_BUCKET_EXPORT, Key=f'{prefix}.json', Body=payload, ContentType='application/json')
    client.put_object(Bucket=settings.MINIO_BUCKET_EXPORT, Key=f'{prefix}.csv', Body=b'\xef\xbb\xbf' + csv_out.getvalue().encode('utf-8'), ContentType='text/csv; charset=utf-8')
    return f'{prefix}.json'

def _session_input_hash(session):
    body = s3_client().get_object(Bucket=session.bucket, Key=session.object_key)['Body']
    digest = hashlib.sha256()
    try:
        for chunk in iter(lambda: body.read(1024 * 1024), b''):
            digest.update(chunk)
    finally:
        body.close()
    return digest.hexdigest()

def _preview_hash(rows):
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, default=str, separators=(',', ':')).encode()).hexdigest()

def _issue_confirm_token(job, *, input_hash, preview_hash, catalog_version=None):
    token = secrets.token_urlsafe(32)
    job.input_hash = input_hash
    job.preview_hash = preview_hash
    if catalog_version is not None:
        job.catalog_version = catalog_version
    job.confirm_token_hash = hashlib.sha256(token.encode()).hexdigest()
    job.confirm_expires_at = timezone.now() + timedelta(seconds=int(getattr(settings, 'IMPORT_CONFIRM_TOKEN_TTL', 1800)))
    ttl = max(1, int((job.confirm_expires_at - timezone.now()).total_seconds()))
    # Do not expose a token for a rolled-back preview transaction.
    transaction.on_commit(lambda: cache.set(_confirm_cache_key(job.id), token, timeout=ttl))
    job.summary = {**(job.summary or {}), 'confirm_expires_at': job.confirm_expires_at.isoformat()}
    job.summary.pop('confirm_token', None)
    fields = ['input_hash', 'preview_hash', 'confirm_token_hash', 'confirm_expires_at', 'summary', 'updated_at']
    if catalog_version is not None:
        fields.append('catalog_version')
    job.save(update_fields=fields)
    return token


def _current_catalog_version():
    """Return the single catalog version currently represented in the DB."""
    versions = list(Category.objects.exclude(catalog_version='').values_list('catalog_version', flat=True).distinct())
    if not versions:
        return ''
    # Catalog versions are semantic (major.minor.patch), so compare numeric
    # components instead of relying on lexical ordering (4.0.0 > 10.0.0).
    def key(value):
        try:
            return (1, tuple(int(part) for part in str(value).split('.')), '')
        except (TypeError, ValueError):
            return (0, (), str(value))
    return max(versions, key=key)


def _catalog_version_for(kind, rows):
    versions = {str(row.get('catalog_version') or '') for row in rows if row.get('catalog_version')}
    if len(versions) > 1:
        raise ValueError('CATALOG_VERSION_MISMATCH: import contains multiple catalog versions')
    declared = next(iter(versions), '')
    current = _current_catalog_version()
    if current and declared and current != declared:
        raise ValueError('CATALOG_VERSION_MISMATCH')
    # An initial catalog import establishes the first active version.
    return current or declared


def _catalog_fingerprint():
    return _preview_hash(list(Category.objects.order_by('major_code', 'minor_code').values()))


def _assert_part_importable(part_revision):
    if part_revision is not None and part_revision.revision_state != 'draft':
        raise ValueError(f'IMMUTABLE_REVISION: part revision is not draft: {part_revision.part.part_code}/{part_revision.revision}')


def _assert_bom_importable(bom_revision):
    if bom_revision is not None and bom_revision.revision_state != 'draft':
        raise ValueError(f'IMMUTABLE_REVISION: BOM revision is not draft: {bom_revision.bom.bom_code}/{bom_revision.revision}')


def _set_import_result(job, status, total, valid, errors, **extra):
    summary = {**(job.summary or {}), "total": total, "valid": valid, "error_count": len(errors),
               "errors": errors[:MAX_ERRORS], **extra}
    if status != 'awaiting_confirmation': summary.pop('confirm_token', None)
    job.status = status
    job.business_state = 'committed' if status == 'completed' else ('staged' if status == 'awaiting_confirmation' else 'none')
    job.row_version += 1
    job.summary = summary
    try:
        job.error_report_key = _error_report(job, errors)
    except Exception as report_exc:
        # Reporting storage outages must not hide the validation/commit result.
        summary["error_report_error"] = str(report_exc)
        job.error_report_key = ""
    job.save(update_fields=["status", "business_state", "summary", "error_report_key", "row_version", "updated_at"])


def _parse_import_job(job):
    """Read and validate one upload without mutating domain tables."""
    stream = _read_session(job.upload_session)
    try:
        # Hash exactly the bytes being parsed, once. A separate GET for the
        # hash could attest different bytes after an object replacement.
        raw = stream.read(MAX_BYTES + 1)
    finally:
        stream.close()
    if len(raw) > MAX_BYTES:
        raise ValueError('UPLOAD_SIZE_EXCEEDED: import file must not exceed 5 MiB')
    if len(raw) != job.upload_session.size:
        raise ValueError('INPUT_SIZE_MISMATCH')
    rows = _rows(job.upload_session, io.BytesIO(raw))
    parsed, errors = [], []
    validator = {"category": _validate_category, "part": _validate_part, "bom": _validate_bom}.get(job.kind)
    if not validator:
        raise ValueError(f"unsupported import kind: {job.kind}")
    total = 0
    for index, row in enumerate(rows):
        total += 1
        if total > 10000:
            raise ValueError('IMPORT_ROW_LIMIT_EXCEEDED')
        try:
            normalized = validator(row, index)
            if job.kind == 'bom':
                root_qs = PartRevision.objects.filter(
                    part__part_code=normalized['root'], part__tenant_id=job.tenant_id,
                    revision=normalized['root_revision'],
                )
                child_qs = PartRevision.objects.filter(
                    part__part_code=normalized['child'], part__tenant_id=job.tenant_id,
                    revision=normalized['child_revision'],
                )
                if not root_qs.exists():
                    raise ValueError(f"root part/revision not found in PLM: {normalized['root']} / {normalized['root_revision']}")
                child_revision = child_qs.first()
                if child_revision is None:
                    raise ValueError(f"child part/revision not found in PLM: {normalized['child']} / {normalized['child_revision']}")
                if child_revision.revision_state != 'released':
                    raise ValueError(f"referenced child revision is not released: {normalized['child']} / {normalized['child_revision']}")
            parsed.append(normalized)
        except Exception as exc:
            errors.append({"row": index + 2, "message": str(exc), "data": row})
    if job.kind == 'category' and not errors:
        try:
            _complete_category_hierarchy(parsed)
        except Exception as exc:
            errors.append({'row': 0, 'message': str(exc)})
    return parsed, errors, total, hashlib.sha256(raw).hexdigest()


def _import_actor(job):
    from django.contrib.auth import get_user_model
    from .roles import user_role
    actor = get_user_model().objects.select_for_update().filter(pk=job.actor_id).first()
    security = UserSecurity.objects.select_for_update().filter(user_id=job.actor_id).first()
    role = user_role(actor)
    allowed = ('sysadmin', 'admin') if job.kind == 'category' else ('engineer', 'admin')
    if not actor or not actor.is_active or role not in allowed:
        raise ValueError('STALE_CONFIRMATION: actor is no longer authorized')
    version = security.permission_version if security else 1
    if version != job.permission_version:
        raise ValueError('STALE_CONFIRMATION: actor permission version changed')
    session = job.upload_session
    if session.tenant_id != job.tenant_id or session.owner_id != actor.pk or session.purpose != 'import_source':
        raise ValueError('STALE_CONFIRMATION: upload ownership or purpose changed')
    return actor


def _validate_commit_binding(job, parsed, input_hash):
    """Recheck every confirmation binding immediately before commit."""
    if not job.actor_id:
        raise ValueError('STALE_CONFIRMATION')
    if not job.confirm_expires_at or job.confirm_expires_at <= timezone.now():
        raise ValueError('STALE_CONFIRMATION')
    cached_token = cache.get(_confirm_cache_key(job.id))
    if not cached_token or hashlib.sha256(str(cached_token).encode()).hexdigest() != job.confirm_token_hash:
        raise ValueError('STALE_CONFIRMATION')
    if not job.confirm_token_hash or not job.input_hash or not job.preview_hash:
        raise ValueError('STALE_CONFIRMATION')
    if input_hash != job.input_hash:
        raise ValueError('STALE_CONFIRMATION')
    if _preview_hash(parsed) != job.preview_hash:
        raise ValueError('STALE_CONFIRMATION')
    current_catalog = _catalog_version_for(job.kind, parsed)
    if job.catalog_version != current_catalog or (job.summary or {}).get('catalog_fingerprint') != _catalog_fingerprint():
        raise ValueError('STALE_CONFIRMATION')
    if str((job.summary or {}).get('actor_id')) != str(job.actor_id):
        raise ValueError('STALE_CONFIRMATION')
    _import_actor(job)


def _commit_rows(kind, rows, tenant_id):
    if kind == 'category':
        _commit_categories(rows)
    elif kind == 'part':
        _commit_parts(rows, tenant_id)
    else:
        _commit_boms(rows, tenant_id)


def _commit_categories(rows):
    codes = {(r["major_code"], r["minor_code"]) for r in rows}
    if len(codes) != len(rows):
        raise ValueError("duplicate category codes in import")
    for row in rows:
        if row["minor_code"] != "00" and not Category.objects.filter(major_code=row["major_code"], minor_code="00").exists() and (row["major_code"], "00") not in codes:
            raise ValueError(f"parent category not found: {row['major_code']}")
    for row in rows:
        Category.objects.update_or_create(major_code=row["major_code"], minor_code=row["minor_code"], defaults=row)


def _commit_parts(rows, tenant_id='default'):
    for row in rows:
        major, minor = row["category_code"][:2], row["category_code"][2:]
        category = Category.objects.get(major_code=major, minor_code=minor)
        unit = Unit.objects.filter(code=row["unit_code"]).first() if row["unit_code"] else None
        part = Part.objects.filter(part_code=row["part_code"], tenant_id=tenant_id).first()
        if part is not None:
            if part.status in ('released', 'obsolete') or part.revisions.filter(revision_state__in=('released', 'obsolete')).exists():
                raise ValueError(f'IMMUTABLE_REVISION: published part cannot be overwritten: {row["part_code"]}')
            part.category = category
            part.save(update_fields=['category', 'updated_at'])
        else:
            part = Part.objects.create(part_code=row["part_code"], tenant_id=tenant_id, category=category)
        rev = PartRevision.objects.filter(part=part, revision=row["revision"]).first()
        _assert_part_importable(rev)
        if rev is None:
            rev = PartRevision(part=part, revision=row["revision"])
        rev.name = row["name"]
        rev.kind = row["kind"]
        rev.business_lifecycle = row["business_lifecycle"]
        rev.unit = unit
        rev.standard_code = row["standard_code"]
        rev.material = row["material"]
        rev.manufacturer = row["manufacturer"]
        rev.manufacturer_part_number = row["manufacturer_part_number"]
        rev.is_customized = row["is_customized"]
        rev.rohs_standard = row["rohs_standard"]
        rev.description = row["description"]
        rev.save()


def _commit_boms(rows, tenant_id='default'):
    grouped = {}
    for row in rows:
        grouped.setdefault((row["bom_code"], row["revision"]), []).append(row)
    for (bom_code, revision), items in grouped.items():
        first = items[0]
        bom = BOM.objects.filter(bom_code=bom_code, tenant_id=tenant_id).first()
        if bom is None:
            bom = BOM.objects.create(bom_code=bom_code, tenant_id=tenant_id,
                                     bom_type=first["bom_type"], name=first["name"])
        else:
            if bom.revisions.filter(revision_state__in=('released', 'obsolete')).exists():
                raise ValueError(f'IMMUTABLE_REVISION: published BOM cannot be overwritten: {bom_code}')
            bom.bom_type = first["bom_type"]
            bom.name = first["name"]
            bom.save(update_fields=['bom_type', 'name'])
        root = PartRevision.objects.filter(
            part__part_code=first["root"], part__tenant_id=tenant_id,
            revision=first["root_revision"],
        ).select_related('part').first()
        if not root:
            raise ValueError(f"root part not found: {first['root']}")
        brevision = BOMRevision.objects.filter(bom=bom, revision=revision).select_related('bom').first()
        _assert_bom_importable(brevision)
        if brevision is None:
            brevision = BOMRevision.objects.create(bom=bom, revision=revision, root_part_revision=root)
        else:
            brevision.root_part_revision = root
            brevision.save(update_fields=['root_part_revision'])
        for row in items:
            child = PartRevision.objects.filter(
                part__part_code=row["child"], part__tenant_id=tenant_id,
                revision=row["child_revision"],
            ).select_related('part').first()
            if not child:
                raise ValueError(f"child part not found: {row['child']}")
            if child.revision_state != 'released':
                raise ValueError(f"referenced child revision is not released: {row['child']} / {row['child_revision']}")
            unit = Unit.objects.filter(code=row["unit_code"]).first() if row["unit_code"] else None
            BOMItem.objects.update_or_create(bom_revision=brevision, line_no=row["line_no"], defaults={"child_part_revision": child, "quantity": row["quantity"], "unit": unit, "position": row["position"]})
        from .bom_services import validate_bom_tree
        validate_bom_tree(brevision, lifecycle_gate=True)


def process_import_job(job_id, commit=False):
    """Run a preview or commit with one durable state transition.

    Parsing happens before the final lock, but every commit binding and domain
    write is rechecked while the Job row is locked. This makes duplicate Celery
    deliveries harmless and gives cancellation deterministic lock ordering.
    """
    with transaction.atomic():
        job = ImportJob.objects.select_for_update().select_related('upload_session').get(pk=job_id)
        if not commit and job.status not in ('queued', 'dry_run'):
            return job.summary or {'status': job.status}
        if commit and job.status in ('completed', 'failed', 'cancelled', 'expired'):
            return job.summary or {'status': job.status}
        if commit and job.status not in ('awaiting_confirmation', 'committing', 'dry_run'):
            raise ValueError('STATE_TRANSITION_INVALID')
        if commit and (job.summary or {}).get('error_count', 1) != 0:
            raise ValueError('commit requires a successful dry_run import with zero errors')

        try:
            parsed, errors, total, input_hash = _parse_import_job(job)
            catalog_version = _catalog_version_for(job.kind, parsed)
            if errors:
                status = 'failed' if commit else 'completed_with_errors'
                _set_import_result(job, status, total, len(parsed), errors)
                return job.summary

            if not commit:
                # Execute the same business commit code inside a savepoint and
                # force a rollback so previews catch FK, immutability, and BOM
                # graph errors without writing formal domain rows.
                try:
                    with transaction.atomic():
                        _commit_rows(job.kind, parsed, job.tenant_id)
                        raise RuntimeError('_preview_rollback')
                except RuntimeError as exc:
                    if str(exc) != '_preview_rollback':
                        raise
                _set_import_result(job, 'awaiting_confirmation', total, len(parsed), [], catalog_version=catalog_version)
                job.summary = {**(job.summary or {}), 'actor_id': job.actor_id,
                               'catalog_fingerprint': _catalog_fingerprint()}
                _issue_confirm_token(job, input_hash=input_hash, preview_hash=_preview_hash(parsed), catalog_version=catalog_version)
                return job.summary

            _validate_commit_binding(job, parsed, input_hash)
            with transaction.atomic():
                _commit_rows(job.kind, parsed, job.tenant_id)
            _set_import_result(job, 'completed', total, len(parsed), [], created=len(parsed))
            job.confirm_token_hash = ''
            job.confirm_expires_at = None
            job.save(update_fields=['confirm_token_hash', 'confirm_expires_at', 'updated_at'])
            transaction.on_commit(lambda: cache.delete(_confirm_cache_key(job.id)))
            return job.summary
        except Exception as exc:
            error_text = str(exc)
            if commit and (error_text.startswith('STALE_CONFIRMATION') or error_text.startswith('CATALOG_VERSION_MISMATCH')):
                stale = error_text.startswith('STALE_CONFIRMATION')
                job.status = 'expired' if stale else 'failed'
                job.business_state = 'staged' if job.status == 'expired' else 'none'
                job.confirm_token_hash = ''
                job.row_version += 1
                job.summary = {**(job.summary or {}), 'error_count': 1,
                               'errors': [{'row': 0, 'message': str(exc)}]}
                job.save(update_fields=['status', 'business_state', 'confirm_token_hash', 'row_version', 'summary', 'updated_at'])
                transaction.on_commit(lambda: cache.delete(_confirm_cache_key(job.id)))
            else:
                _set_import_result(job, 'failed', 0, 0, [{'row': 0, 'message': str(exc)}])
            raise


@shared_task(name="plm.process_import_job")
def run_import_job(job_id, commit=False):
    return process_import_job(job_id, commit=commit)


def cancel_import_job(job_id):
    """Cancel a queued/dry-run import without touching domain tables."""
    with transaction.atomic():
        job = ImportJob.objects.select_for_update().get(pk=job_id)
        if job.status in ("completed", "failed", "cancelled", "expired"):
            return job.summary or {"status": job.status}
        if job.status not in ('queued', 'running', 'awaiting_confirmation', 'committing', 'dry_run'):
            raise ValueError('STATE_TRANSITION_INVALID')
        job.status = "cancelled"
        cache.delete(_confirm_cache_key(job.id))
        job.confirm_token_hash = ''
        job.row_version += 1
        job.summary = {**(job.summary or {}), "cancelled_at": timezone.now().isoformat()}
        job.save(update_fields=["status", "confirm_token_hash", "row_version", "summary", "updated_at"])
        transaction.on_commit(lambda: cache.delete(_confirm_cache_key(job.id)))
        return job.summary


def _export_rows(kind, filters):
    if kind == "category":
        qs = Category.objects.all()
        return (["code", "major_code", "minor_code", "name", "major_name", "path", "attribute_group", "parent_code", "parent_name", "description", "aliases", "standard_references", "is_selectable", "part_nature", "sort_order", "catalog_version", "is_enabled", "is_leaf"],
                ((c.code, c.major_code, c.minor_code, c.name, c.major_name, c.path, c.attribute_group, c.parent_code, c.parent_name, c.description, c.aliases, c.standard_references, c.is_selectable, c.part_nature, c.sort_order, c.catalog_version, c.is_enabled, c.is_leaf) for c in qs))
    if kind == "part":
        qs = PartRevision.objects.select_related("part", "part__category", "unit").all()
        return (["part_code", "category_code", "revision", "revision_seq", "name", "kind", "business_lifecycle", "unit_code", "standard_code", "material", "manufacturer", "manufacturer_part_number", "is_customized", "rohs_standard", "description", "revision_state"],
                ((r.part.part_code, r.part.category.code if r.part.category else "", r.revision, r.revision_seq, r.name, r.kind, r.business_lifecycle, r.unit.code if r.unit else "", r.standard_code, r.material, r.manufacturer, r.manufacturer_part_number, r.is_customized, r.rohs_standard, r.description, r.revision_state) for r in qs))
    if kind == "bom":
        qs = BOMItem.objects.select_related("bom_revision__bom", "bom_revision__root_part_revision__part", "child_part_revision__part", "unit").all()
        return (["bom_code", "revision", "root_part_code", "line_no", "child_part_code", "quantity", "unit_code", "position"],
                ((i.bom_revision.bom.bom_code, i.bom_revision.revision, i.bom_revision.root_part_revision.part.part_code, i.line_no, i.child_part_revision.part.part_code, i.quantity, i.unit.code if i.unit else "", i.position) for i in qs))
    raise ValueError(f"unsupported export kind: {kind}")


@shared_task(name="plm.process_export_job")
def run_export_job(job_id):
    job = ExportJob.objects.get(pk=job_id)
    try:
        from .export_service import render_export
        extension = "json" if job.format.lower() == "json" else "csv"
        body, count, content_type = render_export(job.kind, job.format, job.filters or {}, job.tenant_id)
        key = f"exports/{job.tenant_id}/{job.id}.{extension}"
        s3_client().put_object(Bucket=settings.MINIO_BUCKET_EXPORT, Key=key, Body=body, ContentType=content_type)

        job.status, job.object_key = "completed", key
        job.row_count = count
        job.artifact_sha256 = hashlib.sha256(body).hexdigest()
        job.artifact_expires_at = timezone.now() + timedelta(seconds=int(getattr(settings, 'EXPORT_ARTIFACT_TTL', 86400)))
        job.row_version += 1
        job.save(update_fields=["status", "object_key", "row_count", "artifact_sha256", "artifact_expires_at", "row_version", "updated_at"])
        return {"rows": count, "object_key": key}
    except Exception:
        job.status = "failed"
        job.row_version += 1
        job.save(update_fields=["status", "row_version", "updated_at"])
        raise


def cancel_export_job(job_id):
    job = ExportJob.objects.get(pk=job_id)
    if job.status in ("completed", "failed", "cancelled"):
        return {"status": job.status}
    job.status = "cancelled"
    job.save(update_fields=["status"])
    return {"status": "cancelled"}


def export_download_url(job, expires=3600):
    if not job.object_key or job.status != "completed" or (job.artifact_expires_at and job.artifact_expires_at <= timezone.now()):
        return ""
    return s3_client().generate_presigned_url("get_object", Params={"Bucket": settings.MINIO_BUCKET_EXPORT, "Key": job.object_key}, ExpiresIn=min(expires, int(getattr(settings, 'EXPORT_DOWNLOAD_URL_TTL', 600))))

@shared_task(name='plm.finalize_upload_job')
def finalize_upload_job(job_id):
    """Run the same reconciliation/finalize path outside the request timeout."""
    from .views import _complete_upload_session
    job = FinalizeJob.objects.select_related('upload_session').get(pk=job_id)
    if job.status == 'completed':
        return {'status': job.status, 'upload_session': str(job.upload_session_id)}
    try:
        job.status = 'running'; job.save(update_fields=['status','updated_at'])
        _complete_upload_session(job.upload_session, job.parts)
        # Keep the same optimistic-concurrency generation semantics as the
        # synchronous finalize path.
        session = job.upload_session
        session.refresh_from_db()
        session.generation += 1
        session.save(update_fields=['generation'])
        job.status = 'completed'; job.save(update_fields=['status','updated_at'])
        return {'status': job.status, 'upload_session': str(job.upload_session_id)}
    except Exception as exc:
        job.status = 'failed'; job.error = str(exc); job.save(update_fields=['status','error','updated_at'])
        raise
