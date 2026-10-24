#!/usr/bin/env python3
"""Verify target-bound typing on a disposable simulator using the actual XCTest runner.

Build the runner with `IPU_RUNNER_DERIVED_DATA=/tmp/ipu-input-build bash runner/build.sh
--simulator`, then pass its .xctestrun with --xctestrun and a new --out directory.
Creates and deletes only its own simulator; never uses a personal device or daemon.
"""
import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request

from runner_auth import authorization

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = "com.leeguoo.iphone-use.input-guard-fixture"
FIXTURE = r'''
import UIKit
@main final class AppDelegate: UIResponder, UIApplicationDelegate {
  func application(_ application: UIApplication,
                   didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?) -> Bool { true }
}
@objc(InputGuardSceneDelegate) final class SceneDelegate: UIResponder, UIWindowSceneDelegate {
  var window: UIWindow?
  private weak var secondField: UITextField?
  private var shifted = false
  @objc private func shiftFocusIfRequested(_ field: UITextField) {
    if !shifted, let text = field.text, text.hasPrefix("shift-focus-test-"), text.count >= 20 {
      shifted = true
      secondField?.becomeFirstResponder()
    }
  }
  func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options: UIScene.ConnectionOptions) {
    guard let scene = scene as? UIWindowScene else { return }
    let controller = UIViewController()
    controller.view.backgroundColor = .systemBackground
    let first = UITextField(), second = UITextField()
    secondField = second
    first.addTarget(self, action: #selector(shiftFocusIfRequested(_:)), for: .editingChanged)
    for (field, id) in [(first, "field-a"), (second, "field-b")] {
      field.borderStyle = .roundedRect
      field.accessibilityIdentifier = id
      field.accessibilityLabel = "Draft"
      field.autocorrectionType = .no
      field.spellCheckingType = .no
      field.autocapitalizationType = .none
    }
    let stack = UIStackView(arrangedSubviews: [first, second])
    stack.axis = .vertical; stack.spacing = 30
    stack.translatesAutoresizingMaskIntoConstraints = false
    controller.view.addSubview(stack)
    NSLayoutConstraint.activate([
      stack.topAnchor.constraint(equalTo: controller.view.safeAreaLayoutGuide.topAnchor, constant: 60),
      stack.leadingAnchor.constraint(equalTo: controller.view.leadingAnchor, constant: 24),
      stack.trailingAnchor.constraint(equalTo: controller.view.trailingAnchor, constant: -24),
      first.heightAnchor.constraint(equalToConstant: 50), second.heightAnchor.constraint(equalToConstant: 50),
    ])
    window = UIWindow(windowScene: scene)
    window?.rootViewController = controller; window?.makeKeyAndVisible()
    DispatchQueue.main.async { first.becomeFirstResponder() }
  }
}
'''


def command(*args, timeout=120):
    result = subprocess.run([str(arg) for arg in args], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stderr[-2000:]}")
    return result.stdout.strip()


