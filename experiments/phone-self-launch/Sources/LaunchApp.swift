import SwiftUI
import Security
import UniformTypeIdentifiers
import CryptoKit
import UIKit

/// Pairing record and launch environment stay in this App's device-only Keychain.
enum PrivateSetup {
    static let service = "com.leeguoo.iphone-use.self-launch"
    static func read(_ name: String) -> Data? {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service, kSecAttrAccount as String: name,
            kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var result: CFTypeRef?
        if SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess { return result as? Data }
        guard ["configuration", "remote-pairing"].contains(name),
              let saved = read("device-setup"),
              let object = try? JSONSerialization.jsonObject(with: saved) as? [String: Any] else { return nil }
        if name == "configuration", let config = object["configuration"] as? [String: Any] {
            return try? JSONSerialization.data(withJSONObject: config, options: [.sortedKeys])
        }
        if name == "remote-pairing", let values = object["pairing_record"] as? [NSNumber] {
            return Data(values.map(\.uint8Value))
        }
        return nil
    }
    static func write(_ data: Data, name: String) throws {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service, kSecAttrAccount as String: name]
        let attributes: [String: Any] = [kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly]
        let updated = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if updated == errSecItemNotFound {
            let added = SecItemAdd(query.merging(attributes) { _, new in new } as CFDictionary, nil)
            guard added == errSecSuccess else { throw Failure.storage }
        } else if updated != errSecSuccess { throw Failure.storage }
    }
    static func removeAll() {
        SecItemDelete([kSecClass as String: kSecClassGenericPassword,
                       kSecAttrService as String: service] as CFDictionary)
    }
    static func saveDeviceSetup(_ bytes: Data) throws {
        guard let object = try? JSONSerialization.jsonObject(with: bytes) as? [String: Any],
              object["configuration"] is [String: Any], object["pairing_record"] is [NSNumber] else { throw Failure.storage }
        // Both configuration and pairing key are one atomic Keychain item.
        try write(bytes, name: "device-setup")
        for name in ["configuration", "remote-pairing"] {
            let code = SecItemDelete([kSecClass as String: kSecClassGenericPassword,
                kSecAttrService as String: service, kSecAttrAccount as String: name] as CFDictionary)
            guard code == errSecSuccess || code == errSecItemNotFound else { throw Failure.storage }
        }
    }
    static func createPhoneConfiguration() throws {
        guard read("configuration") == nil else { return }
        func token() throws -> String {
            var bytes = [UInt8](repeating: 0, count: 32)
            let result = bytes.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, $0.count, $0.baseAddress!) }
            guard result == errSecSuccess else { throw Failure.storage }
            return bytes.map { String(format: "%02x", $0) }.joined()
        }
        guard let team = Bundle.main.object(forInfoDictionaryKey: "IPUDevelopmentTeam") as? String,
              team.count == 10, team.utf8.allSatisfy({ (65...90).contains($0) || (48...57).contains($0) }) else { throw Failure.storage }
        let configuration: [String: Any] = ["schema": 1, "endpoint": "10.7.0.1",
            "expected_udid": "", "runner_bundle_id": "com.leeguoo.iphone-use.wda.\(team.lowercased()).xctrunner",
            "runner_environment": ["IPU_RUNNER_TOKEN": try token(), "IPU_DAEMON_TOKEN": try token(),
                "IPU_DAEMON_HOST": "127.0.0.1", "IPU_DAEMON_PORT": "8787", "USE_PORT": "8100", "MJPEG_SERVER_PORT": "9100"]]
        try write(JSONSerialization.data(withJSONObject: configuration, options: [.sortedKeys]), name: "configuration")
    }
    enum Failure: Error { case storage }
}

@MainActor final class LaunchModel: ObservableObject {
    @Published var phase = "idle"
    @Published var errorCode: String?
    @Published var setupReady = false
    @Published var recordReady = false
    @Published var importing = false
    @Published var importKind = "configuration"
    @Published var pairingPin = ""
    var active: Bool { !["idle", "stopped", "failed"].contains(phase) }

