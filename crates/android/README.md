# android-use

让 Agent 操作 Android。与 iphone-use 共用快照、元素差异计算、滚动距离和无进展判断；Android 后端通过 ADB 连接设备，直接调用 UIAutomator runner。

Android Release 发布后的安装入口：

```sh
curl -fsSL https://raw.githubusercontent.com/leeguooooo/iphone-use/main/scripts/install-android.sh | sh
```

当前开发分支可从源码构建：

```sh
~/.local/bin/heavy-cargo build -p android-use
# 其他机器没有 heavy-cargo 时使用 cargo build -p android-use
./target/debug/android-use setup
adb devices -l
./target/debug/android-use serve --serial DEVICE_SERIAL
```

需要安装 Android SDK Platform Tools，并在手机上开启 USB 调试、解锁和授权这台电脑。`setup` 下载固定版本的设备 runner，校验 SHA-256；运行时不依赖 Python、Appium，也不要求 root。`serve` 在前台运行，Ctrl-C 关闭服务并清理自己创建的 ADB 转发。设备 runner 只监听手机的 `127.0.0.1:19008`，通过 ADB 转发访问。启动时对固定版本的 runner 应用回环地址补丁；原始文件或指令不匹配就拒绝启动。不会接管或停止外部 UIAutomator 服务，设备端口被占用时会报错。

服务仅监听 `127.0.0.1`，自动生成 bearer token，保存到 `~/.android-use/connection.json`。Unix 文件权限为 0600。CLI 与 MCP 自动读取连接配置，标准输出不打印 token。Android 的配置、锁和 Release tag 与 iPhone 分开。

另开终端：

```sh
android-use status
android-use capabilities
android-use elements
android-use act '{"type":"launch_app","app":"com.android.settings"}'
android-use act '{"type":"tap","label":"搜索设置"}'
android-use act '{"type":"type","text":"你好 👩‍💻 日本語","clear":true}'
android-use act '{"steps":[{"type":"back"},{"type":"home"}],"observe":true,"settle_ms":1500}'
android-use screenshot /tmp/android-screen.png
android-use release
```

“搜索设置”是设备当前语言中的标签，需以 `elements` 返回的文字为准。打开 App 使用 Android 包名。`type` 需要一个已聚焦的原生文本框，支持 EditText 与 AutoCompleteTextView；需要明确传 `clear:true` 替换全文，输入后回读确认。首版不支持追加：部分设备把空字段的占位提示当作 text 返回，直接拼接会把提示也写进去。密码框、WebView 文本框不支持这条输入路径，拒绝时不会改用剪贴板或宿主键盘。

点击元素时使用同一次读屏返回的 `index` 和 `snapshot`：

```sh
android-use act '{"type":"tap","element":3,"snapshot":"TOKEN_FROM_ELEMENTS"}'
android-use elements --since TOKEN_FROM_ELEMENTS
```

快照包括设备、App、画面尺寸和元素状态；执行前重新读取，过期时拒绝点击。增量读屏只返回新增或变化的行，行号仍对应完整画面；基准已被淘汰时返回完整画面。坐标输入均为 0..1，正 `scroll.dy` 表示向下浏览。

一个批次最多 32 步。先检查所有参数，再按顺序执行；失败时返回 `completed`、`failed_step`、`outcome`、`retry_safe`。`outcome:unknown` 表示动作可能已经执行，禁止重放。已完成的批次即使后续读屏失败仍返回 `outcome:applied`，同时给出 `observation_error` 和 `settle`。画面稳定不代表业务成功，调用者需要检查文字或状态。

每次控制会取得 30 秒的设备租约。不同 Agent 请使用不同 `--owner`，完成后 `release`；批次内不允许其他调用者插入操作。不同 daemon 通过设备锁避免控制同一台手机。

任意 MCP 客户端都可以配置 stdio 命令：

```json
{"mcpServers":{"android-use":{"command":"android-use","args":["mcp"]}}}
```

工具包含 `phone_status`、`phone_capabilities`、`phone_elements`、`phone_actions`、`phone_tap`、`phone_type`、`phone_screenshot`、`phone_release`。MCP 会话各自拥有租约，正常断开会释放。工具结果同时包含文字和结构化 JSON，截图以 MCP image 返回。

HTTP 接口与 CLI 使用相同控制器：`GET /agent/status`、`/agent/capabilities`、`/agent/elements?since=...`、`/agent/screenshot`；`POST /agent/input`、`/agent/actions`、`/agent/release`。请求携带 `Authorization: Bearer ...` 和 `X-Phone-Owner`。

首版集中在本地控制，不包含实时投屏、手机独立运行、语音或云设备管理。截图遵守系统限制，受保护画面可能是空白。上游 XML 读屏会把部分非 BMP 字符（如 emoji）替换成点号；聚焦的原生输入框另走 JSON 回读保留真实值，其他区域需要截图确认这些字符。ADB 支持的无线连接也可以作为 serial 使用，但 USB 和无线的验收结果分别记录。

二进制发布使用独立的 `android-v0.1.0` tag，GitHub Release 包含各平台 `.tar.gz` 和 `.sha256`。Android prerelease 不覆盖 iPhone latest；Windows 用户下载归档中的 `android-use.exe`。Linux ARM64 暂未打包。
