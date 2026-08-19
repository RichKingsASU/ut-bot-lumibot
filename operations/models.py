from django.conf import settings
from django.db import models
class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(max_length=100, db_index=True); object_type = models.CharField(max_length=100); object_id = models.CharField(max_length=100)
    previous_state = models.JSONField(default=dict); resulting_state = models.JSONField(default=dict); correlation_id = models.CharField(max_length=64, db_index=True)
    class Meta:
        permissions = [("operate_kill_switch", "Can operate kill switch"), ("run_reconciliation", "Can run reconciliation"), ("manage_risk", "Can manage risk controls")]
