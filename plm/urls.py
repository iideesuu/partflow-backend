from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import ldap_login, CategoryViewSet, UnitViewSet, PartViewSet, BOMViewSet, UploadSessionViewSet, ImportJobViewSet, ExportJobViewSet, storage_health
router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('units', UnitViewSet, basename='unit')
router.register('parts', PartViewSet, basename='part')
router.register('boms', BOMViewSet, basename='bom')
router.register('attachments/upload-sessions', UploadSessionViewSet, basename='upload-session')
router.register('imports', ImportJobViewSet, basename='import-job')
router.register('exports', ExportJobViewSet, basename='export-job')
urlpatterns = [path('auth/login/', ldap_login), path('', include(router.urls)), path('storage/health/', storage_health)]

