from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('plm', '0014_audit_chain')]
    operations = [
        migrations.AddField(
            model_name='uploadsession', name='s3_version_id',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='uploadsession', name='tenant_id',
            field=models.CharField(default='default', max_length=64),
        ),
        migrations.AddField(
            model_name='uploadsession', name='owner',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='owned_upload_sessions', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='uploadsession', name='purpose',
            field=models.CharField(default='attachment', max_length=32),
        ),
        migrations.AddField(
            model_name='uploadsession', name='generation',
            field=models.PositiveIntegerField(default=1),
        ),
    ]
