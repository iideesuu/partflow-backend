from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):
    dependencies=[('plm','0002_category_aliases_category_catalog_version_and_more')]
    operations=[
        migrations.AddField(model_name='partrevision',name='parameters',field=models.JSONField(blank=True,default=dict)),
        migrations.CreateModel(name='AuditEvent',fields=[('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),('actor',models.CharField(blank=True,max_length=150)),('action',models.CharField(max_length=80)),('resource_type',models.CharField(blank=True,max_length=80)),('resource_id',models.CharField(blank=True,max_length=80)),('success',models.BooleanField(default=True)),('details',models.JSONField(blank=True,default=dict)),('created_at',models.DateTimeField(auto_now_add=True))],options={'ordering':['-created_at']}),
        migrations.CreateModel(name='PartAttachment',fields=[('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),('attachment_type',models.CharField(default='drawing',max_length=32)),('filename',models.CharField(max_length=255)),('description',models.CharField(blank=True,max_length=500)),('created_at',models.DateTimeField(auto_now_add=True)),('revision',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='attachments',to='plm.partrevision')),('upload_session',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='part_attachments',to='plm.uploadsession'))]),
    ]
