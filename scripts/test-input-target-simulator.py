#!/usr/bin/env python3
"""Verify target-bound typing on a disposable simulator using the actual XCTest runner.

Build the runner with `IPU_RUNNER_DERIVED_DATA=/tmp/ipu-input-build bash runner/build.sh
--simulator`, then pass its .xctestrun with --xctestrun and a new --out directory.
Creates and deletes only its own simulator; never uses a personal device or daemon.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
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
  func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options: UIScene.ConnectionOptions) {
    guard let scene = scene as? UIWindowScene else { return }
    let controller = UIViewController()
    controller.view.backgroundColor = .systemBackground
    let first = UITextField(), second = UITextField()
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
    parser.add_argument("--runtime", default="com.apple.CoreSimulator.SimRuntime.iOS-27-0")
    parser.add_argument("--device-type", default="com.apple.CoreSimulator.SimDeviceType.iPhone-17")
    args = parser.parse_args()
    xctestrun = args.xctestrun.resolve(strict=True)
    out = args.out.resolve()
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    tok = secrets.token_hex(32)
    reports, cleanup_errors, udid, runner = [], [], None, None
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
    except Exception as error:
        reports.append({"case": "harness-or-current-case", "passed": False, "error": str(error)})
    finally:
        if runner and runner.poll() is None:
            try:
                os.killpg(runner.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                runner.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(runner.pid, signal.SIGKILL)
                runner.wait(timeout=10)
        if udid:
            for operation in ["shutdown", "delete"]:
                try:
                    command("xcrun", "simctl", operation, udid)
                except Exception as error:
                    cleanup_errors.append(str(error))
        log = out / "runner.log"
        if log.exists():
            log.write_text(log.read_text(errors="replace").replace(tok, "[redacted runner token]"))
        files = [Path(__file__).relative_to(ROOT), Path("runner/IPhoneUseRunner/IPhoneUseRunnerUITests/RunnerRoutes.swift"),
                 Path("runner/IPhoneUseRunner/IPhoneUseRunnerUITests/RunnerElements.swift"),
                 Path("runner/IPhoneUseRunner/IPhoneUseRunnerUITests/IPURBridge.m")]
        manifest = {"scope": "actual XCTest runner on disposable iOS Simulator; not physical-device evidence",
            "simulator": udid, "runtime": args.runtime, "cases": reports, "cleanup_errors": cleanup_errors,
            "xctestrun_sha256": hashlib.sha256(xctestrun.read_bytes()).hexdigest(),
            "runner_binary_sha256": hashlib.sha256((xctestrun.parent / "Debug-iphonesimulator/iPhoneUse-Runner.app/PlugIns/iPhoneUse.xctest/iPhoneUse").read_bytes()).hexdigest(),
            "sources": {str(path): hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in files}}
        (out / "results.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": reports, "cleanup_errors": cleanup_errors}))
    return 0 if len(reports) == 5 and all(r["passed"] for r in reports) and not cleanup_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