    func refresh() {
        var secret = [UInt8](repeating: 0, count: 65536)
        let length = secret.withUnsafeMutableBufferPointer { ipu_self_launch_take_record($0.baseAddress, $0.count) }
        if length > 0 && length <= secret.count {
            do {
                try PrivateSetup.saveDeviceSetup(Data(secret.prefix(length)))
                _ = ipu_self_launch_setup_saved(true)
            } catch {
                errorCode = "new_record_storage_failed"
                _ = ipu_self_launch_setup_saved(false)
                ipu_self_launch_stop()
            }
        }
        _ = secret.withUnsafeMutableBytes { $0.initializeMemory(as: UInt8.self, repeating: 0) }
        var buffer = [UInt8](repeating: 0, count: 1024)
        let count = buffer.withUnsafeMutableBufferPointer { ipu_self_launch_status($0.baseAddress, $0.count) }
        if count > 0 && count <= buffer.count,
           let object = try? JSONSerialization.jsonObject(with: Data(buffer.prefix(count-1))) as? [String: Any] {
            phase = object["phase"] as? String ?? "failed"
            if let code = object["error_code"] as? String { errorCode = code }
        }
        setupReady = PrivateSetup.read("configuration") != nil
        recordReady = PrivateSetup.read("remote-pairing") != nil
    }
    func importFile(_ url: URL) {
        let scope = url.startAccessingSecurityScopedResource()
        defer { if scope { url.stopAccessingSecurityScopedResource() } }
        do {
            let size = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? Int.max
            guard size > 0 && size <= 65536 else { errorCode = "invalid_import_size"; return }
            let bytes = try Data(contentsOf: url)
            if importKind == "configuration" {
                guard let object = try? JSONSerialization.jsonObject(with: bytes) as? [String: Any],
                      object["schema"] as? Int == 1 else { errorCode = "invalid_configuration"; return }
            } else {
                guard let object = try? PropertyListSerialization.propertyList(from: bytes, format: nil) as? [String: Any],
                      (object["private_key"] as? Data)?.count == 32,
                      (object["public_key"] as? Data)?.count == 32,
                      object["identifier"] as? String != nil else { errorCode = "remote_pair_record_required"; return }
            }
            try PrivateSetup.write(bytes, name: importKind == "configuration" ? "configuration" : "remote-pairing")
            errorCode = nil
            refresh()
        } catch { errorCode = "private_import_failed" }
    }
    func start() {
        guard let config = PrivateSetup.read("configuration"), let pair = PrivateSetup.read("remote-pairing") else { return }
        let result = config.withUnsafeBytes { c in pair.withUnsafeBytes { p in
            ipu_self_launch_start(c.bindMemory(to: UInt8.self).baseAddress, config.count,
                                  p.bindMemory(to: UInt8.self).baseAddress, pair.count)
        }}
        errorCode = nil
        refresh()
        if result == -1 { errorCode = "invalid_configuration_or_record" }
    }
    func stop() { ipu_self_launch_stop(); refresh() }
    func pairOnPhone() {
        guard let config = PrivateSetup.read("configuration") else { return }
        let result = config.withUnsafeBytes { ipu_self_launch_pair_start($0.bindMemory(to: UInt8.self).baseAddress, config.count) }
        errorCode = result == -1 ? "invalid_configuration" : nil
        refresh()
    }
    func submitPin() {
        let bytes = Data(pairingPin.utf8)
        let result = bytes.withUnsafeBytes { ipu_self_launch_submit_pin($0.bindMemory(to: UInt8.self).baseAddress, bytes.count) }
        pairingPin = ""
        if result != 0 { errorCode = "invalid_or_expired_pin" }
        refresh()
    }

