from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('plm', '0010_release_publication')]

    operations = [
        migrations.AddField(
            model_name='partattachment',
            name='encryption_mode',
            field=models.CharField(
                choices=[
                    ('unknown', 'Unknown encryption'),
                    ('none', 'No encryption'),
                    ('transparent', 'Transparent enterprise encryption'),
                    ('client_decrypted', 'Client decrypted before upload'),
                ],
                default='unknown',
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name='partattachment',
            name='security_state',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending scan'),
                    ('scanning', 'Scanning'),
                    ('available', 'Available'),
                    ('quarantined', 'Quarantined'),
                    ('unscannable', 'Encrypted/opaque - client scan required'),
                    ('error', 'Scan error'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
    ]
