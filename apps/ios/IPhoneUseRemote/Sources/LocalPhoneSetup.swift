import SwiftUI
import PhoneRuntimeCore
import UniformTypeIdentifiers

@available(iOS 17.4, *)
struct LocalPhoneSetupView: View {
    @ObservedObject var app: AppModel
    @ObservedObject private var runtime: PhoneLocalRuntime
    @State private var busy = false
    @State private var message = ""
    @State private var importing = false
    #if DEBUG
    @MainActor private static var automaticValidationStarted = false
    @State private var qaCount = 0
    @State private var qaText = ""
    #endif
    init(app: AppModel) { self.app = app; self.runtime = app.localPhone }
    var body: some View {
        Form {
            Section {
                Text("启动后，助手可以在这台 iPhone 上执行任务。首次授权配置和安装需要电脑，后续启动由手机完成。")
                Text(runtime.phase == "running" ? "本机执行服务已运行" : runtime.state)
                if !message.isEmpty { Text(message).foregroundStyle(.secondary) }
                Button("导入首次授权配置") { importing = true }.disabled(busy)
                if !runtime.provisioned { Text("请先完成这台手机的首次授权配置。") }
                Button(busy ? "正在启动…" : "启动本机执行服务") { Task { await start() } }
                    .disabled(busy || !runtime.provisioned)
                    .accessibilityIdentifier("start-local-runtime")
                Button("停止本机执行服务", role: .destructive) { Task { await runtime.stop(); await runtime.refresh() } }.disabled(busy)
            } footer: {
                Text("本机开发网络只连接手机自己的开发服务。启用时可能切换当前 VPN；停止后可在系统设置中恢复原 VPN。")
            }
            #if DEBUG
            if ProcessInfo.processInfo.arguments.contains("--local-runtime-qa") {
                Section("控制验收") {
                    Button("QA tap") { qaCount += 1 }.accessibilityIdentifier("local-runtime-qa-button")
                    Text("QA count: \(qaCount)").accessibilityIdentifier("local-runtime-qa-counter")
                    Button("已拔 USB 并关闭 Wi-Fi，验证正式助手") {
                        qaCount = 0; qaText = ""
                        Task { await validate(detached: true) }
                    }.disabled(busy)
                    TextField("QA input", text: $qaText).accessibilityIdentifier("local-runtime-qa-text")
                        .textInputAutocapitalization(.never).autocorrectionDisabled()
                }
            }
            #endif
            Section("来源") {
                Text("本机网络方案参考 LocalDevVPN / StosVPN，作者为 SideStore Team、Stossy11、Jackson Coxson 与贡献者。")
            }
        }.navigationTitle("本机执行服务")
            .task {
                await runtime.refresh()
                #if DEBUG
                if ProcessInfo.processInfo.arguments.contains("--local-runtime-qa"), !Self.automaticValidationStarted {
                    Self.automaticValidationStarted = true
                    if ProcessInfo.processInfo.arguments.contains("--wait-offline-qa") {
                        Task { await waitForOfflineValidation() }
                    } else { await validate() }
                }
                #endif
            }
            .fileImporter(isPresented: $importing, allowedContentTypes: [.propertyList]) { result in
                Task { @MainActor in
                    do { try runtime.importTrust(from: result.get()); message = "授权配置已保存在这台手机，可以启动本机服务。" }
                    catch { message = "授权配置导入失败，请检查文件是否属于这台手机。" }
                }
            }
    }
    #if DEBUG
    private func waitForOfflineValidation() async {
        await start()
        var expired = false
        let background = UIApplication.shared.beginBackgroundTask(withName: "offline-validation") { expired = true }
        defer { if background != .invalid { UIApplication.shared.endBackgroundTask(background) } }
        let deadline = ProcessInfo.processInfo.systemUptime + 150
        message = "自动验收已准备好：拔掉 USB，在系统设置中关闭 Wi-Fi即可。"
        var observedWiFi = false
        while !expired && ProcessInfo.processInfo.systemUptime < deadline {
            let path = await runtime.validationTransportSnapshot()
            if path["wifi_path_active"] == true { observedWiFi = true }
            if observedWiFi, path["wifi_path_active"] == false, path["ethernet_path_active"] == false {
                do {
                    try await runtime.activateValidationApp()
                    try await Task.sleep(nanoseconds: 500_000_000)
                    qaCount = 0; qaText = ""
                    await validate(detached: true, userAttested: false)
                } catch { message = "自动返回验收页面失败，请重新连接手机。" }
                return
            }
            try? await Task.sleep(nanoseconds: 500_000_000)
        }
        message = "等待断开超时，请恢复连接后重新准备。"
    }
    private func validate(detached: Bool = false, userAttested: Bool = true) async {
        guard !busy else { return }
        await start()
        busy = true
        defer { busy = false }
        var transport: [String: Bool] = [:]
        var validationStage = "connect_local_daemon"
        do {
            if detached {
                validationStage = "verify_network_isolation"
                transport = await runtime.validationTransportSnapshot()
                guard transport["wifi_path_active"] == false, transport["ethernet_path_active"] == false else { throw PhoneLocalRuntime.RuntimeFailure.controlValidationFailed }
            }
            for _ in 0..<20 {
                if let local = app.sessions.values.first(where: { $0.record.isThisPhone && $0.record.address.contains(":18787") }) {
                    await local.refreshStatus()
                    if local.status?.drivable == true { break }
                }
                try await Task.sleep(nanoseconds: 250_000_000)
            }
            guard app.sessions.values.contains(where: { $0.record.isThisPhone && $0.phase == .connected && $0.status?.drivable == true }) else { throw PhoneLocalRuntime.RuntimeFailure.controlValidationFailed }
            validationStage = "validate_controls"
            let result = try await runtime.validateControls()
            guard var report = try JSONSerialization.jsonObject(with: result) as? [String: Any],
                  qaCount == 1, report["expected_input"] as? String == qaText else { throw PhoneLocalRuntime.RuntimeFailure.controlValidationFailed }
            report.removeValue(forKey: "expected_input")
            report["physical_detachment_user_attested"] = detached && userAttested
            for (key, value) in transport { report[key] = value }
            report["ui_count_observed"] = true; report["ui_input_observed"] = true
            let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
            let file = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent(detached ? "local-runtime-offline-qa.json" : "local-runtime-qa.json")
            try data.write(to: file, options: [.atomic, .completeFileProtection])
            message = "本机控制验收通过"
        } catch {
            let local = app.sessions.values.first(where: { $0.record.isThisPhone && $0.record.address.contains(":18787") })
            let failure = error as NSError
            let data = try? JSONSerialization.data(withJSONObject: ["schema": 1, "ok": false, "observed_at": ISO8601DateFormatter().string(from: Date()), "error_code": "native_app_validation_failed", "physical_detachment_user_attested": detached && userAttested, "transport": transport, "failure_stage": validationStage, "native_phase": runtime.phase, "local_connected": local?.phase == .connected, "local_drivable": local?.status?.drivable == true, "device_state": local?.status?.deviceState ?? "unavailable", "setup_blocked_on": local?.status?.setupBlockedOn ?? "", "failure_domain": failure.domain, "failure_number": failure.code])
            let file = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent(detached ? "local-runtime-offline-qa.json" : "local-runtime-qa.json")
            try? data?.write(to: file, options: [.atomic, .completeFileProtection])
            message = "本机控制验收失败"
        }
    }
    #endif
    private func start() async {
        guard !busy else { return }
        busy = true; message = ""
        defer { busy = false }
        do {
            let password = try await runtime.start()
            let result = await app.add(address: "http://127.0.0.1:18787", password: password)
            switch result {
            case .connected(let id): app.agent.targetID = id; message = "已连接，可以返回助手执行手机任务。"
            case .saved: message = "本机服务正在连接，请稍后重试。"
            case .rejected: message = "本机服务已启动，但连接尚未完成。请重试。"
            }
        } catch { message = error.localizedDescription }
    }
}
