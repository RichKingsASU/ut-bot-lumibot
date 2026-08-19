# Server-side RBAC matrix
| Role | Resource | Action | Permission | Expected behavior |
|---|---|---|---|---|
| Administrator | all trading/operations | administer | combined least-privilege grants | Allowed; changes audited where high risk |
| Trader | orders | view/create/change | `trading.view_order/add_order/change_order` | Allowed; new order awaits approval |
| Operator | reconciliation | run | `operations.run_reconciliation` | Allowed and audited |
| Operator | kill switch | enable/disable | `operations.operate_kill_switch` | Allowed and audited |
| Analyst / Read Only | orders/positions | view | view permissions | Read only; mutation returns 403 |
| Auditor | positions/orders/audit | view | view permissions | Read only, including audit trail |
| Anonymous | any protected page | any | none | Redirect to login or return 403 |

Roles are synchronized by `python manage.py bootstrap_roles`. Django permission decorators and service-layer permission checks enforce mutations server-side. Assignment/provisioning remains an Administrator process and requires UAT approval.