    func connectAssistant() async {
        guard let data = PrivateSetup.read("configuration"),
              let config = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let environment = config["runner_environment"] as? [String: String],
              let token = environment["IPU_RUNNER_TOKEN"],
              let port = UInt16(environment["USE_PORT"] ?? "8100"), port > 0 else { return }
        let path = "/daemon/pair-code"
        let timestamp = String(Int(Date().timeIntervalSince1970))
        let nonce = UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased()
        let hash = SHA256.hash(data: Data()).map { String(format: "%02x", $0) }.joined()
        let payload = "ipu-runner-v1\nPOST\n\(path)\n\(timestamp)\n\(nonce)\n\(hash)"
        let signature = HMAC<SHA256>.authenticationCode(for: Data(payload.utf8), using: SymmetricKey(data: Data(token.utf8)))
            .map { String(format: "%02x", $0) }.joined()
        var request = URLRequest(url: URL(string: "http://127.0.0.1:\(port)\(path)")!)
        request.httpMethod = "POST"
        request.timeoutInterval = 5
        request.setValue("IPU-HMAC-SHA256 ts=\(timestamp), nonce=\(nonce), sig=\(signature)", forHTTPHeaderField: "Authorization")
        let session = URLSession(configuration: .ephemeral)
        defer { session.invalidateAndCancel() }
        do {
            let (bytes, response) = try await session.data(for: request)
            guard (response as? HTTPURLResponse)?.statusCode == 200,
                  let object = try JSONSerialization.jsonObject(with: bytes) as? [String: Any],
                  let value = object["value"] as? [String: Any], let code = value["code"] as? String,
                  let daemonPort = value["port"] as? Int, (1...65535).contains(daemonPort) else {
                errorCode = "daemon_not_ready"; return
            }
            var link = URLComponents()
            link.scheme = "iphoneuse"; link.host = "pair"
            link.queryItems = [URLQueryItem(name: "u", value: "http://127.0.0.1:\(daemonPort)"), URLQueryItem(name: "c", value: code)]
            guard let url = link.url, await UIApplication.shared.open(url) else { errorCode = "assistant_app_unavailable"; return }
            errorCode = nil
        } catch { errorCode = "daemon_connection_failed" }
    }
}

@main struct SelfLaunchApp: App {
    @StateObject private var model = LaunchModel()
    var body: some Scene {
        WindowGroup {
            NavigationStack {
                List {
                    Section("手机启动控制服务") {
                        Text("先启用 LocalDevVPN，再在这里启动。此程序只连接手机自己的开发服务。")
                        Text("验证期间请保持此页面在前台。后台保活和断开 Mac 后的完整操作尚未验收。")
                            .font(.footnote).foregroundStyle(.secondary)
                        LabeledContent("启动配置", value: model.setupReady ? "已在手机生成" : "待准备")
                        LabeledContent("RemotePairing 记录", value: model.recordReady ? "已保存" : "待导入")
                        Button("导入启动配置") { model.importKind = "configuration"; model.importing = true }
                            .disabled(model.active)
                        Button("导入 RemotePairing 记录") { model.importKind = "remote-pairing"; model.importing = true }
                            .disabled(model.active)
                        Button("首次在手机上配对并启动") { model.pairOnPhone() }
                            .disabled(model.active || !model.setupReady || model.recordReady)
                        Text("记录仅保存在这台手机的钥匙串，不上传、不导出。普通 lockdown 配对记录不能代替 RemotePairing 记录。")
                            .font(.footnote)
                    }
                    Section("会话") {
                        Text(model.phase).monospaced()
                        if model.phase == "awaiting_pairing_pin" {
                            SecureField("输入系统显示的配对码", text: $model.pairingPin).keyboardType(.numberPad)
                            Button("提交配对码") { model.submitPin() }
                            Text("请本人允许系统配对提示，再输入显示的配对码。")
                        }
                        if let error = model.errorCode { Text(error).foregroundStyle(.red).monospaced() }
                        Button("在手机上启动") { model.start() }
                            .disabled(model.active || !model.setupReady || !model.recordReady)
                        Button("停止本程序的会话", role: .destructive) { model.stop() }.disabled(!model.active)
                        Button("连接本机助手") { Task { await model.connectAssistant() } }
                            .disabled(model.phase != "test_plan_started")
                        Button("清除本机配置", role: .destructive) { PrivateSetup.removeAll(); model.refresh() }
                            .disabled(model.active)
                    }
                }.navigationTitle("Phone Self Launch")
                    .fileImporter(isPresented: $model.importing, allowedContentTypes: [.data]) { result in
                        if case .success(let url) = result { model.importFile(url) }
                    }
                    .task {
                        do { try PrivateSetup.createPhoneConfiguration() }
                        catch { model.errorCode = "phone_configuration_failed" }
                        while !Task.isCancelled {
                            model.refresh()
                            try? await Task.sleep(for: .seconds(1))
                        }
                    }
            }
        }
    }
}
