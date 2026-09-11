"""HTTP validators for API responses."""
import hashlib
import uuid

class ETagMiddleware:
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        response = self.get_response(request)
        response["X-Request-Id"] = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        if request.method in ("GET", "HEAD") and 200 <= response.status_code < 300:
            tag = '"' + hashlib.sha256(getattr(response, "content", b"")).hexdigest()[:32] + '"'
            response["ETag"] = tag
            if request.headers.get("If-None-Match") == tag:
                response.status_code = 304; response.content = b""; response["Content-Length"] = "0"
        return response
