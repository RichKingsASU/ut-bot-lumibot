import uuid
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
class Order(models.Model):
    class Side(models.TextChoices): BUY = "BUY", "Buy"; SELL = "SELL", "Sell"
    class Status(models.TextChoices): PENDING_APPROVAL="PENDING_APPROVAL","Pending approval"; ACCEPTED="ACCEPTED","Accepted"; PARTIAL="PARTIAL","Partial"; FILLED="FILLED","Filled"; REJECTED="REJECTED","Rejected"; CANCELLED="CANCELLED","Cancelled"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.CharField(max_length=128, unique=True)
    symbol = models.CharField(max_length=20, db_index=True); side = models.CharField(max_length=4, choices=Side.choices)
    quantity = models.DecimalField(max_digits=18, decimal_places=6, validators=[MinValueValidator(0.000001)])
    filled_quantity = models.DecimalField(max_digits=18, decimal_places=6, default=0, validators=[MinValueValidator(0)])
    limit_price = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING_APPROVAL, db_index=True)
    broker_order_id = models.CharField(max_length=128, null=True, blank=True, unique=True)
    strategy = models.CharField(max_length=100, default="manual", db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True); updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(filled_quantity__lte=models.F("quantity")), name="filled_lte_quantity")]
class Position(models.Model):
    symbol = models.CharField(max_length=20, unique=True); quantity = models.DecimalField(max_digits=18, decimal_places=6)
    average_price = models.DecimalField(max_digits=18, decimal_places=6, validators=[MinValueValidator(0)]); version = models.PositiveBigIntegerField(default=0); updated_at = models.DateTimeField(auto_now=True)
class RiskPolicy(models.Model):
    active = models.BooleanField(default=True, unique=True); max_order_notional = models.DecimalField(max_digits=18, decimal_places=2, default=10000, validators=[MinValueValidator(0)])
    max_position_notional = models.DecimalField(max_digits=18, decimal_places=2, default=50000, validators=[MinValueValidator(0)]); max_daily_exposure = models.DecimalField(max_digits=18, decimal_places=2, default=100000, validators=[MinValueValidator(0)]); max_symbol_exposure = models.DecimalField(max_digits=18, decimal_places=2, default=25000, validators=[MinValueValidator(0)]); stale_market_data_seconds = models.PositiveIntegerField(default=30)
class TradingControl(models.Model):
    singleton = models.BooleanField(default=True, unique=True); trading_enabled = models.BooleanField(default=False); reason = models.CharField(max_length=255, default="Initial safe state"); changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL); changed_at = models.DateTimeField(auto_now=True)
class ReconciliationRun(models.Model):
    started_at = models.DateTimeField(auto_now_add=True); completed_at = models.DateTimeField(null=True); status = models.CharField(max_length=20, default="RUNNING"); discrepancies = models.JSONField(default=list); correlation_id = models.CharField(max_length=64, db_index=True)
