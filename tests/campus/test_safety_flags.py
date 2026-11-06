"""Unit tests cho module đọc cờ an toàn (app/config/safety.py)."""
import os
import unittest
from unittest import mock

from app.config.safety import (
    fsm_enabled,
    hitl_env_enabled,
    prompt_guard_enabled,
    toctou_binding_enabled,
)

FLAGS = (
    ("SAFETY_PROMPT_GUARD_ENABLED", prompt_guard_enabled),
    ("SAFETY_FSM_ENABLED", fsm_enabled),
    ("SAFETY_HITL_ENABLED", hitl_env_enabled),
    ("SAFETY_TOCTOU_BINDING_ENABLED", toctou_binding_enabled),
)


class SafetyFlagsTests(unittest.TestCase):
    def test_defaults_to_true_when_unset(self):
        clean_env = {
            k: v for k, v in os.environ.items() if not k.startswith("SAFETY_")
        }
        with mock.patch.dict(os.environ, clean_env, clear=True):
            for env_name, fn in FLAGS:
                with self.subTest(flag=env_name):
                    self.assertTrue(fn())

    def test_truthy_and_falsy_values(self):
        for env_name, fn in FLAGS:
            for truthy in ("true", "TRUE", "1", "yes", "on", " true "):
                with self.subTest(flag=env_name, val=truthy):
                    with mock.patch.dict(os.environ, {env_name: truthy}):
                        self.assertTrue(fn())
            for falsy in ("false", "FALSE", "0", "no", "off", " OFF "):
                with self.subTest(flag=env_name, val=falsy):
                    with mock.patch.dict(os.environ, {env_name: falsy}):
                        self.assertFalse(fn())


if __name__ == "__main__":
    unittest.main()
