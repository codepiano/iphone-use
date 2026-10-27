#!/usr/bin/env python3
"""Verify target-bound typing on a disposable simulator using the actual XCTest runner.

Build the runner with `IPU_RUNNER_DERIVED_DATA=/tmp/ipu-input-build bash runner/build.sh
--simulator`, then pass its .xctestrun with --xctestrun and a new --out directory.
Creates and deletes only its own simulator; never uses a personal device or daemon.
"""
import argparse
import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import platform
import re
import traceback
import secrets
import select
import shutil
import signal
import socket
import sys
import subprocess
import time
import urllib.error
import urllib.request

from runner_auth import authorization

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = "com.leeguoo.iphone-use.input-guard-fixture"
FIXTURE = r'''
import UIKit
import CryptoKit
@main final class AppDelegate: UIResponder, UIApplicationDelegate {
  func application(_ application: UIApplication,
                   didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?) -> Bool { true }
}
@objc(InputGuardSceneDelegate) final class SceneDelegate: UIResponder, UIWindowSceneDelegate, UITextFieldDelegate, UITextViewDelegate {
  var window: UIWindow?
  private weak var secondField: UITextField?
  private weak var firstField: UITextField?
  private weak var multilineField: UITextView?
  private weak var secureField: UITextField?
  private weak var metadataControl: UIButton?
  private var firstEvents = 0, secondEvents = 0, returnEvents = 0
  private var vetoMode = "off", vetoA = 0, vetoMulti = 0
  private var stateFault = "off", stateFaultTriggered = false
  private var faultScalars = 0, faultHash = ""
  func textField(_ field: UITextField, shouldChangeCharactersIn range: NSRange, replacementString string: String) -> Bool {
    if vetoMode == "a" && field === firstField { vetoA += 1; return false }
    return true
  }
  func textView(_ view: UITextView, shouldChangeTextIn range: NSRange, replacementText text: String) -> Bool {
    if vetoMode == "multi" && view === multilineField { vetoMulti += 1; return false }
    return true
  }
  private let receiptRun = UUID().uuidString
  private var receiptTimer: Timer?
  private var lastReceiptRequest: String?
  @objc private func secondEdited(_ field: UITextField) { secondEvents += 1 }
  @objc private func returnPressed(_ field: UITextField) { returnEvents += 1 }
  @objc private func writeRequestedReceipt(_ timer: Timer?) {
    let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    guard let data = try? Data(contentsOf: documents.appendingPathComponent("boundary-state-command.json")),
          let command = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
          let nonce = command["nonce"] as? String, nonce != lastReceiptRequest else { return }
    if let veto = command["veto"] as? String, ["off","a","multi"].contains(veto) { vetoMode = veto }
    if let fault = command["state_fault"] as? String, ["off","disable","hide","secure"].contains(fault) { stateFault = fault }
    func field(_ value: String?) -> [String: Any] {
      let text = value ?? ""
      return ["scalars":text.unicodeScalars.count,"utf16":text.utf16.count,
        "sha256":SHA256.hash(data: Data(text.utf8)).map { String(format:"%02x",$0) }.joined()]
    }
    let state: [String: Any] = ["nonce":nonce,"run_id":receiptRun,"pid":ProcessInfo.processInfo.processIdentifier,
      "foreground":window?.windowScene?.activationState == .foregroundActive,
      "fields_present":firstField != nil && secondField != nil && multilineField != nil && secureField != nil,
      "fields":["a":field(firstField?.text),"b":field(secondField?.text),"multi":field(multilineField?.text),"secure":field(secureField?.text)],
      "metadata_enabled":metadataControl?.isEnabled ?? true, "metadata_selected":metadataControl?.isSelected ?? false,
      "a_enabled":firstField?.isEnabled ?? false,"a_hidden":firstField?.isHidden ?? false,
      "a_secure":firstField?.isSecureTextEntry ?? false,"state_fault":stateFault,
      "state_fault_triggered":stateFaultTriggered,"fault_scalars":faultScalars,"fault_sha256":faultHash,
      "selection_a":firstField?.selectedTextRange.map { ["location":firstField!.offset(from:firstField!.beginningOfDocument,to:$0.start),"length":firstField!.offset(from:$0.start,to:$0.end)] } ?? [:],
      "events_a":firstEvents,"events_b":secondEvents,"returns":returnEvents,"shifted":shifted,
      "focus_a":firstField?.isFirstResponder ?? false,"focus_b":secondField?.isFirstResponder ?? false,
      "focus_multi":multilineField?.isFirstResponder ?? false,"veto":vetoMode,"veto_calls_a":vetoA,"veto_calls_multi":vetoMulti]
    if let data = try? JSONSerialization.data(withJSONObject:state,options:[.sortedKeys]),
       (try? data.write(to:documents.appendingPathComponent("boundary-state.json"),options:.atomic)) != nil {
      lastReceiptRequest = nonce
    }
  }
  private var shifted = false
  private var fieldReceiptGeneration = 0
  private weak var liveTitle: UILabel?
  private var liveTimer: Timer?
  private var liveNonce: String?
  @objc private func updateLiveFixture(_ timer: Timer?) {
    let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    let command = documents.appendingPathComponent("live-video-command.json")
    guard let data = try? Data(contentsOf: command),
          let body = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
          let counter = body["counter"] as? Int, (1...999999).contains(counter),
          let nonce = body["nonce"] as? String, nonce != liveNonce else { return }
    let label = "Live frame \(counter)"
    liveTitle?.text = label
    liveNonce = nonce
    let receipt: [String: Any] = ["counter": counter, "nonce": nonce, "label": label]
    if let data = try? JSONSerialization.data(withJSONObject: receipt, options: [.sortedKeys]) {
      try? data.write(to: documents.appendingPathComponent("live-video-state.json"), options: .atomic)
    }
  }
  @objc private func shiftFocusIfRequested(_ field: UITextField) {
    firstEvents += 1
    if !stateFaultTriggered, stateFault != "off", let text = field.text,
        text.hasPrefix("state-guard-test-"), text.unicodeScalars.count >= 20 {
      stateFaultTriggered = true
      faultScalars = text.unicodeScalars.count
      faultHash = SHA256.hash(data:Data(text.utf8)).map { String(format:"%02x",$0) }.joined()
      switch stateFault {
      case "disable": field.isEnabled = false
      case "hide": field.isHidden = true
      case "secure": field.isSecureTextEntry = true
      default: break
      }
    }
    let marker = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("input-started.count")
    fieldReceiptGeneration += 1
    if field.text?.hasPrefix("queue-deadline-") == true || ProcessInfo.processInfo.arguments.contains("--continuous-value-receipt") {
      let generation = fieldReceiptGeneration
      let receiptFile = marker.deletingLastPathComponent().appendingPathComponent("field-a-state.json")
      DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { [weak self, weak field] in
        guard self?.fieldReceiptGeneration == generation, let field = field else { return }
        let value = field.text ?? ""
        let digest = SHA256.hash(data: Data(value.utf8)).map { String(format: "%02x", $0) }.joined()
        let state: [String: Any] = ["characters": value.count, "sha256": digest]
        if let data = try? JSONSerialization.data(withJSONObject: state, options: [.sortedKeys]) {
          try? data.write(to: receiptFile, options: .atomic)
        }
      }
    }
    if field.text?.isEmpty != false {
      shifted = false
      try? FileManager.default.removeItem(at: marker)
    } else if !FileManager.default.fileExists(atPath: marker.path) {
      try? String(field.text?.count ?? 0).write(to: marker, atomically: true, encoding: .utf8)
    }
    if !shifted, let text = field.text, text.hasPrefix("shift-focus-test-"), text.count >= 20 {
      shifted = true
      secondField?.becomeFirstResponder()
    }
  }
  func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options: UIScene.ConnectionOptions) {
    guard let scene = scene as? UIWindowScene else { return }
    let controller = UIViewController()
    controller.view.backgroundColor = .systemBackground
    let title = UILabel()
    title.text = "Input guard fixture"
    title.font = .systemFont(ofSize: 22, weight: .semibold)
    title.accessibilityIdentifier = "fixture-title"
    title.translatesAutoresizingMaskIntoConstraints = false
    controller.view.addSubview(title)
    NSLayoutConstraint.activate([
      title.topAnchor.constraint(equalTo: controller.view.safeAreaLayoutGuide.topAnchor, constant: 16),
      title.leadingAnchor.constraint(equalTo: controller.view.leadingAnchor, constant: 24),
    ])
    let first = UITextField(), second = UITextField()
    firstField = first; secondField = second
    first.delegate = self; second.delegate = self
    second.addTarget(self, action:#selector(secondEdited(_:)), for:.editingChanged)
    first.addTarget(self, action:#selector(returnPressed(_:)), for:.editingDidEndOnExit)
    second.addTarget(self, action:#selector(returnPressed(_:)), for:.editingDidEndOnExit)
    first.placeholder = "Draft placeholder"
    first.addTarget(self, action: #selector(shiftFocusIfRequested(_:)), for: .editingChanged)
    for (field, id) in [(first, "field-a"), (second, "field-b")] {
      field.borderStyle = .roundedRect
      field.accessibilityIdentifier = id
      field.accessibilityLabel = "Draft"
      field.autocorrectionType = .no
      field.spellCheckingType = .no
      field.autocapitalizationType = .none
    }
    let multiline = UITextView(), secure = UITextField()
    multilineField = multiline; secureField = secure
    multiline.delegate = self
    multiline.accessibilityIdentifier = "field-multiline"
    multiline.accessibilityLabel = "Multiline draft"
    multiline.autocorrectionType = .no
    multiline.spellCheckingType = .no
    multiline.autocapitalizationType = .none
    multiline.layer.borderWidth = 1
    secure.accessibilityIdentifier = "field-secure"
    secure.accessibilityLabel = "Secure draft"
    secure.isSecureTextEntry = true
    secure.borderStyle = .roundedRect
    var fields: [UIView] = [first, second, multiline, secure]
    if ProcessInfo.processInfo.arguments.contains("--metadata-controls") {
      let control = UIButton(type:.system)
      control.setTitle("Metadata control",for:.normal)
      control.accessibilityIdentifier = "metadata-control"
      control.isEnabled = false; control.isSelected = true
      metadataControl = control; fields.append(control)
    }
    let stack = UIStackView(arrangedSubviews: fields)
    stack.axis = .vertical; stack.spacing = 30
    stack.translatesAutoresizingMaskIntoConstraints = false
    controller.view.addSubview(stack)
    NSLayoutConstraint.activate([
      stack.topAnchor.constraint(equalTo: controller.view.safeAreaLayoutGuide.topAnchor, constant: 60),
      stack.leadingAnchor.constraint(equalTo: controller.view.leadingAnchor, constant: 24),
      stack.trailingAnchor.constraint(equalTo: controller.view.trailingAnchor, constant: -24),
      first.heightAnchor.constraint(equalToConstant: 50), second.heightAnchor.constraint(equalToConstant: 50),
      multiline.heightAnchor.constraint(equalToConstant: 90), secure.heightAnchor.constraint(equalToConstant: 50),
    ])
    window = UIWindow(windowScene: scene)
    window?.rootViewController = controller; window?.makeKeyAndVisible()
    receiptTimer = Timer.scheduledTimer(timeInterval:0.05,target:self,
      selector:#selector(writeRequestedReceipt(_:)),userInfo:nil,repeats:true)
    if ProcessInfo.processInfo.arguments.contains("--live-video-fixture") {
      liveTitle = title
      liveTimer = Timer.scheduledTimer(timeInterval: 0.1, target: self,
        selector: #selector(updateLiveFixture(_:)), userInfo: nil, repeats: true)
      updateLiveFixture(nil)
    }
    DispatchQueue.main.async {
      first.becomeFirstResponder()
      if ProcessInfo.processInfo.arguments.contains("--long-value-fixture") {
        first.text = "queue-deadline-" + String(repeating: "字", count: 6000)
        first.selectedTextRange = first.textRange(from:first.endOfDocument,to:first.endOfDocument)
        second.text = "🙂🙂value"
        secure.text = "fixture-secure-value"
        first.sendActions(for: .editingChanged)
      }
    }
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


class VideoPeer:
    """An independent MCP session for read-only multi-viewer acceptance."""
    def __init__(self, binary, environment, log_path):
        with log_path.open("a") as log:
            self.process = subprocess.Popen([str(binary)],env=environment,stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,stderr=log,start_new_session=True)
        self.buffer = b""
        self.identifier = 0

    def initialize(self):
        result=self.request("initialize",{"protocolVersion":"2025-06-18","capabilities":{},
            "clientInfo":{"name":"independent-video-viewer","version":"1"}})
        assert "result" in result,result
        self.process.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        self.process.stdin.flush()

    def request(self, method, params):
        self.identifier+=1
        self.process.stdin.write((json.dumps({"jsonrpc":"2.0","id":self.identifier,"method":method,"params":params})+"\n").encode())
        self.process.stdin.flush()
        until=time.monotonic()+12
        while time.monotonic()<until:
            while b"\n" in self.buffer:
                line,self.buffer=self.buffer.split(b"\n",1)
                reply=json.loads(line)
                if reply.get("id")==self.identifier:return reply
            if select.select([self.process.stdout],[],[],max(0,until-time.monotonic()))[0]:
                data=os.read(self.process.stdout.fileno(),65536)
                if not data:raise RuntimeError("independent viewer exited")
                self.buffer+=data
        raise RuntimeError("independent viewer deadline")

    def frame(self, reset=False):
        result=self.request("resources/read",{"uri":f"ui://iphone-use/video-v1/{int(reset)}/{self.identifier+1}"})
        return json.loads(result["result"]["contents"][0]["text"])

    def close(self):
        if self.process.poll() is None:
            os.killpg(self.process.pid,signal.SIGTERM)
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid,signal.SIGKILL)
                self.process.wait(timeout=10)


class CaseReports(list):
    def append(self, record):
        super().append(record)
        print(f"case {record.get('case')}: {'passed' if record.get('passed') else 'failed'}", file=sys.stderr, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xctestrun", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--daemon", type=Path, help="also verify cross-call continuation through this candidate daemon")
    parser.add_argument("--mcp", type=Path, help="observe MCP cancellation through this candidate stdio binary (requires --daemon)")
    parser.add_argument("--recovery", action="store_true", help="also verify fresh failure images and privacy withholding")
    parser.add_argument("--hosts", action="store_true", help="verify WorkBuddy resource frames through restarted stdio processes")
    parser.add_argument("--input-privacy", action="store_true", help="verify pending and in-flight typing across private holds")
    parser.add_argument("--observation-scope", action="store_true", help="verify applied input keeps its receipt while stale observations are withheld")
    parser.add_argument("--native-scope", action="store_true", help="verify no late relaunch after acknowledged termination")
    parser.add_argument("--list-deadline", action="store_true", help="observe the real 80-second queue deadline with an owned long-input fixture (adds ~110s)")
    parser.add_argument("--list-recovery", action="store_true", help="verify scoped list diagnostics and interruption after native swipe ACK")
    parser.add_argument("--video", action="store_true", help="verify native H.264 via WorkBuddy resources and independent ffmpeg decode (requires --hosts)")
    parser.add_argument("--expect-boundary-isolation", action="store_true", help="experimental Runner must stop at A20/B0 in reached focus-switch faults")
    parser.add_argument("--metadata-controls", action="store_true", help="compare disabled/selected UIKit control against independent App state")
    parser.add_argument("--long-boundaries", action="store_true", help="verify long-field App veto and public MCP append")
    parser.add_argument("--state-boundaries", action="store_true", help="verify mid-input disable/hide/secure conversion on short and long routes")
    parser.add_argument("--runtime", default="com.apple.CoreSimulator.SimRuntime.iOS-27-0")
    parser.add_argument("--device-type", default="com.apple.CoreSimulator.SimDeviceType.iPhone-17")
    args = parser.parse_args()
    xctestrun = args.xctestrun.resolve(strict=True)
    out = args.out.resolve()
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    tok = secrets.token_hex(32)
    reports, cleanup_errors, udid, runner, daemon, mcp = CaseReports(), [], None, None, None, None
    observations = []
    video_peers = []
    daemon_binary = args.daemon.resolve(strict=True) if args.daemon else None
    mcp_binary = args.mcp.resolve(strict=True) if args.mcp else None
    if args.state_boundaries and not (args.expect_boundary_isolation and daemon_binary):
        raise RuntimeError("--state-boundaries requires --expect-boundary-isolation and --daemon")
    if args.long_boundaries and not (args.expect_boundary_isolation and daemon_binary and mcp_binary):
        raise RuntimeError("--long-boundaries requires --expect-boundary-isolation, --daemon and --mcp")
    if args.list_deadline and not daemon_binary:
        raise RuntimeError("--list-deadline requires --daemon")
    if args.list_recovery and not (daemon_binary and mcp_binary):
        raise RuntimeError("--list-recovery requires --daemon and --mcp")
    if args.video and (not args.hosts or not shutil.which("ffmpeg")):
        raise RuntimeError("--video requires --hosts and ffmpeg")
    if args.expect_boundary_isolation and not daemon_binary:
        raise RuntimeError("--expect-boundary-isolation requires --daemon")
    if args.native_scope and not daemon_binary:
        raise RuntimeError("--native-scope requires --daemon")
    if args.observation_scope and not daemon_binary:
        raise RuntimeError("--observation-scope requires --daemon")
    if args.input_privacy and not daemon_binary:
        raise RuntimeError("--input-privacy requires --daemon")
    if args.hosts and not mcp_binary:
        raise RuntimeError("--hosts requires --mcp and --daemon")
    if args.recovery and not daemon_binary:
        raise RuntimeError("--recovery requires --daemon")
    if mcp_binary and not daemon_binary:
        raise RuntimeError("--mcp requires --daemon")
    daemon_state = out / "daemon-state"
    daemon_runtime = out / "daemon-runtime"
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    video_port = 0
    if args.video:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            video_port = listener.getsockname()[1]
    # Never inherit a personal instance, device, runner port or runner token.
    environment = {k: v for k, v in os.environ.items()
                   if not k.startswith(("IPHONE_USE_", "PHONE_REMOTE_", "IPU_", "TEST_RUNNER_IPU_", "SIMCTL_CHILD_"))}
    environment.update(TEST_RUNNER_IPU_RUNNER_PORT=str(port), TEST_RUNNER_IPU_RUNNER_MJPEG_PORT=str(video_port),
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
        runtimes = json.loads(command("xcrun", "simctl", "list", "runtimes", "--json"))["runtimes"]
        runtime = next((row for row in runtimes if row.get("identifier") == args.runtime), None)
        if not runtime or runtime.get("isAvailable") is not True:
            raise RuntimeError("requested runtime is unavailable: " + args.runtime)
        supported = runtime.get("supportedDeviceTypes", [])
        if supported and not any(row.get("identifier") == args.device_type for row in supported):
            raise RuntimeError("requested device is unsupported by runtime: " + args.device_type + " / " + args.runtime)
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
        command("xcrun", "simctl", "launch", udid, BUNDLE, *(["--metadata-controls"] if args.metadata_controls else []))
        wait_for(lambda: call(prefix + "/wda/activeAppInfo").get("bundleId") == BUNDLE, "fixture foreground")

        def settle_fixture():
            # Slow CI captures need enough frames to establish the same quiet
            # window. Keep the pixel/blank checks and the overall setup bound.
            until = time.monotonic() + 15
            while True:
                observed = call(prefix + "/wda/settle?budget_ms=3000&quiet_ms=150&min_ms=500")
                if observed.get("stable") is True and observed.get("blank") is not True:
                    return
                if time.monotonic() >= until:
                    raise RuntimeError("fixture did not render a stable nonblank scene: " + str(observed))

        settle_fixture()

        def find(identifier):
            return call(prefix + "/element", {"using": "accessibility id", "value": identifier})["ELEMENT"]

        def app_receipt(veto=None, state_fault=None):
            documents = Path(command("xcrun","simctl","get_app_container",udid,BUNDLE,"data"))/"Documents"
            documents.mkdir(exist_ok=True)
            nonce = secrets.token_hex(16)
            request={"nonce":nonce}
            if veto is not None: request["veto"]=veto
            if state_fault is not None: request["state_fault"]=state_fault
            (documents/"boundary-state-command.json").write_text(json.dumps(request))
            observed = {}
            def fresh():
                nonlocal observed
                try: observed=json.loads((documents/"boundary-state.json").read_text())
                except (OSError,ValueError): return False
                return observed.get("nonce")==nonce
            wait_for(fresh,"fresh App-owned receipt")
            assert observed.get("foreground") is True and observed.get("fields_present") is True,observed
            return observed


        if args.metadata_controls:
            control=find("metadata-control")
            receipt=app_receipt()
            enabled=call(prefix+f"/element/{control}/attribute/enabled")
            selected=call(prefix+f"/element/{control}/attribute/selected")
            evidence={"enabled":enabled,"selected":selected,"app_receipt":receipt}
            (out/"metadata-control.json").write_text(json.dumps(evidence,indent=2)+"\n")
            assert receipt["metadata_enabled"] is False and receipt["metadata_selected"] is True,receipt
            assert enabled is False and selected is True,evidence
            secure=find("field-secure")
            assert call(prefix+f"/element/{secure}/attribute/enabled") is True
            assert call(prefix+f"/element/{secure}/attribute/type")=="XCUIElementTypeSecureTextField"
            reports.append({"case":"disabled-selected-control-matches-App-state","passed":True,"evidence":evidence})

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
        settle_fixture()
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
                IPHONE_USE_RUNNER_MJPEG_URL=f"http://127.0.0.1:{video_port or port}",
                IPHONE_USE_RUNNER_MANAGED="0", IPHONE_USE_AGENT_TOKEN=tok,
                IPHONE_USE_PASSWORD="fixture-" + tok, IPHONE_USE_AUTO_FOCUS="0",
                IPHONE_USE_IDLE_RELEASE_SECS="0", IPHONE_USE_FLOWS_NO_AUTO_UPDATE="1")
            with (out / "daemon.log").open("w") as log:
                daemon = subprocess.Popen([str(daemon_binary), "serve"], env=env, stdout=log, stderr=log, start_new_session=True)

            def api(path, body=None, owner="input-continuation-fixture", takeover=False, timeout=60):
                data = None if body is None else json.dumps(body).encode()
                headers = {"Content-Type": "application/json", "Authorization": "Bearer " + tok,
                           "X-Phone-Control": "1", "X-Phone-Owner": owner}
                if takeover:
                    headers["X-Phone-Owner-Takeover"] = "1"
                request = urllib.request.Request(f"http://127.0.0.1:{daemon_port}{path}", data=data, headers=headers)
                try:
                    with opener.open(request, timeout=timeout) as response:
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
                # A previous unknown result may have invalidated the daemon's client session.
                # Establish it before issuing raw element handles; this sends no text.
                status, ready = api("/agent/input", {"type": "text", "text": ""})
                assert status == 200 and ready.get("ok") is True, ready
                first, second = find("field-a"), find("field-b")
                call(prefix + f"/element/{first}/click", {})
                wait_for(lambda: call(prefix + f"/element/{first}/attribute/focused") is True, "first field focus")
                before = call(prefix + f"/element/{first}/attribute/value") or ""
                target = call(prefix + "/wda/input-target")["token"]
                call(prefix + f"/element/{target}/clear", {"inputTarget": target})
                assert call(prefix + f"/element/{first}/attribute/value") in (None, "")
                return len(before)

            def app_trial(before, after):
                assert before["run_id"]==after["run_id"] and before["pid"]==after["pid"],"App process/trial changed"
                assert before["nonce"]!=after["nonce"],"stale App receipt"
                assert after["returns"]==before["returns"],"unexpected Return event"
                for other in ["b","multi","secure"]:
                    assert after["fields"][other]==before["fields"][other],"unselected field changed: "+other
                assert after["events_b"]==before["events_b"],"other field received editing events"

            def app_fault(before, after, draft):
                app_trial(before,after)
                assert before["fields"]["a"]["scalars"]==0 and before["focus_a"] is True and before["shifted"] is False,before
                assert after["shifted"] is True and after["focus_b"] is True,after
                assert after["events_a"]-before["events_a"]==20,after
                assert after["fields"]["a"]["scalars"]==20,after
                assert after["fields"]["a"]["sha256"]==hashlib.sha256(draft[:20].encode()).hexdigest(),after

            def begin():
                status, result = api("/agent/input", {"type": "text", "text": "字" * 500, "budget_ms": 6000})
                assert status == 502 and result.get("characters_uncertain") == 0, result
                assert result.get("characters_confirmed", 0) > 0 and result.get("continuation_safe") is True, result
                return result

            prepare()
            app_before = app_receipt() if args.expect_boundary_isolation else None
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
            app_after = app_receipt() if app_before else None
            if app_after:
                app_trial(app_before,app_after)
                assert app_after["fields"]["a"]["sha256"]==hashlib.sha256(("字"*500).encode()).hexdigest(),app_after
                assert app_after["events_a"]-app_before["events_a"]==500,app_after
            reports.append({"case": "daemon-continuation-500-character-readback", "passed": True,
                            "confirmed_partial_portions": portions, "final_length": 500,
                            "app_receipts":{"before":app_before,"after":app_after}})

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
            counter_session = call("/status")["sessionId"]
            def native_count(method, route):
                state=call("/status")
                assert state.get("sessionId")==counter_session,"Native Runner restarted during the trial"
                counts=state.get("http_request_counts")
                assert isinstance(counts,dict),"this experiment requires authenticated Native admission counters"
                return counts.get(method+" "+route,0)
            native_keys = lambda: native_count("POST","/wda/keys")
            before_calls = native_keys()
            app_before = app_receipt() if args.expect_boundary_isolation else None
            draft = "shift-focus-test-" + "字" * (500 - len("shift-focus-test-"))
            status, result = api("/agent/input", {"type": "text", "text": draft, "budget_ms": 15000})
            assert status == 502 and result.get("error") == "text_partially_typed", result
            assert result.get("characters_confirmed") == 0 and result.get("characters_uncertain") == 200, result
            assert "continue_token" not in result, result
            assert native_keys() - before_calls == 1, "mid-chunk focus change must stop before another chunk"
            first, second = find("field-a"), find("field-b")
            lengths = {"a": len(call(prefix + f"/element/{first}/attribute/value") or ""),
                       "b": len(call(prefix + f"/element/{second}/attribute/value") or "")}
            if args.expect_boundary_isolation:
                assert lengths == {"a":20,"b":0}, lengths
                app_after=app_receipt();app_fault(app_before,app_after,draft)
            reports.append({"case": "daemon-mid-chunk-focus-change-is-unknown-without-continuation",
                            "passed": True, "native_key_requests": 1, "field_lengths": lengths,
                            "app_receipts":{"before":app_before,"after":app_after if app_before else None}})

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

            status, released = api("/agent/owner", {"release": True}, owner="other-fixture-owner")
            assert status == 200, released
            first, second = find("field-a"), find("field-b")
            call(prefix + f"/element/{first}/click", {})
            wait_for(lambda: call(prefix + f"/element/{first}/attribute/focused") is True, "short input focus")
            route_count = lambda route: native_count("POST",route)
            before_atomic, before_keys = route_count("/ipu/text"), native_keys()
            before_targets = native_count("GET","/wda/input-target")
            status, result = api("/agent/input", {"type": "text", "text": "short replacement", "clear": True})
            assert status == 200 and result.get("ok") is True, result
            assert call(prefix + f"/element/{first}/attribute/value") == "short replacement"
            assert route_count("/ipu/text") - before_atomic == 1
            assert native_keys() == before_keys
            assert native_count("GET","/wda/input-target") == before_targets
            reports.append({"case": "daemon-short-clear-is-one-bound-native-request", "passed": True, "native_requests": 1})

            status, result = api("/agent/input", {"type": "text", "text": "Draft placeholder", "clear": True})
            assert status == 200 and result.get("ok") is True, result
            assert call(prefix + f"/element/{first}/attribute/value") == "Draft placeholder"
            status, result = api("/agent/input", {"type": "text", "text": "short replacement", "clear": True})
            assert status == 200 and result.get("ok") is True, result
            assert call(prefix + f"/element/{first}/attribute/value") == "short replacement"
            reports.append({"case": "daemon-short-clear-does-not-mistake-typed-placeholder-text-for-empty", "passed": True})

            status, result = api("/agent/input", {"type": "text", "text": "must not\nsubmit", "clear": True})
            assert status == 422 and result.get("outcome") == "not_sent", result
            assert "newline_requires_multiline_field" in result.get("runner_error", {}).get("message", ""), result
            assert call(prefix + f"/element/{first}/attribute/value") == "short replacement"
            reports.append({"case": "daemon-short-newline-refused-before-clearing-single-line-field", "passed": True})

            secure = find("field-secure")
            call(prefix + f"/element/{secure}/click", {})
            wait_for(lambda: call(prefix + f"/element/{secure}/attribute/focused") is True, "secure field focus")
            status, result = api("/agent/input", {"type": "text", "text": "must-not-type"})
            assert status == 422 and result.get("outcome") == "not_sent", result
            assert "secure_field_requires_human" in result.get("runner_error", {}).get("message", ""), result
            assert call(prefix + f"/element/{secure}/attribute/value") in (None, "")
            reports.append({"case": "daemon-short-secure-field-requires-human", "passed": True})

            multiline = find("field-multiline")
            call(prefix + f"/element/{multiline}/click", {})
            wait_for(lambda: call(prefix + f"/element/{multiline}/attribute/focused") is True, "multiline field focus")
            status, result = api("/agent/input", {"type": "text", "text": "one\ntwo", "clear": True})
            assert status == 200 and result.get("ok") is True, result
            assert call(prefix + f"/element/{multiline}/attribute/value") == "one\ntwo"
            reports.append({"case": "daemon-short-multiline-textview-newline-readback", "passed": True})

            second = find("field-b")
            call(prefix + f"/element/{second}/click", {})
            wait_for(lambda: call(prefix + f"/element/{second}/attribute/focused") is True, "second field setup focus")
            second_target = call(prefix + "/wda/input-target")["token"]
            call(prefix + f"/element/{second_target}/clear", {"inputTarget": second_target})
            prepare()
            draft = "shift-focus-test-" + "字" * 40
            before_atomic = route_count("/ipu/text")
            app_before = app_receipt() if args.expect_boundary_isolation else None
            status, result = api("/agent/input", {"type": "text", "text": draft})
            assert status == 502 and result.get("outcome") == "unknown" and result.get("retry_safe") is False, result
            assert "continue_token" not in result
            assert route_count("/ipu/text") - before_atomic == 1
            wait_for(lambda: api("/agent/status")[1].get("drivable") is True, "daemon recovery after unknown")
            # Read the receiver in one fresh AX snapshot. A health probe can replace the
            # native session after unknown input and invalidate handles between two lookups.
            tree = call(prefix + "/source?format=json")
            values = {}
            pending_nodes = [tree]
            while pending_nodes:
                node = pending_nodes.pop()
                if node.get("rawIdentifier") in ("field-a", "field-b"):
                    values[node["rawIdentifier"]] = node.get("value") or ""
                pending_nodes.extend(node.get("children", []))
            assert set(values) == {"field-a", "field-b"}, values
            a, b = values["field-a"], values["field-b"]
            if args.expect_boundary_isolation:
                assert a == draft[:20] and b == "", {"a":a,"b":b}
                app_after=app_receipt();app_fault(app_before,app_after,draft)
            else:
                assert a + b == draft, {"a": a, "b": b}
            reports.append({"case": "daemon-short-mid-input-focus-change-is-unknown-without-retry",
                            "passed": True, "native_requests": 1, "field_lengths": {"a": len(a), "b": len(b)},
                            "app_receipts":{"before":app_before,"after":app_after if app_before else None}})

            # Observe actual TCP disconnection separately from the acceptance verdicts above.
            # If default input continues, explicitly release this fixture's owner to stop it;
            # that is cleanup, not evidence that disconnect itself cancelled the device.
            for typing_budget in [None, 6000]:
                prepare()
                before_calls = native_keys()
                payload = {"type": "text", "text": "字" * 2000}
                if typing_budget is not None:
                    payload["budget_ms"] = typing_budget
                data = json.dumps(payload).encode()
                head = (f"POST /agent/input HTTP/1.1\r\nHost: 127.0.0.1:{daemon_port}\r\n"
                        f"Authorization: Bearer {tok}\r\nX-Phone-Control: 1\r\n"
                        f"X-Phone-Owner: input-continuation-fixture\r\nContent-Type: application/json\r\n"
                        f"Content-Length: {len(data)}\r\n\r\n").encode()
                connection = socket.create_connection(("127.0.0.1", daemon_port), timeout=10)
                try:
                    connection.sendall(head + data)
                    until = time.monotonic() + 10
                    while True:
                        live = call("/status")
                        if live.get("busy") is True and live.get("busyMs", 0) >= 200:
                            break
                        if time.monotonic() >= until:
                            raise RuntimeError("disconnect observation did not reach an active native request")
                        time.sleep(0.02)
                    closed_at = time.monotonic()
                    connection.shutdown(socket.SHUT_RDWR)
                finally:
                    connection.close()
                quiet_since = None
                released_for_cleanup = False
                observed_stop = None
                until = time.monotonic() + 15
                while time.monotonic() < until:
                    completed = native_keys() - before_calls
                    if completed >= 2 and not released_for_cleanup:
                        status, released = api("/agent/owner", {"release": True})
                        assert status == 200, released
                        released_for_cleanup = True
                    live = call("/status")
                    if completed >= 1 and live.get("busy") is not True:
                        if quiet_since is None:
                            quiet_since = time.monotonic()
                        elif time.monotonic() - quiet_since >= 0.75:
                            observed_stop = round((time.monotonic() - closed_at) * 1000)
                            break
                    else:
                        quiet_since = None
                    time.sleep(0.02)
                if observed_stop is None and not released_for_cleanup:
                    status, released = api("/agent/owner", {"release": True})
                    assert status == 200, released
                    released_for_cleanup = True
                observations.append({"case": "tcp-disconnect-during-input", "typing_budget_ms": typing_budget,
                    "admitted_native_chunks": native_keys() - before_calls,
                    "observed_quiet_after_disconnect_ms": observed_stop,
                    "explicit_owner_release_for_cleanup": released_for_cleanup,
                    "interpretation": "stop causality is unproven for bounded input; owner-release cleanup is not TCP cancellation"})


            if args.input_privacy:
                prepare()
                saved = begin()
                token = saved["continue_token"]
                before = call(prefix + f"/element/{first}/attribute/value")
                before_calls = native_keys()
                status, held = api("/agent/hold", {"secs":60,"private":True})
                assert status == 200, held
                status, blocked = api("/agent/input", {"type":"text","text":"x"})
                assert status == 409 and blocked.get("error") == "input_privacy_changed", blocked
                status, lifted = api("/agent/hold", {"secs":0})
                assert status == 200, lifted
                status, refused = api("/agent/input", {"type":"text","continue_token":token})
                assert status == 409 and refused.get("error") == "input_continuation_expired", refused
                assert native_keys() == before_calls
                assert call(prefix + f"/element/{first}/attribute/value") == before
                reports.append({"case":"private-hold-blocks-text-and-invalidates-prior-continuation", "passed":True,
                    "additional_native_key_requests":0,"confirmed_before_hold":saved["characters_confirmed"]})

                prepare()
                marker = Path(command("xcrun","simctl","get_app_container",udid,BUNDLE,"data")) / "Documents/input-started.count"
                marker.unlink(missing_ok=True)
                before_calls = native_keys()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pending = pool.submit(api,"/agent/input",{"type":"text","text":"字"*800})
                    until = time.monotonic()+10
                    while not marker.exists():
                        if pending.done() or time.monotonic() >= until:
                            raise RuntimeError("fixture never observed the first input event before privacy hold")
                        time.sleep(0.02)
                    first_event_count = int(marker.read_text())
                    assert first_event_count > 0
                    status, held = api("/agent/hold",{"secs":60,"private":True})
                    assert status == 200, held
                    status, lifted = api("/agent/hold",{"secs":0})
                    assert status == 200, lifted
                    status, partial = pending.result(timeout=30)
                assert status == 502 and partial.get("characters_confirmed") == 200, partial
                assert partial.get("characters_uncertain") == 0 and "continue_token" not in partial, partial
                assert partial.get("detail",{}).get("input_error") == "input_privacy_changed", partial
                assert native_keys()-before_calls == 1
                assert call(prefix + f"/element/{first}/attribute/value") == "字"*200
                reports.append({"case":"private-on-off-during-native-typing-stops-after-current-acknowledged-chunk", "passed":True,
                    "fixture_input_event_observed":True,"first_event_count":first_event_count,
                    "native_key_requests":1,"characters_confirmed":200,"characters_uncertain":0})
                prepare()
                status, held = api("/agent/hold",{"secs":1,"private":True})
                assert status == 200, held
                wait_for(lambda: api("/agent/status")[1].get("screen_private_secs") == 0,"natural private hold expiry")
                fresh = begin()
                status, held = api("/agent/hold",{"secs":60})
                assert status == 200, held
                for _ in range(5):
                    status, fresh = api("/agent/input",{"type":"text","continue_token":fresh["continue_token"]})
                    if status == 200 and fresh.get("ok") is True:
                        break
                    assert status == 502 and fresh.get("continuation_safe") is True, fresh
                else:
                    raise RuntimeError("fresh continuation after expiry did not complete")
                assert call(prefix + f"/element/{first}/attribute/value") == "字"*500
                status, lifted = api("/agent/hold",{"secs":0})
                assert status == 200, lifted
                reports.append({"case":"fresh-input-after-private-expiry-survives-normal-hold", "passed":True,"final_length":500})


            if args.observation_scope:
                marker = Path(command("xcrun","simctl","get_app_container",udid,BUNDLE,"data")) / "Documents/input-started.count"
                for batch in [False,True]:
                    prepare()
                    marker.unlink(missing_ok=True)
                    before_atomic, before_keys = route_count("/ipu/text"), native_keys()
                    action = {"type":"text","text":"observation-probe"}
                    path = "/agent/actions" if batch else "/agent/input?return=delta&settle_ms=2500"
                    payload = {"observe":True,"steps":[{"kind":"action","action":action}]} if batch else action
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        pending = pool.submit(api,path,payload)
                        until = time.monotonic()+10
                        while not marker.exists():
                            if pending.done() or time.monotonic()>=until:
                                raise RuntimeError("no fixture input event before scoped observation test")
                            time.sleep(0.01)
                        assert int(marker.read_text())>0
                        status, held = api("/agent/hold",{"secs":60,"private":True})
                        assert status==200,held
                        status, lifted = api("/agent/hold",{"secs":0})
                        assert status==200,lifted
                        status, receipt = pending.result(timeout=30)
                    assert status==(423 if batch else 200) and receipt.get("ok") is (not batch),receipt
                    reason="screen_privacy_changed" if batch else "input_privacy_changed"
                    assert receipt.get("observation_omitted") is True and receipt.get("scope_changed")==reason,receipt
                    assert all(key not in receipt for key in ["elements","delta","snapshot","alert","image"]),receipt
                    if batch:
                        assert receipt.get("completed")==1 and receipt.get("applied_actions")==1,receipt
                        assert receipt["steps"][0]["ok"] is True,receipt
                    assert route_count("/ipu/text")-before_atomic==1 and native_keys()==before_keys
                    assert call(prefix+f"/element/{first}/attribute/value")=="observation-probe"
                    reports.append({"case":"batch-applied-receipt-withholds-stale-observation" if batch else "single-applied-receipt-withholds-stale-observation",
                        "passed":True,"native_atomic_requests":1,"ok":not batch,"observation_omitted":True,"independent_readback":True})

            if args.native_scope:
                prepare()
                before_terminate=route_count("/wda/apps/terminate")
                before_launch=route_count("/wda/apps/launch")
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pending=pool.submit(api,"/agent/input",{"type":"launch_app","bundle":BUNDLE,"fresh":True})
                    until=time.monotonic()+10
                    while route_count("/wda/apps/terminate")==before_terminate:
                        if pending.done() or time.monotonic()>=until:
                            raise RuntimeError("fresh launch did not acknowledge termination")
                        time.sleep(0.01)
                    status,held=api("/agent/hold",{"secs":60,"private":True})
                    assert status==200,held
                    status,lifted=api("/agent/hold",{"secs":0})
                    assert status==200,lifted
                    status,receipt=pending.result(timeout=30)
                assert status==409 and receipt.get("outcome")=="partial",receipt
                assert receipt.get("native_mutations_confirmed")==1 and receipt.get("native_mutations_uncertain")==0,receipt
                assert receipt.get("retry_safe") is False,receipt
                assert route_count("/wda/apps/terminate")==before_terminate+1
                assert route_count("/wda/apps/launch")==before_launch
                reports.append({"case":"native-termination-ack-preserved-without-late-relaunch","passed":True,
                    "native_mutations_confirmed":1,"native_mutations_uncertain":0,"later_launch_requests":0})
                command("xcrun","simctl","launch",udid,BUNDLE)
                settle_fixture()
                first,second=find("field-a"),find("field-b")
                call(prefix+f"/element/{first}/click",{})
                wait_for(lambda: call(prefix+f"/element/{first}/attribute/focused") is True,"fixture focus after interrupted fresh launch")

            if mcp_binary:
                prepare()
                env = dict(environment)
                env.update(IPHONE_USE_URL=f"http://127.0.0.1:{daemon_port}", IPHONE_USE_TOKEN=tok,
                    IPHONE_USE_OWNER="input-continuation-fixture", IPHONE_USE_MCP_TOOLS="phone_type,phone_run_steps",
                    IPHONE_USE_MCP_STRUCTURED="full")
                with (out / "mcp.log").open("w") as log:
                    mcp = subprocess.Popen([str(mcp_binary)], env=env, stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=log, start_new_session=True)
                reply_buffer = b""

                def rpc(message):
                    mcp.stdin.write((json.dumps(message) + "\n").encode())
                    mcp.stdin.flush()

                def reply(identifier, timeout=10):
                    nonlocal reply_buffer
                    until = time.monotonic() + timeout
                    while time.monotonic() < until:
                        while b"\n" in reply_buffer:
                            line, reply_buffer = reply_buffer.split(b"\n", 1)
                            result = json.loads(line)
                            if result.get("id") == identifier:
                                return result
                        readable, _, _ = select.select([mcp.stdout], [], [], max(0, until - time.monotonic()))
                        if readable:
                            data = os.read(mcp.stdout.fileno(), 65536)
                            if not data:
                                raise RuntimeError("MCP exited before its reply")
                            reply_buffer += data
                    raise RuntimeError("MCP reply deadline")

                rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                    "protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "input-cancel-fixture", "version": "1"}}})
                assert "result" in reply(1)
                rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})
                mcp_rpc, mcp_reply = rpc, reply
                before_calls = native_keys()
                rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
                    "name": "phone_type", "arguments": {"text": "字" * 2000, "observe": False}}})
                until = time.monotonic() + 10
                while True:
                    live = call("/status")
                    if live.get("busy") is True and live.get("busyMs", 0) >= 200:
                        break
                    if mcp.poll() is not None or time.monotonic() >= until:
                        raise RuntimeError("MCP input did not enter an active native request")
                    time.sleep(0.02)
                cancelled_at = time.monotonic()
                rpc({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {
                    "requestId": 2, "reason": "input fixture cancellation"}})
                cancelled = reply(2)
                verdict = cancelled.get("result", {}).get("structuredContent", {})
                assert verdict.get("outcome") == "unknown" and verdict.get("retry_safe") is False, cancelled
                quiet_since = None
                observed_stop = None
                until = time.monotonic() + 10
                while time.monotonic() < until:
                    completed = native_keys() - before_calls
                    assert completed <= 1, "MCP cancellation dispatched a later chunk"
                    live = call("/status")
                    if completed == 1 and live.get("busy") is not True:
                        if quiet_since is None:
                            quiet_since = time.monotonic()
                        elif time.monotonic() - quiet_since >= 0.75:
                            observed_stop = round((time.monotonic() - cancelled_at) * 1000)
                            break
                    else:
                        quiet_since = None
                    time.sleep(0.02)
                assert observed_stop is not None, "native input did not become quiet after MCP cancellation"
                reports.append({"case": "mcp-cancel-notification-stops-after-current-native-chunk",
                    "passed": True, "native_key_requests": 1, "verdict": "unknown",
                    "observed_quiet_after_notification_ms": observed_stop})

            if args.recovery:
                status, result = api("/agent/input", {"type": "tap_locator", "locator": {"label": "__missing_fixture_target__"}})
                assert status == 422 and result.get("error") == "element_not_found", result
                assert result.get("outcome") == "not_sent" and result.get("retry_safe") is True, result
                image = result.get("image", {})
                assert image.get("png_base64") and image.get("pixel_size", [0, 0])[0] > 0, result
                assert image["received_at_ms"] >= image["requested_at_ms"]
                assert "failure" in image.get("relation", "")
                reports.append({"case": "daemon-visual-failure-fresh-image-preserves-verdict", "passed": True,
                                "pixel_size": image["pixel_size"], "source": image.get("source")})

                status, held = api("/agent/hold", {"secs": 60, "private": True})
                assert status == 200, held
                status, result = api("/agent/input", {"type": "tap_locator", "locator": {"label": "__missing_fixture_target__"}})
                assert status == 409 and result.get("error") == "input_privacy_changed" and "image" not in result, result
                reports.append({"case": "daemon-private-hold-withholds-failure-image", "passed": True})
                status, released = api("/agent/hold", {"secs": 0})
                assert status == 200, released

                if mcp_binary:
                    rpc({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                        "name": "phone_run_steps", "arguments": {"steps": [{"kind": "tap_locator",
                            "locator": {"label": "__missing_fixture_target__"}}], "observe": False}}})
                    recovered = reply(3)
                    payload = recovered.get("result", {})
                    assert payload.get("isError") is True, recovered
                    verdict = payload.get("structuredContent", {})
                    assert verdict.get("outcome") == "not_sent" and verdict.get("retry_safe") is True, recovered
                    images = [block for block in payload.get("content", []) if block.get("type") == "image"]
                    assert len(images) == 1 and "png_base64" not in json.dumps(verdict), "image must be lifted once"
                    assert all("png_base64" not in block.get("text", "") for block in payload.get("content", []))
                    reports.append({"case": "stdio-visual-recovery-one-image-with-original-batch-fate", "passed": True})


            if args.hosts:
                status, before_owner = api("/agent/status")
                assert status == 200
                before_calls = native_keys()
                for iteration in [1, 2]:
                    if mcp and mcp.poll() is None:
                        os.killpg(mcp.pid, signal.SIGTERM)
                        mcp.wait(timeout=10)
                    env = dict(environment)
                    env.update(IPHONE_USE_URL=f"http://127.0.0.1:{daemon_port}", IPHONE_USE_TOKEN=tok,
                        IPHONE_USE_OWNER="workbuddy-view-fixture", IPHONE_USE_MCP_HOST="workbuddy",
                        IPHONE_USE_MCP_TOOLS="phone_screen", IPHONE_USE_MCP_STRUCTURED="off")
                    with (out / "mcp.log").open("a") as log:
                        mcp = subprocess.Popen([str(mcp_binary)], env=env, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=log, start_new_session=True)
                    reply_buffer = b""
                    rpc({"jsonrpc":"2.0","id":1,"method":"initialize","params":{
                        "protocolVersion":"2025-06-18","capabilities":{},
                        "clientInfo":{"name":"workbuddy-fixture","version":"1"}}})
                    assert "result" in reply(1)
                    rpc({"jsonrpc":"2.0","method":"notifications/initialized"})
                    rpc({"jsonrpc":"2.0","id":2,"method":"resources/read","params":{
                        "uri":f"ui://iphone-use/frame-v1/600/{iteration}"}})
                    resource = reply(2)
                    frame = json.loads(resource["result"]["contents"][0]["text"])
                    assert frame["owner"] == before_owner.get("owner"), frame
                    png = base64.b64decode(frame["frame"]["data"], validate=True)
                    assert png.startswith(b"\x89PNG\r\n\x1a\n")
                status, after_owner = api("/agent/status")
                assert status == 200 and after_owner.get("owner") == before_owner.get("owner")
                assert native_keys() == before_calls, "resource frame path sent keyboard input"
                reports.append({"case":"workbuddy-resource-frame-across-two-mcp-processes", "passed":True,
                    "processes":2, "frame_mime":"image/png", "owner_unchanged":True, "native_key_requests":0})
                status, held = api("/agent/hold", {"secs":60,"private":True})
                assert status == 200, held
                rpc({"jsonrpc":"2.0","id":3,"method":"resources/read","params":{
                    "uri":"ui://iphone-use/frame-v1/600/3"}})
                resource = reply(3)
                hidden = json.loads(resource["result"]["contents"][0]["text"])
                assert hidden["frame"] is None and hidden.get("clear_frame") is True, hidden
                assert hidden.get("private_secs",0) > 0, hidden
                status, lifted = api("/agent/hold", {"secs":0})
                assert status == 200, lifted
                rpc({"jsonrpc":"2.0","id":4,"method":"resources/read","params":{
                    "uri":"ui://iphone-use/frame-v1/600/4"}})
                resource = reply(4)
                visible = json.loads(resource["result"]["contents"][0]["text"])
                assert base64.b64decode(visible["frame"]["data"],validate=True).startswith(b"\x89PNG\r\n\x1a\n")
                assert native_keys() == before_calls
                reports.append({"case":"workbuddy-private-capture-clears-frame-and-new-read-resumes", "passed":True,
                    "private_frame":None,"clear_frame":True,"fresh_read_after_unhide":"image/png","native_key_requests":0})

            if args.video:
                status,initial=api("/agent/status")
                before_keys=native_keys()
                identifier=100
                def video_read(reset):
                    nonlocal identifier
                    identifier+=1
                    rpc({"jsonrpc":"2.0","id":identifier,"method":"resources/read","params":{
                        "uri":f"ui://iphone-use/video-v1/{int(reset)}/{identifier}"}})
                    result=reply(identifier)
                    return json.loads(result["result"]["contents"][0]["text"])
                packets=[]
                scope=None
                until=time.monotonic()+15
                while time.monotonic()<until and len(packets)<3:
                    frame=video_read(scope is None)
                    assert not frame.get("video_unavailable"),frame
                    video=frame.get("video",{})
                    if video.get("reset"):packets=[]
                    scope=video.get("scope",scope)
                    packets.extend(video.get("packets",[]))
                assert packets and packets[0]["keyframe"],"no native keyframe in bounded reads"
                raw=b"".join(base64.b64decode(packet["data"],validate=True) for packet in packets)
                (out/"native-panel.h264").write_bytes(raw)
                command("ffmpeg","-v","error","-f","h264","-i",out/"native-panel.h264","-frames:v","1",out/"native-panel.png")
                png=(out/"native-panel.png").read_bytes()
                assert png.startswith(b"\x89PNG\r\n\x1a\n")
                size=[int.from_bytes(png[16:20],"big"),int.from_bytes(png[20:24],"big")]
                assert min(size)>0
                reports.append({"case":"native-h264-runner-daemon-stdio-resource-independent-decode","passed":True,
                    "packets":len(packets),"encoded_bytes":len(raw),"decoded_pixel_size":size,"credentials_in_panel":False,
                    "annexb_sha256":hashlib.sha256(raw).hexdigest(),"decoded_png_sha256":hashlib.sha256(png).hexdigest(),
                    "native_passthrough_log": "passing the device runner\'s own H.264 through" in (out/"daemon.log").read_text(errors="replace")})
                keepalive=video_read(False)
                assert keepalive.get("video",{}).get("scope"),keepalive
                scope=keepalive["video"]["scope"]
                assert api("/agent/hold",{"secs":60,"private":True})[0]==200
                assert api("/agent/hold",{"secs":0})[0]==200
                stale=video_read(False)
                assert stale.get("clear_frame") is True and "video" not in stale,stale
                fresh=video_read(True)
                assert fresh.get("video",{}).get("scope")!=scope and not fresh.get("video_unavailable"),fresh
                assert native_keys()==before_keys
                status,final=api("/agent/status")
                assert final.get("owner")==initial.get("owner")
                reports.append({"case":"native-h264-private-on-off-clears-old-subscription","passed":True,
                    "stale_packets_returned":0,"new_scope":True,"native_key_requests":0,"owner_unchanged":True})

                started=time.monotonic()
                rotations=0
                packet_count=0
                awaiting_key=False
                while time.monotonic()-started<20:
                    body=video_read(False)
                    assert body.get("video") and not body.get("video_unavailable"),body
                    video=body["video"]
                    assert video["scope"]==fresh["video"]["scope"],"no privacy transition during endurance"
                    if video.get("reset"):
                        rotations+=1
                        awaiting_key=True
                    if video["packets"]:
                        if awaiting_key:
                            assert video["packets"][0]["keyframe"],"rotation must begin on a keyframe"
                            awaiting_key=False
                        packet_count+=len(video["packets"])
                assert rotations>=1 and packet_count>=3
                reports.append({"case":"native-h264-continuous-view-crosses-http-deadline","passed":True,
                    "observed_ms":round((time.monotonic()-started)*1000),"automatic_rotations":rotations,
                    "packets_received":packet_count,"png_fallbacks":0,"native_key_requests":native_keys()-before_keys})
                peers=[]
                for name in ["viewer-a","viewer-b"]:
                    env=dict(environment)
                    env.update(IPHONE_USE_URL=f"http://127.0.0.1:{daemon_port}",IPHONE_USE_TOKEN=tok,
                        IPHONE_USE_OWNER=name,IPHONE_USE_MCP_HOST="workbuddy",IPHONE_USE_MCP_TOOLS="phone_screen")
                    peer=VideoPeer(mcp_binary,env,out/"mcp.log")
                    video_peers.append(peer)
                    peer.initialize()
                    peers.append(peer)
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results=list(pool.map(lambda peer:peer.frame(True),peers))
                assert all(body.get("video") and not body.get("video_unavailable") for body in results),results
                for peer,body in zip(peers,results):
                    until=time.monotonic()+5
                    while not body["video"]["packets"]:
                        assert time.monotonic()<until,"independent viewer received no keyframe"
                        body=peer.frame(False)
                        assert body.get("video") and not body.get("video_unavailable"),body
                    assert body["video"]["packets"][0]["keyframe"],body
                # Keep B polling while A reconnects/closes: a paused B would
                # legitimately expire its own two-second lease on a slow host.
                for operation in [lambda:peers[0].frame(True),peers[0].close]:
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        pending=pool.submit(operation)
                        independent=None
                        while not pending.done() or independent is None:
                            independent=peers[1].frame(False)
                            assert independent.get("video",{}).get("reset") is False,independent
                        pending.result(timeout=12)
                peers[1].close()
                until=time.monotonic()+6
                while True:
                    status,viewers=api("/agent/status")
                    if viewers.get("viewer_count")==0:break
                    assert time.monotonic()<until,viewers
                    time.sleep(0.05)
                assert native_keys()==before_keys
                assert viewers.get("owner")==initial.get("owner")
                reports.append({"case":"native-h264-two-mcp-viewers-independent-and-idle-close","passed":True,
                    "independent_processes":2,"other_viewer_reset":False,"final_viewer_count":0,
                    "native_key_requests":0,"owner_unchanged":True})

            if args.list_recovery:
                env=dict(environment)
                env.update(IPHONE_USE_URL=f"http://127.0.0.1:{daemon_port}",IPHONE_USE_TOKEN=tok,
                    IPHONE_USE_OWNER="input-continuation-fixture",IPHONE_USE_MCP_HOST="generic",
                    IPHONE_USE_MCP_TOOLS="phone_scroll_find,phone_collect_list",IPHONE_USE_MCP_STRUCTURED="full")
                peer=VideoPeer(mcp_binary,env,out/"mcp.log")
                video_peers.append(peer)
                peer.initialize()
                before_actions=route_count("/actions")
                for lookup in [True,False]:
                    result=peer.request("tools/call",{"name":"phone_scroll_find" if lookup else "phone_collect_list",
                        "arguments":{"label":"__list_recovery_missing__","max_swipes":0} if lookup else {"row_kind":"Slider","max_pages":1}})["result"]
                    verdict=result.get("structuredContent",{})
                    assert verdict.get("swipes")==0 and verdict.get("native_mutations_confirmed")==0,verdict
                    assert bool(result.get("isError"))==lookup,result
                    if lookup:assert verdict.get("found") is False and verdict.get("error")=="element_not_found",verdict
                    else:assert verdict.get("complete") is False and verdict.get("stop_reason")=="no_rows",verdict
                    images=[block for block in result.get("content",[]) if block.get("type")=="image"]
                    assert len(images)==1,result
                    assert base64.b64decode(images[0]["data"],validate=True).startswith(b"\x89PNG\r\n\x1a\n")
                    assert "png_base64" not in json.dumps(verdict)
                    assert all("png_base64" not in block.get("text","") for block in result.get("content",[]))
                    assert route_count("/actions")==before_actions
                    reports.append({"case":"stdio-scroll-find-fresh-diagnostic-without-swipe" if lookup else "stdio-collect-no-rows-fresh-diagnostic-keeps-incomplete",
                        "passed":True,"image_blocks":1,"native_swipes":0,"original_verdict_preserved":True})
                before_actions=route_count("/actions")
                source_reads=lambda:sum(bool(re.search(r"ipu-runner: GET (?:/session/[^/ ]+)?/source(?:\?[^ ]*)? ->",line)) for line in log_path.read_text(errors="replace").splitlines())
                before_reads=source_reads()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pending=pool.submit(api,"/agent/scroll_find",{"label":"__list_recovery_missing__","max_swipes":1})
                    until=time.monotonic()+10
                    while route_count("/actions")==before_actions:
                        if pending.done() or time.monotonic()>=until:raise RuntimeError("list did not acknowledge native swipe")
                        time.sleep(0.01)
                    assert api("/agent/hold",{"secs":60,"private":True})[0]==200
                    assert api("/agent/hold",{"secs":0})[0]==200
                    status,receipt=pending.result(timeout=15)
                (out/"list-scope-receipt.json").write_text(json.dumps({"status":status,"receipt":receipt},indent=2)+"\n")
                assert status==409 and receipt.get("outcome")=="partial",receipt
                assert receipt.get("swipes")==1 and receipt.get("native_mutations_confirmed")==1 and receipt.get("native_mutations_uncertain")==0,receipt
                assert receipt.get("retry_safe") is False and receipt.get("observation_omitted") is True,receipt
                assert all(key not in receipt for key in ["snapshot","rows","target","candidates","image"]),receipt
                assert route_count("/actions")==before_actions+1,{"before_actions":before_actions,"after_actions":route_count("/actions")}
                assert source_reads()==before_reads+1,{"before_reads":before_reads,"after_reads":source_reads()}
                reports.append({"case":"list-private-transition-preserves-swipe-ack-without-post-scope-read","passed":True,
                    "native_swipes_confirmed":1,"native_mutations_uncertain":0,"later_source_reads":0,"retry_safe":False})
                peer.close()

            if args.list_deadline:
                # An interrupted gesture can still be decelerating. Start a
                # new owned fixture task, rather than replaying a guarded clear.
                command("xcrun","simctl","terminate",udid,BUNDLE)
                command("xcrun","simctl","launch",udid,BUNDLE)
                settle_fixture()
                assert api("/agent/input",{"type":"text","text":""})[0]==200
                first,second=find("field-a"),find("field-b")
                wait_for(lambda:call(prefix+f"/element/{first}/attribute/focused") is True,"fresh deadline fixture focus")
                assert call(prefix+f"/element/{first}/attribute/value") in (None,""),"fresh workload field is not empty"
                container=Path(command("xcrun","simctl","get_app_container",udid,BUNDLE,"data"))
                marker=container/"Documents/input-started.count"
                if marker.exists():marker.unlink()  # Synthetic fixture marker only.
                field_receipt=container/"Documents/field-a-state.json"
                if field_receipt.exists():field_receipt.unlink()
                text="queue-deadline-"+"字"*6000
                before_actions=route_count("/actions")
                count_sources=lambda:sum(bool(re.search(r"ipu-runner: GET (?:/session/[^/ ]+)?/source(?:\?[^ ]*)? ->",line)) for line in log_path.read_text(errors="replace").splitlines())
                before_sources=count_sources()
                pool=ThreadPoolExecutor(max_workers=2)
                try:
                    typing=pool.submit(api,"/agent/input",{"type":"text","text":text,"clear":False},timeout=360)
                    until=time.monotonic()+10
                    while not marker.exists():
                        if typing.done() or time.monotonic()>=until:raise RuntimeError("long input did not start before queue deadline probe")
                        time.sleep(0.01)
                    started=time.monotonic()
                    (out/"list-deadline-progress.json").write_text(json.dumps({"phase":"queued_behind_owned_input","started_at_ms":round(time.time()*1000)})+"\n")
                    queued=pool.submit(api,"/agent/scroll_find",{"label":"__deadline_fixture_missing__","max_swipes":1},timeout=90)
                    status,receipt=queued.result(timeout=92)
                    elapsed=round((time.monotonic()-started)*1000)
                    (out/"list-deadline-receipt.json").write_text(json.dumps({"status":status,"elapsed_ms":elapsed,"receipt":receipt},indent=2)+"\n")
                    assert status==504 and receipt.get("error")=="list_deadline",receipt
                    assert receipt.get("outcome")=="not_sent" and receipt.get("retry_safe") is True,receipt
                    assert receipt.get("native_mutations_confirmed")==0 and receipt.get("native_mutations_uncertain")==0 and receipt.get("swipes")==0,receipt
                    assert 80000<=elapsed<=85000,{"elapsed_ms":elapsed}
                    assert not typing.done(),"busy precondition ended before the queue deadline"
                    assert count_sources()==before_sources and route_count("/actions")==before_actions
                    (out/"list-deadline-progress.json").write_text(json.dumps({"phase":"deadline_returned_waiting_for_original_input","elapsed_ms":elapsed})+"\n")
                    status,finished=typing.result(timeout=60)
                    assert status==200 and finished.get("ok") is True,finished
                    assert count_sources()==before_sources and route_count("/actions")==before_actions
                    first=find("field-a")
                    readback=call(prefix+f"/element/{first}/attribute/value")
                    expected_hash=hashlib.sha256(text.encode()).hexdigest()
                    def fixture_value_matches():
                        if not field_receipt.exists():return False
                        state=json.loads(field_receipt.read_text())
                        return state.get("characters")==len(text) and state.get("sha256")==expected_hash
                    wait_for(fixture_value_matches,"fixture-owned full field count/hash")
                    oracle=json.loads(field_receipt.read_text())
                    (out/"list-deadline-field-oracle.json").write_text(json.dumps(oracle,indent=2)+"\n")
                    (out/"list-deadline-progress.json").write_text(json.dumps({"phase":"finished_original_input_and_independent_readback","elapsed_ms":elapsed,"characters_verified":oracle["characters"],"readback_sha256":oracle["sha256"],"ax_attribute_chars_observed":len(readback or "")})+"\n")
                    reports.append({"case":"real-queued-list-stops-at-entry-deadline-before-native-dispatch","passed":True,
                        "elapsed_ms":elapsed,"native_mutations_confirmed":0,"native_mutations_uncertain":0,"new_swipes":0,"new_source_reads":0,
                        "busy_input_observed":True,"privacy_or_owner_transition_used_for_cleanup":False,"original_input_completed":True,"independent_characters_verified":oracle["characters"],"fixture_value_sha256":oracle["sha256"],"ax_attribute_chars_observed":len(readback or "")})
                finally:
                    pool.shutdown(wait=False,cancel_futures=True)

        if args.state_boundaries:
            previous_run=None
            for fault in ["disable","hide","secure"]:
                for length in [57,500]:
                    command("xcrun","simctl","terminate",udid,BUNDLE)
                    command("xcrun","simctl","launch",udid,BUNDLE)
                    settle_fixture()
                    before=app_receipt(state_fault=fault)
                    assert before["run_id"]!=previous_run and before["focus_a"] is True,before
                    previous_run=before["run_id"]
                    assert before["a_enabled"] is True and before["a_hidden"] is False and before["a_secure"] is False,before
                    assert before["fields"]["a"]["scalars"]==0 and before["state_fault_triggered"] is False,before
                    text="state-guard-test-"+"字"*(length-len("state-guard-test-"))
                    routes=["/ipu/text","/wda/keys"]
                    counts={route:native_count("POST",route) for route in routes}
                    status,verdict=api("/agent/input",{"type":"text","text":text})
                    after=app_receipt()
                    evidence={"before":before,"after":after,"verdict":verdict}
                    (out/f"state-{fault}-{length}.json").write_text(json.dumps(evidence,indent=2)+"\n")
                    assert status==502 and verdict.get("outcome")==("unknown" if length<=200 else "partial") and verdict.get("retry_safe") is False,verdict
                    if length>200:
                        assert verdict.get("error")=="text_partially_typed",verdict
                        assert verdict.get("characters_confirmed")==0 and verdict.get("characters_uncertain")==200,verdict
                        assert verdict.get("characters_total")==length,verdict
                    assert "continue_token" not in verdict,verdict
                    app_trial(before,after)
                    prefix_hash=hashlib.sha256(text[:20].encode()).hexdigest()
                    assert after["state_fault_triggered"] is True and after["fault_scalars"]==20,after
                    assert after["fault_sha256"]==prefix_hash,after
                    assert after["fields"]["a"]["scalars"]==20 and after["fields"]["a"]["sha256"]==prefix_hash,after
                    assert after["events_a"]-before["events_a"]==20,after
                    assert {"disable":not after["a_enabled"],"hide":after["a_hidden"],"secure":after["a_secure"]}[fault] is True,after
                    wait_for(lambda:call("/status").get("busy") is not True,"Native quiet after state fault")
                    time.sleep(.5)
                    stable=app_receipt()
                    app_trial(after,stable)
                    assert stable["fields"]==after["fields"] and stable["events_a"]==after["events_a"],stable
                    for route in routes:
                        expected=1 if route==("/ipu/text" if length<=200 else "/wda/keys") else 0
                        assert native_count("POST",route)-counts[route]==expected,"later input admitted after state fault"
                    reports.append({"case":f"mid-input-{fault}-{length}","passed":True,"app_receipts":{"before":before,"after":after,"stable":stable},"verdict":verdict,"admitted_native_chunks":1})

            # Faults alter the owned App. Give subsequent controls a new,
            # normal fixture instead of reusing a hidden/secure/disabled field.
            command("xcrun","simctl","terminate",udid,BUNDLE)
            command("xcrun","simctl","launch",udid,BUNDLE)
            settle_fixture()

        if args.expect_boundary_isolation:
            for identifier,key,focus,counter in [("field-a","a","focus_a","veto_calls_a"),
                                                 ("field-multiline","multi","focus_multi","veto_calls_multi")]:
                prepare()
                field=find(identifier)
                call(prefix+f"/element/{field}/click",{})
                before=app_receipt(veto=key)
                assert before[focus] is True and before["veto"]==key,before
                status,reply=api("/agent/input",{"type":"text","text":"blocked"})
                assert status==502 and reply.get("outcome")=="unknown" and reply.get("retry_safe") is False,reply
                after=app_receipt()
                assert after["run_id"]==before["run_id"] and after["pid"]==before["pid"]
                assert after["fields"]==before["fields"],"App veto was bypassed"
                assert after[counter]-before[counter]==1,"focused App veto was not reached exactly once"
                assert after["events_a"]==before["events_a"] and after["events_b"]==before["events_b"]
                assert after["returns"]==before["returns"]
                wait_for(lambda:api("/agent/status")[1].get("drivable") is True,"healthy Runner after App veto")
                ready=app_receipt(veto="off")
                assert ready["veto"]=="off" and ready[focus] is True,ready
                status,reply=api("/agent/input",{"type":"text","text":"accepted","clear":True})
                assert status==200 and reply.get("ok") is True,reply
                positive=app_receipt()
                assert positive["fields"][key]["sha256"]==hashlib.sha256(b"accepted").hexdigest(),positive
                for other in ["a","b","multi","secure"]:
                    if other!=key:assert positive["fields"][other]==after["fields"][other],"unrelated field changed"
                assert positive["returns"]==after["returns"]
                reports.append({"case":"focused-App-veto-"+key,"passed":True,
                    "app_receipts":{"before":before,"after":after,"positive":positive},"veto_callbacks":1})

        if args.long_boundaries:
            command("xcrun","simctl","terminate",udid,BUNDLE)
            command("xcrun","simctl","launch",udid,BUNDLE,"--long-value-fixture")
            settle_fixture()
            seed="queue-deadline-"+"字"*6000
            before=app_receipt(veto="a")
            assert before["focus_a"] is True and before["fields"]["a"]["sha256"]==hashlib.sha256(seed.encode()).hexdigest(),before
            assert before["selection_a"]=={"location":len(seed),"length":0},before
            status,verdict=api("/agent/input",{"type":"text","text":"blocked"})
            assert status==502 and verdict.get("outcome")=="unknown" and verdict.get("retry_safe") is False,verdict
            after=app_receipt()
            assert after["fields"]==before["fields"] and after["selection_a"]==before["selection_a"],after
            assert after["veto_calls_a"]==before["veto_calls_a"]+1,after
            assert after["events_a"]==before["events_a"] and after["returns"]==before["returns"],after
            reports.append({"case":"long-field-focused-App-veto","passed":True,"app_receipts":{"before":before,"after":after}})
            wait_for(lambda:api("/agent/status")[1].get("drivable") is True,"healthy Runner after long-field veto")
            before=app_receipt(veto="off")
            started=time.monotonic()
            mcp_rpc({"jsonrpc":"2.0","id":30,"method":"tools/call","params":{"name":"phone_type","arguments":{"text":"字"*501,"observe":False}}})
            answer=mcp_reply(30,timeout=45)
            elapsed=round((time.monotonic()-started)*1000)
            result=answer.get("result",{})
            verdict=result.get("structuredContent")
            if not isinstance(verdict,dict):
                verdict=next((json.loads(item["text"]) for item in result.get("content",[]) if item.get("type")=="text" and item.get("text","").startswith("{")),{})
            after=app_receipt()
            # Record the independent receipt even when the public deadline fails.
            (out/"long-mcp-receipt.json").write_text(json.dumps({"wall_ms":elapsed,"answer":answer,"before":before,"after":after},indent=2)+"\n")
            assert verdict.get("ok") is True and result.get("isError") is not True,answer
            app_trial(before,after)
            assert after["fields"]["a"]["sha256"]==hashlib.sha256((seed+"字"*501).encode()).hexdigest(),after
            assert after["events_a"]-before["events_a"]==501,after
            assert after["selection_a"]=={"location":len(seed)+501,"length":0},after
            reports.append({"case":"public-MCP-long-field-501-append","passed":True,"wall_ms":elapsed,"app_receipts":{"before":before,"after":after},"answer":answer})

    except Exception as error:
        reports.append({"case": "harness-or-current-case", "passed": False, "error": str(error),"error_type":type(error).__name__,"traceback":traceback.format_exc(limit=5)})
    finally:
        for peer in video_peers:
            try:peer.close()
            except Exception as error:cleanup_errors.append(str(error))
        for process in [mcp, daemon, runner]:
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
        for name in ["runner.log", "daemon.log", "mcp.log"]:
            log = out / name
            if log.exists():
                log.write_text(log.read_text(errors="replace").replace(tok, "[redacted fixture token]"))
        files = [Path(__file__).relative_to(ROOT), Path("runner/IPhoneUseRunner/IPhoneUseRunnerUITests/RunnerRoutes.swift"),
                 Path("runner/IPhoneUseRunner/IPhoneUseRunnerUITests/RunnerElements.swift"),
                 Path("runner/IPhoneUseRunner/IPhoneUseRunnerUITests/IPURBridge.m"),
                 Path("runner/IPhoneUseRunner/IPhoneUseRunnerUITests/RunnerTests.swift")]
        if args.video:
            files.extend(map(Path,["runner/IPhoneUseRunner/IPhoneUseRunnerUITests/RunnerH264.swift","runner/IPhoneUseRunner/IPhoneUseRunnerUITests/RunnerMJPEG.swift"]))
        if daemon_binary:
            files.extend(map(Path, ["Cargo.lock", "crates/server/Cargo.toml", "crates/mcp/Cargo.toml", "crates/server/src/http.rs", "crates/server/src/collect.rs", "crates/server/src/runner.rs", "crates/server/src/input_continuation.rs", "crates/server/src/recovery.rs", "crates/server/src/video.rs", "crates/server/src/observation.rs", "crates/server/src/native_scope.rs", "crates/server/src/timing.rs"]))
        if mcp_binary:
            files.extend(map(Path, ["crates/mcp/src/server.rs", "crates/mcp/src/client.rs", "crates/mcp/src/screen.rs", "crates/mcp/src/screen.html", "crates/mcp/src/screen_video.rs", "crates/mcp/src/compact.rs"]))
        manifest = {"native_request_oracle":"authenticated admission counters",
                    "experimental_character_boundaries": args.expect_boundary_isolation,
                    "scope": "actual XCTest runner on disposable iOS Simulator; not physical-device evidence",
            "simulator": udid, "runtime": args.runtime, "cases": reports, "observations": observations, "cleanup_errors": cleanup_errors,
            "xctestrun_sha256": hashlib.sha256(xctestrun.read_bytes()).hexdigest(),
            "runner_binary_sha256": hashlib.sha256((xctestrun.parent / "Debug-iphonesimulator/iPhoneUse-Runner.app/PlugIns/iPhoneUse.xctest/iPhoneUse").read_bytes()).hexdigest(),
            "sources": {str(path): hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in files}}
        if daemon_binary:
            manifest["daemon_binary_sha256"] = hashlib.sha256(daemon_binary.read_bytes()).hexdigest()
        if mcp_binary:
            manifest["mcp_binary_sha256"] = hashlib.sha256(mcp_binary.read_bytes()).hexdigest()
        (out / "results.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": reports, "observations": observations, "cleanup_errors": cleanup_errors}))
    expected = (20 if mcp_binary else 19 if daemon_binary else 6) + ((3 if mcp_binary else 2) if args.recovery else 0) + 2 * int(args.hosts) + 3 * int(args.input_privacy) + 2 * int(args.observation_scope) + int(args.native_scope) + 4 * int(args.video) + 3 * int(args.list_recovery) + int(args.list_deadline)
    expected += 2 * int(args.expect_boundary_isolation)
    expected += 2 * int(args.long_boundaries)
    expected += int(args.metadata_controls)
    expected += 6 * int(args.state_boundaries)
    return 0 if len(reports) == expected and all(r["passed"] for r in reports) and not cleanup_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
