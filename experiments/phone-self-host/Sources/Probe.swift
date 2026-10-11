import SwiftUI
import Network
import UIKit
import Darwin

struct Report: Codable {
    let schema: Int
    let timestamp: String
    let operatingSystem: String
    let localWiFiAddress: String?
    let executor: String
    let scope: String
    let results: [ResultRow]
}

func localWiFiAddress() -> String? {
    var interfaces: UnsafeMutablePointer<ifaddrs>?
    guard getifaddrs(&interfaces) == 0, let first = interfaces else { return nil }
    defer { freeifaddrs(interfaces) }
    var cursor: UnsafeMutablePointer<ifaddrs>? = first
    while let current = cursor {
        defer { cursor = current.pointee.ifa_next }
        guard String(cString: current.pointee.ifa_name) == "en0",
              let address = current.pointee.ifa_addr,
              address.pointee.sa_family == UInt8(AF_INET) else { continue }
        var host = [CChar](repeating: 0, count: Int(NI_MAXHOST))
        if getnameinfo(address, socklen_t(address.pointee.sa_len), &host, socklen_t(host.count),
                       nil, 0, NI_NUMERICHOST) == 0 { return String(cString: host) }
    }
    return nil
}

@MainActor final class ProbeModel: ObservableObject {
    @Published var rows: [ResultRow] = []
    @Published var running = false
    @Published var error = ""
    @Published var reportURL: URL?
    @Published var alternateAddress = "10.7.0.1"

    func run(includeAlternate: Bool) async {
        guard !running else { return }
        running = true
        rows = []
        error = ""
        reportURL = nil
        defer { running = false }
        var endpoints = [
            Endpoint(host: "127.0.0.1", port: 62078, purpose: "lockdown"),
            Endpoint(host: "127.0.0.1", port: 49152, purpose: "remote pairing candidate"),
            Endpoint(host: "127.0.0.1", port: 8100, purpose: "existing runner"),
            Endpoint(host: "127.0.0.1", port: 8787, purpose: "embedded daemon")
        ]
        if includeAlternate {
            let address = alternateAddress.trimmingCharacters(in: .whitespacesAndNewlines)
            guard IPv4Address(address) != nil || IPv6Address(address) != nil else {
                error = "请输入设备 IP 地址。"
                return
            }
            endpoints += [Endpoint(host: address, port: 62078, purpose: "alternate address lockdown"),
                          Endpoint(host: address, port: 49152, purpose: "alternate address remote pairing candidate")]
        }
        for endpoint in endpoints { rows.append(await TCPAttempt(endpoint).run()) }
        let report = Report(schema: 1, timestamp: ISO8601DateFormatter().string(from: Date()),
            operatingSystem: UIDevice.current.systemVersion, localWiFiAddress: localWiFiAddress(), executor: "on-device iOS application",
            scope: "TCP and unauthenticated RemotePairing handshake only; no pairing, XCTest launch, input, or Mac-detachment validation",
            results: rows)
        do {
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            let data = try encoder.encode(report)
            let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let url = documents.appendingPathComponent("self-host-probe.json")
            try data.write(to: url, options: [.atomic, .completeFileProtection])
            reportURL = url
        } catch { self.error = "报告保存失败：\(error.localizedDescription)" }
    }
}

