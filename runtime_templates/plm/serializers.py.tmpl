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
    part_code = serializers.CharField(source='part.part_code', read_only=True)
    attachment_count = serializers.IntegerField(source='attachments.count', read_only=True)
    publication_status = serializers.SerializerMethodField()
    publication_id = serializers.SerializerMethodField()
    def get_publication_status(self, obj):
        publication = getattr(obj, 'release_publication', None)
        return publication.status if publication else None
    def get_publication_id(self, obj):
        publication = getattr(obj, 'release_publication', None)
        return str(publication.pk) if publication else None
    def validate_parameters(self, value):
        if not isinstance(value, dict): raise serializers.ValidationError('parameters must be a key/value object')
        return value
    class Meta:
        model = PartRevision
        fields = ['id','part_code','revision','revision_seq','name','kind','business_lifecycle','unit','unit_code','standard_code','material','manufacturer','manufacturer_part_number','is_customized','rohs_standard','parameters','description','revision_state','row_version','submitter','reviewer','publisher','attachment_count','publication_status','publication_id','created_at']
        read_only_fields = ['id','created_at','revision_seq','row_version','revision_state','submitter','reviewer','publisher']
        extra_kwargs = {'name': {'required': False}, 'revision': {'required': False}}
class PartSerializer(serializers.ModelSerializer):
    initial_revision = PartRevisionSerializer(write_only=True, required=False)
    revisions = PartRevisionSerializer(many=True, read_only=True)
    category_code = serializers.CharField(source='category.code', read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(source='category', queryset=Category.objects.all(), write_only=True, required=True)
    class Meta:
        model = Part
        fields = ['id','part_code','part_number','number_request','category_id','category_code','status','tenant_id','row_version','created_at','updated_at','revisions','initial_revision']
        read_only_fields = ['id','part_number','created_at','updated_at','revisions','status','row_version']
    def validate_part_code(self, value):
        import re
        if not re.fullmatch(r'\d{4}-\d{5}', value) or value.endswith('-00000'): raise serializers.ValidationError('invalid part number')
        return value
    def create(self, validated_data):
        rev = validated_data.pop('initial_revision', None)
        if not rev: raise serializers.ValidationError({'initial_revision':'required when creating a part'})
        if not str(rev.get('name') or '').strip(): raise serializers.ValidationError({'initial_revision':{'name':'name is required'}})
        from django.db import transaction
        with transaction.atomic():
            category = Category.objects.select_for_update().get(pk=validated_data['category'].pk)
            if not category.is_enabled or not category.is_leaf or not category.is_selectable or category.minor_code == '00':
                raise serializers.ValidationError({'category_id':'choose an enabled selectable minor category'})
            if validated_data['part_code'][:4] != category.code:
                raise serializers.ValidationError({'part_code':'number prefix must match selected category'})
            reservation = NumberRequest.objects.filter(returned_part_code=validated_data['part_code'],status='reserved').first()
            request = validated_data.get('number_request')
            if reservation and reservation != request:
                raise serializers.ValidationError({'number_request':'this number is reserved; supply its number request id'})
            if request and (request.status != 'reserved' or request.returned_part_code != validated_data['part_code']):
                raise serializers.ValidationError({'number_request':'number request does not match this part code'})
            part = Part.objects.create(**validated_data)
            PartRevision.objects.create(part=part, **rev)
            if request:
                request.status='used'; request.save(update_fields=['status'])
            return part
class BOMItemSerializer(serializers.ModelSerializer):
    child_part_code = serializers.CharField(source='child_part_revision.part.part_code', read_only=True)
    child_revision = serializers.CharField(source='child_part_revision.revision', read_only=True)
    child_name = serializers.CharField(source='child_part_revision.name', read_only=True)
    unit_code = serializers.CharField(source='unit.code', read_only=True)
    class Meta:
        model = BOMItem
        fields = ['id','bom_revision','line_no','child_part_revision','child_part_code','child_revision','child_name','quantity','unit','unit_code','position','parent_item','no_position_reason']
        read_only_fields = ['id','child_part_code','child_revision','child_name','unit_code']
    def validate(self, attrs):
        br = attrs.get('bom_revision') or getattr(self.instance, 'bom_revision', None)
        child = attrs.get('child_part_revision') or getattr(self.instance, 'child_part_revision', None)
        quantity = attrs.get('quantity', getattr(self.instance, 'quantity', None))
        position = attrs.get('position', getattr(self.instance, 'position', '__NO_POSITION__'))
        parent = attrs.get('parent_item', getattr(self.instance, 'parent_item', None))
        reason = attrs.get('no_position_reason', getattr(self.instance, 'no_position_reason', ''))
        if position == '__NO_POSITION__' and not str(reason or '').strip():
            raise serializers.ValidationError({'no_position_reason': 'reason is required when position is omitted'})
        from .bom_services import validate_bom_item
        validate_bom_item(bom_revision=br, child_part_revision=child, quantity=quantity,
                          unit=attrs.get('unit', getattr(self.instance, 'unit', None)),
                          parent_item=parent, position=position, instance=self.instance)
        return attrs
class BOMRevisionSerializer(serializers.ModelSerializer):
    items = BOMItemSerializer(many=True, read_only=True)
    root_part_code = serializers.CharField(source='root_part_revision.part.part_code', read_only=True)
    root_part_revision_code = serializers.CharField(source='root_part_revision.revision', read_only=True)
    class Meta: model = BOMRevision; fields = ['id','bom','revision','root_part_revision','root_part_code','root_part_revision_code','revision_state','row_version','submitter','reviewer','publisher','items']; read_only_fields=['revision_state','row_version','submitter','reviewer','publisher']
class BOMSerializer(serializers.ModelSerializer):
    revisions = BOMRevisionSerializer(many=True, read_only=True)
    class Meta: model = BOM; fields = ['id','bom_code','bom_type','name','created_at','revisions']; read_only_fields = ['id','created_at','revisions']
    def validate_bom_type(self, value):
        if str(value).upper() != 'EBOM':
            raise serializers.ValidationError('BOM_TYPE_NOT_SUPPORTED: only EBOM is supported')
        return 'EBOM'
class UploadSessionSerializer(serializers.ModelSerializer):
    class Meta: model = UploadSession; fields = '__all__'; read_only_fields = ['id','object_key','bucket','state','upload_id','created_at']
class ImportJobSerializer(serializers.ModelSerializer):
    class Meta: model = ImportJob; fields = '__all__'; read_only_fields = ['id','status','summary','error_report_key','created_at']
class ExportJobSerializer(serializers.ModelSerializer):
    class Meta: model = ExportJob; fields = '__all__'; read_only_fields = ['id','status','object_key','created_at']

class PartAttachmentSerializer(serializers.ModelSerializer):
    versions = serializers.SerializerMethodField()
    object_key = serializers.CharField(source='upload_session.object_key', read_only=True)
    bucket = serializers.CharField(source='upload_session.bucket', read_only=True)
    class Meta:
        model = PartAttachment
        fields = ['id','revision','upload_session','attachment_type','filename','description','encryption_mode','object_key','bucket','security_state','scan_generation','scanner_engine_version','scanner_signature_version','scan_error','scanned_at','created_at','versions']
        read_only_fields = ['id','object_key','bucket','created_at','filename','security_state','scan_generation','scanner_engine_version','scanner_signature_version','scan_error','scanned_at']

    def get_versions(self, obj):
        return [{'id': str(v.id), 'version_id': v.version_id, 'sha256': v.sha256,
                 'size_bytes': v.size_bytes, 'security_state': v.security_state,
                 'rescan_required': v.rescan_required,
                 'created_at': v.created_at} for v in obj.versions.all()]

    def validate(self, attrs):
        # Re-labelling the same ciphertext must not turn it into plaintext.
        # A replacement object is needed when leaving the opaque path.
        if (self.instance and self.instance.encryption_mode in ('transparent', 'unknown')
                and attrs.get('encryption_mode') in ('none', 'client_decrypted')
                and attrs.get('upload_session', self.instance.upload_session) == self.instance.upload_session):
            raise serializers.ValidationError({'encryption_mode': 'upload a new authorized plaintext file; the same object cannot be relabelled as decrypted'})
        return attrs

class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = '__all__'
        read_only_fields = ['id','actor','created_at']

class NumberRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = NumberRequest
        fields = '__all__'
        read_only_fields = ['id','source','source_request_id','returned_part_code','status']
