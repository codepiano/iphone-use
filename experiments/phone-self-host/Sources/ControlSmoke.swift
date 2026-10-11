import Foundation
import SwiftUI
import UIKit
import CryptoKit
import Network

@MainActor final class ControlSmoke: ObservableObject {
    @Published var count = 0
    @Published var text = ""
    @Published var phase = "未验证"
    @Published var running = false
    @Published var image: UIImage?
    @Published var reportURL: URL?
    private static func networkPath() async -> NWPath {
        await withCheckedContinuation { continuation in
            let monitor = NWPathMonitor()
            monitor.pathUpdateHandler = { path in
                monitor.pathUpdateHandler = nil
                monitor.cancel()
                continuation.resume(returning: path)
            }
            monitor.start(queue: DispatchQueue(label: "selfhost.validation.network"))
        }
    }
    func run(background: Bool = false, detached: Bool = false) async {
        guard !running else { return }
        running = true; count = 0; text = ""; image = nil; reportURL = nil
        let started = Date()
        var expired = false
        let backgroundTask = UIApplication.shared.beginBackgroundTask(withName: "selfhost-control-validation") { expired = true }
        defer { if backgroundTask != .invalid { UIApplication.shared.endBackgroundTask(backgroundTask) } }
        let challenge = "selfhost-" + UUID().uuidString.prefix(8).lowercased()
        var report: [String: Any] = ["schema": 1, "executor": "on-device app via signed local runner HTTP",
            "started_at": ISO8601DateFormatter().string(from: started),
            "scope": "real input/source/screenshot in this test app; Mac disconnection requires a separate recorded observation"]
        report["background_requested"] = background
        report["physical_detachment_user_attested"] = detached
        defer { running = false }
        do {
            phase = "等待验收页面就绪"
            for _ in 0..<30 {
                if UIApplication.shared.applicationState == .active { break }
                try await Task.sleep(nanoseconds: 100_000_000)
            }
            try await Task.sleep(nanoseconds: 300_000_000)
            phase = "检查独立服务"
            let client = PhoneRunnerClient()
            if detached {
                phase = "检查手机网络隔离"
                let path = await Self.networkPath()
                report["wifi_path_active"] = path.usesInterfaceType(.wifi)
                report["ethernet_path_active"] = path.usesInterfaceType(.wiredEthernet)
                report["cellular_path_active"] = path.usesInterfaceType(.cellular)
                guard !path.usesInterfaceType(.wifi), !path.usesInterfaceType(.wiredEthernet) else {
                    throw PhoneRunnerClient.Failure(code: "phone_still_on_external_local_network")
                }
            }
            let status = try await client.request("GET", "/status")
            guard let value = status["value"] as? [String: Any], let daemon = value["daemon"] as? [String: Any], daemon["state"] as? String == "serving" else {
                throw PhoneRunnerClient.Failure(code: "embedded_daemon_not_serving")
            }
            if background {
                phase = "检查后台维持"
                _ = try await client.ownedSource()
                _ = try await client.request("POST", "/home", body: [:])
                for _ in 0..<30 {
                    if UIApplication.shared.applicationState == .background { break }
                    try await Task.sleep(nanoseconds: 100_000_000)
                }
                guard UIApplication.shared.applicationState == .background else {
                    throw PhoneRunnerClient.Failure(code: "app_did_not_background")
                }
                report["background_observed"] = true
                try await Task.sleep(nanoseconds: 10_000_000_000)
                guard !expired else { throw PhoneRunnerClient.Failure(code: "validation_background_budget_expired") }
                _ = try await client.request("GET", "/status")
                let active = try await client.request("GET", "/apps/active")
                guard (active["value"] as? [String: Any])?["bundleId"] as? String == "com.apple.springboard" else {
                    throw PhoneRunnerClient.Failure(code: "background_screen_changed")
                }
                report["background_service_verified"] = true
                _ = try await client.request("POST", "/launch", body: ["bundle": "com.leeguoo.iphone-use.selfhost-probe"])
                for _ in 0..<30 {
                    if UIApplication.shared.applicationState == .active { break }
                    try await Task.sleep(nanoseconds: 100_000_000)
                }
                guard UIApplication.shared.applicationState == .active else { throw PhoneRunnerClient.Failure(code: "app_did_not_return") }
                report["foreground_return_observed"] = true
            }
            phase = "验证真实点击"
            try await Task.sleep(nanoseconds: 300_000_000)
            try await client.tap("selfhost-smoke-button")
            for _ in 0..<20 {
                if count == 1 { break }
                try await Task.sleep(nanoseconds: 100_000_000)
            }
            guard count == 1 else { throw PhoneRunnerClient.Failure(code: "tap_not_observed") }
            report["tap_observed"] = true
            phase = "聚焦输入框"
            try await client.tap("selfhost-smoke-text")
            phase = "验证真实输入"
            try await Task.sleep(nanoseconds: 250_000_000)
            _ = try await client.request("POST", "/type", body: ["text": challenge])
            for _ in 0..<20 {
                if text == challenge { break }
                try await Task.sleep(nanoseconds: 100_000_000)
            }
            guard text == challenge else { throw PhoneRunnerClient.Failure(code: "typing_not_observed") }
            let tree = try await client.ownedSource()
            guard PhoneRunnerClient.node("selfhost-smoke-text", in: tree)?["value"] as? String == challenge else {
                throw PhoneRunnerClient.Failure(code: "source_postcondition_failed")
            }
            report["typing_observed"] = true; report["source_verified"] = true
            phase = "验证真实截图"
            let screenshot = try await client.request("GET", "/screenshot?max_side=512&format=jpeg")
            guard let encoded = screenshot["value"] as? String, let bytes = Data(base64Encoded: encoded),
                  let picture = UIImage(data: bytes), picture.size.width > 0, picture.size.height > 0 else {
                throw PhoneRunnerClient.Failure(code: "screenshot_unavailable")
            }
            image = picture
            report["screenshot_sha256"] = SHA256.hash(data: bytes).map { String(format: "%02x", $0) }.joined()
            report["screenshot_width"] = picture.size.width; report["screenshot_height"] = picture.size.height
            report["ok"] = true
            phase = "点击、输入、读屏和截图通过"
        } catch {
            report["ok"] = false
            report["error_code"] = (error as? PhoneRunnerClient.Failure)?.code ?? "validation_request_failed"
            report["failed_stage"] = phase
            if let failure = error as? PhoneRunnerClient.Failure {
                report["http_status"] = failure.httpStatus
                report["server_error"] = failure.serverError
                report["auth_reason"] = failure.authReason
            } else {
                let failure = error as NSError
                report["failure_domain"] = failure.domain
                report["failure_number"] = failure.code
            }
            report["observed_typed_length"] = text.count
            phase = report["error_code"] as? String ?? "验证失败"
        }
        report["finished_at"] = ISO8601DateFormatter().string(from: Date())
        report["elapsed_seconds"] = Date().timeIntervalSince(started)
        do {
            let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
            let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let url = documents.appendingPathComponent("self-host-control-smoke.json")
            try data.write(to: url, options: [.atomic, .completeFileProtection])
            reportURL = url
        } catch { phase = "验收报告保存失败" }
    }
}

