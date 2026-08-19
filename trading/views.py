import uuid
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from .forms import KillSwitchForm, OrderForm
from .models import Order, Position, TradingControl
from .services import create_order, set_kill_switch
@login_required
def dashboard(request):
    return render(request, "trading/dashboard.html", {"orders": Order.objects.order_by("-created_at")[:20], "positions": Position.objects.order_by("symbol"), "control": TradingControl.objects.first(), "idempotency_key": str(uuid.uuid4())})
@login_required
@permission_required("trading.add_order", raise_exception=True)
def order_create(request):
    if request.method != "POST": return redirect("dashboard")
    form = OrderForm(request.POST)
    if form.is_valid():
        try:
            order, created = create_order(actor=request.user, correlation_id=request.correlation_id, **form.cleaned_data)
            messages.success(request, "Order queued for human approval." if created else "Duplicate request returned the existing order.")
        except ValidationError as exc: messages.error(request, "; ".join(exc.messages))
    else: messages.error(request, "Invalid order request.")
    return redirect("dashboard")
@login_required
@permission_required("operations.operate_kill_switch", raise_exception=True)
def kill_switch(request):
    if request.method != "POST": return redirect("dashboard")
    form = KillSwitchForm(request.POST)
    if form.is_valid(): set_kill_switch(actor=request.user, correlation_id=request.correlation_id, **form.cleaned_data); messages.warning(request, "Trading control updated.")
    return redirect("dashboard")
