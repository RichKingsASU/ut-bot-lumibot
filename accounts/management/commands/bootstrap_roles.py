from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
ROLE_PERMISSIONS = {"Administrator": ["view_order","add_order","change_order","view_position","run_reconciliation","operate_kill_switch","manage_risk"], "Trader": ["view_order","add_order","change_order","view_position"], "Operator": ["view_order","view_position","run_reconciliation","operate_kill_switch"], "Analyst": ["view_order","view_position"], "Read Only": ["view_order","view_position"], "Auditor": ["view_order","view_position","view_auditevent"]}
class Command(BaseCommand):
    help = "Create approved least-privilege role groups"
    def handle(self, *args, **options):
        for role, codenames in ROLE_PERMISSIONS.items():
            group, _ = Group.objects.get_or_create(name=role); group.permissions.set(Permission.objects.filter(codename__in=codenames))
        self.stdout.write(self.style.SUCCESS("Roles synchronized"))
