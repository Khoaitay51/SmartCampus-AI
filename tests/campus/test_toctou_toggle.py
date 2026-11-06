"""Unit tests cho SAFETY_TOCTOU_BINDING_ENABLED ở phía AI Backend (Consent Hash + Edge Payload)."""
import os
import unittest
from unittest import mock

from app.campus.binding import compute_payload_hash, verify_binding, with_binding

ROOM = "11111111-1111-1111-1111-111111111111"
ENV = "SAFETY_TOCTOU_BINDING_ENABLED"


class BackendToctouToggleTests(unittest.TestCase):
    def test_verify_binding_blocks_mutation_when_enabled(self):
        params = with_binding(ROOM, "set_door", {"state": "locked"}, "EXAM", "v1")
        params["state"] = "unlocked"  # post-proposal state substitution (Loopjacking)
        with mock.patch.dict(os.environ, {ENV: "true"}):
            ok, reason = verify_binding(ROOM, "set_door", params)
        self.assertFalse(ok)
        self.assertEqual(reason, "payload_mutated_after_proposal")

    def test_verify_binding_bypasses_mutation_when_disabled(self):
        params = with_binding(ROOM, "set_door", {"state": "locked"}, "EXAM", "v1")
        params["state"] = "unlocked"
        with mock.patch.dict(os.environ, {ENV: "false"}):
            ok, reason = verify_binding(ROOM, "set_door", params)
        self.assertTrue(ok)
        self.assertEqual(reason, "toctou_binding_disabled")

    def test_verify_binding_bypasses_client_hash_mismatch_when_disabled(self):
        params = with_binding(ROOM, "set_door", {"state": "locked"}, "EXAM", "v1")
        with mock.patch.dict(os.environ, {ENV: "false"}):
            ok, reason = verify_binding(
                ROOM, "set_door", params, client_hash="tampered_ui_hash"
            )
        self.assertTrue(ok)
        self.assertEqual(reason, "toctou_binding_disabled")

    def test_verify_binding_blocks_client_hash_mismatch_when_enabled(self):
        params = with_binding(ROOM, "set_door", {"state": "locked"}, "EXAM", "v1")
        with mock.patch.dict(os.environ, {ENV: "true"}):
            ok, reason = verify_binding(
                ROOM, "set_door", params, client_hash="tampered_ui_hash"
            )
        self.assertFalse(ok)
        self.assertEqual(reason, "payload_differs_from_what_operator_saw")

    def test_valid_binding_passes_when_enabled(self):
        params = with_binding(ROOM, "set_fan", {"state": "on"}, "LECTURE", "v1")
        shown_hash, _ = compute_payload_hash(ROOM, "set_fan", params)
        with mock.patch.dict(os.environ, {ENV: "true"}):
            ok, reason = verify_binding(
                ROOM, "set_fan", params, client_hash=shown_hash
            )
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")


if __name__ == "__main__":
    unittest.main()
