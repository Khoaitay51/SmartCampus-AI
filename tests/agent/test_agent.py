"""
tests/agent/test_agent.py
"""
import unittest

from app.agent.agent import ReActXenAgent
from app.agent.state import AgentRunState


class TestAgentUnit(unittest.TestCase):
    def test_agent_init(self):
        class DummyLLM:
            async def complete(self, prompt: str) -> str:
                return "dummy"

        async def dummy_rag(name, args, ctx):
            return "ok"

        agent = ReActXenAgent(DummyLLM(), dummy_rag)
        self.assertIsNotNone(agent)


if __name__ == "__main__":
    unittest.main()
