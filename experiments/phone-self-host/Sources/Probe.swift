import SwiftUI
import Network
import UIKit
import Darwin

struct Endpoint: Codable {
    let host: String
    let port: UInt16
    let purpose: String
}
struct ResultRow: Codable, Identifiable {
    var id: String { "\(endpoint.host):\(endpoint.port)" }
    let endpoint: Endpoint
    let outcome: String
    let detail: String
    let elapsedMilliseconds: Int
}
struct Report: Codable {
    let schema: Int
    let timestamp: String
    let operatingSystem: String
    let localWiFiAddress: String?
    let executor: String
    let scope: String
    let results: [ResultRow]
}

/// Socket and unauthenticated protocol probes. Never pairs, launches a runner, or reads credentials.
final class TCPAttempt {
    private let queue = DispatchQueue(label: "ipu-selfhost-probe")
    private var connection: NWConnection?
    private var finished = false
    private var received = Data()
    private let endpoint: Endpoint
    private let started = Date()
    private var continuation: CheckedContinuation<ResultRow, Never>?
    init(_ endpoint: Endpoint) { self.endpoint = endpoint }

    func run() async -> ResultRow {
        await withCheckedContinuation { continuation in
            queue.async {
                self.continuation = continuation
                let connection = NWConnection(
                    host: NWEndpoint.Host(self.endpoint.host),
                    port: NWEndpoint.Port(rawValue: self.endpoint.port)!, using: .tcp)
                self.connection = connection
                connection.stateUpdateHandler = { state in
                    switch state {
                    case .ready:
                        if self.endpoint.port == 49152 { self.handshake(connection) }
                        else { self.finish("tcp_open", "TCP connected; protocol and authorization not verified") }
                    case .failed(let error): self.finish("tcp_failed", String(describing: error))
                    case .waiting(let error):
                        // Waiting can recover after a permission prompt; allow the deadline.
                        self.waitingDetail = String(describing: error)
                        if case .posix(let code) = error, code == .EPERM || code == .EACCES {
                            self.finish("tcp_denied", String(describing: error))
                        }
                    default: break
                    }
                }
                connection.start(queue: self.queue)
                self.queue.asyncAfter(deadline: .now() + 5) {
                    self.finish("probe_timeout", self.waitingDetail ?? "No completed probe within 5 seconds")
                }
            }
        }
    }
    private func handshake(_ connection: NWConnection) {
        do {
            let frame = try RemotePairingHandshake.request()
            connection.send(content: frame, completion: .contentProcessed { error in
                if let error { self.finish("handshake_send_failed", String(describing: error)) }
                else { self.receiveHandshake(connection) }
            })
        } catch { finish("handshake_invalid_request", "Could not encode protocol probe") }
    }
    private func receiveHandshake(_ connection: NWConnection) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 65546) { bytes, _, complete, error in
            guard !self.finished else { return }
            if let bytes { self.received.append(bytes) }
            do {
                if let detail = try RemotePairingHandshake.response(self.received) {
                    self.finish("remote_pairing_handshake", detail)
                    return
                }
            } catch {
                self.finish("handshake_unrecognized", "TCP open, but response did not match RemotePairing handshake")
                return
            }
            if let error { self.finish("handshake_receive_failed", String(describing: error)) }
            else if complete { self.finish("handshake_closed", "Peer closed before a complete RemotePairing handshake") }
            else { self.receiveHandshake(connection) }
        }
    }
    private var waitingDetail: String?
    private func finish(_ outcome: String, _ detail: String) {
        guard !finished else { return }
        finished = true
        connection?.stateUpdateHandler = nil
        connection?.cancel()
        connection = nil
        continuation?.resume(returning: ResultRow(endpoint: endpoint, outcome: outcome,
            detail: detail, elapsedMilliseconds: Int(Date().timeIntervalSince(started) * 1000)))
        continuation = nil
    }
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
    var body: some Scene {
        WindowGroup {
            NavigationStack {
                List {
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
                    .task {
                        if ProcessInfo.processInfo.arguments.contains("--probe-on-launch") {
                            await model.run(includeAlternate: false)
                        }
                    }
            }
        }
    }
}
