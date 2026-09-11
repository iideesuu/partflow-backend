from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies = [('plm', '0004_revision_lifecycle_actors')]
    operations = [
        migrations.AlterField(model_name='partrevision', name='revision_state', field=models.CharField(choices=[('draft','Draft'),('pending_review','Pending review'),('rejected','Rejected'),('approved','Approved'),('release_pending','Release pending'),('released','Released'),('release_failed','Release failed'),('obsolete','Obsolete')], default='draft', max_length=20)),
        migrations.AlterField(model_name='bomrevision', name='revision_state', field=models.CharField(choices=[('draft','Draft'),('pending_review','Pending review'),('rejected','Rejected'),('approved','Approved'),('release_pending','Release pending'),('released','Released'),('release_failed','Release failed'),('obsolete','Obsolete')], default='draft', max_length=20)),
    ]
