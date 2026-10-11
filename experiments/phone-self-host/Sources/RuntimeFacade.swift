import Foundation
import Combine
import CryptoKit
import UIKit
import Network

/// Main app API. Credentials stay in Keychain and never enter status reports.
@MainActor public final class PhoneLocalRuntime: ObservableObject {
    private let tunnel: LocalTunnel
    private var changes: AnyCancellable?
    public init(bundle: String) {
        tunnel = LocalTunnel(bundle: bundle)
        changes = tunnel.objectWillChange.sink { [weak self] _ in self?.objectWillChange.send() }
    }
    public var state: String { tunnel.state }
    public var phase: String { tunnel.nativePhase }
    public var error: String { tunnel.error.isEmpty ? tunnel.nativeError : tunnel.error }
    public var provisioned: Bool { ProtectedStore.read("remote_onboarding") != nil || ProtectedStore.read("pair_record") != nil }
    public func refresh() async { await tunnel.load() }
    public func start() async throws -> String {
        guard provisioned else { throw RuntimeFailure.needsTrust }
        await tunnel.load()
        if ["未启动", "stopped", "failed", "runner_exited", "rsd_verified", "not_linked"].contains(phase) { await tunnel.startAndCommand("launch") }
        let deadline = ProcessInfo.processInfo.systemUptime + 420
        while ProcessInfo.processInfo.systemUptime < deadline {
            try Task.checkCancellation()
            await tunnel.refresh()
            if phase == "running" {
                guard let data = ProtectedStore.read("daemon_password"), let password = String(data: data, encoding: .utf8) else { throw RuntimeFailure.missingCredential }
                let status = try? await PhoneRunnerClient().request("GET", "/status")
                if let value = status?["value"] as? [String: Any],
                   (value["daemon"] as? [String: Any])?["state"] as? String == "serving" { return password }
            }
            if phase == "not_linked" || (!error.isEmpty && error != "native_host_already_active") { throw RuntimeFailure.startFailed }
            try await Task.sleep(nanoseconds: 500_000_000)
        }
        throw RuntimeFailure.timeout
    }
    #if DEBUG
    public func validationTransportSnapshot() async -> [String: Bool] {
        await withCheckedContinuation { continuation in
            let monitor = NWPathMonitor()
            monitor.pathUpdateHandler = { path in
                monitor.pathUpdateHandler = nil
                monitor.cancel()
                continuation.resume(returning: ["wifi_path_active": path.usesInterfaceType(.wifi), "ethernet_path_active": path.usesInterfaceType(.wiredEthernet), "cellular_path_active": path.usesInterfaceType(.cellular)])
            }
            monitor.start(queue: DispatchQueue(label: "local.runtime.validation.transport"))
        }
    }
    public func validateControls() async throws -> Data {
        guard phase == "running" else { throw RuntimeFailure.controlValidationFailed }
        let client = PhoneRunnerClient()
        try await Task.sleep(nanoseconds: 500_000_000)
        _ = try await client.ownedSource()
        try await client.tap("local-runtime-qa-button")
        let challenge = "selfhost-" + UUID().uuidString.prefix(8).lowercased()
        try await client.tap("local-runtime-qa-text")
        try await Task.sleep(nanoseconds: 250_000_000)
        _ = try await client.request("POST", "/type", body: ["text": challenge])
        let tree = try await client.ownedSource()
        guard PhoneRunnerClient.node("local-runtime-qa-counter", in: tree)?["label"] as? String == "QA count: 1",
              PhoneRunnerClient.node("local-runtime-qa-text", in: tree)?["value"] as? String == challenge else {
            throw RuntimeFailure.controlValidationFailed
        }
        let screenshot = try await client.request("GET", "/screenshot?max_side=512&format=jpeg")
        guard let encoded = screenshot["value"] as? String, let bytes = Data(base64Encoded: encoded), let image = UIImage(data: bytes), image.size.width > 0, image.size.height > 0 else { throw RuntimeFailure.controlValidationFailed }
        return try JSONSerialization.data(withJSONObject: ["schema": 1, "executor": "native assistant via on-phone runner", "observed_at": ISO8601DateFormatter().string(from: Date()), "ok": true, "tap_verified": true, "typing_verified": true, "expected_input": challenge, "screenshot_width": image.size.width, "screenshot_height": image.size.height, "screenshot_sha256": SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()], options: [.prettyPrinted, .sortedKeys])
    }
    #endif
    public func importTrust(from url: URL) throws {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        do {
            let file = try FileHandle(forReadingFrom: url)
            defer { try? file.close() }
            let bytes = try file.read(upToCount: 131_073) ?? Data()
            guard bytes.count <= 131_072,
                  let envelope = try PropertyListSerialization.propertyList(from: bytes, format: nil) as? [String: Any],
                  let record = envelope["pair_record"] as? Data,
                  let identity = envelope["device_id"] as? String, (16...64).contains(identity.utf8.count),
                  identity.utf8.allSatisfy({ (48...57).contains($0) || (65...90).contains($0) || (97...122).contains($0) || $0 == 45 }) else {
                throw RuntimeFailure.invalidTrust
            }
            try PairRecordImport.validate(record)
            let data = try PropertyListSerialization.data(fromPropertyList: ["device_id": identity, "pair_record": record], format: .binary, options: 0)
            try ProtectedStore.write("remote_onboarding", data)
            objectWillChange.send()
        } catch { throw RuntimeFailure.invalidTrust }
    }
    public func stop() async { await tunnel.load(); await tunnel.command("stop-host"); await tunnel.stop() }
    public enum RuntimeFailure: LocalizedError {
        case needsTrust, missingCredential, startFailed, timeout, invalidTrust, controlValidationFailed
        public var errorDescription: String? {
            switch self {
            case .controlValidationFailed: return "本机控制验收失败。"
            case .invalidTrust: return "授权配置无效，请选择这台手机导出的配置文件。"
            case .needsTrust: return "尚未完成首次手机授权配置。"
            case .missingCredential: return "本机服务凭据不可用，请重新配置。"
            case .startFailed: return "本机执行服务启动失败，请检查系统授权后重试。"
            case .timeout: return "本机执行服务启动超时，请重试。"
            }
        }
    }
}
