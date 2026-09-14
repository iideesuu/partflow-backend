import json, os, hashlib
from django.core.cache import cache
from django.contrib.auth import authenticate as django_authenticate, login, logout, get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from datetime import timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from .auth import authenticate as ldap_authenticate, shadow_user, ldap_enabled
from .roles import user_role, assign_role, ROLES, ROLE_PERMISSIONS
from .models import UserSecurity
from .models import AuditEvent
from django.utils import timezone
from django.db import transaction

def _rate_key(username, request):
    remote = request.META.get('REMOTE_ADDR', 'unknown')
    raw = ((username or '').strip().lower() + '|' + remote).encode()
    return 'plm:auth:fail:' + hashlib.sha256(raw).hexdigest()

def _rate_status(username, request):
    key = _rate_key(username, request)
    return key, int(cache.get(key, 0) or 0)

def _auth_failure(username, request):
    key, count = _rate_status(username, request)
    count += 1
    cache.set(key, count, 15 * 60)
    return count

def _payload(user, request=None):
    role=user_role(user)
    security, _ = UserSecurity.objects.get_or_create(user=user)
    permission_version = security.permission_version
    return {'username':user.username,'display_name':user.first_name,'role':role,'permission_version':permission_version}

@ensure_csrf_cookie
@require_http_methods(['GET'])
def csrf(request): return JsonResponse({'detail':'ok'})

@ensure_csrf_cookie
@require_http_methods(['GET','POST'])
def login_view(request):
    if request.method == 'GET':
        return JsonResponse({'detail':'login endpoint','method':'POST','fields':['username','password'],'csrf':'GET /api/v1/auth/csrf/ first'})
    try: data=json.loads(request.body or '{}')
    except ValueError: return JsonResponse({'code':'INVALID_JSON','detail':'invalid JSON'},status=400)
    username = str(data.get('username') or '').strip()
    key, failures = _rate_status(username, request)
    if failures >= 5:
        return JsonResponse({'code':'RATE_LIMITED','detail':'too many authentication failures','retry_after':900}, status=429, headers={'Retry-After':'900'})
    # Shadow users have unusable passwords. Existing password-bearing Django
    # accounts (including admin) keep their local identity when LDAP is on.
    # Resolve casing once so neither failed nor disabled local accounts can
    # fall through to a same-named directory identity.
    candidates = list(get_user_model().objects.filter(username__iexact=username)[:2])
    if len(candidates) > 1:
        return JsonResponse({'code':'AUTH_INVALID','detail':'invalid credentials'}, status=401)
    local_user = candidates[0] if candidates else None
    use_local = bool(local_user and (local_user.has_usable_password() or local_user.is_superuser))
    local_security = UserSecurity.objects.filter(user=local_user).first() if local_user else None
    if local_security and local_security.locked_until and local_security.locked_until > timezone.now():
        retry = max(1, int((local_security.locked_until - timezone.now()).total_seconds()))
        return JsonResponse({'code':'RATE_LIMITED','detail':'account temporarily locked','retry_after':retry}, status=429, headers={'Retry-After':str(retry)})
    if not use_local and ldap_enabled():
        try: user=shadow_user(ldap_authenticate(username,data.get('password','')))
        except Exception:
            failures = _auth_failure(username, request)
            if local_security:
                local_security.failed_attempts += 1
                if local_security.failed_attempts >= 5: local_security.locked_until = timezone.now() + timedelta(minutes=15)
                local_security.save(update_fields=['failed_attempts','locked_until','updated_at'])
            if failures >= 5: return JsonResponse({'code':'RATE_LIMITED','detail':'too many authentication failures','retry_after':900}, status=429, headers={'Retry-After':'900'})
            return JsonResponse({'code':'AUTH_INVALID','detail':'LDAP authentication failed'},status=401)
    else:
        user=django_authenticate(request,username=local_user.username if local_user else username,password=data.get('password',''))
        if not user:
            failures = _auth_failure(username, request)
            if local_security:
                local_security.failed_attempts += 1
                if local_security.failed_attempts >= 5: local_security.locked_until = timezone.now() + timedelta(minutes=15)
                local_security.save(update_fields=['failed_attempts','locked_until','updated_at'])
            if failures >= 5: return JsonResponse({'code':'RATE_LIMITED','detail':'too many authentication failures','retry_after':900}, status=429, headers={'Retry-After':'900'})
            return JsonResponse({'code':'AUTH_INVALID','detail':'invalid credentials'},status=401)
    cache.delete(key)
    security, _ = UserSecurity.objects.get_or_create(user=user)
    security.failed_attempts = 0
    security.locked_until = None
    security.save(update_fields=['failed_attempts','locked_until','updated_at'])
    login(request,user,backend='django.contrib.auth.backends.ModelBackend')
    now = timezone.now().timestamp()
    request.session['authenticated_at'] = now
    request.session['last_seen_at'] = now
    request.session['permission_version'] = security.permission_version
    request.session['session_nonce'] = str(security.session_nonce)
    result=_payload(user, request); return JsonResponse({'role':result['role'],'user':result})

@ensure_csrf_cookie
@require_http_methods(['GET'])
def me(request):
    if not request.user.is_authenticated: return JsonResponse({'authenticated':False},status=401)
    result=_payload(request.user, request); return JsonResponse({'authenticated':True,'role':result['role'],'user':result})

@require_http_methods(['POST'])
def logout_view(request): logout(request); return JsonResponse({'detail':'logged out'})

