"""
tests/tools/test_tools.py
"""
import sys
import unittest
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from app.tools.registry import ACTION_TOOLS, RAG_TOOLS, is_tool_allowed_in_mode


class TestToolsRegistry(unittest.TestCase):
    def test_rag_and_action_tools_exist(self):
        self.assertGreater(len(RAG_TOOLS), 0)
        self.assertGreater(len(ACTION_TOOLS), 0)

    def test_permissions_matrix(self):
        self.assertTrue(is_tool_allowed_in_mode("set_fan", "SAVING"))
        self.assertFalse(is_tool_allowed_in_mode("set_door", "EXAM"))


if __name__ == "__main__":
    unittest.main()
