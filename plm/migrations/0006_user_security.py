from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    dependencies = [('plm', '0005_alter_revision_states')]
    operations = [migrations.CreateModel(name='UserSecurity', fields=[
        ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='security', serialize=False, to='auth.user')),
        ('permission_version', models.PositiveIntegerField(default=1)),
        ('session_nonce', models.UUIDField(default=uuid.uuid4, editable=False)),
        ('revoked_at', models.DateTimeField(blank=True, null=True)),
        ('failed_attempts', models.PositiveIntegerField(default=0)),
        ('locked_until', models.DateTimeField(blank=True, null=True)),
        ('updated_at', models.DateTimeField(auto_now=True)),
    ])]
