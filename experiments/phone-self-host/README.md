# iPhone 自主被控探索

2026-10-11，基于 `8976975`。目标：iPhone 不连接 Mac，仍能被另一台设备看屏和操作。

**当前判断：本地开发隧道值得继续验证；普通 App 直接连接自己的开发端口，在这台 iOS 27 手机上没有通过。尚未实现脱离 Mac 运行。**

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

这些结果只覆盖本机网络入口和未认证协议握手，没有做配对、控制权限申请或测试会话创建。LocalDevVPN 尚未安装、未测试。观察到的重置不能用于断言所有 iOS 版本都禁止同机开发连接，也不能单独确定系统拒绝的内部原因。

## 已有代码能复用的部分

- `runner/` 负责看屏、触摸、输入，并能链接 `crates/ios-embed` 在手机内运行完整控制服务。
- `crates/legacy-launch` 已实现 iOS 15/16 的 lockdown、heartbeat 和 XCTest 启动。当前实现是外部进程，它必须在 runner 生命周期内持续运行。
- 依赖的 `idevice` 固定在 `41c388baef0dd55c0ce4924789abbfde889d9b87`，包含 RemotePairing、软件 TCP 隧道和 RSD 服务发现。
- 该版本的 `XCUITestService::new` 接受 `IdeviceProvider`。`run` 从 lockdown 读取版本，现代路径经 `CoreDeviceProxy` 创建 RSD 栈。它没有直接接收现成 RemotePairing adapter + RSD handshake 的公开入口；不能只把手机内隧道传给现有启动器。

源码入口：`crates/legacy-launch/src/lib.rs`、`crates/ios-embed/src/lib.rs`；依赖源码 `idevice/src/services/dvt/xctest/mod.rs` 中的 `run`、`connect_rsd_stack_once`，以及 `remote_pairing/{mod,socket,tunnel}.rs`。

## 下一轮实验

1. 测试手机启用 LocalDevVPN 后，用本 App 的「检测指定地址」测 `10.7.0.1:49152`。第一项验收是收到合法 RemotePairing 握手，而非仅显示 TCP 连接成功。此步骤会启用手机 VPN 配置，需要核对原有 VPN 的使用情况并保留恢复方法。
2. 通过后，使用保存在设备本地的 RemotePairing 记录建立隧道，验证真实 RSD 服务响应。旧式 lockdown 配对记录和 RemotePairing 记录不是同一格式。真实配对记录不进入仓库、日志或报告。
3. 为 XCTest 启动器增加现成 RSD 隧道入口，再测试启动一个独立 runner。在现有 runner 的占用被正常释放前，不能开启第二个 XCTest 自动化会话。
4. 验证控制 App 进入后台后的会话维持。普通 App 的有限后台任务时间不等于持续保活。把网络会话放进自有 Network Extension 是候选方案，需要实测生命周期和签名能力，不能假定外部 LocalDevVPN 会替我们的启动器保活。
5. 最后验收 Mac 断网后持续看屏和操作，再覆盖锁屏/解锁、Wi-Fi/蜂窝切换、VPN 重连、进程被结束、重启后在手机上手动恢复。普通设备重启后的首次解锁仍由人完成。

没有通过第 1、2 项前，不开发公网中继和设备列表。隧道成立后，也不能据此宣称可以无人值守或作为普通 App Store App 提供全系统控制。

## 复现探测 App

需要 Xcode、iOS 17.4+ SDK 和 `xcodegen`，无需 Rust 编译。签名团队默认沿用本仓库设置，可以在构建时覆盖 `DEVELOPMENT_TEAM`。

```sh
./experiments/phone-self-host/test.sh
./experiments/phone-self-host/build.sh unsigned
./experiments/phone-self-host/build.sh signed

xcrun devicectl device install app --device <UDID> \
  experiments/phone-self-host/build/Build/Products/Debug-iphoneos/PhoneSelfHostProbe.app
```

打开 Self Host Probe，选择「检测本机端口」「检测自身 Wi-Fi 地址」或输入虚拟网络地址后选择「检测指定地址」。指定网络地址可能触发系统本地网络权限提示。报告保存在 App 的 `Documents/self-host-probe.json`，也可以在 App 中导出。

```sh
xcrun devicectl device copy from --device <UDID> \
  --domain-type appDataContainer \
  --domain-identifier com.leeguoo.iphone-use.selfhost-probe \
  --source Documents/self-host-probe.json --destination /tmp/self-host-probe.json

# Mac 正对照只发送未认证握手，不读配对记录。
python3 experiments/phone-self-host/mac-control.py --host <手机Wi-Fi-IP>
python3 experiments/phone-self-host/mac-control.py --udid <UDID>
```

支持 `--probe-on-launch` 启动参数自动进行回环地址探测。探测不发送完整配对请求、不导入配对记录、不启动或终止 runner、不操作其他 App。测试覆盖拆包、无效帧、错误方向的响应、敏感字段不进入报告；最终版本已开发签名构建并安装到上述真机运行。

## 协议与参考项目

- [idevice](https://github.com/leeguooooo/idevice/tree/41c388baef0dd55c0ce4924789abbfde889d9b87)：MIT，探测报文依据其公开协议实现独立编写。保留其许可见 `THIRD-PARTY-NOTICES.txt`。
- [StikDebug](https://github.com/StikDebug/StikDebug/tree/775fba15f3fbadc18f7f1444dc6ffb1566adaa4c)：已有同机开发服务连接方案；它的 README 要求配对记录和 LocalDevVPN。这里只用于调研，没有复制其 AGPL 代码。
- [LocalDevVPN](https://github.com/jkcoxson/LocalDevVPN/tree/af3fd697803ada4ac2b8d518358f5ab0a534844c)：可测试的虚拟网络工具，本实验未复制代码或安装该工具。
- [Apple 后台执行说明](https://developer.apple.com/documentation/uikit/extending-your-app-s-background-execution-time)：普通后台任务提供有限执行时间。
- [Apple Network Extension 用途说明](https://developer.apple.com/documentation/technotes/tn3120-expected-use-cases-for-network-extension-packet-tunnel-providers)：自有 Network Extension 方案还需验证，不能把网络扩展当成任意后台服务。
