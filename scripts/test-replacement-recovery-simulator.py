#!/usr/bin/env python3
"""Selected-field recovery over real MCP on an explicitly leased Simulator.

Requires a loopback managed Simulator daemon/record and an existing owner lease.
Never accepts a physical target, starts a model, reconnects or replays a write.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import traceback
import urllib.parse
import uuid

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = "com.leeguoo.iphone-use.recovery-regression-fixture"


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


pair = module("recovery_protocol", "owned-mcp-fixture.py")
drag = module("recovery_transport", "test-drag-simulator.py")

# name, seed, field, length, recover, clear fault, advance, shift
CASES = [
    ("strict-advance", "short", "field-a", 500, False, "", True, False),
    ("normal-opt-in", "short", "field-a", 500, True, "", False, False),
    ("unfocused-b-opt-in", "short", "field-b", 500, True, "", True, False),
    ("advance-opt-in-1", "short", "field-a", 500, True, "", True, False),
    ("advance-opt-in-2", "short", "field-a", 500, True, "", True, False),
    ("empty-clear-opt-in", "long", "field-a", 0, True, "", True, False),
    ("refilled-before-focus", "short", "field-a", 500, True, "repopulate", True, False),
    ("disabled-original", "short", "field-a", 500, True, "disable", True, False),
    ("hidden-original", "short", "field-a", 500, True, "hide", True, False),
    ("secure-conversion", "short", "field-a", 500, True, "secure", True, False),
    ("covered-original", "short", "field-a", 500, True, "overlay", True, False),
    ("refilled-on-focus", "short", "field-a", 500, True, "refocus-repopulate", True, False),
    ("failed-selection", "ignore-all", "field-a", 500, True, "", False, False),
    ("partial-selection", "selection-partial", "field-a", 500, True, "", False, False),
    ("late-focus", "short", "field-a", 500, True, "", False, True),
]


EXPERIMENTAL_CASES = [("insertion-veto", "short", "field-a", 500, True, "insert-veto", False, False)]

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def judge(name, before, after, reply):
    """Independent UIKit receipts, not an ACK/error or a self-reported pass."""
    errors = []
    def need(condition, message):
        if not condition:
            errors.append(message)
    fields = after.get("fields", {})
    previous = before.get("fields", {})
    body = pair.payload(reply)[2]
    need(after.get("trial") == before.get("trial") and after.get("pid") == before.get("pid"), "receipt trial/process changed")
    need(after.get("foreground_active") is True, "fixture is no longer foreground")
    for key in ["multi", "secure"]:
        need(fields.get(key) == previous.get(key), key + " field changed")
    if errors:
        return errors
    touches = after.get("a_touch_starts", -100) - after.get("a_touches_at_clear", 0)
    if name in ["normal-opt-in", "unfocused-b-opt-in", "advance-opt-in-1", "advance-opt-in-2", "empty-clear-opt-in"]:
        key = "b" if name == "unfocused-b-opt-in" else "a"
        wanted = "" if name == "empty-clear-opt-in" else "字" * 500
        need(fields.get(key, {}).get("sha256") == digest(wanted), "requested replacement not exact")
        for other in fields:
            if other != key:
                need(fields[other] == previous.get(other), "unselected field changed: " + other)
        need(body.get("ok") is True and reply.get("result", {}).get("isError") is not True, "successful state lacks acknowledged completion")
        if name.startswith("advance-opt-in"):
            need(after.get("advance_triggered") is True and touches == 1 and after.get("focus") == "a", "handoff/restoration did not occur exactly once")
        if name == "empty-clear-opt-in":
            need(after.get("advance_triggered") is True and touches == 0 and after.get("focus") == "b", "empty clear restored focus or did not trigger handoff")
    elif name in ["strict-advance", "refilled-before-focus", "disabled-original", "hidden-original", "secure-conversion", "covered-original", "refilled-on-focus"]:
        need(after.get("advance_triggered") is True, "clear-time fault never triggered")
        need(fields.get("b") == previous.get("b"), "next field changed")
        wanted = "App restored draft" if name == "refilled-before-focus" else "App refocus draft" if name == "refilled-on-focus" else ""
        need(fields.get("a", {}).get("sha256") == digest(wanted), "original/App content was overwritten")
        need(touches == (1 if name == "refilled-on-focus" else 0), "unexpected recovery touch count")
        need(body.get("outcome") == "unknown" and body.get("retry_safe") is False, "uncertain replacement was promoted/retryable")
        if name == "disabled-original": need(after.get("a_enabled") is False, "disable fault absent")
        if name == "hidden-original": need(after.get("a_hidden") is True, "hide fault absent")
        if name == "secure-conversion": need(after.get("a_secure") is True, "secure conversion absent")
        if name == "covered-original":
            need(after.get("overlay_present") is True, "covering control absent")
            need(after.get("overlay_actions") == 0, "overlay action was activated")
    elif name == "insertion-veto":
        need(fields.get("a", {}).get("sha256") == digest(""), "App insertion veto was bypassed")
        need(fields.get("b") == previous.get("b"), "next field changed")
        need(after.get("insertion_vetoes") == 1, "App insertion veto was not reached exactly once")
        need(body.get("ok") is False and body.get("outcome") == "unknown" and body.get("retry_safe") is False, "veto was promoted or retryable")
    elif name in ["failed-selection", "partial-selection"]:
        need(fields == previous and not any(after.get("events", {}).values()), "selection refusal edited content")
        need(1 <= after.get("selection_commands", 0) <= 2, "selection fault not exercised within bound")
        need(body.get("ok") is False, "selection failure acknowledged as completion")
    elif name == "late-focus":
        need(after.get("shift_trigger_length") == 20, "input-time focus fault never triggered")
        need(after.get("a_touch_starts") == after.get("a_touches_at_shift", 0), "policy rebound focus after text started")
        need(fields.get("b", {}).get("characters", 1000) <= 180, "more text leaked than the current bounded segment")
        if (fields.get("a", {}).get("sha256") != digest("shift-focus-test-" + "字" * 483)
                or fields.get("b") != previous.get("b")):
            need(body.get("outcome") == "unknown" and body.get("retry_safe") is False,
                 "partial/misdirected input was promoted to a successful/retryable result")
        # A future improvement may stop sooner or edit the original without a
        # coordinate refocus. Record actual task completion separately below.
    else:
        need(False, "unknown recovery case")
    return errors


def pause_reply_summary(body):
    # The diagnostic needs delivery counts, never the token or requested text.
    keys=["ok","error","outcome","retry_safe","continuation_safe","characters_confirmed","characters_uncertain","characters_total"]
    summary={key:body[key] for key in keys if key in body}
    summary["token_present"]=isinstance(body.get("continue_token"),str)
    remaining=body.get("remaining_text")
    summary["remaining_sha256"]=digest(remaining) if isinstance(remaining,str) else None
    summary["reported_total_ms"]=(body.get("timing") or {}).get("total_ms")
    return summary


def verified_pause_prefix(body, before, paused, text, cumulative, field):
    """A safe ACK alone cannot authorize another input; require the App receipt."""
    token = body.get("continue_token")
    if not (body.get("ok") is False and body.get("outcome") == "partial" and body.get("continuation_safe") is True
            and body.get("retry_safe") is False and body.get("characters_uncertain") == 0
            and isinstance(token,str) and re.fullmatch(r"[0-9a-f]{64}",token)):
        raise RuntimeError("unconfirmed partial response; no continuation sent")
    confirmed = body.get("characters_confirmed")
    if (not isinstance(confirmed,int) or isinstance(confirmed,bool)
            or not 0 < confirmed < len(text)-cumulative
            or body.get("characters_total") != len(text)-cumulative):
        raise RuntimeError("invalid confirmed prefix; no continuation sent")
    cumulative += confirmed
    if body.get("remaining_text") != text[cumulative:]:
        raise RuntimeError("unsent text disagrees with original request; no continuation sent")
    if (paused.get("trial") != before.get("trial") or paused.get("pid") != before.get("pid")
            or paused.get("foreground_active") is not True or paused.get("focus") != field
            or paused.get("fields",{}).get(field) != {"characters":cumulative,"sha256":digest(text[:cumulative])}
            or any(paused.get("fields",{}).get(key) != old for key,old in before["fields"].items() if key != field)):
        raise RuntimeError("independent App prefix/focus check failed; no continuation sent")
    return cumulative


def require_target(daemon, args):
    status = daemon.require_simulator(args.udid)
    if status.get("owner") != args.owner or status.get("screen_private_secs", 1) != 0:
        raise RuntimeError("requires the caller's existing nonprivate Simulator lease")
    return status



def wait_for_native_idle(daemon, args, peer=None, phase="setup", timeout=15):
    """Poll only metadata; never reset/replay while a request remains pending."""
    deadline = time.monotonic() + timeout
    polls = 0
    while True:
        if peer is not None and peer.pending is not None:
            raise RuntimeError("MCP request remains pending; no fixture reset")
        try:
            require_target(daemon, args)
        except RuntimeError as error:
            if str(error) != "simulator is not drivable":
                raise
            # An uncertain write deliberately degrades the read path. Status
            # polling schedules the daemon's bounded readonly health probe;
            # no fixture reset, input, reconnect or screen read is sent here.
            status = daemon.call("/agent/status")
            same_scope = (isinstance(status, dict)
                and status.get("target") == "simulator"
                and str(status.get("udid", "")).lower() == args.udid.lower()
                and status.get("owner") == args.owner
                and status.get("screen_private_secs") == 0
                and status.get("human_handoff") is False
                and status.get("released") is False
                and status.get("reconnecting") is False
                and status.get("runner") is True
                and status.get("runner_locked") is False)
            recovering = same_scope and (status.get("drivable") is True or
                (status.get("drivable") is False and status.get("device_state") == "degraded"))
            # Keep the actual public status enum, not the internal advice name,
            # in the receipt so a future cross-layer mismatch is inspectable.
            if hasattr(args, "out"):
                sample = {"phase":phase,"device_state":status.get("device_state") if isinstance(status,dict) else None,
                    "drivable":status.get("drivable") if isinstance(status,dict) else None,
                    "same_scope":same_scope,"recovering":recovering}
                with (args.out / "idle-status.jsonl").open("a") as log:
                    log.write(json.dumps(sample)+"\n")
            if not recovering:
                raise
            left = deadline - time.monotonic()
            if left <= 0:
                raise RuntimeError("read path did not become drivable within setup budget; no fixture reset") from error
            print(json.dumps({"idle_phase":phase,"waiting_read_recovery":True}), flush=True)
            time.sleep(min(.2, left))
            continue
        native, _ = drag.runner_call(args, "/status")
        busy = native.get("value", {}).get("busy")
        if busy is False:
            if polls:
                print(json.dumps({"idle_phase":phase,"busy_polls":polls,"native_idle":True}), flush=True)
            return native
        if busy is not True:
            raise RuntimeError("native idle status unavailable; no fixture reset")
        polls += 1
        if polls == 1:
            print(json.dumps({"idle_phase":phase,"native_idle":False,"busy_ms":native.get("value",{}).get("busyMs")}), flush=True)
        left = deadline - time.monotonic()
        if left <= 0:
            raise RuntimeError("native request did not become idle within setup budget; no fixture reset")
        time.sleep(min(.2, left))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--udid", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--runner-record", type=Path, required=True)
    parser.add_argument("--mcp", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--case", action="append", choices=[c[0] for c in CASES+EXPERIMENTAL_CASES], help="select a named cohort; omitted means the standard suite; experimental cases require explicit selection")
    parser.add_argument("--budget-ms", type=int, metavar="6000..15000", help="explicit planned-pause cohort; resume only independently verified unsent text")
    args = parser.parse_args()
    if args.budget_ms is not None and not 6000 <= args.budget_ms <= 15000:
        parser.error("--budget-ms must be from 6000 to 15000")
    selected_cases=CASES if not args.case else [c for c in CASES+EXPERIMENTAL_CASES if c[0] in args.case]
    uuid.UUID(args.udid)
    args.out = args.out.resolve()
    args.runner_record = args.runner_record.resolve(strict=True)
    args.mcp = args.mcp.resolve(strict=True)
    daemon = drag.Daemon(args.base, args.owner)
    require_target(daemon, args)
    record = json.loads(args.runner_record.read_text())
    if record.get("udid", "").lower() != args.udid.lower() or record.get("daemon_port") != urllib.parse.urlsplit(args.base).port:
        raise RuntimeError("managed record does not match this Simulator/daemon")
    running = json.loads(pair.fixture.command("xcrun", "simctl", "list", "devices", "--json"))
    if not any(x["udid"].lower() == args.udid.lower() and x["state"] == "Booted" for rows in running["devices"].values() for x in rows):
        raise RuntimeError("requested booted Simulator is not present")
    wait_for_native_idle(daemon, args, phase="before_install")
    existing = subprocess.run(["xcrun", "simctl", "get_app_container", args.udid, BUNDLE, "data"], capture_output=True, timeout=30)
    if existing.returncode == 0:
        raise RuntimeError("fixture already installed; do not overwrite another run")
    args.out.mkdir(parents=True, mode=0o700, exist_ok=False)
    peer = None
    installed = False
    reports = []
    harness_error = None
    cleanup_errors = []
    state_reader = None
    active_case = None
    active_before = None
    environment = {k:v for k,v in os.environ.items() if not k.startswith(("IPHONE_USE_", "PHONE_REMOTE_", "IPU_", "TEST_RUNNER_"))}
    environment.update(IPHONE_USE_URL=daemon.base, IPHONE_USE_OWNER=args.owner, IPHONE_USE_MCP_PREWARM="0", IPHONE_USE_MCP_STRUCTURED="full", IPHONE_USE_STATE_DIR=str(args.out / "mcp-state"), IPHONE_USE_FLOWS_NO_AUTO_UPDATE="1")
    def call(name, arguments):
        return peer.request("tools/call", {"name":name, "arguments":arguments}, timeout=70)
    try:
        pair.fixture.FIXTURE = (ROOT / "scripts/paired-bench-fixture.swift").read_text()
        pair.fixture.BUNDLE = BUNDLE
        app = pair.fixture.build_fixture(args.out)
        require_target(daemon, args)
        pair.fixture.command("xcrun", "simctl", "install", args.udid, app)
        installed = True
        # Resolve installation metadata before launch/keyboard initialization.
        # A hosted iOS 18.2 run stalled in get_app_container after launch before
        # any input. Keep the read bounded and preserve its phase on failure.
        phase = time.monotonic()
        print(json.dumps({"setup_phase":"resolve_fixture_container"}), flush=True)
        documents = Path(pair.fixture.command("xcrun", "simctl", "get_app_container", args.udid, BUNDLE, "data", timeout=30)) / "Documents"
        print(json.dumps({"setup_phase":"fixture_container_resolved", "elapsed_seconds":time.monotonic()-phase}), flush=True)
        peer = pair.Peer([str(args.mcp)], environment, args.out / "mcp.log")
        phase = time.monotonic()
        print(json.dumps({"setup_phase":"launch_fixture"}), flush=True)
        pair.fixture.command("xcrun", "simctl", "launch", args.udid, BUNDLE, "--trial", "recovery-warmup", "--seed", "short")
        print(json.dumps({"setup_phase":"fixture_launch_returned", "elapsed_seconds":time.monotonic()-phase}), flush=True)
        receipt = documents / "paired-state.json"
        def state():
            return json.loads(receipt.read_text()) if receipt.exists() else {}
        state_reader = state
        for number, case in enumerate(selected_cases):
            name, seed, target, length, recover, fault, advance, shift = case
            active_case = name
            active_before = None
            wait_for_native_idle(daemon, args, peer, phase="before_"+name)
            print(json.dumps({"case_started":name}), flush=True)
            trial = "recovery-" + str(number) + "-" + uuid.uuid4().hex[:8]
            setup = {"trial":trial, "seed":seed, "advance":advance, "shift":shift, "clear_fault":fault}
            temp = documents / "paired-reset.json.tmp"
            temp.write_text(json.dumps(setup))
            temp.replace(documents / "paired-reset.json")
            until = time.monotonic() + 20
            while True:
                before = state()
                if before.get("trial") == trial and before.get("foreground_active") and before.get("keyboard_did_show") and before.get("focus") == "a": break
                if time.monotonic() > until: raise RuntimeError("fixture setup did not converge: " + name)
                time.sleep(.1)
            active_before = before
            active, _ = drag.runner_call(args, "/wda/activeAppInfo")
            if active.get("value", {}).get("bundleId") != BUNDLE or active["value"].get("pid") != before["pid"]:
                raise RuntimeError("fixture foreground/process changed before task")
            seen = call("phone_elements", {})
            result, _, tree = pair.payload(seen)
            if result.get("isError"): raise RuntimeError("observation refused")
            rows = tree.get("elements", [])
            index = next(i for i, row in enumerate(rows) if row.get("identifier") == target)
            text = "shift-focus-test-" + "字" * 483 if shift else "字" * length
            arguments = {"element":index,"snapshot":tree["snapshot"],"value":text,"observe":False}
            if recover: arguments["recover_focus_after_clear"] = True
            if args.budget_ms is not None: arguments["budget_ms"] = args.budget_ms
            task_started = time.monotonic()
            reply = call("phone_set_value", arguments)
            reply_received_ns = time.time_ns()
            continuations = []
            cumulative = 0
            while args.budget_ms is not None:
                body = pair.payload(reply)[2]
                token = body.get("continue_token")
                if token is None: break
                if len(continuations) >= 10: raise RuntimeError("continuation bound exceeded; no replay")
                wait_for_native_idle(daemon,args,peer,phase="paused_"+name)
                paused = state()
                field = "b" if target == "field-b" else "a"
                try:
                    cumulative = verified_pause_prefix(body,before,paused,text,cumulative,field)
                except RuntimeError:
                    # Preserve the rejected receipt and later readonly samples.
                    # A later match never promotes this failed trial or sends input.
                    try: first_mtime=receipt.stat().st_mtime_ns
                    except OSError: first_mtime=None
                    samples=[{"sampled_ns":time.time_ns(),"receipt_mtime_ns":first_mtime,"state":paused}]
                    evidence={"case":name,"trial":trial,"before":before,"reply_received_ns":reply_received_ns,
                              "confirmed_before":cumulative,"field":field,"reply_summary":pause_reply_summary(body),
                              "samples":samples,"continuation_sent_after_rejection":False}
                    diagnostic=args.out/"pause-rejection.json"
                    diagnostic.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n")
                    for delay in [.15,.25]:
                        time.sleep(delay)
                        try: sample={"sampled_ns":time.time_ns(),"receipt_mtime_ns":receipt.stat().st_mtime_ns,"state":state()}
                        except Exception as error: sample={"sampled_ns":time.time_ns(),"read_error":type(error).__name__}
                        samples.append(sample)
                        diagnostic.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n")
                    raise
                if token in {pair.payload(previous["reply"])[2]["continue_token"] for previous in continuations}:
                    raise RuntimeError("repeated continuation token; no continuation sent")
                continuations.append({"reply":reply,"independent_prefix":paused,"confirmed_total":cumulative})
                reply = call("phone_type", {"continue_token":token,"observe":False})
                reply_received_ns = time.time_ns()
            task_ms = (time.monotonic()-task_started)*1000
            # No transport timeout is retried. A received refusal is followed
            # only by readonly idle/stability checks, then a distinct trial.
            wait_for_native_idle(daemon, args, peer, phase="after_"+name)
            until = time.monotonic() + 2
            after = state()
            while True:
                time.sleep(.25)
                fresh = state()
                if fresh == after: break
                after = fresh
                if time.monotonic() > until: raise RuntimeError("fixture edits did not settle; no next reset")
            errors = judge(name, before, after, reply)
            wanted = digest(text)
            field = "b" if target == "field-b" else "a"
            reports.append({"case":name,"trial":trial,"before":before,"after":after,"reply":reply,"continuations":continuations,"task_ms":task_ms,"budget_ms":args.budget_ms,"matched_expected_observation":not errors,"errors":errors,"requested_text_match":after.get("fields",{}).get(field,{}).get("sha256") == wanted,"kind":"known_limit_observation" if shift else "replacement" if name in [x[0] for x in CASES[1:6]] else "expected_stop"})
            (args.out / "result.json").write_text(json.dumps({"cases":reports},ensure_ascii=False,indent=2)+"\n")
            print(json.dumps({"case":name,"matched_expected_observation":not errors,"kind":reports[-1]["kind"]}), flush=True)
            if errors: raise RuntimeError(name + ": " + "; ".join(errors))
    except Exception as error:
        harness_error = str(error)
        (args.out / "traceback.txt").write_text(traceback.format_exc())
        # This is a readonly fixture receipt, not proof that a pending operation
        # completed. Keep it even when cleanup must defer to the outer owner.
        try: observed=state_reader() if state_reader is not None else None
        except Exception as read_error: observed={"read_error":type(read_error).__name__}
        pending={"id":peer.pending,"method":peer.pending_method,"tool":peer.pending_tool} if peer is not None else None
        interrupted={"case":active_case,"error_type":type(error).__name__,"before":active_before,
                     "observed_state":observed,"pending_request":pending,"diagnostic_only":True}
        (args.out/"interrupted-case.json").write_text(json.dumps(interrupted,ensure_ascii=False,indent=2)+"\n")
    finally:
        if peer:
            pending = peer.pending is not None
            try: peer.close()
            except Exception as error:
                cleanup_errors.append("MCP cleanup: " + str(error))
                try: pair.stop(peer.process)
                except Exception as stopped: cleanup_errors.append("MCP stop: " + str(stopped))
        else: pending = False
        try:
            if pending:
                raise RuntimeError("fixture cleanup deferred: MCP delivery remains pending")
            wait_for_native_idle(daemon, args, phase="before_cleanup")
            if installed: pair.fixture.command("xcrun", "simctl", "uninstall", args.udid, BUNDLE)
        except Exception as error: cleanup_errors.append(str(error))
        try:
            if (args.out / "mcp-state").exists(): shutil.rmtree(args.out / "mcp-state")
        except OSError as error: cleanup_errors.append("private state cleanup: " + str(error))
    result = {"scope":"Simulator-only public MCP recovery regression; expected stops/known limit are not full task successes", "source_commit":pair.fixture.command("git","-C",ROOT,"rev-parse","HEAD"), "source_sha256":{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ["scripts/test-replacement-recovery-simulator.py","scripts/paired-bench-fixture.swift"]}, "mcp_sha256":hashlib.sha256(args.mcp.read_bytes()).hexdigest(), "cases":reports,"harness_error":harness_error,"cleanup_errors":cleanup_errors,"selected_cases":[c[0] for c in selected_cases],"budget_ms":args.budget_ms,"passed":len(reports)==len(selected_cases) and not harness_error and not cleanup_errors}
    (args.out / "result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ["passed","harness_error","cleanup_errors"]}),flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
