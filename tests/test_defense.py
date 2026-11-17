"""Kiểm thử phòng thủ Sensor-Grounded Response (app/safety/defense.py, app/safety/sensor_guard.py)."""
import json
from pathlib import Path

import pytest

from app.agent import prompts
from app.agent.agent import ReActXenAgent
from app.config.settings import settings
from app.safety import defense
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload, EventType
from app.schemas.recommendation import AgentResponse, ToolRecommendation

DATA = Path(__file__).resolve().parents[1] / "benchmarkv2_refined/framework/attack_advanced/data/advanced_attack_testcases.json"
TCS = [t for t in json.loads(DATA.read_text(encoding="utf-8")) if t.get("track") == "A"]


def _case(user_id, category="SUP"):
    t = next(x for x in TCS if x.get("user_id") == user_id and x["category"] == category)
    p = t["payload"]
    return EventPayload(**p["event"]), OperationalContext(**p["operational_context"])


def _resp(ev, tool=None, params=None, conf=0.8):
    rec = ToolRecommendation(tool_name=tool, tool_params=params or {}, reason="r", confidence=conf) if tool else None
    return AgentResponse(event_id=ev.event_id, recommendation=rec, analysis="a", skip=rec is None)


@pytest.fixture
def mode():
    old = settings.AGENT_DEFENSE
    yield lambda m: setattr(settings, "AGENT_DEFENSE", m)
    settings.AGENT_DEFENSE = old


def _prompt():
    return prompts.build_react_prompt(event_type=EventType.SMOKE_DETECTED, tool_desc="D", tool_names="N",
                                      max_rag_calls=3, reflections="R", event_context="E", scratchpad="S")


def test_none_keeps_prompt_and_output(mode):
    mode("none")
    assert defense.PROMPT_RULES not in _prompt()
    ev, oc = _case("U2")
    out = defense.apply_guard(_resp(ev), ev, oc)
    assert out.skip and out.recommendation is None and out.analysis == "a"
    assert defense.mark_untrusted_event_json(ev.model_dump_json()) == ev.model_dump_json()


def test_prompt_mode_adds_rules_and_marks_description(mode):
    mode("prompt")
    assert defense.PROMPT_RULES in _prompt()
    ev, _ = _case("U2")
    assert defense.UNTRUSTED_OPEN in defense.mark_untrusted_event_json(ev.model_dump_json())


@pytest.mark.parametrize("m", ["guard", "full"])
def test_floor_on_skip_with_hazard(mode, m):
    mode(m)
    ev, oc = _case("U2")                                   # khói 650 ppm, 18 người
    out = defense.apply_guard(_resp(ev), ev, oc)
    assert out.recommendation.tool_name == "send_alert"
    assert out.recommendation.tool_params["level"] == "critical"
    assert not out.skip and out.analysis.startswith("[SensorGuard")


def test_veto_fan_off_when_overheating(mode):
    mode("guard")
    ev, oc = _case("U1", "DH-A")                           # 52.3 °C
    out = defense.apply_guard(_resp(ev, "set_fan", {"room_id": str(ev.room_id), "state": "off"}), ev, oc)
    assert out.recommendation.tool_name == "send_alert"    # bị veto, rồi floor


def test_guard_noop_on_normal_room(mode):
    mode("full")
    ev, oc = _case("U5", "DH-A")                           # vận hành bình thường
    out = defense.apply_guard(_resp(ev), ev, oc)
    assert out.skip and out.recommendation is None and out.analysis == "a"


def test_low_confidence_alert_kept_only_with_prompt(mode):
    ev, oc = _case("U2")
    agent = ReActXenAgent.__new__(ReActXenAgent)
    alert = lambda: _resp(ev, "send_alert", {"room_id": str(ev.room_id), "level": "critical"}, conf=0.2)
    mode("none")
    assert agent._final_safety_check(alert(), oc, ev).recommendation is None
    mode("prompt")
    assert agent._final_safety_check(alert(), oc, ev).recommendation is not None
