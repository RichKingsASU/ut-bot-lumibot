from django.test import TestCase
from django.urls import reverse
class HealthTests(TestCase):
    def test_health(self): self.assertEqual(self.client.get(reverse("health")).json(),{"status":"ok"})
    def test_readiness_checks_database(self): self.assertEqual(self.client.get(reverse("readiness")).status_code,200)
