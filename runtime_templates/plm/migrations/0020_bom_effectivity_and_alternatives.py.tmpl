from django.db import migrations, models
import django.db.models.deletion
import django.contrib.postgres.fields.ranges
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [('plm', '0019_bom_row_version')]

    operations = [
        migrations.AddField('unit', 'base_unit_code', models.CharField(blank=True, max_length=32)),
        migrations.AddField('unit', 'factor_to_base', models.DecimalField(decimal_places=12, default=1, max_digits=24)),
        migrations.AddField('unit', 'is_active', models.BooleanField(default=True)),
        migrations.AddField('unit', 'row_version', models.PositiveIntegerField(default=1)),
        migrations.AddField('partrevision', 'effective_range', django.contrib.postgres.fields.ranges.DateTimeRangeField(blank=True, null=True)),
        migrations.AddField('bom', 'tenant_id', models.CharField(default='default', max_length=64)),
        migrations.AddField('bomrevision', 'effective_range', django.contrib.postgres.fields.ranges.DateTimeRangeField(blank=True, null=True)),
        migrations.AddField('bomitem', 'alternative_group_id', models.UUIDField(blank=True, null=True)),
        migrations.AddField('bomitem', 'quantity_entered', models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True)),
        migrations.AddField('bomitem', 'unit_entered', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='entered_bom_items', to='plm.unit')),
        migrations.AddField('bomitem', 'conversion_factor', models.DecimalField(decimal_places=12, default=1, max_digits=24)),
        migrations.AddField('bomitem', 'child_bom_revision', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, related_name='parent_items', to='plm.bomrevision')),
        migrations.AlterField('bomitem', 'child_part_revision', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, related_name='bom_items', to='plm.partrevision')),
        migrations.AddField('bomitem', 'alternative_role', models.CharField(choices=[('primary', 'Primary'), ('alternate', 'Alternate')], default='primary', max_length=16)),
        migrations.AddField('bomitem', 'priority', models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField('bomitem', 'remarks', models.TextField(blank=True)),
        migrations.AlterField('bom', 'bom_code', models.CharField(max_length=64)),
        migrations.AddConstraint('bom', models.UniqueConstraint(fields=('tenant_id', 'bom_code'), name='uniq_bom_tenant_code')),
    ]
