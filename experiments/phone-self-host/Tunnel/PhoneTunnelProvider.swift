import Foundation
import NetworkExtension

/// Local loopback only. Address-swap approach based on LocalDevVPN/StosVPN.
/// See THIRD-PARTY-NOTICES.txt for attribution and license.
final class PhoneTunnelProvider: NEPacketTunnelProvider {
    private let stateQueue = DispatchQueue(label: "ipu-phone-tunnel-state")
    private var results: [ResultRow] = []
    private var running = false
    private var bridge: ScopedTunnelBridge?
    private var hostError: String?
    private var monitor: DispatchSourceTimer?
    private var failures = 0
    private var retryAfter = Date.distantPast

    override func startTunnel(options: [String: NSObject]?, completionHandler: @escaping (Error?) -> Void) {
        let settings = NEPacketTunnelNetworkSettings(tunnelRemoteAddress: "10.7.0.1")
        let ipv4 = NEIPv4Settings(addresses: ["10.7.1.1"], subnetMasks: ["255.255.255.255"])
        ipv4.includedRoutes = [NEIPv4Route(destinationAddress: "10.7.0.1", subnetMask: "255.255.255.255")]
        ipv4.excludedRoutes = [.default()]
        settings.ipv4Settings = ipv4
        setTunnelNetworkSettings(settings) { error in
            guard error == nil else { completionHandler(error); return }
            self.stateQueue.sync { self.running = true; self.results = [] }
            self.reflectPackets()
            completionHandler(nil)
            self.runProbes()
            self.stateQueue.async {
                self.startMonitor()
                self.ensureBridge()
            }
        }
    }
    private func reflectPackets() {
        packetFlow.readPackets { packets, protocols in
            guard self.stateQueue.sync(execute: { self.running }) else { return }
            var reflected: [Data] = []
            var families: [NSNumber] = []
            for (packet, family) in zip(packets, protocols) {
                guard family.int32Value == AF_INET, let changed = LocalPacketReflection.reflect(packet) else { continue }
                reflected.append(changed)
                families.append(family)
            }
            if !reflected.isEmpty { self.packetFlow.writePackets(reflected, withProtocols: families) }
            self.reflectPackets()
        }
    }
    override func stopTunnel(with reason: NEProviderStopReason, completionHandler: @escaping () -> Void) {
        monitor?.cancel(); monitor = nil
        NativeHost.stop()
        bridge?.stop(); bridge = nil
        stateQueue.sync { running = false }
        completionHandler()
    }
    private func runProbes() {
        Task {
            var collected = [ResultRow]()
            for host in ["127.0.0.1", "10.7.0.1"] {
                collected.append(await TCPAttempt(Endpoint(host: host, port: 49152, purpose: "extension direct RemotePairing")).run())
            }
            collected.append(await TunnelTCPAttempt(provider: self).run())
            self.stateQueue.sync { if self.running { self.results = collected } }
        }
    }
    private func ensureBridge() {
        guard running, bridge == nil else { return }
        do {
            let token = try ProtectedStore.token("bridge_token")
            let bridge = ScopedTunnelBridge(provider: self, token: token)
            self.bridge = bridge
            bridge.start { error in
                self.stateQueue.async {
                    guard self.bridge === bridge else { return }
                    if error != nil {
                        self.hostError = "bridge_start_failed"
                        bridge.stop(); self.bridge = nil
                        NativeHost.stop()
                    } else { self.hostError = nil }
                }
            }
        } catch { hostError = "keychain_unavailable" }
    }
    private func startMonitor() {
        let timer = DispatchSource.makeTimerSource(queue: stateQueue)
        timer.schedule(deadline: .now() + 2, repeating: 5)
        timer.setEventHandler { [weak self] in
            guard let self, self.running else { return }
            if self.bridge == nil { self.ensureBridge(); return }
            guard let bridge = self.bridge, let port = bridge.port else { return }
            let status = NativeHost.status()
            let phase = status["phase"] as? String ?? "unknown"
            if phase == "running" { self.failures = 0; return }
            guard ProtectedStore.read("session_enabled") == Data([1]),
                  ProtectedStore.read("pair_record") != nil,
                  ["stopped", "runner_exited", "failed"].contains(phase), Date() >= self.retryAfter else { return }
            let error = status["error_code"] as? String
            // Pairing and authorization failures need a person; retry transport loss only.
            if let error, !["bridge_connect_failed", "device_connect_failed", "tunnel_timeout",
                "tunnel_listener_failed", "tunnel_handshake_failed", "rsd_connect_failed",
                "rsd_handshake_failed", "xctest_failed"].contains(error) { return }
            self.failures += 1
            self.retryAfter = Date().addingTimeInterval(min(300, 15 * pow(2, Double(min(self.failures, 5)))))
            self.hostError = NativeHost.start(mode: "launch", bridgePort: port, bridgeToken: bridge.token)
        }
        monitor = timer
        timer.resume()
    }
    override func handleAppMessage(_ messageData: Data, completionHandler: ((Data?) -> Void)? = nil) {
        let command = String(data: messageData, encoding: .utf8)
        if ["pair", "probe", "launch"].contains(command ?? "") {
            if command == "launch" {
                do { try ProtectedStore.write("session_enabled", Data([1])) }
                catch { stateQueue.sync { hostError = "keychain_unavailable" }; completionHandler?(nil); return }
            }
            if let bridge, let port = bridge.port {
                let error = NativeHost.start(mode: command!, bridgePort: port, bridgeToken: bridge.token)
                stateQueue.sync { hostError = error }
            } else { stateQueue.sync { hostError = "bridge_not_ready" } }
        } else if command == "stop-host" {
            do { try ProtectedStore.write("session_enabled", Data([0])) }
            catch { stateQueue.sync { hostError = "keychain_unavailable" } }
            NativeHost.stop()
        }
        else if command != "status" { completionHandler?(nil); return }
        let (rows, error) = stateQueue.sync { (results, hostError) }
        var report: [String: Any] = ["native": NativeHost.status()]
        if let data = try? JSONEncoder().encode(rows), let value = try? JSONSerialization.jsonObject(with: data) {
            report["probes"] = value
        }
        if let error { report["error_code"] = error }
        completionHandler?(try? JSONSerialization.data(withJSONObject: report))
    }
}

