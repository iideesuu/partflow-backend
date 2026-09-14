from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    dependencies = [('plm', '0009_attachment_scan')]
    operations = [migrations.CreateModel(name='ReleasePublication', fields=[
        ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
        ('operation_key', models.CharField(max_length=180, unique=True)),
        ('status', models.CharField(choices=[('pending','Pending'),('published','Published'),('failed','Failed')], default='pending', max_length=20)),
        ('canonical_release_key', models.CharField(blank=True, max_length=512)),
        ('version_id', models.CharField(blank=True, max_length=255)),
        ('content_sha256', models.CharField(blank=True, max_length=64)),
        ('error', models.TextField(blank=True)),
        ('published_at', models.DateTimeField(blank=True, null=True)),
        ('created_at', models.DateTimeField(auto_now_add=True)),
        ('revision', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='release_publication', to='plm.partrevision')),
    ])]
