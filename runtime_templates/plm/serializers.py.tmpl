from rest_framework import serializers
from .models import *
class CategorySerializer(serializers.ModelSerializer):
    code = serializers.ReadOnlyField()
    class Meta:
        model = Category
        fields = ['id','major_code','minor_code','code','name','major_name','path','attribute_group','parent_code','parent_name','description','aliases','standard_references','is_selectable','part_nature','sort_order','catalog_version','is_enabled','is_leaf']
        read_only_fields = ['id','code']
    def validate(self, attrs):
        for f in ('major_code','minor_code'):
            if f in attrs and (len(attrs[f]) != 2 or not attrs[f].isdigit()): raise serializers.ValidationError({f:'must be two digits'})
        return attrs
class UnitSerializer(serializers.ModelSerializer):
    class Meta: model = Unit; fields = '__all__'
class PartRevisionSerializer(serializers.ModelSerializer):
    unit_code = serializers.CharField(source='unit.code', read_only=True)
    class Meta:
        model = PartRevision
        fields = ['id','revision','revision_seq','name','kind','business_lifecycle','unit','unit_code','standard_code','material','manufacturer','manufacturer_part_number','is_customized','rohs_standard','description','revision_state','row_version','created_at']
        read_only_fields = ['id','created_at']
class PartSerializer(serializers.ModelSerializer):
    initial_revision = PartRevisionSerializer(write_only=True, required=True)
    revisions = PartRevisionSerializer(many=True, read_only=True)
    category_code = serializers.CharField(source='category.code', read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(source='category', queryset=Category.objects.all(), write_only=True, required=True)
    class Meta:
        model = Part
        fields = ['id','part_code','part_number','category_id','category_code','status','tenant_id','row_version','created_at','updated_at','revisions','initial_revision']
        read_only_fields = ['id','part_number','created_at','updated_at','revisions']
    def validate_part_code(self, value):
        import re
        if not re.fullmatch(r'\d{4}-\d{5}', value) or value.endswith('-00000'): raise serializers.ValidationError('invalid part number')
        return value
    def create(self, validated_data):
        rev = validated_data.pop('initial_revision')
        from django.db import transaction
        with transaction.atomic():
            part = Part.objects.create(**validated_data)
            PartRevision.objects.create(part=part, **rev)
            return part
class BOMItemSerializer(serializers.ModelSerializer):
    class Meta: model = BOMItem; fields = '__all__'; read_only_fields = ['id']
class BOMRevisionSerializer(serializers.ModelSerializer):
    items = BOMItemSerializer(many=True, read_only=True)
    class Meta: model = BOMRevision; fields = ['id','bom','revision','root_part_revision','revision_state','items']
class BOMSerializer(serializers.ModelSerializer):
    revisions = BOMRevisionSerializer(many=True, read_only=True)
    class Meta: model = BOM; fields = ['id','bom_code','bom_type','name','created_at','revisions']; read_only_fields = ['id','created_at','revisions']
class UploadSessionSerializer(serializers.ModelSerializer):
    class Meta: model = UploadSession; fields = '__all__'; read_only_fields = ['id','object_key','bucket','state','upload_id','created_at']
class ImportJobSerializer(serializers.ModelSerializer):
    class Meta: model = ImportJob; fields = '__all__'; read_only_fields = ['id','status','summary','error_report_key','created_at']
class ExportJobSerializer(serializers.ModelSerializer):
    class Meta: model = ExportJob; fields = '__all__'; read_only_fields = ['id','status','object_key','created_at']
