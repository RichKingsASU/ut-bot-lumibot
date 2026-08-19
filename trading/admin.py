from django.contrib import admin
from .models import Order, Position, ReconciliationRun, RiskPolicy, TradingControl
admin.site.register([Order, Position, ReconciliationRun, RiskPolicy, TradingControl])
