from django import forms
from .models import Order
class OrderForm(forms.Form):
    idempotency_key = forms.CharField(max_length=128, widget=forms.HiddenInput)
    symbol = forms.CharField(max_length=20); side = forms.ChoiceField(choices=Order.Side.choices); quantity = forms.DecimalField(min_value=0.000001, max_digits=18, decimal_places=6); limit_price = forms.DecimalField(min_value=0.000001, max_digits=18, decimal_places=6)
class KillSwitchForm(forms.Form):
    enabled = forms.BooleanField(required=False); reason = forms.CharField(max_length=255)
