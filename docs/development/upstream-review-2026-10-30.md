# 三个项目的 issue / PR 对照（2026-10-30）

范围是原项目 `zhongerxin/iPhone-use`、当前 fork 的上游
`leeguooooo/iphone-use`，以及 `hughlee824/iphone-use`。核对了近期 issue、
开放 PR 和与输入、连接、授权、恢复相关的已合并 PR；这是相关性筛选，
不是对全部历史议题的穷尽审计。PR 的测试数字是提交者报告，不等于本机复测。
当前开发基线为 leeguooooo 的 `afab9e113acac700718a6f918197ab7e11137a87`。

## 与当前批量操作最相关的发现

1. **应用限制可能涉及自动化环境，不只涉及触摸节奏。**
   原项目 [#43](https://github.com/zhongerxin/iPhone-use/issues/43) 报告淘宝反复验证码；
   [#49](https://github.com/zhongerxin/iPhone-use/issues/49) 报告没有主动控制时，
   安装 WDA 后仍出现退出登录、卸载后恢复。后者没有重新安装作二次复现，
   作者也明确没有证明淘宝检测 WDA。因此不能把我们的失败直接归因为风控，
   更不能承诺改坐标/延迟就能消除限制。
2. **动作确认与业务结果必须分开。**
   leeguooooo 的 [#321](https://github.com/leeguooooo/iphone-use/pull/321)
   记录滚动惯性吞掉下一次点击，而两次操作都收到 ACK；
   [#347](https://github.com/leeguooooo/iphone-use/pull/347)
   修复手势可能已送达后再走坐标回退造成的重放。
   两个 PR 已合并，合并提交均是本 fork 基线的祖先，不重复移植。
3. **输入保护仍有未完成的边界。**
   leeguooooo [#335](https://github.com/leeguooooo/iphone-use/pull/335)
   仍是开放 Draft，包含目标绑定、分段回执、单次续传和完整值读取等工作。
   部分修复已经拆入主线；默认 Native 路径在一个在途段内仍可能随焦点变化误入字段。
   当前适配器不声称逐字隔离，也不整包合并该 Draft。

## 采用与改进清单

| 来源 | 有价值的机制 | 本次处理 |
| --- | --- | --- |
| 原项目 [PR #33](https://github.com/zhongerxin/iPhone-use/pull/33)，开放 | 动作前检查页面变化；明确拒绝陈旧观察 | 借鉴原则，新 `touch_path` 必须携带快照并在派发前重新读树；页面变化停止。没有搬入 20 ms 后台轮询或自动平移旧坐标。 |
| 原项目 [PR #45](https://github.com/zhongerxin/iPhone-use/pull/45)、[#46](https://github.com/zhongerxin/iPhone-use/pull/46)，开放 | 授权暂停覆盖队列、在途响应、旧预览；有界恢复 | 使用 leeguooooo 现有 owner/privacy generation 门控，新入口检查派发时控制范围；本次任务检查点暂停后不自动恢复。跨代预览仍由现有实现负责。 |
| 原项目 [PR #52](https://github.com/zhongerxin/iPhone-use/pull/52)，开放 | 按设备的进程级 FIFO 租约、换手先观察 | 本次复用现有 daemon owner 租约，另加同任务检查点文件锁。跨 PUA、KVM 等不同控制栈的共同 FIFO 还没有实现；避免叠加两个互不感知的抢占体系。 |
| 原项目 [PR #47](https://github.com/zhongerxin/iPhone-use/pull/47)、[#51](https://github.com/zhongerxin/iPhone-use/pull/51)，开放 | USB 优先，按已配对设备切换 CoreDevice 加密隧道 | leeguooooo 已有原生 relay；此前已单独验证拔线后的新读屏和一次导航，不再搬入 Node 转发器。无线冷启动、反复插拔和长时间稳定性仍需另验。 |
| 原项目 [PR #36](https://github.com/zhongerxin/iPhone-use/pull/36)，开放 | 识别通知横幅，避免把 SpringBoard 当成目标 App | 记录为后续改进；当前控制器发现前台根应用变化就暂停。读屏保持只读，不自动滑走用户通知。 |
| leeguooooo [PR #333](https://github.com/leeguooooo/iphone-use/pull/333)，已合并 | 只对明确忙碌的读取重试一次；键盘遮挡有界恢复；保留未知结果 | 合并提交已在基线中。当前控制器更保守：出错即暂停，不重放写入、不覆盖遮挡保护。 |
| leeguooooo [PR #233](https://github.com/leeguooooo/iphone-use/pull/233)，已合并 | 随会话续租、到期释放的保活机制 | 基线已有，无需重写。该实现会周期性发送 F13 HID；不是完全无事件的 user-presence 方案。新控制器不靠盲点屏幕保活，也不改用户自动锁屏设置。 |
| HughLee [PR #24](https://github.com/hughlee824/iphone-use/pull/24)，已合并 | 纯触摸粘贴：先准备剪贴板，用户界面完成粘贴，核验后恢复；禁止重叠事务 | 优先后续候选。其 Swift 原生通道不能直接移植到 Rust daemon；需要单独做剪贴板所有权、崩溃恢复和真机文本验收。本次仅加入短文本单次插入，不把 prepared 当作已输入。 |
| HughLee [PR #34](https://github.com/hughlee824/iphone-use/pull/34)，已合并 | 清空后读取确认，再输入；处理光标/选区和 emoji | 后续文本替换必须采用这类验收。当前入口禁止隐式 clear/replace，避免引入未经验证的替换行为。 |
| HughLee [PR #38](https://github.com/hughlee824/iphone-use/pull/38)，已合并 | 会话发现与借用；区分 created / borrowed；剪贴板事务未结束时禁止复用 | 值得用于以后正式切换工具时的生命周期设计。本次不创建/接管连接，也不在退出时断开借用的 daemon。 |
| HughLee [PR #32](https://github.com/hughlee824/iphone-use/pull/32)、[#47](https://github.com/hughlee824/iphone-use/pull/47)，已合并 | 有证据才显示 UI Automation 授权阶段；设置过程流式进度；清理归属明确 | 后续安装引导候选。leeguooooo [#381](https://github.com/leeguooooo/iphone-use/pull/381) 已改进证书、设备选择与授权恢复指引，先复用基线能力。 |
| HughLee [PR #54](https://github.com/hughlee824/iphone-use/pull/54)，已合并 | 旋转时保留同一预览流、检查显示面身份与坐标边界 | 记录为预览改进；本次没有改预览 UI。新路径遇到 viewport 不同直接拒绝，不借预览旋转静默换算坐标。 |

本轮没有检索到 HughLee 的公开 issue 结果，也没有检索到其开放 PR；
其已合并 PR 的讨论和验收记录提供了主要证据。原项目的上述核心 PR 仍开放，
不能把 PR 描述当作已经随原插件发布。

## 本次真正新增的部分

- 复用外部轨迹库 0.4 的点击和移动规划，使用独立种子、按钮内安全落点及接触时长。
- 新的逐采样时间接口；不把高密度路径硬塞进 16 点、等时长的旧拖拽接口。
- 串行检查点、前后条件、逐条业务验收、节奏下限与轮间休息。
- 验证/限流/异常空结果提示及不确定投递时锁存暂停，拒绝自动重放、进程重启续跑。
- 保留 daemon 的既有授权、所有权与隐私边界；没有更换正在运行的工具。

详细接口和测试范围见 [Guarded touch execution](guarded-touch-execution.md)。
应用兼容性、真实触摸识别、长时间稳定性和风控效果没有由这些离线测试证明。
