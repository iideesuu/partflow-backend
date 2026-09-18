from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('plm', '0022_reconcile_effectivity')]

    operations = [
        migrations.AddField(
            model_name='exportjob',
            name='idempotency_key',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
