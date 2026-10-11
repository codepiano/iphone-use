# iPhone 自主被控探索

2026-10-11，基于 `8976975`。目标：iPhone 不连接 Mac，仍能被另一台设备看屏和操作。

**当前状态：已实现并构建手机内开发网络、RemotePairing/RSD 启动器、网络扩展保活和开发镜像恢复代码。尚未通过真机独立启动及 Mac 断开验收，目标没有完成。**

2026-10-11 后续构建使用独立 App 和独立 runner，不改变原项目的其他会话。iPhone 17 Pro Max 当前离线；另一个空闲 iPhone 14（iOS 27.2）的外部 Wi-Fi 启动返回 `wifi_automation_refused`，要求 USB 授权。该结果属于原有 Mac 启动路径，不能代替手机内隧道的验收。没有反复重试 Wi-Fi 启动。

## 真机结果

设备为 iPhone 17 Pro Max，iOS 27.0。探测程序是普通开发签名 App，独立 bundle ID `com.leeguoo.iphone-use.selfhost-probe`，不使用 XCTest 权限。实验期间原有 runner、Mac USB 测试会话保持运行；没有做 Mac 断网或 runner 重启。

| 连接方式 | 端点 | 结果 | 能说明什么 |
|---|---|---|---|
| 手机 App → 回环地址 | `127.0.0.1:62078` | `EPERM` | 普通 App 的本机 lockdown TCP 连接被拒绝 |
| 手机 App → 回环地址 | `127.0.0.1:49152` | TCP 可连接，RemotePairing 握手后 `ECONNRESET` | 端口连通不足以证明开发服务可用 |
| 手机 App → 自己的 Wi-Fi 地址 | 自身 IP 的 62078 / 49152 | 分别 `EPERM` / `ECONNRESET` | 改用自身 Wi-Fi IP 没有解决问题 |
| 手机 App → 现有 runner / daemon | `127.0.0.1:8100` / `:8787` | TCP 可连接 | 已启动服务能被同机 App 访问；未验证鉴权或完整 API |
| Mac → 手机 Wi-Fi 地址 | 手机 IP 的 49152 | 收到 RemotePairing 握手，协议版本 26 | 同一握手格式在外部网络路径上有效 |
| Mac → USB 转发 | 49152 | 对端关闭连接 | USB 转发也未通过，不能用它作正对照 |

手机 Wi-Fi 地址由探测 App 的 `getifaddrs(en0)` 取得，Mac 正对照使用相同 IP。报告仅保留结果、时间、IP 和协议版本，不保留设备标识或原始握手内容。

- [手机回环协议探测](evidence/ios27-loopback-handshake.json)
- [手机自身 Wi-Fi 协议探测](evidence/ios27-own-lan-handshake.json)
- [Mac 局域网正对照](evidence/ios27-network-handshake.json)
- [USB 对照](evidence/ios27-usb-handshake.json)
- [最初仅测 TCP 的报告](evidence/ios27-no-vpn.json)：62078 当时被归为超时，细节已显示 EPERM；后续版本将其明确标为 `tcp_denied`。

这些结果只覆盖本机网络入口和未认证协议握手，没有做配对、控制权限申请或测试会话创建。外部 LocalDevVPN 尚未安装、未测试。后续改为 App 自带本地网络扩展，使用同类地址反射方案；它也尚未通过真机验证。观察到的重置不能用于断言所有 iOS 版本都禁止同机开发连接，也不能单独确定系统拒绝的内部原因。

## 已有代码能复用的部分

- `runner/` 负责看屏、触摸、输入，并能链接 `crates/ios-embed` 在手机内运行完整控制服务。
- `crates/legacy-launch` 已实现 iOS 15/16 的 lockdown、heartbeat 和 XCTest 启动。当前实现是外部进程，它必须在 runner 生命周期内持续运行。
- 依赖的 `idevice` 固定在 `41c388baef0dd55c0ce4924789abbfde889d9b87`，包含 RemotePairing、软件 TCP 隧道和 RSD 服务发现。
- 原版本的 `XCUITestService::new` 接受 `IdeviceProvider`。`run` 从 lockdown 读取版本，现代路径经 `CoreDeviceProxy` 创建 RSD 栈。它没有直接接收现成 RemotePairing adapter + RSD handshake 的公开入口；不能只把手机内隧道传给现有启动器。

