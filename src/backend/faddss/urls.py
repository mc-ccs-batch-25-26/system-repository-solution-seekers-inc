from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apps.users.urls')),
    path('api/', include('apps.criteria.urls')),
    path('api/', include('apps.cycles.urls')),
    path('api/', include('apps.scoring.urls')),
    path('api/', include('apps.audit.urls')),
    path('api/', include('apps.beneficiaries.urls')),
    path('api/', include('apps.reports.urls')),
]
