from django.conf import settings
from django.contrib.auth import logout
from django.http import JsonResponse
from django.utils import timezone

from .models import UserSecurity


class SessionSecurityMiddleware:
    """Validate server-side session lifetime and user permission generation."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            security, _ = UserSecurity.objects.get_or_create(user=request.user)
            now = timezone.now().timestamp()
            started = request.session.get('authenticated_at', now)
            last_seen = request.session.get('last_seen_at', now)
            invalid = (
                request.session.get('session_nonce', str(security.session_nonce)) != str(security.session_nonce)
                or request.session.get('permission_version', security.permission_version) != security.permission_version
                or security.revoked_at is not None
                or not request.user.is_active
                or now - started >= settings.SESSION_COOKIE_AGE
                or now - last_seen >= settings.SESSION_IDLE_TIMEOUT
            )
            if invalid:
                logout(request)
                # A stale/revoked browser session must not prevent the
                # anonymous login bootstrap.  Clear it, then allow the CSRF
                # seed and login endpoint to run; every business endpoint
                # remains fail-closed with AUTH_INVALID.
                if request.path.endswith('/auth/csrf/') or request.path.endswith('/auth/login/'):
                    return self.get_response(request)
                return JsonResponse({'code': 'AUTH_INVALID', 'detail': 'session expired or revoked'}, status=401)
            request.session['authenticated_at'] = started
            request.session['last_seen_at'] = now
            request.session['permission_version'] = security.permission_version
            request.session['session_nonce'] = str(security.session_nonce)
        elif request.session.get('_auth_user_id'):
            logout(request)
            if request.path.endswith('/auth/csrf/') or request.path.endswith('/auth/login/'):
                return self.get_response(request)
            return JsonResponse({'code': 'AUTH_INVALID', 'detail': 'session expired or revoked'}, status=401)
        return self.get_response(request)
