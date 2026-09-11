import os, re
from dataclasses import dataclass
from django.contrib.auth import get_user_model
from django.db import transaction
from ldap3 import Connection, Server, SUBTREE
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

@dataclass(frozen=True)
class LDAPIdentity:
    username: str
    dn: str
    display_name: str = ''
    email: str = ''

def ldap_enabled():
    return os.getenv('LDAP_ENABLED', '0').strip().lower() in {'1','true','yes','on'}

def _config():
    # V1.6 names are canonical; legacy aliases remain read-only compatibility.
    host=os.getenv('LDAP_HOST','').strip(); base=(os.getenv('LDAP_BASE_DN') or os.getenv('LDAP_BASE') or '').strip(); bind_dn=os.getenv('LDAP_BIND_DN','').strip(); password=os.getenv('LDAP_BIND_PASSWORD') or os.getenv('LDAP_PASS',''); uid=(os.getenv('LDAP_UID_ATTRIBUTE') or os.getenv('LDAP_UID') or 'sAMAccountName').strip(); port=int(os.getenv('LDAP_PORT','389')); connect_timeout=float(os.getenv('LDAP_CONNECT_TIMEOUT','5')); search_timeout=float(os.getenv('LDAP_SEARCH_TIMEOUT','10'))
    if not host or not base or not bind_dn or not password: raise ValueError('LDAP configuration is incomplete')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]*',uid): raise ValueError('invalid LDAP UID attribute')
    if connect_timeout <= 0 or search_timeout <= 0: raise ValueError('invalid LDAP timeout')
    return host,port,base,bind_dn,password,uid,connect_timeout,search_timeout

def authenticate(username,password):
    if not ldap_enabled(): raise ValueError('LDAP is disabled')
    username=(username or '').strip()
    if not username or not password: raise ValueError('credentials required')
    host,port,base,bind_dn,bind_password,uid,connect_timeout,search_timeout=_config(); server=Server(host,port=port,use_ssl=(port==636),connect_timeout=connect_timeout)
    # read_only rejects mutating LDAP operations; this module only binds/searches.
    service=Connection(server,user=bind_dn,password=bind_password,read_only=True,receive_timeout=search_timeout,auto_bind=False)
    try:
        if not service.bind(): raise ValueError('LDAP service bind failed')
        if not service.search(base,f'(&(objectClass=person)({uid}={escape_filter_chars(username)}))',search_scope=SUBTREE,attributes=[uid,'displayName','mail']): raise ValueError('LDAP user not found')
        if len(service.entries)!=1: raise ValueError('LDAP user is ambiguous')
        entry=service.entries[0]; attrs=entry.entry_attributes_as_dict; check=Connection(server,user=str(entry.entry_dn),password=password,read_only=True,receive_timeout=search_timeout,auto_bind=False)
        try:
            if not check.bind(): raise ValueError('invalid LDAP credentials')
        finally: check.unbind()
        first=lambda key:str((attrs.get(key) or [''])[0])
        canonical_username=first(uid).strip()
        if not canonical_username: raise ValueError('LDAP user identity is incomplete')
        return LDAPIdentity(username=canonical_username,dn=str(entry.entry_dn),display_name=first('displayName'),email=first('mail'))
    except LDAPException as exc: raise ValueError('LDAP unavailable') from exc
    finally: service.unbind()

def shadow_user(identity):
    User=get_user_model()
    with transaction.atomic():
        # Resolve local shadow identity case-insensitively, without re-enabling it.
        user=User.objects.select_for_update().filter(username__iexact=identity.username[:150]).first()
        created=False
        if user is None:
            user,created=User.objects.get_or_create(username=identity.username[:150], defaults={'is_active':True})
        if not created and not user.is_active: raise ValueError('user is disabled locally')
        changed=[]
        if identity.display_name and user.first_name!=identity.display_name: user.first_name=identity.display_name; changed.append('first_name')
        if identity.email and user.email!=identity.email: user.email=identity.email; changed.append('email')
        if user.has_usable_password(): user.set_unusable_password(); changed.append('password')
        if changed: user.save(update_fields=changed)
    return user
