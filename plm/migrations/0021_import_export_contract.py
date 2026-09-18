from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('plm', '0020_bom_effectivity_and_alternatives')]
    operations = [
        migrations.AddField(model_name='importjob', name='business_state', field=models.CharField(default='none', max_length=16)),
        migrations.AddField(model_name='importjob', name='tenant_id', field=models.CharField(db_index=True, default='default', max_length=64)),
        migrations.AddField(model_name='importjob', name='actor', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='import_jobs', to='auth.user')),
        migrations.AddField(model_name='importjob', name='input_hash', field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name='importjob', name='preview_hash', field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name='importjob', name='catalog_version', field=models.CharField(blank=True, max_length=32)),
        migrations.AddField(model_name='importjob', name='permission_version', field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='importjob', name='confirm_token_hash', field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name='importjob', name='confirm_expires_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='importjob', name='idempotency_key', field=models.CharField(blank=True, max_length=200)),
        migrations.AddField(model_name='importjob', name='parent_job', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='retries', to='plm.importjob')),
        migrations.AddField(model_name='importjob', name='row_version', field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='importjob', name='updated_at', field=models.DateTimeField(auto_now=True)),
        migrations.AlterField(model_name='importjob', name='status', field=models.CharField(default='queued', max_length=32)),
        migrations.AddField(model_name='exportjob', name='tenant_id', field=models.CharField(db_index=True, default='default', max_length=64)),
        migrations.AddField(model_name='exportjob', name='actor', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='export_jobs', to='auth.user')),
        migrations.AddField(model_name='exportjob', name='template_version', field=models.CharField(default='v1.6', max_length=32)),
        migrations.AddField(model_name='exportjob', name='snapshot_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='exportjob', name='row_count', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='exportjob', name='artifact_sha256', field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name='exportjob', name='artifact_expires_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='exportjob', name='download_count', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='exportjob', name='row_version', field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name='exportjob', name='updated_at', field=models.DateTimeField(auto_now=True)),
    ]
