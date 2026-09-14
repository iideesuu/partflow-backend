import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('plm', '0011_attachment_encryption')]
    operations = [
        migrations.AlterField(model_name='part', name='part_code', field=models.CharField(max_length=32)),
        migrations.AddConstraint(model_name='part', constraint=models.UniqueConstraint(fields=('tenant_id','part_code'), name='uniq_part_tenant_code')),
        migrations.CreateModel(
            name='AttachmentVersion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('tenant_id', models.CharField(default='default', max_length=64)),
                ('version_id', models.CharField(max_length=255)),
                ('sha256', models.CharField(max_length=64)),
                ('size_bytes', models.BigIntegerField()),
                ('detected_mime', models.CharField(blank=True, max_length=255)),
                ('security_state', models.CharField(choices=[('scanning','Scanning'),('available','Available'),('quarantined','Quarantined'),('rescanning','Rescanning'),('rejected','Rejected')], default='scanning', max_length=16)),
                ('rescan_required', models.BooleanField(default=False)),
                ('last_pass_policy_version', models.CharField(blank=True, max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('attachment', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='versions', to='plm.partattachment')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='ReleaseActivation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('tenant_id', models.CharField(default='default', max_length=64)),
                ('operation_key', models.CharField(max_length=180, unique=True)),
                ('status', models.CharField(choices=[('pending','Pending'),('promoting','Promoting'),('active','Active'),('failed','Failed'),('abandoned','Abandoned')], default='pending', max_length=16)),
                ('error', models.TextField(blank=True)),
                ('activated_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('revision', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='release_activation', to='plm.partrevision')),
            ],
        ),
        migrations.CreateModel(
            name='RevisionReview',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('tenant_id', models.CharField(default='default', max_length=64)),
                ('decision', models.CharField(choices=[('pending','Pending'),('approved','Approved'),('rejected','Rejected')], default='pending', max_length=16)),
                ('comment', models.TextField(blank=True)),
                ('content_sha256', models.CharField(max_length=64)),
                ('attachment_set_sha256', models.CharField(blank=True, max_length=64)),
                ('snapshot', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='revision_reviews', to='auth.user')),
                ('revision', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='reviews', to='plm.partrevision')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='AttachmentStoragePlacement',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('tenant_id', models.CharField(default='default', max_length=64)),
                ('storage_tier', models.CharField(choices=[('draft','Draft'),('release','Release')], default='draft', max_length=16)),
                ('bucket', models.CharField(max_length=128)),
                ('object_key', models.CharField(max_length=512)),
                ('storage_version_id', models.CharField(blank=True, max_length=255)),
                ('visible', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('activation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='placements', to='plm.releaseactivation')),
                ('version', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='placements', to='plm.attachmentversion')),
            ],
        ),
        migrations.CreateModel(
            name='ReleasePromotion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('tenant_id', models.CharField(default='default', max_length=64)),
                ('status', models.CharField(choices=[('pending','Pending'),('promoted','Promoted'),('failed','Failed')], default='pending', max_length=16)),
                ('error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('activation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='promotions', to='plm.releaseactivation')),
                ('version', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='promotions', to='plm.attachmentversion')),
            ],
        ),
        migrations.AddConstraint(model_name='attachmentversion', constraint=models.UniqueConstraint(fields=('attachment','version_id'), name='uniq_attachment_version_id')),
        migrations.AddConstraint(model_name='revisionreview', constraint=models.UniqueConstraint(condition=models.Q(decision='pending'), fields=('revision',), name='uniq_pending_revision_review')),
        migrations.AddConstraint(model_name='attachmentstorageplacement', constraint=models.UniqueConstraint(fields=('storage_tier','object_key'), name='uniq_storage_placement_key')),
        migrations.AddConstraint(model_name='releasepromotion', constraint=models.UniqueConstraint(fields=('activation','version'), name='uniq_release_promotion')),
    ]
