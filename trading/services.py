from decimal import Decimal
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import Sum
from operations.models import AuditEvent
from .models import Order, Position, RiskPolicy, TradingControl
@transaction.atomic
def create_order(*, actor, idempotency_key, symbol, side, quantity, limit_price, correlation_id):
    if not actor.has_perm("trading.add_order"): raise PermissionDenied
    existing = Order.objects.select_for_update().filter(idempotency_key=idempotency_key).first()
    if existing: return existing, False
    control, _ = TradingControl.objects.select_for_update().get_or_create(singleton=True)
    if not control.trading_enabled: raise ValidationError("Trading kill switch is active")
    policy = RiskPolicy.objects.filter(active=True).first()
    if not policy: raise ValidationError("No active risk policy; refusing order")
    quantity, price = Decimal(quantity), Decimal(limit_price)
    notional = quantity * price
    if notional > policy.max_order_notional: raise ValidationError("Order exposure limit exceeded")
    position = Position.objects.filter(symbol=symbol.upper()).first()
    if position and abs(position.quantity * price) + notional > policy.max_symbol_exposure: raise ValidationError("Symbol exposure limit exceeded")
    daily = Order.objects.exclude(status__in=[Order.Status.REJECTED, Order.Status.CANCELLED]).aggregate(v=Sum(models.F("quantity") * models.F("limit_price"))).get("v") or 0
    if daily + notional > policy.max_daily_exposure: raise ValidationError("Daily exposure limit exceeded")
    order = Order.objects.create(idempotency_key=idempotency_key, symbol=symbol.upper(), side=side, quantity=quantity, limit_price=price, created_by=actor)
    AuditEvent.objects.create(actor=actor, action="order.created", object_type="Order", object_id=str(order.pk), resulting_state={"status": order.status, "symbol": order.symbol, "quantity": str(order.quantity)}, correlation_id=correlation_id)
    return order, True
@transaction.atomic
def set_kill_switch(*, actor, enabled, reason, correlation_id):
    if not actor.has_perm("operations.operate_kill_switch"): raise PermissionDenied
    control, _ = TradingControl.objects.select_for_update().get_or_create(singleton=True)
    previous = {"trading_enabled": control.trading_enabled, "reason": control.reason}
    control.trading_enabled = enabled; control.reason = reason; control.changed_by = actor; control.save()
    AuditEvent.objects.create(actor=actor, action="kill_switch.changed", object_type="TradingControl", object_id=str(control.pk), previous_state=previous, resulting_state={"trading_enabled": enabled, "reason": reason}, correlation_id=correlation_id)
    return control
