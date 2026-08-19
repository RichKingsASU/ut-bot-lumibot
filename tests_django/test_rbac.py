from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse
class RBACViewsTests(TestCase):
    def setUp(self): self.user=User.objects.create_user("viewer",password="password-long-enough")
    def test_anonymous_dashboard_redirects_to_login(self): self.assertEqual(self.client.get(reverse("dashboard")).status_code,302)
    def test_read_only_user_cannot_submit_order(self):
        self.client.force_login(self.user); self.assertEqual(self.client.post(reverse("order_create"),{}).status_code,403)
    def test_operator_permission_is_server_side(self):
        self.client.force_login(self.user); self.assertEqual(self.client.post(reverse("kill_switch"),{}).status_code,403)