@require_http_methods(['GET','POST'])
@transaction.atomic
def users(request):
    if not request.user.is_authenticated or user_role(request.user) not in ('admin','sysadmin'): return JsonResponse({'code':'ROLE_REQUIRED','detail':'sysadmin role required'},status=403)
    User=get_user_model()
    if request.method=='GET': return JsonResponse({'roles':ROLES,'users':[{'username':u.username,'active':u.is_active,'role':user_role(u)} for u in User.objects.order_by('username')]})
    try:
        data=json.loads(request.body or '{}')
        action = str(data.get('action') or 'assign_role')
        target=User.objects.select_for_update().get(username=data['username'])
        actor_role = user_role(request.user)
        if target.is_superuser and actor_role != 'admin': raise PermissionError('superuser is protected')
        before_role = user_role(target)
        if action == 'assign_role':
            target=assign_role(request.user,target.username,data['role'])
        elif action == 'revoke':
            target.groups.remove(*target.groups.filter(name__startswith='plm:'))
        elif action not in ('disable','enable'):
            raise ValueError('invalid user action')
        security, _ = UserSecurity.objects.select_for_update().get_or_create(user=target)
        if action == 'disable': target.is_active = False; target.save(update_fields=['is_active'])
        elif action == 'enable': target.is_active = True; target.save(update_fields=['is_active'])
        elif action == 'revoke': security.revoked_at = timezone.now()
        if action != 'assign_role':
            security.permission_version += 1
            security.session_nonce = __import__('uuid').uuid4()
            security.save(update_fields=['permission_version','session_nonce','revoked_at','updated_at'])
        AuditEvent.objects.create(actor=request.user.username, action='user.' + action,
            resource_type='User', resource_id=target.username,
            details={'previous_role': before_role, 'role': user_role(target), 'active': target.is_active, 'permission_version': security.permission_version})
    except (KeyError,ValueError,PermissionError,User.DoesNotExist) as exc: return JsonResponse({'code':'ROLE_ASSIGNMENT_INVALID','detail':str(exc)},status=400)
    return JsonResponse({'user':_payload(target, request)})

@require_http_methods(['GET'])
def admin_roles(request):
    if not request.user.is_authenticated or user_role(request.user) not in ('admin','sysadmin'):
        return JsonResponse({'code':'ROLE_REQUIRED','detail':'sysadmin role required'}, status=403)
    return JsonResponse({'roles':[{'name': role, 'permissions': sorted(ROLE_PERMISSIONS.get(role, set()))} for role in ROLES]})

@require_http_methods(['GET','PATCH','POST'])
@transaction.atomic
def admin_user_detail(request, user_id=None):
    if not request.user.is_authenticated or user_role(request.user) not in ('admin','sysadmin'):
        return JsonResponse({'code':'ROLE_REQUIRED','detail':'sysadmin role required'},status=403)
    User=get_user_model()
    try: target=User.objects.select_for_update().get(pk=user_id)
    except User.DoesNotExist: return JsonResponse({'detail':'not found'},status=404)
    security,_=UserSecurity.objects.get_or_create(user=target)
    if request.method=='GET':
        payload=_payload(target,request); payload.update({'user_id':target.pk,'email':target.email,'is_active':target.is_active,'permission_version':security.permission_version,'last_login':target.last_login}); return JsonResponse(payload)
    try: data=json.loads(request.body or '{}')
    except ValueError: return JsonResponse({'code':'INVALID_JSON','detail':'invalid JSON'},status=400)
    if request.method=='PATCH':
        if set(data)-{'role'}: return JsonResponse({'code':'FIELD_NOT_WRITABLE','detail':'only role may be changed'},status=422)
        if not request.headers.get('Idempotency-Key'):
            return JsonResponse({'code':'IDEMPOTENCY_KEY_REQUIRED','detail':'Idempotency-Key header is required'},status=428)
        expected=request.headers.get('If-Match')
        if not expected:
            return JsonResponse({'code':'PRECONDITION_REQUIRED','detail':'If-Match header is required'}, status=428)
        if expected and expected.strip('"')!=str(security.permission_version): return JsonResponse({'code':'CONCURRENT_MODIFICATION','permission_version':security.permission_version},status=409)
        try:
            role=data.get('role')
            if role is None: target.groups.remove(*target.groups.filter(name__startswith='plm:'))
            else: target=assign_role(request.user,target.username,role)
        except (ValueError,PermissionError) as exc: return JsonResponse({'code':'ROLE_ASSIGNMENT_INVALID','detail':str(exc)},status=400)
        security.permission_version+=1; security.session_nonce=__import__('uuid').uuid4(); security.save(update_fields=['permission_version','session_nonce','updated_at'])
        return JsonResponse({'user':_payload(target,request),'permission_version':security.permission_version})
    action=str(data.get('action') or '').lower()
    if not request.headers.get('Idempotency-Key'):
        return JsonResponse({'code':'IDEMPOTENCY_KEY_REQUIRED','detail':'Idempotency-Key header is required'},status=428)
    if action not in ('disable','restore','revoke-sessions'): return JsonResponse({'code':'STATE_TRANSITION_INVALID','detail':'invalid user action'},status=400)
    if action=='disable': target.is_active=False; target.save(update_fields=['is_active'])
    elif action=='restore': target.is_active=True; target.save(update_fields=['is_active'])
    security.permission_version+=1; security.session_nonce=__import__('uuid').uuid4(); security.save(update_fields=['permission_version','session_nonce','updated_at'])
    return JsonResponse({'user':_payload(target,request),'permission_version':security.permission_version})
