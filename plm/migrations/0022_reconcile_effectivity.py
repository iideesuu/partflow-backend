from django.db import migrations, models
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeOperators
from django.contrib.postgres.operations import BtreeGistExtension
from django.db.models.expressions import RawSQL


_RECONCILE_SQL = r'''
DO $$
DECLARE
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['plm_partrevision', 'plm_bomrevision'] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema() AND information_schema.columns.table_name = tbl
              AND column_name = 'effective_range'
        ) THEN
            EXECUTE format('ALTER TABLE %I ADD COLUMN effective_range tstzrange NULL', tbl);
        END IF;
    END LOOP;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='plm_partrevision' AND column_name='effective_from')
       OR EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='plm_partrevision' AND column_name='effective_to') THEN
        EXECUTE 'UPDATE plm_partrevision SET effective_range = tstzrange(effective_from, effective_to, ''[)'') WHERE effective_range IS NULL AND (effective_from IS NOT NULL OR effective_to IS NOT NULL)';
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='plm_partrevision' AND column_name='effective_from') THEN EXECUTE 'ALTER TABLE plm_partrevision DROP COLUMN effective_from'; END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='plm_partrevision' AND column_name='effective_to') THEN EXECUTE 'ALTER TABLE plm_partrevision DROP COLUMN effective_to'; END IF;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='plm_bomrevision' AND column_name='effective_from')
       OR EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='plm_bomrevision' AND column_name='effective_to') THEN
        EXECUTE 'UPDATE plm_bomrevision SET effective_range = tstzrange(effective_from, effective_to, ''[)'') WHERE effective_range IS NULL AND (effective_from IS NOT NULL OR effective_to IS NOT NULL)';
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='plm_bomrevision' AND column_name='effective_from') THEN EXECUTE 'ALTER TABLE plm_bomrevision DROP COLUMN effective_from'; END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='plm_bomrevision' AND column_name='effective_to') THEN EXECUTE 'ALTER TABLE plm_bomrevision DROP COLUMN effective_to'; END IF;
    END IF;
END $$;
'''


class Migration(migrations.Migration):
    dependencies = [('plm', '0021_import_export_contract')]

    operations = [
        BtreeGistExtension(),
        migrations.RunSQL(_RECONCILE_SQL, migrations.RunSQL.noop),
        migrations.AddConstraint(
            model_name='partrevision',
            constraint=models.CheckConstraint(
                condition=RawSQL("effective_range IS NULL OR (NOT isempty(effective_range) AND lower_inc(effective_range) AND NOT upper_inc(effective_range))", (), output_field=models.BooleanField()),
                name='partrevision_effective_range_half_open',
            ),
        ),
        migrations.AddConstraint(
            model_name='partrevision',
            constraint=ExclusionConstraint(
                name='partrevision_part_effective_range_excl',
                expressions=[('part', RangeOperators.EQUAL), ('effective_range', RangeOperators.OVERLAPS)],
            ),
        ),
        migrations.AddConstraint(
            model_name='bomrevision',
            constraint=models.CheckConstraint(
                condition=RawSQL("effective_range IS NULL OR (NOT isempty(effective_range) AND lower_inc(effective_range) AND NOT upper_inc(effective_range))", (), output_field=models.BooleanField()),
                name='bomrevision_effective_range_half_open',
            ),
        ),
        migrations.AddConstraint(
            model_name='bomrevision',
            constraint=ExclusionConstraint(
                name='bomrevision_bom_effective_range_excl',
                expressions=[('bom', RangeOperators.EQUAL), ('effective_range', RangeOperators.OVERLAPS)],
            ),
        ),
    ]
