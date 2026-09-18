from django.db import migrations, models
import hashlib, json


def install_append_only_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute("""
    CREATE OR REPLACE FUNCTION plm_audit_event_immutable() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      RAISE EXCEPTION 'AuditEvent is append-only';
    END; $$;
    DROP TRIGGER IF EXISTS plm_audit_event_no_update ON plm_auditevent;
    CREATE TRIGGER plm_audit_event_no_update
      BEFORE UPDATE OR DELETE ON plm_auditevent
      FOR EACH ROW EXECUTE FUNCTION plm_audit_event_immutable();
    """)


def remove_append_only_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute("DROP TRIGGER IF EXISTS plm_audit_event_no_update ON plm_auditevent")
    schema_editor.execute("DROP FUNCTION IF EXISTS plm_audit_event_immutable()")


def backfill_hashes(apps, schema_editor):
    AuditEvent = apps.get_model('plm', 'AuditEvent')
    previous = ''
    for row in AuditEvent.objects.order_by('created_at', 'id').iterator():
        payload = {
            'id': str(row.id), 'actor': row.actor, 'action': row.action,
            'resource_type': row.resource_type, 'resource_id': row.resource_id,
            'success': bool(row.success), 'details': row.details or {},
            'request_id': row.request_id or '', 'job_id': row.job_id or '',
            'prev_hash': previous,
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()
        AuditEvent.objects.filter(pk=row.pk).update(prev_hash=previous, entry_hash=digest)
        previous = digest


def ensure_legacy_tenant_columns(apps, schema_editor):
    """Repair databases where 0012 was marked applied from an old artifact."""
    if schema_editor.connection.vendor != 'postgresql':
        return
    for table in ('plm_revisionreview', 'plm_attachmentversion',
                  'plm_releaseactivation', 'plm_attachmentstorageplacement',
                  'plm_releasepromotion'):
        schema_editor.execute(
            f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS tenant_id varchar(64) NOT NULL DEFAULT \'default\''
        )


class Migration(migrations.Migration):
    dependencies = [('plm', '0013_rename_storage_version_id')]
    operations = [
        migrations.RunPython(ensure_legacy_tenant_columns, migrations.RunPython.noop),
        migrations.AddField(model_name='auditevent', name='request_id', field=models.CharField(blank=True, db_index=True, max_length=128)),
        migrations.AddField(model_name='auditevent', name='job_id', field=models.CharField(blank=True, db_index=True, max_length=128)),
        migrations.AddField(model_name='auditevent', name='prev_hash', field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name='auditevent', name='entry_hash', field=models.CharField(blank=True, null=True, max_length=64)),
        migrations.RunPython(backfill_hashes, migrations.RunPython.noop),
        migrations.AlterField(model_name='auditevent', name='entry_hash', field=models.CharField(blank=True, null=True, max_length=64, unique=True)),
        migrations.RunPython(install_append_only_trigger, remove_append_only_trigger),
    ]