def build_fixture(out):
    import plistlib
    app = out / "InputGuard.app"
    app.mkdir()
    source = out / "fixture.swift"
    source.write_text(FIXTURE)
    sdk = command("xcrun", "--sdk", "iphonesimulator", "--show-sdk-path")
    architecture = "arm64" if platform.machine() == "arm64" else "x86_64"
    command("xcrun", "--sdk", "iphonesimulator", "swiftc", "-parse-as-library", "-sdk", sdk,
            "-target", f"{architecture}-apple-ios15.0-simulator", source, "-o", app / "InputGuard")
    info = {"CFBundleExecutable": "InputGuard", "CFBundleIdentifier": BUNDLE,
            "CFBundleName": "InputGuard", "CFBundlePackageType": "APPL", "CFBundleVersion": "1",
            "CFBundleShortVersionString": "1.0", "MinimumOSVersion": "15.0",
            "CFBundleSupportedPlatforms": ["iPhoneSimulator"], "UIDeviceFamily": [1, 2],
            "UILaunchScreen": {}, "UIApplicationSceneManifest": {
                "UIApplicationSupportsMultipleScenes": False,
                "UISceneConfigurations": {"UIWindowSceneSessionRoleApplication": [{
                    "UISceneConfigurationName": "Default",
                    "UISceneDelegateClassName": "InputGuardSceneDelegate"}]}}}
    (app / "Info.plist").write_bytes(plistlib.dumps(info))
    command("codesign", "--force", "--sign", "-", app)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xctestrun", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--daemon", type=Path, help="also verify cross-call continuation through this candidate daemon")
    parser.add_argument("--runtime", default="com.apple.CoreSimulator.SimRuntime.iOS-27-0")
    parser.add_argument("--device-type", default="com.apple.CoreSimulator.SimDeviceType.iPhone-17")
    args = parser.parse_args()
    xctestrun = args.xctestrun.resolve(strict=True)
    out = args.out.resolve()
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    tok = secrets.token_hex(32)
    reports, cleanup_errors, udid, runner, daemon = [], [], None, None, None
    daemon_binary = args.daemon.resolve(strict=True) if args.daemon else None
    daemon_state = out / "daemon-state"
    daemon_runtime = out / "daemon-runtime"
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    # Never inherit a personal instance, device, runner port or runner token.
    environment = {k: v for k, v in os.environ.items()
                   if not k.startswith(("IPHONE_USE_", "PHONE_REMOTE_", "IPU_", "TEST_RUNNER_IPU_", "SIMCTL_CHILD_"))}
    environment.update(TEST_RUNNER_IPU_RUNNER_PORT=str(port), TEST_RUNNER_IPU_RUNNER_MJPEG_PORT="0",
                       TEST_RUNNER_IPU_RUNNER_TOKEN=tok, TEST_RUNNER_IPU_DAEMON_PORT="0")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(path, body=None, expected=200):
        method = "GET" if body is None else "POST"
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method,
            headers={"Content-Type": "application/json", "Authorization": authorization(tok, method, path, data or b"")})
        try:
            with opener.open(request, timeout=60) as response:
                status, result = response.status, json.load(response)
        except urllib.error.HTTPError as error:
            status, result = error.code, json.load(error)
        if status != expected:
            raise RuntimeError(f"{method} {path}: expected {expected}, got {status}: {result}")
        if expected == 200 and isinstance(result.get("value"), dict) and result["value"].get("error"):
            raise RuntimeError(f"{path}: {result}")
        return result["value"]

    try:
        app = build_fixture(out)
        udid = command("xcrun", "simctl", "create", f"ipu-input-guard-{secrets.token_hex(4)}",
                       args.device_type, args.runtime)
        command("xcrun", "simctl", "boot", udid)
        command("xcrun", "simctl", "bootstatus", udid, "-b", timeout=180)
        command("xcrun", "simctl", "install", udid, app)
        with (out / "runner.log").open("w") as log:
            runner = subprocess.Popen(["xcodebuild", "test-without-building", "-xctestrun", str(xctestrun),
                "-destination", f"id={udid}", "-only-testing:IPhoneUseRunnerUITests/RunnerTests/testServe",
                "-parallel-testing-enabled", "NO"], env=environment, stdout=log, stderr=log, start_new_session=True)
        deadline = time.monotonic() + 120
        while True:
            if runner.poll() is not None:
                raise RuntimeError("runner exited before readiness; see runner.log")
            try:
                status = call("/status")
                if status.get("ready"):
                    break
            except (OSError, ValueError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("runner readiness deadline; see runner.log")
            time.sleep(0.5)
        session = call("/session", {})
        assert session["capabilities"]["ipu:guardedInput"] is True
        sid = session["sessionId"]
        prefix = f"/session/{sid}"
        def wait_for(check, label):
            until = time.monotonic() + 10
            while not check():
                if time.monotonic() >= until:
                    raise RuntimeError("deadline waiting for " + label)
                time.sleep(0.1)

        # The fixture is test setup, not a launch benchmark. Start it once through simctl;
        # cold XCTest app activation can otherwise exhaust the guard test's request budget.
        command("xcrun", "simctl", "launch", udid, BUNDLE)
        wait_for(lambda: call(prefix + "/wda/activeAppInfo").get("bundleId") == BUNDLE, "fixture foreground")

        def find(identifier):
            return call(prefix + "/element", {"using": "accessibility id", "value": identifier})["ELEMENT"]

        first, second = find("field-a"), find("field-b")
        call(prefix + f"/element/{first}/click", {})
        wait_for(lambda: call(prefix + f"/element/{first}/attribute/focused") is True, "first field focus")
        target = call(prefix + "/wda/input-target")["token"]
        call(prefix + "/wda/keys", {"value": ["alpha"], "inputTarget": target})
        assert call(prefix + f"/element/{first}/attribute/value") == "alpha"
        reports.append({"case": "bound-input-readback", "passed": True})
        call(prefix + f"/element/{target}/clear", {"inputTarget": target})
        assert call(prefix + f"/element/{first}/attribute/value") in (None, "")
        call(prefix + "/wda/keys", {"value": ["beta"], "inputTarget": target})
        assert call(prefix + f"/element/{first}/attribute/value") == "beta"
        reports.append({"case": "bound-clear-and-append", "passed": True})

        call(prefix + f"/element/{second}/click", {})
        wait_for(lambda: call(prefix + f"/element/{second}/attribute/focused") is True, "second field focus")
        refusal = call(prefix + "/wda/keys", {"value": ["WRONG"], "inputTarget": target}, expected=400)
        assert "input_target_focus_changed" in refusal["message"]
        assert call(prefix + f"/element/{second}/attribute/value") in (None, "")
        assert call(prefix + f"/element/{first}/attribute/value") == "beta"
        reports.append({"case": "same-label-field-switch-refused", "passed": True, "refusal": refusal})

        target = call(prefix + "/wda/input-target")["token"]
        call(prefix + "/wda/homescreen", {})
        refusal = call(prefix + "/wda/keys", {"value": ["WRONG"], "inputTarget": target}, expected=400)
        assert refusal["message"].endswith("nothing was sent")
        call(prefix + "/wda/apps/launch", {"bundleId": BUNDLE})
        wait_for(lambda: call(prefix + "/wda/activeAppInfo").get("bundleId") == BUNDLE, "fixture resumed")
        # App transitions invalidate assumptions about the old element handles. Resolve the
        # fields from the fresh hierarchy before choosing the next focus target.
        first, second = find("field-a"), find("field-b")
        assert call(prefix + f"/element/{second}/attribute/value") in (None, "")
        reports.append({"case": "foreground-app-switch-refused", "passed": True, "refusal": refusal})

        call(prefix + f"/element/{first}/click", {})
        wait_for(lambda: call(prefix + f"/element/{first}/attribute/focused") is True, "first field focus")
        target = call(prefix + "/wda/input-target")["token"]
        call("/session", {})
        refusal = call(prefix + "/wda/keys", {"value": ["WRONG"], "inputTarget": target}, expected=400)
        assert "input_target_expired_or_unreadable" in refusal["message"]
        reports.append({"case": "session-replacement-refused", "passed": True, "refusal": refusal})
        # A command from a different native controller must invalidate a binding even when
        # it leaves focus on the same field. This is stronger than checking current focus alone.
        first, second = find("field-a"), find("field-b")
        target = call(prefix + "/wda/input-target")["token"]
        call(prefix + "/wda/keys", {"value": ["x"]})
        refusal = call(prefix + "/wda/keys", {"value": ["WRONG"], "inputTarget": target}, expected=400)
        assert "input_target_invalidated_by_another_command" in refusal["message"]
        reports.append({"case": "external-native-command-invalidates-binding", "passed": True, "refusal": refusal})

        if daemon_binary:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                daemon_port = listener.getsockname()[1]
            daemon_state.mkdir(mode=0o700)
            daemon_runtime.mkdir(mode=0o700)
            token_file = daemon_state / "runner-token"
            token_file.write_text(tok)
            token_file.chmod(0o600)
            env = dict(environment)
            env.update(IPHONE_USE_HOST="127.0.0.1", IPHONE_USE_PORT=str(daemon_port),
                IPHONE_USE_INSTANCE="guard-" + udid[:8].lower(), TMPDIR=str(daemon_runtime),
                IPHONE_USE_STATE_DIR=str(daemon_state), IPHONE_USE_SIMULATOR=udid,
                IPHONE_USE_RUNNER_URL=f"http://127.0.0.1:{port}",
                IPHONE_USE_RUNNER_MJPEG_URL=f"http://127.0.0.1:{port}",
                IPHONE_USE_RUNNER_MANAGED="0", IPHONE_USE_AGENT_TOKEN=tok,
                IPHONE_USE_PASSWORD="fixture-" + tok, IPHONE_USE_AUTO_FOCUS="0",
                IPHONE_USE_IDLE_RELEASE_SECS="0", IPHONE_USE_FLOWS_NO_AUTO_UPDATE="1")
            with (out / "daemon.log").open("w") as log:
                daemon = subprocess.Popen([str(daemon_binary), "serve"], env=env, stdout=log, stderr=log, start_new_session=True)

            def api(path, body=None, owner="input-continuation-fixture", takeover=False):
                data = None if body is None else json.dumps(body).encode()
                headers = {"Content-Type": "application/json", "Authorization": "Bearer " + tok,
                           "X-Phone-Control": "1", "X-Phone-Owner": owner}
                if takeover:
                    headers["X-Phone-Owner-Takeover"] = "1"
                request = urllib.request.Request(f"http://127.0.0.1:{daemon_port}{path}", data=data, headers=headers)
                try:
                    with opener.open(request, timeout=60) as response:
                        return response.status, json.load(response)
                except urllib.error.HTTPError as error:
                    return error.code, json.load(error)

            until = time.monotonic() + 45
            while True:
                if daemon.poll() is not None:
                    raise RuntimeError("candidate daemon exited; see daemon.log")
                try:
                    status, observed = api("/agent/status")
                    if status == 200:
                        assert observed.get("target") == "simulator" and observed.get("udid") == udid, observed
                        if observed.get("drivable") is True:
                            break
                except (OSError, ValueError):
                    pass
                if time.monotonic() >= until:
                    raise RuntimeError("candidate daemon readiness deadline")
                time.sleep(0.2)

            def prepare():
                nonlocal first, second
                first, second = find("field-a"), find("field-b")
                call(prefix + f"/element/{first}/click", {})
                wait_for(lambda: call(prefix + f"/element/{first}/attribute/focused") is True, "first field focus")
                before = call(prefix + f"/element/{first}/attribute/value") or ""
                target = call(prefix + "/wda/input-target")["token"]
                call(prefix + f"/element/{target}/clear", {"inputTarget": target})
                assert call(prefix + f"/element/{first}/attribute/value") in (None, "")
                return len(before)

            def begin():
                status, result = api("/agent/input", {"type": "text", "text": "字" * 500, "budget_ms": 6000})
                assert status == 502 and result.get("characters_uncertain") == 0, result
                assert result.get("characters_confirmed", 0) > 0 and result.get("continuation_safe") is True, result
                return result

            prepare()
            result = begin()
            portions = [result["characters_confirmed"]]
            for _ in range(5):
                token = result["continue_token"]
                status, result = api("/agent/input", {"type": "text", "continue_token": token})
                if status == 200 and result.get("ok") is True:
                    break
                assert status == 502 and result.get("continuation_safe") is True, result
                portions.append(result["characters_confirmed"])
            else:
                raise RuntimeError("continuation did not finish within five calls")
            assert call(prefix + f"/element/{first}/attribute/value") == "字" * 500
            reports.append({"case": "daemon-continuation-500-character-readback", "passed": True,
                            "confirmed_partial_portions": portions, "final_length": 500})

            assert prepare() == 500
            reports.append({"case": "native-clear-after-mid-field-click", "passed": True,
                            "before_length": 500, "after_length": 0})
            result = begin()
            before = call(prefix + f"/element/{first}/attribute/value")
            status, released = api("/agent/owner", {"release": True})
            assert status == 200, released
            status, result = api("/agent/input", {"type": "text", "continue_token": result["continue_token"]})
            assert status == 409 and result.get("error") == "input_continuation_expired", result
            assert call(prefix + f"/element/{first}/attribute/value") == before
            reports.append({"case": "daemon-owner-release-invalidates-continuation", "passed": True})

            prepare()
            result = begin()
            before = call(prefix + f"/element/{first}/attribute/value")
            call(prefix + f"/element/{second}/click", {})
            wait_for(lambda: call(prefix + f"/element/{second}/attribute/focused") is True, "second field focus")
            status, result = api("/agent/input", {"type": "text", "continue_token": result["continue_token"]})
            assert status == 422 and result.get("error") == "runner_rejected", result
            assert call(prefix + f"/element/{first}/attribute/value") == before
            assert call(prefix + f"/element/{second}/attribute/value") in (None, "")
            reports.append({"case": "daemon-native-focus-change-refuses-continuation", "passed": True})

            prepare()
            result = begin()
            before = call(prefix + f"/element/{first}/attribute/value")
            call("/session", {})
            status, result = api("/agent/input", {"type": "text", "continue_token": result["continue_token"]})
            assert status == 422 and result.get("error") == "runner_rejected", result
            first = find("field-a")
            assert call(prefix + f"/element/{first}/attribute/value") == before
            reports.append({"case": "daemon-native-session-change-refuses-continuation", "passed": True})

            prepare()
            log_path = out / "runner.log"
            native_keys = lambda: log_path.read_text(errors="replace").count(f"POST {prefix}/wda/keys ->")
            before_calls = native_keys()
            draft = "shift-focus-test-" + "字" * (500 - len("shift-focus-test-"))
            status, result = api("/agent/input", {"type": "text", "text": draft, "budget_ms": 15000})
            assert status == 502 and result.get("error") == "text_partially_typed", result
            assert result.get("characters_confirmed") == 0 and result.get("characters_uncertain") == 200, result
            assert "continue_token" not in result, result
            assert native_keys() - before_calls == 1, "mid-chunk focus change must stop before another chunk"
            first, second = find("field-a"), find("field-b")
            lengths = {"a": len(call(prefix + f"/element/{first}/attribute/value") or ""),
                       "b": len(call(prefix + f"/element/{second}/attribute/value") or "")}
            reports.append({"case": "daemon-mid-chunk-focus-change-is-unknown-without-continuation",
                            "passed": True, "native_key_requests": 1, "field_lengths": lengths})

            prepare()
            before_calls = native_keys()
            with ThreadPoolExecutor(max_workers=1) as pool:
                running = pool.submit(api, "/agent/input", {"type": "text", "text": "字" * 500, "budget_ms": 15000},
                                      "input-continuation-fixture", True)
                until = time.monotonic() + 10
                while True:
                    status = call("/status")
                    if status.get("busy") is True and status.get("busyMs", 0) >= 200:
                        break
                    if running.done() or time.monotonic() >= until:
                        raise RuntimeError("input did not enter a live native chunk before takeover")
                    time.sleep(0.02)
                status, rejected = api("/agent/input", {"type": "text", "text": "x", "budget_ms": 1},
                                       owner="other-fixture-owner", takeover=True)
                assert status == 400, rejected
                status, result = running.result(timeout=60)
            assert status == 502 and result.get("characters_confirmed") == 200, result
            assert "continue_token" not in result, result
            _, observed = api("/agent/status", owner="other-fixture-owner")
            assert observed.get("owner") == "other-fixture-owner", observed
            assert native_keys() - before_calls == 1
            first = find("field-a")  # An earlier unknown result can force a fresh runner session.
            assert call(prefix + f"/element/{first}/attribute/value") == "字" * 200
            reports.append({"case": "daemon-takeover-during-chunk-is-not-stolen-back-on-completion",
                            "passed": True, "confirmed": 200, "native_key_requests": 1})
    except Exception as error:
        reports.append({"case": "harness-or-current-case", "passed": False, "error": str(error)})
    finally:
        for process in [daemon, runner]:
            if process and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
        for directory in [daemon_state, daemon_runtime]:
            if directory.exists():
                shutil.rmtree(directory)  # Created by this harness, contains only disposable state.
        if udid:
            for operation in ["shutdown", "delete"]:
                try:
                    command("xcrun", "simctl", operation, udid)
                except Exception as error:
                    cleanup_errors.append(str(error))
        for name in ["runner.log", "daemon.log"]:
            log = out / name
            if log.exists():
                log.write_text(log.read_text(errors="replace").replace(tok, "[redacted fixture token]"))
        files = [Path(__file__).relative_to(ROOT), Path("runner/IPhoneUseRunner/IPhoneUseRunnerUITests/RunnerRoutes.swift"),
                 Path("runner/IPhoneUseRunner/IPhoneUseRunnerUITests/RunnerElements.swift"),
                 Path("runner/IPhoneUseRunner/IPhoneUseRunnerUITests/IPURBridge.m"),
                 Path("runner/IPhoneUseRunner/IPhoneUseRunnerUITests/RunnerTests.swift")]
        if daemon_binary:
            files.extend(map(Path, ["crates/server/src/http.rs", "crates/server/src/runner.rs", "crates/server/src/input_continuation.rs"]))
        manifest = {"scope": "actual XCTest runner on disposable iOS Simulator; not physical-device evidence",
            "simulator": udid, "runtime": args.runtime, "cases": reports, "cleanup_errors": cleanup_errors,
            "xctestrun_sha256": hashlib.sha256(xctestrun.read_bytes()).hexdigest(),
            "runner_binary_sha256": hashlib.sha256((xctestrun.parent / "Debug-iphonesimulator/iPhoneUse-Runner.app/PlugIns/iPhoneUse.xctest/iPhoneUse").read_bytes()).hexdigest(),
            "sources": {str(path): hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in files}}
        if daemon_binary:
            manifest["daemon_binary_sha256"] = hashlib.sha256(daemon_binary.read_bytes()).hexdigest()
        (out / "results.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": reports, "cleanup_errors": cleanup_errors}))
    return 0 if len(reports) == (13 if daemon_binary else 6) and all(r["passed"] for r in reports) and not cleanup_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
