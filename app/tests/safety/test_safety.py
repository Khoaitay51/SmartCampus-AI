"""
tests/safety/test_safety.py
"""
import unittest

from app.safety.permissions import is_allowed
from app.safety.policy import SafetyPolicyEngine


class TestSafetyPackage(unittest.TestCase):
    def test_permissions(self):
        self.assertTrue(is_allowed("temperature_anomaly", "set_fan"))
        self.assertFalse(is_allowed("temperature_anomaly", "trigger_buzzer"))


if __name__ == "__main__":
    unittest.main()
