from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plm', '0023_export_idempotency_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='attribute_schema',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
