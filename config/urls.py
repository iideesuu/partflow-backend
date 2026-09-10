from django.urls import path, include
from plm.views import health_live, health_ready
urlpatterns=[path('health/', health_live), path('health/ready/', health_ready), path('api/v1/', include('plm.urls'))]
