from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    dependencies = [('plm', '0008_finalize_job')]
    operations = [
        migrations.AddField(model_name='partattachment', name='security_state', field=models.CharField(choices=[('pending','Pending scan'),('scanning','Scanning'),('available','Available'),('quarantined','Quarantined'),('error','Scan error')], default='pending', max_length=20)),
        migrations.AddField(model_name='partattachment', name='scan_generation', field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name='partattachment', name='scanner_engine_version', field=models.CharField(blank=True, max_length=128)),
        migrations.AddField(model_name='partattachment', name='scanner_signature_version', field=models.CharField(blank=True, max_length=128)),
        migrations.AddField(model_name='partattachment', name='scan_error', field=models.TextField(blank=True)),
        migrations.AddField(model_name='partattachment', name='scanned_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.CreateModel(name='AttachmentScan', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('status', models.CharField(default='queued', max_length=20)), ('generation', models.CharField(blank=True, max_length=64)), ('sha256', models.CharField(blank=True, max_length=64)), ('engine_version', models.CharField(blank=True, max_length=128)), ('signature_version', models.CharField(blank=True, max_length=128)), ('result', models.CharField(blank=True, max_length=255)), ('error', models.TextField(blank=True)), ('started_at', models.DateTimeField(blank=True, null=True)), ('finished_at', models.DateTimeField(blank=True, null=True)), ('created_at', models.DateTimeField(auto_now_add=True)),
            ('attachment', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='scans', to='plm.partattachment')),
        ]),
    ]
