import asyncio
import json
import unittest

from app.fallback import (
    AllProvidersFailed, CircuitBreaker, CircuitState, FallbackLLMClient, LastKnownCache, ParsingExhausted,
    ProviderSpec, ResilientToolExecutor, evaluate_by_rules, evaluate_with_fallback, fallback_trace,
    parse_recommendation,
)


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class ScriptedLLM:
    """Trả lần lượt các phần tử; Exception thì raise."""

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = 0

    async def complete(self, prompt):
        self.calls += 1
        out = self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
        if isinstance(out, Exception):
            raise out
        return out


class BreakerTests(unittest.TestCase):
    def test_open_half_open_close(self):
        clk = FakeClock()
        b = CircuitBreaker("x", failure_threshold=3, window_seconds=60, recovery_seconds=900, clock=clk)
        for _ in range(3):
            self.assertTrue(b.allow_request())
            b.record_failure()
        self.assertEqual(b.state, CircuitState.OPEN)
        self.assertFalse(b.allow_request())
        clk.t = 901
        self.assertTrue(b.allow_request())       # request dò
        self.assertFalse(b.allow_request())      # chỉ 1 request dò
        b.record_failure()                       # dò thất bại -> OPEN lại
        self.assertEqual(b.state, CircuitState.OPEN)
        clk.t = 901 + 901
        self.assertTrue(b.allow_request())
        b.record_success()
        self.assertEqual(b.state, CircuitState.CLOSED)

    def test_failures_outside_window_do_not_trip(self):
        clk = FakeClock()
        b = CircuitBreaker("x", failure_threshold=3, window_seconds=60, clock=clk)
        for t in (0, 100, 200):
            clk.t = t
            b.record_failure()
        self.assertEqual(b.state, CircuitState.CLOSED)


class LLMFallbackTests(unittest.IsolatedAsyncioTestCase):
    def make(self, primary, secondary):
        clk = FakeClock()
        return FallbackLLMClient([
            ProviderSpec("primary", primary, CircuitBreaker("p", failure_threshold=2, clock=clk)),
            ProviderSpec("secondary", secondary, CircuitBreaker("s", clock=clk)),
        ])

    async def test_falls_back_and_trips_breaker(self):
        primary = ScriptedLLM(RuntimeError("503 UNAVAILABLE"))
        secondary = ScriptedLLM("ok-from-secondary")
        llm = self.make(primary, secondary)
        with fallback_trace() as trace:
            for _ in range(4):
                self.assertEqual(await llm.complete("hi"), "ok-from-secondary")
        self.assertEqual(primary.calls, 2)        # sau 2 lỗi thì ngắt mạch, không gọi thêm
        self.assertTrue(trace.is_fallback)
        self.assertIn("model", trace.levels)

    async def test_non_transient_does_not_trip(self):
        primary = ScriptedLLM(ValueError("400 invalid argument"))
        llm = self.make(primary, ScriptedLLM("ok"))
        for _ in range(5):
            await llm.complete("hi")
        self.assertEqual(primary.calls, 5)

    async def test_empty_response_moves_on(self):
        llm = self.make(ScriptedLLM("   "), ScriptedLLM("real"))
        self.assertEqual(await llm.complete("hi"), "real")

    async def test_all_fail(self):
        llm = self.make(ScriptedLLM(RuntimeError("503")), ScriptedLLM(ConnectionError("down")))
        with self.assertRaises(AllProvidersFailed):
            await llm.complete("hi")


GOOD = '{"tool_name":"set_fan","tool_params":{"room_id":"r1","state":"on"},"reason":"nóng","confidence":0.9,"urgency":"high"}'


class ParsingTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_with_fence_and_chatter(self):
        out = await parse_recommendation("Đây là kết quả:\n```json\n" + GOOD + "\n```\nHết.", None)
        self.assertEqual(out.method, "direct")
        self.assertEqual(out.data["tool_name"], "set_fan")

    async def test_trailing_comma(self):
        out = await parse_recommendation(GOOD.replace('"high"}', '"high",}'), None)
        self.assertEqual(out.method, "direct")

    async def test_repair_via_llm(self):
        broken = GOOD[:-1].replace('"confidence":0.9', '"confidence":"cao"')
        out = await parse_recommendation(broken, ScriptedLLM(GOOD))
        self.assertEqual(out.method, "repaired")

    async def test_scrape_when_llm_dead_and_cap_confidence(self):
        broken = 'Tôi nghĩ: tool_name: "set_fan", "confidence": 0.97, "urgency": "high", "reason": "quá nóng" ...'
        with fallback_trace() as trace:
            out = await parse_recommendation(broken, ScriptedLLM(RuntimeError("503")), default_room_id="r9")
        self.assertEqual(out.method, "scraped")
        self.assertLessEqual(out.data["confidence"], 0.6)
        self.assertEqual(out.data["tool_params"]["room_id"], "r9")
        self.assertIn("parsing", trace.levels)

    async def test_exhausted(self):
        with self.assertRaises(ParsingExhausted):
            await parse_recommendation("không có gì cả", ScriptedLLM("vẫn không có gì"))

    async def test_rejects_unknown_tool(self):
        bad = GOOD.replace("set_fan", "launch_rocket")
        with self.assertRaises(ParsingExhausted):
            await parse_recommendation(bad, None)


class FakeRag:
    def __init__(self):
        self.fail = None
        self.seen = []

    async def call_tool(self, name, params):
        self.seen.append((name, params))
        if self.fail:
            raise self.fail
        return {"points": [30, 31]}


class ToolFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_stale_cache_then_message(self):
        rag = FakeRag()
        ex = ResilientToolExecutor(rag, "room-1", cache=LastKnownCache(), context_snapshot={"temperature": 33})
        ok = await ex.execute("get_telemetry", {"metric": "temperature", "window": "15m", "evil": "x"})
        self.assertEqual(json.loads(ok), {"points": [30, 31]})
        self.assertEqual(rag.seen[0][1]["room_id"], "room-1")      # tự chèn room_id
        self.assertNotIn("evil", rag.seen[0][1])                   # lọc tham số lạ

        rag.fail = ConnectionError("getaddrinfo failed")
        with fallback_trace() as trace:
            stale = json.loads(await ex.execute("get_telemetry", {"metric": "temperature", "window": "15m"}))
            self.assertTrue(stale["_stale"])
            msg = await ex.execute("get_telemetry", {"metric": "co2", "window": "1h"})
        self.assertIn("Không thể kết nối", msg)
        self.assertIn("temperature", msg)   # snapshot của event
        self.assertIn("tool", trace.levels)

    async def test_4xx_is_not_degraded(self):
        class Http404(Exception):
            status_code = 404
        rag = FakeRag()
        rag.fail = Http404("room not found")
        ex = ResilientToolExecutor(rag, "r", cache=LastKnownCache())
        with fallback_trace() as trace:
            msg = await ex.execute("get_telemetry", {"metric": "co2", "window": "1h"})
        self.assertIn("HTTP 404", msg)
        self.assertFalse(trace.is_fallback)

    async def test_budget_message_passthrough(self):
        class RagBudgetExceeded(Exception):
            pass
        rag = FakeRag()
        rag.fail = RagBudgetExceeded("Đã dùng 5/5 RAG call")
        ex = ResilientToolExecutor(rag, "r", cache=LastKnownCache())
        self.assertIn("5/5", await ex.execute("get_schedule", {}))


def ev(event_type, mode="LECTURE", **payload):
    ctx = payload.pop("ctx", {})
    return {"event_id": "e1", "event_type": event_type, "room_id": "r1", "payload": payload,
            "operational_context": {"room": {"state": mode}, **ctx}}


