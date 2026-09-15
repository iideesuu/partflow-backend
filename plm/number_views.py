"""External part number evidence registration."""
import re
from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import NumberRequest, NumberSource
from .roles import require_role
from .serializers import NumberRequestSerializer
PART_CODE_RE = re.compile(r"^\d{4}-\d{5}$")

@api_view(["GET", "POST"])
@require_role("engineer", "admin")
def external_number_register(request):
    if request.method == "GET":
        rows = NumberRequest.objects.select_related("source").order_by("-id")[:100]
        return Response({"rule":"NNNN-NNNNN", "requests":NumberRequestSerializer(rows, many=True).data})
    payload = request.data or {}; source_id = payload.get("source_id") or payload.get("source")
    source_request_id = str(payload.get("source_request_id") or "").strip(); operation_key = str(payload.get("operation_key") or "").strip()
    part_code = str(payload.get("part_code") or payload.get("returned_part_code") or "").strip(); errors = {}
    if not source_id: errors["source_id"] = "required"
    if not source_request_id: errors["source_request_id"] = "required"
    if not operation_key: errors["operation_key"] = "required"
    if not PART_CODE_RE.fullmatch(part_code) or part_code.endswith("-00000"): errors["part_code"] = "must match NNNN-NNNNN"
    if errors: return Response({"code":"VALIDATION_ERROR", "errors":errors}, status=400)
    try: source = NumberSource.objects.get(pk=source_id, is_enabled=True)
    except (NumberSource.DoesNotExist, ValueError): return Response({"code":"NUMBER_SOURCE_NOT_FOUND", "detail":"enabled number source not found"}, status=422)
    with transaction.atomic():
        existing = NumberRequest.objects.select_for_update().filter(operation_key=operation_key).first()
        if existing:
            if (existing.source_id, existing.source_request_id, existing.returned_part_code) != (source.pk, source_request_id, part_code):
                return Response({"code":"IDEMPOTENCY_CONFLICT", "detail":"operation_key is already bound to different evidence"}, status=409)
            return Response(NumberRequestSerializer(existing).data)
        row = NumberRequest.objects.create(source=source, source_request_id=source_request_id, operation_key=operation_key, returned_part_code=part_code, status="reserved")
    return Response(NumberRequestSerializer(row).data, status=201)
