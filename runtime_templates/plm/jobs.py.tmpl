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
from django.db import transaction
from django.utils import timezone

from .models import (
    BOM, BOMItem, BOMRevision, Category, ImportJob, Part, PartRevision,
    Unit, UploadSession, ExportJob, FinalizeJob, PartAttachment, AttachmentScan,
)

MAX_BYTES = 5 * 1024 * 1024
MAX_ERRORS = 1000
CLAMAV_MAX_BYTES = int(os.getenv('CLAMAV_MAX_BYTES', str(4 * 1024 * 1024 * 1024)))

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
    bytes would be meaningless.  Such attachments stay blocked until an
    approved endpoint scans the decrypted file and uploads it in
    ``client_decrypted`` mode.
    """
    attachment = PartAttachment.objects.select_related('upload_session').get(pk=attachment_id)
    session = attachment.upload_session
    scan = AttachmentScan.objects.create(attachment=attachment, status='running', generation=uuid.uuid4().hex, started_at=timezone.now())
    attachment.security_state = 'scanning'; attachment.scan_generation = scan.generation; attachment.save(update_fields=['security_state','scan_generation'])
    if attachment.encryption_mode in ('transparent', 'unknown'):
        scan.status = 'opaque'; scan.result = 'OPAQUE_ENCRYPTED_CONTENT'; scan.error = 'encrypted or unknown content cannot be trusted as clean; upload authorized plaintext for container scanning or integrate a trusted decryption/scan service'; scan.finished_at = timezone.now()
        scan.save(update_fields=['status','result','error','finished_at'])
        attachment.security_state = 'unscannable'; attachment.scan_error = scan.error; attachment.scanned_at = timezone.now()
        attachment.save(update_fields=['security_state','scan_error','scanned_at'])
        return {'status': 'opaque', 'code': 'ENCRYPTED_CONTENT_UNSCANNABLE', 'attachment': str(attachment.id)}
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
        clean = normalized_verdict.endswith(': OK') or normalized_verdict == 'OK'
        scan.status = 'clean' if clean else 'infected'; scan.engine_version = os.getenv('CLAMAV_ENGINE_VERSION','unknown'); scan.signature_version = os.getenv('CLAMAV_DB_VERSION','unknown'); scan.finished_at=timezone.now(); scan.save(update_fields=['sha256','result','status','engine_version','signature_version','finished_at'])
        attachment.security_state = 'available' if clean else 'quarantined'; attachment.scanner_engine_version=scan.engine_version; attachment.scanner_signature_version=scan.signature_version; attachment.scanned_at=timezone.now(); attachment.save(update_fields=['security_state','scanner_engine_version','scanner_signature_version','scanned_at'])
        return {'status': scan.status, 'attachment': str(attachment.id)}
    except Exception as exc:
        scan.status='error'; scan.error=str(exc); scan.finished_at=timezone.now(); scan.save(update_fields=['status','error','finished_at'])
        attachment.security_state='error'; attachment.scan_error=str(exc); attachment.scanned_at=timezone.now(); attachment.save(update_fields=['security_state','scan_error','scanned_at'])
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
    return {"major_code": major, "minor_code": minor,
            "name": _text(row, "name"),
            "major_name": _text(row, "major_name", "parent_name", default=_text(row, "name")),
            "parent_code": _text(row, "parent_code"),
            "parent_name": _text(row, "parent_name"),
            "path": _text(row, "path", "full_path"),
            "description": _text(row, "description"),
            "aliases": _text(row, "aliases"),
            "standard_references": _text(row, "standard_references"),
            "attribute_group": _text(row, "attribute_group", "attribute_groups"),
            "part_nature": _text(row, "part_nature"),
            "catalog_version": _text(row, "catalog_version"),
            "is_selectable": selectable in ("true", "1", "yes"),
            "sort_order": sort_order,
            "is_leaf": minor != "00"}


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
            "rohs_standard": _text(row, "rohs_standard")}


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
            "position": _text(row, "position", default="__NO_POSITION__")}


def _error_report(job, errors):
    if not errors:
        return ""
    key = f"imports/{job.id}/errors.json"
    payload = json.dumps({"job_id": str(job.id), "errors": errors}, ensure_ascii=False).encode()
    s3_client().put_object(Bucket=settings.MINIO_BUCKET_EXPORT, Key=key, Body=payload,
                           ContentType="application/json")
    return key


def _set_import_result(job, status, total, valid, errors, **extra):
    summary = {"total": total, "valid": valid, "error_count": len(errors),
               "errors": errors[:MAX_ERRORS], **extra}
    job.status = status
    job.summary = summary
    try:
        job.error_report_key = _error_report(job, errors)
    except Exception as report_exc:
        # Reporting storage outages must not hide the validation/commit result.
        summary["error_report_error"] = str(report_exc)
        job.error_report_key = ""
    job.save(update_fields=["status", "summary", "error_report_key"])


def _commit_categories(rows):
    codes = {(r["major_code"], r["minor_code"]) for r in rows}
    if len(codes) != len(rows):
        raise ValueError("duplicate category codes in import")
    for row in rows:
        if row["minor_code"] != "00" and not Category.objects.filter(major_code=row["major_code"], minor_code="00").exists() and (row["major_code"], "00") not in codes:
            raise ValueError(f"parent category not found: {row['major_code']}")
    for row in rows:
        Category.objects.update_or_create(major_code=row["major_code"], minor_code=row["minor_code"], defaults=row)


def _commit_parts(rows):
    for row in rows:
        major, minor = row["category_code"][:2], row["category_code"][2:]
        category = Category.objects.get(major_code=major, minor_code=minor)
        unit = Unit.objects.filter(code=row["unit_code"]).first() if row["unit_code"] else None
        part, _ = Part.objects.update_or_create(part_code=row["part_code"], defaults={"category": category})
        rev, _ = PartRevision.objects.update_or_create(part=part, revision=row["revision"], defaults={
            "name": row["name"], "kind": row["kind"], "business_lifecycle": row["business_lifecycle"],
            "unit": unit, "standard_code": row["standard_code"], "material": row["material"],
            "manufacturer": row["manufacturer"], "manufacturer_part_number": row["manufacturer_part_number"],
            "is_customized": row["is_customized"], "rohs_standard": row["rohs_standard"],
            "description": row["description"]})


def _commit_boms(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault((row["bom_code"], row["revision"]), []).append(row)
    for (bom_code, revision), items in grouped.items():
        first = items[0]
        bom, _ = BOM.objects.update_or_create(bom_code=bom_code, defaults={"bom_type": first["bom_type"], "name": first["name"]})
        root = PartRevision.objects.filter(part__part_code=first["root"], revision=first["root_revision"]).first()
        if not root:
            raise ValueError(f"root part not found: {first['root']}")
        brevision, _ = BOMRevision.objects.update_or_create(bom=bom, revision=revision, defaults={"root_part_revision": root})
        for row in items:
            child = PartRevision.objects.filter(part__part_code=row["child"], revision=row["child_revision"]).first()
            if not child:
                raise ValueError(f"child part not found: {row['child']}")
            unit = Unit.objects.filter(code=row["unit_code"]).first() if row["unit_code"] else None
            BOMItem.objects.update_or_create(bom_revision=brevision, line_no=row["line_no"], defaults={"child_part_revision": child, "quantity": row["quantity"], "unit": unit, "position": row["position"]})


def process_import_job(job_id, commit=False):
    with transaction.atomic():
        job = ImportJob.objects.select_for_update().select_related("upload_session").get(pk=job_id)
        if commit and (job.status != "dry_run" or (job.summary or {}).get("error_count", 1) != 0):
            raise ValueError("commit requires a successful dry_run import with zero errors")
        if not commit and job.status not in ("queued", "dry_run"):
            return job.summary or {"status": job.status}
    try:
        stream = _read_session(job.upload_session)
        rows = _rows(job.upload_session, stream)
        parsed, errors = [], []
        validator = {"category": _validate_category, "part": _validate_part, "bom": _validate_bom}.get(job.kind)
        if not validator:
            raise ValueError(f"unsupported import kind: {job.kind}")
        total = 0
        for index, row in enumerate(rows):
            total += 1
            try:
                normalized = validator(row, index)
                # Preview must expose downstream PLM matching errors before a
                # user can commit an external BOM.  Commit repeats the check
                # inside one transaction for race safety.
                if job.kind == 'bom':
                    root_qs = PartRevision.objects.filter(part__part_code=normalized['root'], revision=normalized['root_revision'])
                    child_qs = PartRevision.objects.filter(part__part_code=normalized['child'], revision=normalized['child_revision'])
                    if not root_qs.exists():
                        raise ValueError(f"root part/revision not found in PLM: {normalized['root']} / {normalized['root_revision']}")
                    if not child_qs.exists():
                        raise ValueError(f"child part/revision not found in PLM: {normalized['child']} / {normalized['child_revision']}")
                    child_revision = child_qs.first()
                    if child_revision.revision_state != 'released':
                        raise ValueError(f"referenced child revision is not released: {normalized['child']} / {normalized['child_revision']}")
                parsed.append(normalized)
            except Exception as exc:
                errors.append({"row": index + 2, "message": str(exc), "data": row})
        if errors or not commit:
            _set_import_result(job, "dry_run" if not commit else "failed", total, len(parsed), errors)
            return job.summary
        with transaction.atomic():
            if job.kind == "category": _commit_categories(parsed)
            elif job.kind == "part": _commit_parts(parsed)
            else: _commit_boms(parsed)
        _set_import_result(job, "completed", total, len(parsed), [], created=len(parsed))
        return job.summary
    except Exception as exc:
        _set_import_result(job, "failed", 0, 0, [{"row": 0, "message": str(exc)}])
        raise


@shared_task(name="plm.process_import_job")
def run_import_job(job_id, commit=False):
    return process_import_job(job_id, commit=commit)


def cancel_import_job(job_id):
    """Cancel a queued/dry-run import without touching domain tables."""
    with transaction.atomic():
        job = ImportJob.objects.select_for_update().get(pk=job_id)
        if job.status in ("completed", "failed", "cancelled"):
            return {"status": job.status}
        job.status = "cancelled"
        job.summary = {**(job.summary or {}), "cancelled_at": timezone.now().isoformat()}
        job.save(update_fields=["status", "summary"])
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
        header, rows = _export_rows(job.kind, job.filters or {})
        out = io.StringIO(newline="")
        writer = csv.writer(out)
        writer.writerow(header)
        count = 0
        for row in rows:
            writer.writerow([_safe_cell(value) for value in row])
            count += 1
        extension = "json" if job.format.lower() == "json" else "csv"
        if extension == "json":
            # Rebuild from the CSV-compatible rows to keep export columns stable.
            out = io.StringIO(newline="")
            payload = [dict(zip(header, [_safe_cell(value) for value in row])) for row in _export_rows(job.kind, job.filters or {})[1]]
            out.write(json.dumps(payload, ensure_ascii=False, default=str))
        key = f"exports/{job.id}.{extension}"
        body = out.getvalue().encode("utf-8")
        s3_client().put_object(Bucket=settings.MINIO_BUCKET_EXPORT, Key=key, Body=body,
                               ContentType="application/json" if extension == "json" else "text/csv; charset=utf-8")
        job.status, job.object_key = "completed", key
        job.save(update_fields=["status", "object_key"])
        return {"rows": count, "object_key": key}
    except Exception:
        job.status = "failed"
        job.save(update_fields=["status"])
        raise


def cancel_export_job(job_id):
    job = ExportJob.objects.get(pk=job_id)
    if job.status in ("completed", "failed", "cancelled"):
        return {"status": job.status}
    job.status = "cancelled"
    job.save(update_fields=["status"])
    return {"status": "cancelled"}


def export_download_url(job, expires=3600):
    if not job.object_key or job.status != "completed":
        return ""
    return s3_client().generate_presigned_url("get_object", Params={"Bucket": settings.MINIO_BUCKET_EXPORT, "Key": job.object_key}, ExpiresIn=expires)

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
        job.status = 'completed'; job.save(update_fields=['status','updated_at'])
        return {'status': job.status, 'upload_session': str(job.upload_session_id)}
    except Exception as exc:
        job.status = 'failed'; job.error = str(exc); job.save(update_fields=['status','error','updated_at'])
        raise