struct ControlSmokeView: View {
    @StateObject private var model = ControlSmoke()
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            List {
                Section {
                    Button("验收点击") { model.count += 1 }.accessibilityIdentifier("selfhost-smoke-button")
                    Text("点击次数：\(model.count)")
                    TextField("输入验收文字", text: $model.text).accessibilityIdentifier("selfhost-smoke-text")
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                    Text(model.phase)
                    Button("执行独立控制验收") { Task { await model.run() } }.disabled(model.running)
                    Button("后台与返回验收") { Task { await model.run(background: true) } }.disabled(model.running)
                    Button("已拔 USB 并关闭 Wi-Fi，开始验收") { Task { await model.run(background: true, detached: true) } }.disabled(model.running)
                    Text("断开验收前请拔掉这台手机的 USB 并在系统设置中关闭 Wi-Fi，蜂窝可以保留。按钮记录你的物理断开确认；程序同时核对没有 Wi-Fi 或以太网路径。")
                    Text("可以在电脑停止托管会话后运行。本页只操作自己的测试控件，截图显示在本机，报告不包含凭据或图片内容。")
                    if let url = model.reportURL { ShareLink("导出控制验收报告", item: url) }
                }
                if let image = model.image { Image(uiImage: image).resizable().scaledToFit() }
            }.navigationTitle("独立控制验收")
                .toolbar { Button("返回") { dismiss() } }
                .task {
                    #if DEBUG
                    if ProcessInfo.processInfo.arguments.contains("--selfhost-control-smoke") {
                        await model.run(background: ProcessInfo.processInfo.arguments.contains("--selfhost-background-smoke"))
                    }
                    #endif
                }
        }
    }
}
