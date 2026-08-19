from decimal import Decimal
from django.contrib.auth.models import Permission, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from operations.models import AuditEvent
from trading.models import Order, RiskPolicy, TradingControl
from trading.services import create_order, set_kill_switch
class TradingSafetyTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user("trader",password="secure-test-password")
        self.user.user_permissions.add(Permission.objects.get(codename="add_order"))
        RiskPolicy.objects.create(max_order_notional=1000,max_daily_exposure=2000,max_symbol_exposure=1500)
        TradingControl.objects.create(trading_enabled=True,reason="test",changed_by=self.user)
    def order(self,key="request-1",quantity="2",price="100"):
        return create_order(actor=self.user,idempotency_key=key,symbol="spy",side="BUY",quantity=quantity,limit_price=price,correlation_id="cid")
    def test_duplicate_idempotency_key_creates_one_order(self):
        first,created=self.order(); second,recreated=self.order()
        self.assertTrue(created); self.assertFalse(recreated); self.assertEqual(first.pk,second.pk); self.assertEqual(Order.objects.count(),1)
    def test_order_limit_fails_closed(self):
        with self.assertRaises(ValidationError): self.order(quantity="11")
    def test_kill_switch_blocks_orders(self):
        TradingControl.objects.update(trading_enabled=False)
        with self.assertRaisesMessage(ValidationError,"kill switch"): self.order()
    def test_order_is_pending_human_approval_and_audited(self):
        order,_=self.order(); self.assertEqual(order.status,Order.Status.PENDING_APPROVAL); self.assertTrue(AuditEvent.objects.filter(object_id=str(order.pk),action="order.created").exists())
    def test_missing_permission_is_denied(self):
        other=User.objects.create_user("viewer")
        with self.assertRaises(PermissionDenied): create_order(actor=other,idempotency_key="x",symbol="SPY",side="BUY",quantity="1",limit_price="1",correlation_id="cid")
class KillSwitchTests(TestCase):
    def test_operator_action_is_audited(self):
        user=User.objects.create_user("operator"); user.user_permissions.add(Permission.objects.get(codename="operate_kill_switch"))
        control=set_kill_switch(actor=user,enabled=False,reason="incident",correlation_id="incident-1")
        self.assertFalse(control.trading_enabled); self.assertTrue(AuditEvent.objects.filter(action="kill_switch.changed",correlation_id="incident-1").exists())
