from django.contrib import admin
from .models import AuditEvent
@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display=("timestamp","actor","action","object_type","object_id","correlation_id"); readonly_fields=("actor","timestamp","action","object_type","object_id","previous_state","resulting_state","correlation_id")
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False