源码入口：`crates/legacy-launch/src/lib.rs`、`crates/ios-embed/src/lib.rs`；依赖源码 `idevice/src/services/dvt/xctest/mod.rs` 中的 `run`、`connect_rsd_stack_once`，以及 `remote_pairing/{mod,socket,tunnel}.rs`。

## 当前实现

- `Shared/LocalPacketReflection.swift`：只反射 `10.7.1.1 ↔ 10.7.0.1` 的 IPv4 包；默认路由排除在隧道外。网络扩展来自本项目的独立 bundle，引用方案保留 LocalDevVPN/StosVPN 的版权和署名。
- `Tunnel/ScopedTunnelBridge.swift`：本机随机端口、随机鉴权令牌，仅允许连接手机自己的虚拟地址；原生 Rust 通过该桥使用 `createTCPConnectionThroughTunnel`，不会依赖网络扩展普通 socket 的默认路由行为。
- `launcher/`：静态 Rust 库，配对、验签、TLS-PSK、RSD、读取真实设备信息、查找独立 runner 并维持 XCTest 会话；状态不包含配对记录或控制令牌。停止时失效旧会话，旧异步任务不能覆盖新会话状态。
- `patches/idevice-rsd-xctest.patch`：固定版本的两项补丁，增加现成 RSD 隧道的 XCTest 入口和按文件分块上传开发镜像的入口。只修改生成的隔离依赖，不修改全局 cargo 缓存或上游仓库。
- `Shared/ProtectedStore.swift`：配对记录和控制凭据使用共享 Keychain、`AfterFirstUnlockThisDeviceOnly`。每次独立 runner 启动重新生成请求签名令牌；启动被拒绝不会改动当前会话的令牌。
- `Tunnel/PhoneTunnelProvider.swift`：原生会话运行在网络扩展内，普通控制 App 切到后台不负责保活；传输中断有限退避，配对或授权错误等待人处理。支持首次解锁后重试 Keychain 读取；这些生命周期行为尚待实测。
- `launcher/src/image.rs`：缺少开发服务时，按硬件选择镜像、申请 Apple 个性化签名、64 KiB 分块上传、挂载后刷新 RSD。开发镜像来自用户本机的 Xcode 安装，进入私有构建资源，不进 git 或公开发行资产。
- `Sources/ControlSmoke.swift`：在手机上实际发送签名 HTTP 请求，观察自己的按钮计数、输入内容、无障碍树和真实截图。验证结果保存为 JSON，图片不写入报告。该程序不是模拟 runner，必须有真实独立 runner 才能通过。

独立 runner 的 bundle ID 为 `com.leeguoo.iphone-use.selfhost-runner.xctrunner`，控制/MJPEG/daemon 端口分别为 18100/19100/18787。检测到原有 8100 自动化端口仍在运行时，独立启动会拒绝抢占。

## 真机验收待办

1. 测试手机启用 App 中的「本机开发网络」后，用「检测指定地址」测 `10.7.0.1:49152`。第一项验收是收到合法 RemotePairing 握手，而非仅显示 TCP 连接成功。此步骤会启用手机 VPN 配置，需要核对原有 VPN 的使用情况并保留恢复方法。
2. 通过后，使用保存在设备本地的 RemotePairing 记录建立隧道，验证真实 RSD 服务响应。旧式 lockdown 配对记录和 RemotePairing 记录不是同一格式。真实配对记录不进入仓库、日志或报告。
3. 通过已补充的 RSD 入口测试启动独立 runner。在现有 runner 的占用被正常释放前，不能开启第二个 XCTest 自动化会话。
4. 验证控制 App 进入后台后的会话维持、停止与恢复。会话已移入自有 Network Extension；签名构建通过仍不能证明后台生命周期有效。
5. 最后验收 Mac 断网后持续看屏和操作，再覆盖锁屏/解锁、Wi-Fi/蜂窝切换、VPN 重连、进程被结束、重启后在手机上手动恢复。普通设备重启后的首次解锁仍由人完成。

没有通过第 1、2 项前，不开发公网中继和设备列表。隧道成立后，也不能据此宣称可以无人值守或作为普通 App Store App 提供全系统控制。

