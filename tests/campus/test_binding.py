"""Tests cho HITL binding (Consent Integrity) — payload hash + binding state."""
import unittest

from app.campus.binding import (
    BINDING_KEY,
    compute_payload_hash,
    get_binding,
    strip_binding,
    verify_binding,
    with_binding,
)

ROOM = "11111111-1111-1111-1111-111111111111"


class BindingTests(unittest.TestCase):
    def test_hash_covers_executed_command_not_param_spelling(self):
        # 'lock' và 'locked' cùng dịch thành door:locked => cùng hash (cái thực thi mới quan trọng).
        h1, _ = compute_payload_hash(ROOM, "set_door", {"state": "lock"})
        h2, _ = compute_payload_hash(ROOM, "set_door", {"state": "locked"})
        self.assertEqual(h1, h2)

    def test_different_executed_command_changes_hash(self):
        h_lock, _ = compute_payload_hash(ROOM, "set_door", {"state": "locked"})
        h_open, _ = compute_payload_hash(ROOM, "set_door", {"state": "unlocked"})
        self.assertNotEqual(h_lock, h_open)

    def test_with_binding_roundtrip_and_strip(self):
        params = with_binding(ROOM, "set_fan", {"state": "on"}, "LECTURE", "v1")
        b = get_binding(params)
        self.assertEqual(b["expected_mode"], "LECTURE")
        self.assertEqual(b["expected_state_version"], "v1")
        self.assertNotIn(BINDING_KEY, strip_binding(params))
        ok, why = verify_binding(ROOM, "set_fan", params)
        self.assertTrue(ok)
        self.assertEqual(why, "ok")

    def test_mutation_after_proposal_detected(self):
        params = with_binding(ROOM, "set_door", {"state": "locked"}, "EXAM", "v1")
        params["state"] = "unlocked"  # state-substitution sau khi đề xuất
        ok, why = verify_binding(ROOM, "set_door", params)
        self.assertFalse(ok)
        self.assertEqual(why, "payload_mutated_after_proposal")

    def test_tool_swap_detected(self):
        params = with_binding(ROOM, "set_fan", {"state": "on"}, "LECTURE", None)
        ok, _ = verify_binding(ROOM, "set_door", params)
        self.assertFalse(ok)

    def test_client_hash_must_match_what_operator_saw(self):
        params = with_binding(ROOM, "set_door", {"state": "locked"}, "EXAM", None)
        shown, _ = compute_payload_hash(ROOM, "set_door", params)
        self.assertTrue(verify_binding(ROOM, "set_door", params, client_hash=shown)[0])
        ok, why = verify_binding(ROOM, "set_door", params, client_hash="deadbeef")
        self.assertFalse(ok)
        self.assertEqual(why, "payload_differs_from_what_operator_saw")

    def test_legacy_unbound_recommendation_still_allowed(self):
        ok, why = verify_binding(ROOM, "set_fan", {"state": "on"})
        self.assertTrue(ok)
        self.assertEqual(why, "legacy_unbound")

    def test_alert_content_is_bound(self):
        params = with_binding(ROOM, "send_alert", {"level": "info", "message": "ok"}, None, None)
        params["message"] = "evil"
        self.assertFalse(verify_binding(ROOM, "send_alert", params)[0])


if __name__ == "__main__":
    unittest.main()
