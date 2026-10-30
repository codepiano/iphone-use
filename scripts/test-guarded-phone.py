#!/usr/bin/env python3
"""Device-free orchestration tests; planner integration runs when installed."""
import copy
import fcntl
import json
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

import guarded_phone as gp


def screen(label="Ready", token=None):
    return {"screen": {"width": 430, "height": 932}, "snapshot": token or label,
            "elements": [{"kind": "Application", "label": "Fixture", "rect": [0, 0, 430, 932]},
                         {"kind": "Button", "label": label, "rect": [100, 200, 120, 44]},
                         {"kind": "TextField", "label": "Input", "focused": True, "rect": [10, 100, 200, 44]}]}


class Clock:
    def __init__(self):
        self.now, self.sleeps = 1000., []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class Phone:
    def __init__(self):
        self.current, self.posts, self.fail, self.reads = screen(), [], None, 0
        self.after = screen("Done")
        self.drivable = True

    def request(self, method, path, body=None, **kwargs):
        if path == "/agent/status":
            return {"drivable": self.drivable}
        if method == "GET":
            self.reads += 1
            return copy.deepcopy(self.current)
        self.posts.append(copy.deepcopy(body))
        self.current = copy.deepcopy(self.after)
        if self.fail:
            raise self.fail
        return {"ok": True, "settle": {"settled": False}}


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock, self.phone = Clock(), Phone()
        self.policy = gp.Pacing(action_gap_s=2, action_jitter_s=0, item_gap_s=10,
                               items_per_round=2, round_rest_s=30, observe_timeout_s=3, poll_s=1)
        self.session = gp.GuardedPhone(self.phone, self.tmp.name, "Fixture", self.policy,
            clock=self.clock.time, sleep=self.clock.sleep, entropy=lambda _: 42, monotonic=self.clock.time)

    def step(self, item="one", before="Ready", after="Done", step_id="insert"):
        return self.session.step(item, {"kind": "text", "text": "测试"},
            step_id=step_id, before=gp.Expectation((before,)), after=gp.Expectation((after,)))

    def journal(self):
        return json.loads((Path(self.tmp.name) / "checkpoint.json").read_text())

    def test_ack_does_not_replace_independent_verification(self):
        self.phone.after = screen("Still loading")
        with self.assertRaises(gp.Paused):
            self.step()
        self.assertEqual(len(self.phone.posts), 1)
        self.assertEqual(self.journal()["reason"], "postcondition_timeout")
        with self.assertRaises(gp.Paused):
            self.step()
        self.assertEqual(len(self.phone.posts), 1)

    def test_unknown_delivery_and_new_process_cannot_replay(self):
        self.phone.fail = TimeoutError("private text must not be journaled")
        with self.assertRaises(TimeoutError):
            self.step()
        restarted = gp.GuardedPhone(self.phone, self.tmp.name, "Fixture", self.policy)
        with self.assertRaises(gp.Paused):
            restarted.step("one", {"kind": "text", "text": "again"},
                step_id="insert", before=gp.Expectation(("Done",)), after=gp.Expectation(("Done",)))
        self.assertEqual(len(self.phone.posts), 1)
        self.assertNotIn("private", json.dumps(self.journal()))

    def test_interruption_after_dispatch_persists_pause(self):
        self.phone.fail = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.step()
        self.assertEqual(self.journal()["phase"], "paused")
        self.assertEqual(len(self.phone.posts), 1)

    def test_challenge_stops_before_input_and_latches(self):
        self.phone.current = screen("请完成安全验证")
        with self.assertRaises(gp.Paused):
            self.step()
        self.assertEqual(self.phone.posts, [])
        self.assertEqual(self.journal()["reason"], "verification_or_rate_limit_visible")

    def test_empty_results_after_write_stop_without_replay(self):
        self.phone.after = screen("暂无搜索结果")
        with self.assertRaises(gp.Paused):
            self.step()
        self.assertEqual(len(self.phone.posts), 1)
        self.assertEqual(self.journal()["reason"], "empty_result_requires_review")

    def test_app_change_stops(self):
        self.phone.current["elements"][0]["label"] = "Another App"
        with self.assertRaises(gp.Paused):
            self.step()
        self.assertFalse(self.phone.posts)

    def test_unreadable_screen_stops(self):
        self.phone.current["elements"] = []
        with self.assertRaises(gp.Paused):
            self.step()
        self.assertFalse(self.phone.posts)

    def test_text_requires_one_focused_nonsecure_field(self):
        self.phone.current["elements"][2]["kind"] = "SecureTextField"
        with self.assertRaises(gp.Paused):
            self.step()
        self.assertFalse(self.phone.posts)

    def test_precondition_failure_never_sends(self):
        with self.assertRaises(gp.Paused):
            self.step(before="Wrong page")
        self.assertFalse(self.phone.posts)

    def test_live_countdown_does_not_block_page_or_item_verification(self):
        original = self.phone.request
        def request(method, path, body=None, **kwargs):
            result = original(method, path, body, **kwargs)
            if path == "/agent/elements":
                result["snapshot"] = str(self.phone.reads)
                result["elements"].append({"kind": "StaticText", "label":
                    f"Countdown {self.phone.reads}", "rect": [10, 500, 80, 20]})
            return result
        self.phone.request = request
        self.step()
        self.session.finish_item("one", verified=gp.Expectation(("Done",)))
        self.assertEqual(len(self.phone.posts), 1)
        self.assertEqual(self.journal()["phase"], "ready")
        self.assertEqual(len(self.journal()["completed"]), 1)
        self.assertEqual(self.phone.reads, 6)  # fresh pre, post and item reads

    def test_moving_tap_target_never_dispatches_despite_stable_page_anchor(self):
        self.phone.current["elements"].append({"kind": "Button", "label": "Target",
                                               "rect": [10, 300, 100, 40]})
        original = self.phone.request
        def request(method, path, body=None, **kwargs):
            result = original(method, path, body, **kwargs)
            if path == "/agent/elements":
                result["elements"][-1]["rect"][0] += self.phone.reads
            return result
        self.phone.request = request
        with self.assertRaises(gp.Paused):
            self.session.step("one", {"kind": "tap", "locator": {"label": "Target"}},
                step_id="tap", before=gp.Expectation(("Ready",)), after=gp.Expectation(("Done",)))
        self.assertFalse(self.phone.posts)
        self.assertEqual(self.journal()["reason"], "postcondition_timeout")

    def test_moving_anchor_or_changing_viewport_cannot_confirm_page(self):
        for variant in ("anchor", "viewport"):
            original = Phone().request
            counter = [0]
            def request(method, path, body=None, **kwargs):
                result = original(method, path, body, **kwargs)
                if path == "/agent/elements":
                    counter[0] += 1
                    if variant == "anchor":
                        result["elements"][1]["rect"][0] += counter[0]
                    else:
                        result["screen"]["width"] += counter[0]
                return result
            self.phone.request = request
            with tempfile.TemporaryDirectory() as tmp:
                session = gp.GuardedPhone(self.phone, tmp, "Fixture", self.policy,
                    clock=self.clock.time, sleep=self.clock.sleep, monotonic=self.clock.time)
                with self.assertRaises(gp.Paused), session._locked():
                    session._wait(gp.Expectation(("Ready",)))

    def test_disappearing_anchor_resets_the_consecutive_read_requirement(self):
        self.session.pacing = gp.Pacing(observe_timeout_s=6)
        original = self.phone.request
        def request(method, path, body=None, **kwargs):
            result = original(method, path, body, **kwargs)
            if path == "/agent/elements" and self.phone.reads == 2:
                result["elements"][1]["label"] = "Loading"
            return result
        self.phone.request = request
        with self.session._locked():
            self.session._wait(gp.Expectation(("Ready",)))
        self.assertEqual(self.phone.reads, 4)
        self.assertFalse(self.phone.posts)

    def test_live_content_does_not_hide_a_later_challenge(self):
        original = self.phone.request
        def request(method, path, body=None, **kwargs):
            result = original(method, path, body, **kwargs)
            if path == "/agent/elements" and self.phone.reads == 2:
                result["elements"].append({"kind": "StaticText", "label": "请完成安全验证"})
            return result
        self.phone.request = request
        with self.assertRaises(gp.Paused):
            self.step()
        self.assertEqual(self.journal()["reason"], "verification_or_rate_limit_visible")
        self.assertFalse(self.phone.posts)

    def test_absent_condition_is_not_ignored_on_an_otherwise_stable_page(self):
        self.phone.current["elements"].append({"kind": "StaticText", "label": "Wrong page"})
        with self.assertRaises(gp.Paused), self.session._locked():
            self.session._wait(gp.Expectation(("Ready",), ("Wrong page",)))
        self.assertFalse(self.phone.posts)

    def test_late_matching_read_does_not_escape_observation_deadline(self):
        original = self.phone.request
        def request(method, path, body=None, **kwargs):
            if path == "/agent/elements":
                self.assertLessEqual(kwargs["timeout"], self.policy.observe_timeout_s)
                self.clock.now += 4
            return original(method, path, body, **kwargs)
        self.phone.request = request
        with self.assertRaises(gp.Paused):
            self.step()
        self.assertEqual(self.journal()["reason"], "postcondition_timeout")
        self.assertFalse(self.phone.posts)

    def test_pacing_item_checkpoints_round_rest_and_dedup(self):
        self.step()
        self.phone.after = screen("Saved")
        t = self.clock.time()
        self.step(before="Done", after="Saved", step_id="save")
        self.assertGreaterEqual(self.clock.time() - t, 4)  # gap + fresh pre/post reads
        self.session.finish_item("one", verified=gp.Expectation(("Saved",)))
        self.phone.current, self.phone.after = screen(), screen("Done")
        t = self.clock.time()
        self.step("two")
        self.assertGreaterEqual(self.clock.time() - t, 12)
        self.session.finish_item("two", verified=gp.Expectation(("Done",)))
        state = self.journal()
        self.assertGreaterEqual(state["not_before"] - self.clock.time(), 40)
        self.assertNotIn("one", json.dumps(state))
        with self.assertRaises(gp.Paused):
            self.step("one")
        self.assertEqual(len(self.phone.posts), 3)

    def test_cannot_skip_unverified_item(self):
        self.step()
        with self.assertRaises(gp.Paused):
            self.step("two", before="Done")
        self.assertEqual(len(self.phone.posts), 1)

    def test_verified_step_is_durable_before_caller_advances(self):
        self.step()
        restarted = gp.GuardedPhone(self.phone, self.tmp.name, "Fixture", self.policy)
        with self.assertRaises(gp.Paused):
            restarted.step("one", {"kind": "text", "text": "again"}, step_id="insert",
                before=gp.Expectation(("Done",)), after=gp.Expectation(("Done",)))
        self.assertEqual(len(self.phone.posts), 1)

    def test_action_budget_stops_without_another_mutation(self):
        self.step()
        self.session.pacing = gp.Pacing(actions_per_item=1)
        with self.assertRaises(gp.Paused):
            self.step(before="Done", step_id="second")
        self.assertEqual(len(self.phone.posts), 1)
        self.assertEqual(self.journal()["reason"], "item_action_budget_exhausted")

    def test_second_process_lock_is_not_a_queue_of_mutations(self):
        with open(Path(self.tmp.name) / "operation.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with self.assertRaises(gp.Paused):
                self.step()
        self.assertFalse(self.phone.posts)

    def test_checkpoint_is_written_before_transport(self):
        original = self.phone.request
        def request(method, path, body=None, **kwargs):
            if method == "POST":
                self.assertEqual(self.journal()["phase"], "dispatching")
            return original(method, path, body, **kwargs)
        self.phone.request = request
        self.step()

    def test_rebinding_a_checkpoint_cannot_drive_another_app(self):
        self.step()
        other = gp.GuardedPhone(self.phone, self.tmp.name, "Different")
        with self.assertRaises(gp.Paused):
            other.step("two", {}, step_id="insert", before=gp.Expectation(("Done",)), after=gp.Expectation(("Done",)))
        self.assertEqual(len(self.phone.posts), 1)

    def test_no_pre_or_postcondition_is_invalid(self):
        with self.assertRaises(ValueError):
            gp.Expectation(())
        with self.assertRaises(ValueError):
            self.session.step("one", {}, step_id="invalid", before=None, after=gp.Expectation(("Done",)))
        self.assertFalse(self.phone.posts)


try:
    import pointer_trajectory
    HAS_PLANNER = hasattr(pointer_trajectory, "generate_tap")
except ImportError:
    HAS_PLANNER = False


@unittest.skipUnless(HAS_PLANNER, "external pointer-trajectory 0.4 not installed")
class PlannerIntegrationTests(unittest.TestCase):
    def test_real_taps_vary_and_stay_in_button_without_approach_path(self):
        outputs = [gp.plan_touch({"kind": "tap", "locator": {"label": "Ready"}}, screen(), seed)[0]
                   for seed in range(30)]
        landings, durations = set(), set()
        for action in outputs:
            path = action["path"]
            self.assertEqual(action["element"], 1)
            self.assertEqual(action["snapshot"], "Ready")
            self.assertEqual(path["viewport"], {"width": 430, "height": 932})
            self.assertEqual(path["samples"][0]["t_ms"], 0)
            self.assertTrue(all(118 <= s["x"] <= 201 and 207 <= s["y"] <= 236 for s in path["samples"]))
            landings.add((path["samples"][0]["x"], path["samples"][0]["y"]))
            durations.add(path["samples"][-1]["t_ms"])
        self.assertGreater(len(landings), 10)
        self.assertGreater(len(durations), 5)

    def test_real_scroll_keeps_every_sample_and_hold(self):
        request = {"kind": "scroll", "start": {"x": 215, "y": 700}, "end": {"x": 215, "y": 300},
                   "options": {"duration_ms": 431, "hold_before_ms": 30, "hold_after_ms": 70}}
        action, _ = gp.plan_touch(request, screen(), 4294967295)
        expected = pointer_trajectory.generate_gesture({**request["options"], "start": request["start"],
            "end": request["end"], "profile": "scroll", "viewport": screen()["screen"], "seed": 4294967295})
        self.assertEqual(action["path"]["samples"], expected["samples"])
        self.assertEqual(action["path"]["hold_before_ms"], 30)
        self.assertEqual(action["path"]["hold_after_ms"], 70)
        self.assertGreater(len(action["path"]["samples"]), 16)

    def test_ambiguous_or_unsafe_targets_are_not_retargeted(self):
        value = screen()
        value["elements"].append(copy.deepcopy(value["elements"][1]))
        with self.assertRaises(gp.Paused):
            gp.plan_touch({"kind": "tap", "locator": {"label": "Ready"}}, value, 1)
        with self.assertRaises(ValueError):
            gp.plan_touch({"kind": "tap", "locator": {"label": "Ready"}, "options": {"viewport": {}}}, screen(), 1)


class TransportTests(unittest.TestCase):
    def test_http_is_loopback_only_and_credentials_cannot_be_in_url(self):
        for url in ("http://example.com", "https://user:password@example.com", "http://127.0.0.1/agent"):
            with self.assertRaises(ValueError):
                gp.HttpPhone(url, "token", "owner")

    def test_mutation_redirect_and_lost_reply_are_never_reissued(self):
        for mode in ("redirect", "lost_reply"):
            seen = []
            class Handler(BaseHTTPRequestHandler):
                def do_POST(self):
                    self.rfile.read(int(self.headers.get("Content-Length", 0)))
                    seen.append((self.command, self.path))
                    if mode == "lost_reply":
                        self.close_connection = True
                        return
                    self.send_response(302)
                    self.send_header("Location", "/unexpected")
                    self.send_header("Content-Length", "0")
                    self.end_headers()

                def do_GET(self):
                    seen.append((self.command, self.path))
                    self.send_response(200)
                    self.end_headers()

                def log_message(self, *args):
                    pass
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                phone = gp.HttpPhone(f"http://127.0.0.1:{server.server_port}", "fixture-token", "fixture-owner")
                with self.assertRaises((gp.Paused, OSError, http.client.RemoteDisconnected)):
                    phone.request("POST", "/agent/input?return=delta", {"type": "fixture"})
                self.assertEqual(seen, [("POST", "/agent/input?return=delta")])
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()
