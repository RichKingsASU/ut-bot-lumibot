"""Selenium smoke journeys. Run only against an isolated PostgreSQL-backed test server."""
import os
import unittest
from selenium import webdriver
from selenium.webdriver.common.by import By
class CriticalJourneys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.getenv("SELENIUM_BASE_URL"): raise unittest.SkipTest("SELENIUM_BASE_URL not configured")
        cls.base=os.environ["SELENIUM_BASE_URL"].rstrip("/"); cls.driver=webdriver.Chrome()
    @classmethod
    def tearDownClass(cls): cls.driver.quit()
    def login(self, username, password):
        self.driver.get(self.base+"/login/"); self.driver.find_element(By.NAME,"username").send_keys(username); self.driver.find_element(By.NAME,"password").send_keys(password); self.driver.find_element(By.CSS_SELECTOR,"button[type=submit]").click()
    def test_login_dashboard_and_rbac(self):
        self.login(os.environ["SELENIUM_VIEWER_USER"],os.environ["SELENIUM_VIEWER_PASSWORD"]); self.assertIn("Trading Dashboard",self.driver.page_source); self.assertNotIn("Order entry",self.driver.page_source)
    def test_operator_kill_switch(self):
        self.login(os.environ["SELENIUM_OPERATOR_USER"],os.environ["SELENIUM_OPERATOR_PASSWORD"]); reason=self.driver.find_element(By.NAME,"reason"); reason.send_keys("selenium drill"); self.driver.find_element(By.CSS_SELECTOR,"form[action*='kill-switch'] button").click(); self.assertIn("Trading control updated",self.driver.page_source)
