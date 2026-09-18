from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('plm', '0016_upload_session_ownership')]
    operations = [
        migrations.AlterField(
            model_name='attachmentversion', name='security_state',
            field=models.CharField(default='scanning', max_length=16,
                                   choices=[('scanning','Scanning'), ('available','Available'),
                                            ('quarantined','Quarantined'), ('rescanning','Rescanning'),
                                            ('rejected','Rejected'), ('unscannable','Unscannable')]),
        ),
    ]