## 复现探测 App

需要 Xcode、iOS 17.4+ SDK、`xcodegen` 和 Rust iOS target。首次安装和签名在电脑上进行；目标是安装后不依赖电脑维持控制。签名团队默认沿用本仓库设置，可以在构建时覆盖 `DEVELOPMENT_TEAM`。

```sh
python3 experiments/phone-self-host/prepare-dependency.py
~/.local/bin/heavy-cargo test --manifest-path experiments/phone-self-host/launcher/Cargo.toml
./experiments/phone-self-host/launcher/build.sh
./scripts/build-ios-embed.sh
python3 experiments/phone-self-host/build-runner.py
./experiments/phone-self-host/test.sh
./experiments/phone-self-host/build.sh unsigned
./experiments/phone-self-host/build.sh signed

xcrun devicectl device install app --device <UDID> \
  experiments/phone-self-host/build/Build/Products/Debug-iphoneos/PhoneSelfHostProbe.app
```

安装两个独立 App 后，打开 Self Host Probe，依次启用本机开发网络、配对本机开发服务、验证本机隧道。第一次 VPN 配置及系统授权由手机上的人完成。启动独立被控服务前正常暂停原 Mac runner；不要启动第二个 XCTest 会话。

普通网络探测可选择「检测本机端口」「检测自身 Wi-Fi 地址」或输入虚拟网络地址后选择「检测指定地址」。指定网络地址可能触发系统本地网络权限提示。报告保存在 App 的 `Documents/self-host-probe.json`，也可以在 App 中导出。

```sh
xcrun devicectl device copy from --device <UDID> \
  --domain-type appDataContainer \
  --domain-identifier com.leeguoo.iphone-use.selfhost-probe \
  --source Documents/self-host-probe.json --destination /tmp/self-host-probe.json

# Mac 正对照只发送未认证握手，不读配对记录。
python3 experiments/phone-self-host/mac-control.py --host <手机Wi-Fi-IP>
python3 experiments/phone-self-host/mac-control.py --udid <UDID>
```

支持 `--probe-on-launch` 自动进行无认证网络探测。Debug 构建可用 `--selfhost-pair` / `--selfhost-probe` / `--selfhost-launch` 执行指定操作；没有公开 URL scheme 自动启动控制。

只有用户明确点选配对或启动按钮时才申请配对/自动化会话。无认证探测仍不读凭据、不启动 runner。测试覆盖拆包、无效帧、错误方向、报告脱敏、局部包反射、错误包拒绝、独立 Python HMAC 答案、配置凭据检查和镜像路径隔离。最初网络探测版本已真机运行，新增独立启动版本目前仅完成构建，尚未部署验收。

运行状态与控制验收报告分别为 App 的 `Documents/self-host-runtime.json` 和 `Documents/self-host-control-smoke.json`。`phase=running` 不能替代输入和截图验收，也不能替代 Mac 断开观察。

## 协议与参考项目

- [idevice](https://github.com/leeguooooo/idevice/tree/41c388baef0dd55c0ce4924789abbfde889d9b87)：MIT，探测报文依据其公开协议实现独立编写。保留其许可见 `THIRD-PARTY-NOTICES.txt`。
- [StikDebug](https://github.com/StikDebug/StikDebug/tree/775fba15f3fbadc18f7f1444dc6ffb1566adaa4c)：已有同机开发服务连接方案；它的 README 要求配对记录和 LocalDevVPN。这里只用于调研，没有复制其 AGPL 代码。
- [LocalDevVPN](https://github.com/jkcoxson/LocalDevVPN/tree/af3fd697803ada4ac2b8d518358f5ab0a534844c)：可测试的虚拟网络工具，引用其本地地址反射方案，版权与自定义许可证见 `THIRD-PARTY-NOTICES.txt`；未安装外部工具。
- [Apple 后台执行说明](https://developer.apple.com/documentation/uikit/extending-your-app-s-background-execution-time)：普通后台任务提供有限执行时间。
- [Apple Network Extension 用途说明](https://developer.apple.com/documentation/technotes/tn3120-expected-use-cases-for-network-extension-packet-tunnel-providers)：自有 Network Extension 方案还需验证，不能把网络扩展当成任意后台服务。
