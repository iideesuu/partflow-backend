from functools import wraps
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from .models import UserSecurity

ROLES=('viewer','engineer','reviewer','publisher','auditor','sysadmin','admin')
ROLE_ALIASES={'release_manager':'publisher'}
ROLE_PERMISSIONS={'viewer':{'parts.read','bom.read','attachments.read'},'engineer':{'parts.read','parts.create','parts.edit','bom.read','bom.edit','attachments.upload','imports.create'},'reviewer':{'parts.read','bom.read','attachments.read','review.submit','review.decide'},'publisher':{'parts.read','bom.read','review.read','release.publish','attachments.read'},'auditor':{'parts.read','bom.read','attachments.read','audit.read'},'sysadmin':set(),'admin':set()}

def user_role(user):
    if not getattr(user,'is_authenticated',False) or not getattr(user,'is_active',False): return None
    if getattr(user,'is_superuser',False): return 'admin'
    # Only the frozen local role dictionary is authoritative.  LDAP/external
    # groups are intentionally ignored, and unknown plm:* groups never grant
    # permissions.  Sort to make the result deterministic if bad legacy data
    # contains multiple business groups.
    raw=next((g.name[4:] for g in user.groups.filter(name__startswith='plm:').order_by('name') if g.name[4:] in ROLES or g.name[4:] in ROLE_ALIASES),None)
    return ROLE_ALIASES.get(raw,raw)

def has_permission(user,permission): return permission in ROLE_PERMISSIONS.get(user_role(user),set())

class RolePermission(BasePermission):
    def has_permission(self,request,view):
        role=user_role(request.user)
        if not role:
            if getattr(request.user, 'is_authenticated', False):
                raise PermissionDenied({'code':'ROLE_REQUIRED','detail':'Waiting for a PLM administrator to assign a local role.'})
            return False
        # Read operations are available to every authenticated PLM role unless
        # a view explicitly narrows ``read_roles``.  Previously the
        # ``write_roles`` tuple was applied to GET as well, which prevented
        # viewers and reviewers from opening the category/part lists.
        if request.method in ('GET','HEAD','OPTIONS'):
            allowed = getattr(view, 'read_roles', None)
            return not allowed or role == 'admin' or role in allowed
        action_roles = getattr(view, 'action_roles', {}).get(getattr(view, 'action', ''), None)
        if action_roles is not None:
            return role == 'admin' or role in action_roles
        # Destructive operations can be stricter than create/update.  This is
        # used by the admin catalog screens to keep accidental deletes out of
        # engineer workflows.
        if request.method == 'DELETE' and hasattr(view, 'delete_roles'):
            allowed = view.delete_roles
        else:
            allowed = getattr(view, 'roles', None) or getattr(view, 'write_roles', None)
        return not allowed or role == 'admin' or role in allowed

def require_role(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(request,*args,**kwargs):
            role = user_role(request.user)
            if role not in roles:
                from django.http import JsonResponse
                return JsonResponse({'code':'ROLE_REQUIRED' if not role else 'PERMISSION_DENIED','detail':'Waiting for a PLM administrator to assign a local role.' if not role else 'permission denied'},status=403)
            return view(request,*args,**kwargs)
        return wrapped
    return decorator

def assign_role(actor,username,role):
    actor_role = user_role(actor)
    if actor_role not in ('admin','sysadmin'): raise PermissionError('admin or sysadmin role required')
    role=ROLE_ALIASES.get(role,role)
    if role not in ROLES: raise ValueError('invalid role')
    if role == 'admin' and actor_role != 'admin': raise PermissionError('only admin may assign admin role')
    User=get_user_model()
    with transaction.atomic():
        target=User.objects.select_for_update().get(username=username)
        if target.is_superuser and actor_role != 'admin': raise PermissionError('superuser is protected')
        business_groups = list(target.groups.filter(name__startswith='plm:'))
        target.groups.remove(*business_groups)
        target.groups.add(Group.objects.get_or_create(name=f'plm:{role}')[0])
        security, _ = UserSecurity.objects.select_for_update().get_or_create(user=target)
        security.permission_version += 1
        security.session_nonce = __import__('uuid').uuid4()
        security.revoked_at = None
        security.save(update_fields=['permission_version', 'session_nonce', 'revoked_at', 'updated_at'])
    return target