@main struct ProbeApp: App {
    @StateObject private var model = ProbeModel()
    @StateObject private var tunnel = LocalTunnel()
    @State private var showingSmoke = false
    var body: some Scene {
        WindowGroup {
            NavigationStack {
                List {
                    Section("本机开发网络") {
                        Text(tunnel.state)
                        Text("启动器：\(tunnel.nativePhase)")
                        if !tunnel.nativeError.isEmpty { Text(tunnel.nativeError) }
                        Button("配对本机开发服务") { Task { await tunnel.command("pair") } }
                        Button("验证本机隧道") { Task { await tunnel.command("probe") } }
                        Button("启动独立被控服务") { Task { await tunnel.command("launch") } }
                        Button("独立控制验收页面") { showingSmoke = true }
                        Button("停止独立被控服务") { Task { await tunnel.command("stop-host") } }
                        Button("启用本机开发网络") { Task { await tunnel.start() } }
                        Button("停止本机开发网络") { Task { await tunnel.stop() } }
                        Text("只设置手机内虚拟地址，不修改互联网默认路由。启用可能切换当前 VPN。")
                        Text("本机开发网络基于 LocalDevVPN / StosVPN 的地址反射方案，作者为 SideStore Team、Stossy11、Jackson Coxson 与贡献者。").font(.caption)
                        if !tunnel.error.isEmpty { Text(tunnel.error) }
                        ForEach(Array(tunnel.rows.enumerated()), id: \.offset) { _, row in
                            Text("\(row.endpoint.purpose): \(row.outcome) · \(row.detail)").font(.caption)
                        }
                    }
                    Section {
                        Text("检测手机访问自身服务的网络路径。端口连通不代表已获得控制权限。")
                        Button("检测本机端口") { Task { await model.run(includeAlternate: false) } }
                        TextField("指定地址（VPN 或手机局域网 IP）", text: $model.alternateAddress)
                            .textInputAutocapitalization(.never).autocorrectionDisabled()
                        Button("检测自身 Wi-Fi 地址") {
                            guard let address = localWiFiAddress() else {
                                model.error = "未找到 Wi-Fi IPv4 地址。"
                                return
                            }
                            model.alternateAddress = address
                            Task { await model.run(includeAlternate: true) }
                        }
                        Button("检测指定地址") { Task { await model.run(includeAlternate: true) } }
                    }.disabled(model.running)
                    Section {
                        ForEach(model.rows) { row in
                            VStack(alignment: .leading) {
                                Text("\(row.endpoint.host):\(row.endpoint.port) · \(row.endpoint.purpose)")
                                Text("\(row.outcome) · \(row.elapsedMilliseconds) ms").font(.caption)
                                Text(row.detail).font(.caption).foregroundStyle(.secondary)
                            }
                        }
                        if model.running { ProgressView("检测中") }
                        if !model.error.isEmpty { Text(model.error) }
                        if let url = model.reportURL { ShareLink("导出检测报告", item: url) }
                    }
                }.navigationTitle("Self Host Probe")
                    .fullScreenCover(isPresented: $showingSmoke) { ControlSmokeView() }
                    .task {
                        #if DEBUG
                        if ProcessInfo.processInfo.arguments.contains("--selfhost-import-remote-trust") {
                            let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
                            let file = documents.appendingPathComponent("private-remote-onboarding.plist")
                            do {
                                let size = try file.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? Int.max
                                guard size > 0 && size < 131072 else { throw CocoaError(.fileReadCorruptFile) }
                                let bytes = try Data(contentsOf: file)
                                guard let object = try PropertyListSerialization.propertyList(from: bytes, format: nil) as? [String: Any],
                                      let record = object["pair_record"] as? Data,
                                      let identity = object["device_id"] as? String, (16...64).contains(identity.count),
                                      let parsed = try PropertyListSerialization.propertyList(from: record, format: nil) as? [String: Any],
                                      (parsed["private_key"] as? Data)?.count == 32, (parsed["public_key"] as? Data)?.count == 32,
                                      parsed["identifier"] is String else { throw CocoaError(.fileReadCorruptFile) }
                                try ProtectedStore.write("remote_onboarding", bytes)
                                try FileManager.default.removeItem(at: file)
                            } catch { model.error = "首次远程开发配置导入失败" }
                        }
                        if ProcessInfo.processInfo.arguments.contains("--selfhost-import-trust") {
                            let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
                            let file = documents.appendingPathComponent("private-device-onboarding.plist")
                            do {
                                let size = try file.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? Int.max
                                guard size > 0 && size < 131072 else { throw CocoaError(.fileReadCorruptFile) }
                                let bytes = try Data(contentsOf: file)
                                guard let object = try PropertyListSerialization.propertyList(from: bytes, format: nil) as? [String: Any],
                                      let record = object["pair_record"] as? Data,
                                      let identity = object["device_id"] as? String, (16...64).contains(identity.count),
                                      let parsed = try PropertyListSerialization.propertyList(from: record, format: nil) as? [String: Any],
                                      parsed["HostPrivateKey"] != nil, parsed["RootCertificate"] != nil else { throw CocoaError(.fileReadCorruptFile) }
                                try ProtectedStore.write("lockdown_onboarding", bytes)
                                try FileManager.default.removeItem(at: file)
                            } catch { model.error = "首次开发配置导入失败" }
                        }
                        #endif
                        await tunnel.load()
                        #if DEBUG
                        if ProcessInfo.processInfo.arguments.contains("--selfhost-restart-probe") {
                            await tunnel.restartAndCommand("probe")
                        }
                        if ProcessInfo.processInfo.arguments.contains("--selfhost-restart-launch") {
                            await tunnel.restartAndCommand("launch")
                        }
                        if ProcessInfo.processInfo.arguments.contains("--selfhost-control-smoke") {
                            showingSmoke = true
                        }
                        for command in ["pair", "probe", "launch"] {
                            if ProcessInfo.processInfo.arguments.contains("--selfhost-" + command) {
                                await tunnel.startAndCommand(command)
                            }
                        }
                        #endif
                        if ProcessInfo.processInfo.arguments.contains("--probe-on-launch") {
                            await model.run(includeAlternate: false)
                        }
                        while !Task.isCancelled {
                            await tunnel.refresh()
                            try? await Task.sleep(nanoseconds: 2_000_000_000)
                        }
                    }
            }
        }
    }
}
