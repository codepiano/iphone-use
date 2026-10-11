import Foundation
import Darwin

enum NativeHost {
    private typealias Start = @convention(c) (UnsafePointer<CChar>?) -> Int32
    private typealias Stop = @convention(c) () -> Void
    private typealias Status = @convention(c) () -> UnsafeMutablePointer<CChar>?
    private typealias Free = @convention(c) (UnsafeMutablePointer<CChar>?) -> Void
    private typealias CopyRecord = @convention(c) (UnsafeMutablePointer<UInt8>?, Int) -> Int
    private static func symbol<T>(_ name: String, as: T.Type) -> T? {
        guard let pointer = dlsym(UnsafeMutableRawPointer(bitPattern: -2), name) else { return nil }
        return unsafeBitCast(pointer, to: T.self)
    }
    static var linked: Bool { symbol("ipu_host_start", as: Start.self) != nil }
    static func status() -> [String: Any] {
        guard let status = symbol("ipu_host_status", as: Status.self),
              let free = symbol("ipu_host_string_free", as: Free.self), let value = status() else {
            return ["phase": "not_linked", "linked": false]
        }
        defer { free(value) }
        let data = Data(String(cString: value).utf8)
        var result = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? ["phase": "invalid_status"]
        result["linked"] = true
        // Persist only via the private ABI, never through report/status serialization.
        if result["pair_record_available"] as? Bool == true,
           let copy = symbol("ipu_host_copy_pair_record", as: CopyRecord.self) {
            let size = copy(nil, 0)
            if size > 0 && size < 65_536 {
                var data = Data(count: size)
                let copied = data.withUnsafeMutableBytes { copy($0.bindMemory(to: UInt8.self).baseAddress, size) }
                if copied == size {
                    do { if ProtectedStore.read("pair_record") != data { try ProtectedStore.write("pair_record", data) } }
                    catch { result["storage_error"] = "pair_record_save_failed" }
                }
                data.resetBytes(in: 0..<data.count)
            }
        }
        return result
    }
    static func start(mode: String, bridgePort: UInt16, bridgeToken: String) -> String? {
        guard let start = symbol("ipu_host_start", as: Start.self) else { return "native_host_not_linked" }
        do {
            // Keep the shared credential stable across extension restarts and rejected launches.
            // A surviving runner must remain reachable by the app.
            let runnerToken = try ProtectedStore.token("runner_token")
            var config: [String: Any] = ["mode": mode, "device_host": "10.7.0.1", "bridge_port": bridgePort,
                "bridge_token": bridgeToken, "runner_bundle": "com.leeguoo.iphone-use.selfhost-runner.xctrunner",
                "runner_token": runnerToken,
                "target_app": Bundle.main.object(forInfoDictionaryKey: "IPUTargetApp") as? String ?? "com.leeguoo.iphone-use.selfhost-probe",
                "developer_image_root": Bundle.main.bundleURL.appendingPathComponent("DeveloperImage").path,
                "daemon_token": try ProtectedStore.token("daemon_token"),
                "daemon_password": try ProtectedStore.token("daemon_password")]
            if let record = ProtectedStore.read("pair_record") { config["pair_record_base64"] = record.base64EncodedString() }
            if let bytes = ProtectedStore.read("lockdown_onboarding"),
               let onboarding = try PropertyListSerialization.propertyList(from: bytes, format: nil) as? [String: Any],
               let record = onboarding["pair_record"] as? Data, let identity = onboarding["device_id"] as? String {
                config["lockdown_pair_record_base64"] = record.base64EncodedString()
                config["expected_udid"] = identity
            }
            if let bytes = ProtectedStore.read("remote_onboarding"),
               let onboarding = try PropertyListSerialization.propertyList(from: bytes, format: nil) as? [String: Any],
               let record = onboarding["pair_record"] as? Data, let identity = onboarding["device_id"] as? String {
                config["pair_record_base64"] = record.base64EncodedString()
                config["expected_udid"] = identity
            }
            let data = try JSONSerialization.data(withJSONObject: config)
            guard let encoded = String(data: data, encoding: .utf8) else { return "native_config_invalid" }
            let code = encoded.withCString { start($0) }
            if code == 0 && mode == "launch" {
                do { try ProtectedStore.write("runner_token", Data(runnerToken.utf8)) }
                catch { stop(); return "runner_token_save_failed" }
            }
            return code == 0 ? nil : (code == 1 ? "native_host_already_active" : "native_config_invalid")
        } catch { return "keychain_unavailable" }
    }
    static func stop() { symbol("ipu_host_stop", as: Stop.self)?() }
}
