from django.contrib import admin
from .models import AuditLog, ProfileChangeLog

admin.site.register(AuditLog)
admin.site.register(ProfileChangeLog)