class RuleTests(unittest.TestCase):
    def test_smoke_lecture_buzzer_first(self):
        r = evaluate_by_rules(ev("smoke_detected", smoke_value=520))
        self.assertEqual(r["recommendation"]["tool_name"], "trigger_buzzer")
        self.assertEqual(r["recommendation"]["urgency"], "high")
        self.assertIn("EMERGENCY", json.dumps(r["alternatives"]))

    def test_smoke_in_exam_buzzer_and_door_blocked(self):
        r = evaluate_by_rules(ev("smoke_detected", mode="EXAM", smoke_state="suspected"))
        self.assertEqual(r["recommendation"]["tool_name"], "set_mode")
        names = [r["recommendation"]["tool_name"]] + [a["tool_name"] for a in r["alternatives"]]
        self.assertNotIn("trigger_buzzer", names)
        self.assertNotIn("set_door", names)

    def test_smoke_has_priority_on_other_events(self):
        r = evaluate_by_rules(ev("temperature_anomaly", smoke_value=600, temperature=36))
        self.assertEqual(r["recommendation"]["tool_name"], "trigger_buzzer")

    def test_temperature_fan(self):
        r = evaluate_by_rules(ev("temperature_anomaly", temperature=35.5, ctx={"occupancy": {"current_count": 20}}))
        self.assertEqual(r["recommendation"]["tool_name"], "set_fan")
        self.assertEqual(r["recommendation"]["tool_params"]["state"], "on")

    def test_temperature_empty_room_skips(self):
        r = evaluate_by_rules(ev("temperature_anomaly", temperature=35.5, ctx={"occupancy": {"current_count": 0}}))
        self.assertTrue(r["skip"])

    def test_temperature_fan_blocked_in_lock(self):
        r = evaluate_by_rules(ev("temperature_anomaly", mode="LOCK", temperature=40))
        self.assertEqual(r["recommendation"]["tool_name"], "send_alert")

    def test_occupancy_empty_saving(self):
        r = evaluate_by_rules(ev("occupancy_change", empty_for_seconds=1200,
                                 ctx={"occupancy": {"current_count": 0}, "active_session": None}))
        self.assertEqual(r["recommendation"]["tool_name"], "set_fan")
        self.assertEqual(r["recommendation"]["tool_params"]["state"], "off")

    def test_occupancy_recently_empty_skips(self):
        r = evaluate_by_rules(ev("occupancy_change", empty_for_seconds=60, ctx={"occupancy": {"current_count": 0}}))
        self.assertTrue(r["skip"])

    def test_rfid_exam_only_alert(self):
        r = evaluate_by_rules(ev("rfid_unknown", mode="EXAM"))
        self.assertEqual(r["recommendation"]["tool_name"], "send_alert")
        self.assertEqual(r["recommendation"]["tool_params"]["level"], "warning")
        self.assertEqual(r["alternatives"], [])

    def test_manual_normal_skips(self):
        r = evaluate_by_rules(ev("manual_trigger", temperature=25, smoke_value=10))
        self.assertTrue(r["skip"])
        self.assertEqual(r["skip_reason"], "all_metrics_normal")

    def test_unknown_mode_only_alert(self):
        r = evaluate_by_rules(ev("smoke_detected", mode="", smoke_value=999))
        self.assertEqual(r["recommendation"]["tool_name"], "send_alert")


class OrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_agent_crash_uses_rules_and_flags(self):
        async def dead_agent(event):
            raise AllProvidersFailed([("primary", "503"), ("secondary", "503")])

        r = await evaluate_with_fallback(ev("temperature_anomaly", temperature=36), dead_agent)
        self.assertTrue(r["is_fallback"])
        self.assertIn("rules", r["fallback_levels"])
        self.assertEqual(r["recommendation"]["tool_name"], "set_fan")
        self.assertTrue(r["analysis"].startswith("[FALLBACK"))

    async def test_timeout_uses_rules(self):
        async def slow(event):
            await asyncio.sleep(5)

        r = await evaluate_with_fallback(ev("temperature_anomaly", temperature=36), slow, agent_timeout=0.05)
        self.assertTrue(r["is_fallback"])

    async def test_healthy_agent_not_flagged(self):
        async def ok(event):
            return {"event_id": "e1", "recommendation": None, "analysis": "ổn", "skip": True}

        r = await evaluate_with_fallback(ev("manual_trigger"), ok)
        self.assertFalse(r["is_fallback"])
        self.assertEqual(r["analysis"], "ổn")

    async def test_degraded_but_alive_agent_is_flagged(self):
        from app.fallback import record

        async def degraded(event):
            record("model", "dùng gemini-secondary", "llm")
            return {"event_id": "e1", "recommendation": None, "analysis": "ổn", "skip": True}

        r = await evaluate_with_fallback(ev("manual_trigger"), degraded)
        self.assertTrue(r["is_fallback"])
        self.assertEqual(r["fallback_levels"], ["model"])


if __name__ == "__main__":
    unittest.main()
