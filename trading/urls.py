from django.urls import path
from . import views
urlpatterns = [path("", views.dashboard, name="dashboard"), path("orders/create/", views.order_create, name="order_create"), path("controls/kill-switch/", views.kill_switch, name="kill_switch")]
