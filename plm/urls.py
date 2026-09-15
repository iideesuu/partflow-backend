from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import CategoryViewSet, UnitViewSet, PartViewSet, BOMViewSet, UploadSessionViewSet, ImportJobViewSet, ExportJobViewSet, storage_health, admin_health, admin_settings, jobs_index, job_detail, job_errors, numbering_next_number, NumberRequestViewSet, PartRevisionViewSet, TopLevelPartRevisionViewSet, PartAttachmentViewSet, AuditEventViewSet, bom_revision_actions
from .attachment_views import attachment_version_detail, attachment_version_preview, attachment_version_download, attachment_version_content
from .auth_views import csrf, login_view, me, logout_view, users, admin_user_detail, admin_roles
from .bom_views import BOMRevisionViewSet, BOMItemViewSet
from .number_views import external_number_register
router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('units', UnitViewSet, basename='unit')
router.register('parts', PartViewSet, basename='part')
router.register('boms', BOMViewSet, basename='bom')
router.register('attachments/upload-sessions', UploadSessionViewSet, basename='upload-session')
router.register('imports', ImportJobViewSet, basename='import-job')
router.register('exports', ExportJobViewSet, basename='export-job')
router.register('numbers', NumberRequestViewSet, basename='number')
router.register('audit', AuditEventViewSet, basename='audit')
router.register('parts/(?P<part_pk>[^/.]+)/revisions', PartRevisionViewSet, basename='part-revision')
router.register('part-revisions', TopLevelPartRevisionViewSet, basename='part-revision-top')
router.register('parts/(?P<part_pk>[^/.]+)/attachments', PartAttachmentViewSet, basename='part-attachment')
router.register('bom-revisions', BOMRevisionViewSet, basename='bom-revision')
router.register('bom-revisions/(?P<bom_revision_pk>[^/.]+)/items', BOMItemViewSet, basename='bom-item')
audit_list = AuditEventViewSet.as_view({'get':'list'})
urlpatterns = [path('', include(router.urls)), path('storage/health/', storage_health), path('admin/health/', admin_health), path('admin/settings/', admin_settings), path('admin/roles', admin_roles), path('admin/roles/', admin_roles), path('admin/users/<int:user_id>', admin_user_detail), path('admin/users/<int:user_id>/', admin_user_detail), path('admin/users/<int:user_id>/actions', admin_user_detail), path('admin/users/<int:user_id>/actions/', admin_user_detail), path('admin/users', users), path('admin/users/', users), path('jobs/', jobs_index), path('jobs/<uuid:pk>/', job_detail), path('jobs/<uuid:pk>/errors', job_errors), path('jobs/<uuid:pk>/errors/', job_errors), path('numbering/next-number', numbering_next_number), path('numbering/next-number/', numbering_next_number), path('audit-events', audit_list), path('audit-events/', audit_list), path('bom-revisions/<uuid:pk>/actions/', bom_revision_actions), path('auth/csrf/', csrf), path('auth/login/', login_view), path('auth/me/', me), path('auth/logout/', logout_view), path('auth/users/', users)]
urlpatterns += [path('numbering/external-register', external_number_register), path('numbering/external-register/', external_number_register),
    path('attachment-versions/<uuid:version_id>/', attachment_version_detail),
    path('attachment-versions/<uuid:version_id>/preview', attachment_version_preview),
    path('attachment-versions/<uuid:version_id>/preview/', attachment_version_preview),
    path('attachment-versions/<uuid:version_id>/download', attachment_version_download),
    path('attachment-versions/<uuid:version_id>/download/', attachment_version_download),
    path('attachment-versions/<uuid:version_id>/content', attachment_version_content),
    path('attachment-versions/<uuid:version_id>/content/', attachment_version_content),
]
