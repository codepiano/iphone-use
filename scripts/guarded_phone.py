#!/usr/bin/env python3
"""Opt-in, checkpointed phone steps using the external pointer-trajectory planner.

No private planner source is bundled. Import this module from an authorized task;
there is deliberately no unattended list runner or automatic resume/retry.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request


class Paused(RuntimeError):
    """The task needs an explicit decision; no next mutation is allowed."""


@dataclass(frozen=True)
class Pacing:
    # Conservative engineering defaults, not measured human behaviour or an
    # application-approved rate. Completion/observations can only slow them down.
    action_gap_s: float = 2.0
    action_jitter_s: float = 1.5
    item_gap_s: float = 10.0
    items_per_round: int = 3
    round_rest_s: float = 30.0
    actions_per_item: int = 12
    observe_timeout_s: float = 20.0
    poll_s: float = 1.0

    def __post_init__(self):
        for name in ("action_gap_s", "action_jitter_s", "item_gap_s", "round_rest_s",
                     "observe_timeout_s", "poll_s"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid pacing: {name}")
        if self.action_gap_s < 0.1 or self.poll_s < 0.1 or not 1 <= self.observe_timeout_s <= 60:
            raise ValueError("positive bounded action/read intervals required")
        for name in ("items_per_round", "actions_per_item"):
            if type(getattr(self, name)) is not int or not 1 <= getattr(self, name) <= 100:
                raise ValueError(f"invalid pacing: {name}")


@dataclass(frozen=True)
class Expectation:
    """Exact visible label/value anchors. At least one positive anchor is required."""
    present: tuple[str, ...]
    absent: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.present, (tuple, list)) or not isinstance(self.absent, (tuple, list)) or not self.present or any(not isinstance(x, str) or not x for x in (*self.present, *self.absent)):
            raise ValueError("at least one explicit nonempty postcondition anchor is required")

    def matches(self, screen):
        values = {str(row.get(key, "")) for row in screen["elements"]
                  if row.get("visible") is not False for key in ("label", "value")}
        return all(x in values for x in self.present) and all(x not in values for x in self.absent)


class HttpPhone:
    """Only the daemon's guarded agent API, never a raw Runner/proxy endpoint."""
    def __init__(self, url, token, owner):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("expected a daemon origin without embedded credentials")
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise ValueError("expected a daemon origin")
        if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError("remote daemon access requires HTTPS")
        if not token or not owner:
            raise ValueError("explicit token and unique owner required")
        self.url, self.token, self.owner = url.rstrip("/"), token, owner
        # No automatic redirects: never forward a bearer to another origin or
        # turn a redirected mutation into a second request.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, body=None, *, timeout=60):
        if (method, path) not in (("GET", "/agent/status"), ("GET", "/agent/elements"),
                                 ("POST", "/agent/owner"), ("POST", "/agent/input?return=delta")):
            raise ValueError("unsupported guarded endpoint")
        request = urllib.request.Request(self.url + path, method=method,
            data=None if body is None else json.dumps(body, allow_nan=False).encode(),
            headers={"Authorization": "Bearer " + self.token, "X-Phone-Control": "1",
                     "X-Phone-Owner": self.owner, "Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=min(timeout, 60)) as response:
                status, payload = response.status, response.read(4_000_001)
        except urllib.error.HTTPError as response:
            status, payload = response.code, response.read(4_000_001)
        if len(payload) > 4_000_000:
            raise Paused("response_too_large")
        try:
            result = json.loads(payload)
        except (ValueError, UnicodeError) as error:
            raise Paused("invalid_response") from error
        if not isinstance(result, dict):
            raise Paused("invalid_response")
        if status >= 400 or result.get("ok") is False:
            # Keep the server body out of logs: it can contain entered text.
            raise Paused("daemon_refused_or_delivery_unknown")
        return result


def _planner():
    try:
        import pointer_trajectory as planner
    except ImportError as error:
        raise RuntimeError("Install external pointer-trajectory >=0.4,<0.5 in a dedicated environment") from error
    if not all(hasattr(planner, name) for name in ("generate_tap", "validate_tap", "generate_gesture", "validate_gesture")):
        raise RuntimeError("pointer-trajectory 0.4 tap API required")
    if not getattr(planner, "__version__", "").startswith("0.4."):
        raise RuntimeError("validated adapter contract requires pointer-trajectory >=0.4,<0.5")
    return planner


def plan_touch(request, screen, seed=None):
    """Plan one contact from a fresh full screen; callers cannot override its size/seed."""
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    planner = _planner()
    viewport = screen["screen"]
    viewport = {key: int(viewport[key]) for key in ("width", "height")
                if type(viewport[key]) in (int, float) and math.isfinite(viewport[key]) and viewport[key] == int(viewport[key])}
    if len(viewport) != 2:
        raise Paused("invalid_logical_viewport")
    seed = secrets.randbits(32) if seed is None else seed
    kind = request.get("kind")
    allowed = {"kind", "locator", "options"} if kind == "tap" else {"kind", "start", "end", "options"}
    if set(request) - allowed:
        raise ValueError("unknown touch request field")
    options = dict(request.get("options", {}))
    if any(key in options for key in ("viewport", "seed", "target", "start", "end", "profile")):
        raise ValueError("geometry, viewport, profile and seed are managed by the adapter")
    element = None
    if kind == "tap":
        locator = request.get("locator")
        if not isinstance(locator, dict) or not locator or set(locator) - {"label", "identifier", "kind"}:
            raise ValueError("tap requires an exact label/identifier locator")
        if not (locator.get("label") or locator.get("identifier")) or any(not isinstance(v, str) or not v for v in locator.values()):
            raise ValueError("tap requires an exact label/identifier locator")
        matches = [(i, row) for i, row in enumerate(screen["elements"])
                   if all(row.get(key) == value for key, value in locator.items())]
        if len(matches) != 1:
            raise Paused("target_missing_or_ambiguous")
        element, row = matches[0]
        if row.get("visible") is False or row.get("enabled") is False:
            raise Paused("target_not_interactable")
        x, y, width, height = row["rect"]
        plan = planner.generate_tap({**options, "viewport": viewport, "seed": seed,
            "target": {"x": x, "y": y, "width": width, "height": height}})
        planner.validate_tap(plan)
        path = {"viewport": plan["viewport"], "samples": plan["samples"]}
        if plan["duration_ms"] < 10:
            raise ValueError("Runner timed contacts must last at least 10 ms")
    elif kind in ("drag", "scroll", "flick"):
        plan = planner.generate_gesture({**options, "viewport": viewport, "seed": seed,
            "start": request["start"], "end": request["end"], "profile": kind})
        planner.validate_gesture(plan)
        path = {key: plan[key] for key in ("viewport", "samples", "hold_before_ms", "hold_after_ms")}
        if plan["total_duration_ms"] < 10:
            raise ValueError("Runner timed contacts must last at least 10 ms")
    else:
        raise ValueError("expected tap, drag, scroll or flick")
    action = {"type": "touch_path", "path": path, "snapshot": screen["snapshot"]}
    if element is not None:
        action["element"] = element
    return action, seed


class GuardedPhone:
    """Serial, journaled steps. Unknown deliveries and failed checks latch paused.

    Every process sharing a task must use the same state directory. The daemon's
    owner/lease/privacy checks remain authoritative across different tasks.
    """
    BLOCKERS = ("操作过于频繁", "访问过于频繁", "请求过于频繁", "安全验证", "请完成验证",
                "请输入验证码", "拖动滑块", "异常访问", "验证码", "captcha", "too many requests",
                "verify you are human", "unusual activity")

    def __init__(self, phone, state_dir, app_label, pacing=None, *, clock=time.time,
                 sleep=time.sleep, entropy=secrets.randbits, monotonic=time.monotonic):
        if not isinstance(app_label, str) or not app_label:
            raise ValueError("an exact application root label is required")
        self.phone, self.app_label = phone, app_label
        self.pacing, self.clock, self.sleep, self.entropy = pacing or Pacing(), clock, sleep, entropy
        self.monotonic = monotonic
        self.directory = Path(state_dir)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.directory.is_symlink():
            raise ValueError("state directory must not be a symlink")
        self.journal = self.directory / "checkpoint.json"
        identity = json.dumps([app_label, getattr(phone, "url", "injected"), getattr(phone, "owner", "injected")])
        self.binding = hashlib.sha256(identity.encode()).hexdigest()
        self.state = None

    @contextmanager
    def _locked(self):
        fd = os.open(self.directory / "operation.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self.journal.is_symlink():
                raise ValueError("checkpoint must not be a symlink")
            self.state = json.loads(self.journal.read_text()) if self.journal.exists() else {
                "version": 2, "phase": "ready", "active": None, "actions": 0,
                "completed": [], "verified_steps": [], "not_before": 0, "binding": self.binding}
            if self.state.get("version") != 2:
                raise Paused("unsupported_checkpoint")
            if self.state.get("binding") != self.binding:
                raise Paused("checkpoint_belongs_to_another_task")
            if self.state["phase"] != "ready":
                raise Paused("checkpoint_paused_requires_explicit_resume")
            yield
        except BlockingIOError as error:
            raise Paused("task_busy") from error
        finally:
            self.state = None
            os.close(fd)

    def _save(self):
        temp = self.directory / "checkpoint.tmp"
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(self.state, stream, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, self.journal)
        directory_fd = os.open(self.directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    def _stop(self, reason):
        self.state.update(phase="paused", reason=reason)
        self._save()
        raise Paused(reason)

    def _read(self, timeout):
        screen = self.phone.request("GET", "/agent/elements", timeout=timeout)
        rows = screen.get("elements")
        if not isinstance(rows, list) or not rows or not screen.get("snapshot"):
            self._stop("empty_or_unreadable_screen")
        if screen.get("partial") or screen.get("stale") or screen.get("ax_stats", {}).get("truncated"):
            self._stop("partial_or_stale_screen")
        if rows[0].get("kind") != "Application" or rows[0].get("label") != self.app_label:
            self._stop("application_changed")
        if screen.get("alert"):
            self._stop("alert_requires_review")
        for row in rows:
            if row.get("visible") is False:
                continue
            text = " ".join(str(row.get(key, "")) for key in ("label", "value")).casefold()
            if any(word in text for word in self.BLOCKERS):
                self._stop("verification_or_rate_limit_visible")
            if any(word in text for word in ("暂无搜索结果", "无搜索结果", "没有找到相关结果", "no results found")):
                self._stop("empty_result_requires_review")
        return screen

    @staticmethod
    def _observation_key(screen, expectation, request):
        # A countdown or carousel elsewhere must not prevent a stable page
        # check. Keep the anchors' actual geometry/state, and the intended
        # tap target or text focus, stable across two independent fresh reads.
        # The latest full snapshot still binds the eventual daemon dispatch.
        keys = ("kind", "label", "value", "identifier", "rect", "visible",
                "enabled", "selected", "focused")
        def signature(rows):
            return sorted(json.dumps({k: row[k] for k in keys if k in row},
                                     sort_keys=True, allow_nan=False) for row in rows)
        rows = [row for row in screen["elements"] if row.get("visible") is not False]
        anchors = [row for row in rows if any(str(row.get(k, "")) in expectation.present
                                             for k in ("label", "value"))]
        targets = []
        if request and request.get("kind") == "tap":
            locator = request.get("locator")
            if isinstance(locator, dict) and locator:
                targets = [row for row in screen["elements"]
                           if all(row.get(k) == v for k, v in locator.items())]
        elif request and request.get("kind") == "text":
            targets = [row for row in rows if row.get("focused") is True]
        return (json.dumps(screen["screen"], sort_keys=True, allow_nan=False),
                signature(anchors), signature(targets))

    def _wait(self, expectation, request=None):
        if not isinstance(expectation, Expectation):
            raise ValueError("explicit Expectation required")
        deadline, previous = self.monotonic() + self.pacing.observe_timeout_s, None
        while True:
            remaining = deadline - self.monotonic()
            if remaining <= 0:
                self._stop("postcondition_timeout")
            screen = self._read(remaining)
            if self.monotonic() > deadline:
                self._stop("postcondition_timeout")
            matched = expectation.matches(screen)
            # Unrelated live text can change; relevant page anchors and the
            # intended target must agree. Each read still checks all blockers.
            current = self._observation_key(screen, expectation, request) if matched else None
            if matched and current == previous:
                return screen
            previous = current
            if self.monotonic() + self.pacing.poll_s > deadline:
                self._stop("postcondition_timeout")
            self.sleep(self.pacing.poll_s)

    def _pace(self):
        delay = self.state["not_before"] - self.clock()
        if delay > 60:
            self._stop("clock_shift_or_excessive_delay")
        if delay > 0:
            self.sleep(delay)

    @staticmethod
    def _item_key(item):
        if not isinstance(item, str) or not item or len(item) > 1000:
            raise ValueError("nonempty bounded item identity required")
        return hashlib.sha256(item.encode()).hexdigest()

    def step(self, item, request, *, step_id, before, after):
        """Execute at most ONE action; on error the caller must not replay it."""
        key = self._item_key(item)
        step_key = self._item_key(step_id)
        if not isinstance(before, Expectation) or not isinstance(after, Expectation):
            raise ValueError("explicit precondition and postcondition required")
        with self._locked():
            if key in self.state["completed"]:
                raise Paused("item_already_completed")
            if self.state["active"] not in (None, key):
                self._stop("previous_item_not_verified")
            if step_key in self.state["verified_steps"]:
                raise Paused("step_already_verified")
            if self.state["actions"] >= self.pacing.actions_per_item:
                self._stop("item_action_budget_exhausted")
            try:
                self._pace()
                status = self.phone.request("GET", "/agent/status")
                if status.get("drivable") is not True:
                    self._stop("phone_not_drivable")
                # Claim without UI input before the fresh reads, so their
                # cached baseline belongs to this exact owner epoch.
                self.phone.request("POST", "/agent/owner", {"claim": True})
                screen = self._wait(before, request)
                seed = None
                if request.get("kind") in ("tap", "drag", "scroll", "flick"):
                    action, seed = plan_touch(request, screen, self.entropy(32))
                    action["context"] = {"application": self.app_label,
                        "present": list(before.present), "absent": list(before.absent)}
                elif request.get("kind") == "text":
                    if set(request) - {"kind", "text"} or not isinstance(request.get("text"), str) or not 1 <= len(request["text"]) <= 200:
                        raise ValueError("one short text insertion required; replacement is not implicit")
                    focused = [row for row in screen["elements"] if row.get("focused") is True
                               and row.get("kind") in ("TextField", "SearchField", "TextView")]
                    if len(focused) != 1:
                        self._stop("text_focus_not_unique")
                    action = {"type": "text", "text": request["text"], "clear": False}
                else:
                    raise ValueError("unsupported guarded step")
                # Durable before the POST: an interruption at any point after
                # this write requires review, even if transport never replied.
                self.state.update(phase="dispatching", active=key, seed=seed, pending_step=step_key)
                self._save()
                receipt = self.phone.request("POST", "/agent/input?return=delta", action)
                if receipt.get("ok") is not True or receipt.get("outcome") not in (None, "applied", "completed"):
                    self._stop("delivery_not_confirmed")
                self.state.update(phase="verifying")
                self._save()
                self._wait(after)
                gap = self.pacing.action_gap_s + self.pacing.action_jitter_s * self.entropy(32) / 2**32
                self.state["verified_steps"].append(step_key)
                self.state.update(phase="ready", actions=self.state["actions"] + 1,
                                  not_before=self.clock() + gap, pending_step=None)
                self._save()
                return {"verified": True, "seed": seed}
            except BaseException:
                # KeyboardInterrupt/cancellation is a checkpoint too. Never
                # persist exception strings (network errors can contain secrets).
                if self.state["phase"] != "paused":
                    self.state.update(phase="paused", reason="step_interrupted_or_failed")
                    self._save()
                raise

    def finish_item(self, item, *, verified):
        """Caller-supplied business postcondition, independently read again."""
        key = self._item_key(item)
        with self._locked():
            if self.state["active"] != key:
                raise Paused("item_not_active")
            try:
                self._wait(verified)
                self.state["completed"].append(key)
                gap = self.pacing.item_gap_s
                if len(self.state["completed"]) % self.pacing.items_per_round == 0:
                    gap += self.pacing.round_rest_s
                self.state.update(active=None, actions=0, seed=None, verified_steps=[],
                                  not_before=max(self.state["not_before"], self.clock() + gap))
                self._save()
            except BaseException:
                if self.state["phase"] != "paused":
                    self.state.update(phase="paused", reason="item_verification_failed")
                    self._save()
                raise

    # There is intentionally no unpause API: a controller must review the
    # actual result and archive the checkpoint before starting an explicit new
    # task. Completed items remain a durable deduplication record.


def main():
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("step", "finish"))
    parser.add_argument("--state", required=True, help="explicit private task checkpoint directory")
    parser.add_argument("--app", required=True, help="exact accessibility Application label")
    parser.add_argument("--item", required=True, help="stable item identity; stored only as SHA-256")
    args = parser.parse_args()
    try:
        spec = json.load(sys.stdin)
        client = HttpPhone(os.environ.get("IPHONE_USE_URL", "http://127.0.0.1:44321"),
                           os.environ["IPHONE_USE_AGENT_TOKEN"], os.environ["IPHONE_USE_OWNER"])
        session = GuardedPhone(client, args.state, args.app)
        def condition(key):
            value = spec[key]
            if not isinstance(value, dict) or set(value) - {"present", "absent"}:
                raise ValueError("expected present/absent anchors")
            return Expectation(tuple(value["present"]), tuple(value.get("absent", ())))
        if args.command == "step":
            result = session.step(args.item, spec["request"], step_id=spec["step_id"],
                                  before=condition("before"), after=condition("after"))
        else:
            session.finish_item(args.item, verified=condition("verified"))
            result = {"verified": True, "item_finished": True}
        print(json.dumps(result))
    except Exception:
        # Details stay in reason-coded private checkpoints, never dump payloads,
        # environment, HTTP errors or text input to a shared terminal.
        print(json.dumps({"ok": False, "paused": True, "hint": "Inspect checkpoint and actual phone state; do not replay"}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
