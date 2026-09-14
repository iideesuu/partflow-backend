from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import CategoryViewSet, UnitViewSet, PartViewSet, BOMViewSet, UploadSessionViewSet, ImportJobViewSet, ExportJobViewSet, storage_health, admin_health, admin_settings, jobs_index, NumberRequestViewSet, PartRevisionViewSet, PartAttachmentViewSet, AuditEventViewSet, bom_revision_actions
from .auth_views import csrf, login_view, me, logout_view, users
from .bom_views import BOMRevisionViewSet, BOMItemViewSet
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
router.register('parts/(?P<part_pk>[^/.]+)/attachments', PartAttachmentViewSet, basename='part-attachment')
router.register('bom-revisions', BOMRevisionViewSet, basename='bom-revision')
router.register('bom-revisions/(?P<bom_revision_pk>[^/.]+)/items', BOMItemViewSet, basename='bom-item')
urlpatterns = [path('', include(router.urls)), path('storage/health/', storage_health), path('admin/health/', admin_health), path('admin/settings/', admin_settings), path('jobs/', jobs_index), path('bom-revisions/<uuid:pk>/actions/', bom_revision_actions), path('auth/csrf/', csrf), path('auth/login/', login_view), path('auth/me/', me), path('auth/logout/', logout_view), path('auth/users/', users)]
