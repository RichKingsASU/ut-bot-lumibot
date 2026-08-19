from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
class Migration(migrations.Migration):
    initial=True; dependencies=[migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[migrations.CreateModel(name="AuditEvent", fields=[("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),("timestamp",models.DateTimeField(auto_now_add=True,db_index=True)),("action",models.CharField(db_index=True,max_length=100)),("object_type",models.CharField(max_length=100)),("object_id",models.CharField(max_length=100)),("previous_state",models.JSONField(default=dict)),("resulting_state",models.JSONField(default=dict)),("correlation_id",models.CharField(db_index=True,max_length=64)),("actor",models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,to=settings.AUTH_USER_MODEL))], options={"permissions":[("operate_kill_switch","Can operate kill switch"),("run_reconciliation","Can run reconciliation"),("manage_risk","Can manage risk controls")]})]
