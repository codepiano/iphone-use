# 手机自行启动 runner

这套启动器在 iPhone App 内运行 Rust：RemotePairing 验证 → TLS-PSK 开发隧道 → RSD 服务发现 → XCTest 会话。启动路径没有 Mac、usbmuxd、外部 lockdown provider 或命令行子进程。连接地址仅允许 `127.0.0.1` 和 LocalDevVPN 默认网关 `10.7.0.1`。

**这是待真机验证的启动实现，尚不能宣称已经实现完整脱离 Mac。** 配对记录、已安装 runner 和开发服务仍是前提。独立测试 App 需要保持前台；切换到助手后的会话保活、VPN 重连和手机重启后的恢复尚未验证。正式接入主 App 前必须解决这一生命周期问题。

## 构建

```sh
./experiments/phone-self-launch/prepare.sh
~/.local/bin/heavy-cargo test --locked --manifest-path experiments/phone-self-launch/Cargo.toml
./experiments/phone-self-launch/build.sh signed
```

`prepare.sh` 下载 MIT 授权的 idevice，固定 revision `41c388baef0dd55c0ce4924789abbfde889d9b87`，应用仓库中的 `idevice-rsd-launch.patch`。补丁让 XCTest 直接使用调用方的已认证 RSD 隧道，复用原有配置、会话初始化和事件循环；不再先连接外部主机的 lockdown/CoreDeviceProxy。生成的 vendor 和构建产物不进入 Git。依赖许可见 `THIRD-PARTY-NOTICES.txt`。

已有只读 idevice checkout 可以通过 `IPU_IDEVICE_SOURCE=/absolute/path` 复用；脚本会校验提交和源码修改状态，不修改该 checkout。

## 首次设置与日常使用

1. 在测试手机上安装独立 App `com.leeguoo.iphone-use.self-launch`，以及链接了手机内 daemon 的 runner。构建和首次安装目前仍通过 Xcode 完成。
2. 在手机上安装并启用 [LocalDevVPN](https://github.com/jkcoxson/LocalDevVPN)。这会占用手机的 VPN 连接，测试前应处理原有 VPN 的恢复。
3. 首次打开 App 时，在手机上生成两个随机控制令牌和本机配置，无需导入 Mac 文件。点「首次在手机上配对并启动」，本人允许系统配对提示并输入配对码；只有这条明确的首次配对流程可以从已认证本机隧道绑定设备身份。启动器通过 RSD 安装服务读取 runner 路径，身份、配置和配对记录合为一个本机 Keychain 项；等写入确认后才启动 runner。已有记录验证失败时不会自动换成新配对。

仍保留手工导入以兼容早期测试配置。`config.example.json` 是合成占位符；旧式 lockdown 记录不能代替 RemotePairing 记录。已导入配置若指定 daemon 监听地址，也仅允许 `127.0.0.1`。
4. 点「在手机上启动」。启动器会核对 RSD 返回的 `UniqueDeviceID` 和 `OSVersion`，再启动 `RunnerTests/testServe`。它不会自动进行新配对，也不会代替用户接受系统权限提示。
5. `test_plan_started` 只表示 XCTest 已开始。点「连接本机助手」会使用 runner HMAC 鉴权请求手机内 daemon 的一次性配对码，然后打开 `iphoneuse://pair`。只有真实接口成功，才会跳转。

配置中的令牌和配对记录保存在本机 Keychain，使用 `AfterFirstUnlockThisDeviceOnly`，不上传、不展示、不导出。Rust 状态只包含阶段和固定错误码；不启用依赖的 tracing 日志，避免配对库 debug 日志带出密钥。

## 恢复与停止

每次启动有 120 秒的启动截止时间。停止会关闭本程序自己的开发会话；旧线程完全退出后才允许重新启动，避免并行占用 XCTest。失败后可在手机 App 上再次启动，不要求调用 Mac 的 reconnect。

这不保证 runner 被系统杀掉后能在任意后台状态下自动恢复。普通 App 被挂起会影响开发连接；需要在主 App 语音会话或适合用途的网络扩展内验证生命周期，不能用这个独立前台 App 的成功代替产品验收。

## 软件验证

2026-10-11 自动配置更新：10 项 Rust 测试通过，覆盖本机地址限制、启动配置鉴权、错误输入、设备身份和系统版本、停止后的会话排他、配对码的一次性提交、密钥记录的一次性传递、首次配对不可跳过、Keychain 写入确认和拒绝 LAN 监听。Swift iOS 类型检查通过。iOS ARM64 静态库和开发签名 App 构建通过；从干净目录重新生成依赖并应用补丁后，源码与已测试版本一致。

这些结果只验证实现和构建，不包含真实 RemotePairing 认证、XCTest 启动、后台保活或断开 Mac 的验收。

签名测试包已安装到 iPhone 14：`PhoneSelfLaunchQA-20261011.ipa`。包校验、测试结果和源码哈希见 [软件验证记录](evidence/software-validation.json)。

## iPhone 14 验收

后续物理设备测试只使用 iPhone 14。2026-10-11 读取到这台手机为 iOS 27.2，Developer Mode 已启用；现有 Mac Wi-Fi 启动路径报告 `wifi_automation_refused`。这些状态不证明手机内隧道能或不能启动 runner。

已在 iPhone 14 安装并运行独立探测 App。本机未启用 VPN 时，62078 返回 `EPERM`，49152 的 RemotePairing 握手被重置，8100/8787 超时。报告见 [iPhone 14 无 VPN 探测](evidence/iphone14-no-vpn.json)，已去除手机局域网地址。LocalDevVPN 现已使用 App Store Connect 凭据完成开发签名并安装、打开在 iPhone 14；此前缺少 Network Extension / Personal VPN profile 的问题已解决。后续确认其扩展已运行，但普通 App 访问网关返回网络未就绪。随后采用 `explore/phone-self-host` 的自有网络扩展，在 iPhone 14 通过显式隧道连接取得合法 RemotePairing 握手（协议 26）。真实配对尚未完成。手机的 Mac runner supervisor 已暂停，握手不依赖 Mac runner。

需记录并通过：

- LocalDevVPN 开启后的本机合法 RemotePairing 握手、真实认证与 RSD 响应。
- 正常释放原有自动化会话后，由手机启动独立 runner，取得签名 `/status` 和 daemon API 响应。
- Mac 断网、拔线且停止 Mac 启动进程后，手机发出任务并观察真实 App 操作结果。
- 语音通话时切到其他 App，保持会话、打断任务并读回完成状态。
- VPN 断开/重连、Wi-Fi/蜂窝切换、runner 被结束、手机重启并由人首次解锁后，在手机恢复。

不能把编译成功、测试计划开始或 TCP 连通单独计为上述验收通过。

RSD 设备字段核对依据：[pymobiledevice3 的原始实现](https://github.com/doronz88/pymobiledevice3/blob/master/pymobiledevice3/remote/remote_service_discovery.py)。没有复制其代码，也没有复制 StikDebug 的 AGPL 代码。