/// A Network Extension's normal sockets bypass its own tunnel. This API opts in.
final class TunnelTCPAttempt {
    private let provider: NEPacketTunnelProvider
    private let queue = DispatchQueue(label: "ipu-through-tunnel-probe")
    private var connection: NWTCPConnection?
    private var observation: NSKeyValueObservation?
    private var continuation: CheckedContinuation<ResultRow, Never>?
    private var finished = false
    private var sent = false
    private var bytes = Data()
    private let started = Date()
    private let endpoint = Endpoint(host: "10.7.0.1", port: 49152, purpose: "extension through-tunnel RemotePairing")
    init(provider: NEPacketTunnelProvider) { self.provider = provider }
    func run() async -> ResultRow {
        await withCheckedContinuation { continuation in
            queue.async {
                self.continuation = continuation
                let endpoint = NWHostEndpoint(hostname: "10.7.0.1", port: "49152")
                let connection = self.provider.createTCPConnectionThroughTunnel(to: endpoint, enableTLS: false, tlsParameters: nil, delegate: nil)
                self.connection = connection
                self.observation = connection.observe(\.state, options: [.new, .initial]) { conn, _ in
                    self.queue.async {
                        guard !self.finished else { return }
                        switch conn.state {
                        case .connected:
                            guard !self.sent else { return }
                            self.sent = true
                            do {
                                let request = try RemotePairingHandshake.request()
                                conn.write(request) { error in
                                    self.queue.async {
                                        if let error { self.finish("handshake_send_failed", error.localizedDescription) }
                                        else { self.receive() }
                                    }
                                }
                            } catch { self.finish("invalid_request", "Failed to encode handshake") }
                        case .disconnected, .cancelled:
                            self.finish("tunnel_connection_closed", "Connection closed before handshake")
                        default: break
                        }
                    }
                }
                self.queue.asyncAfter(deadline: .now() + 8) { self.finish("probe_timeout", "No handshake within 8 seconds") }
            }
        }
    }
    private func receive() {
        connection?.readMinimumLength(1, maximumLength: 65546) { data, error in
            self.queue.async {
                guard !self.finished else { return }
                if let error { self.finish("handshake_receive_failed", error.localizedDescription); return }
                guard let data, !data.isEmpty else { self.finish("handshake_closed", "Peer closed"); return }
                self.bytes.append(data)
                do {
                    if let summary = try RemotePairingHandshake.response(self.bytes) { self.finish("remote_pairing_handshake", summary) }
                    else { self.receive() }
                } catch { self.finish("handshake_unrecognized", "Response did not match protocol") }
            }
        }
    }
    private func finish(_ outcome: String, _ detail: String) {
        guard !finished else { return }
        finished = true
        observation?.invalidate(); observation = nil
        connection?.cancel(); connection = nil
        continuation?.resume(returning: ResultRow(endpoint: endpoint, outcome: outcome, detail: detail,
            elapsedMilliseconds: Int(Date().timeIntervalSince(started) * 1000)))
        continuation = nil
    }
}
