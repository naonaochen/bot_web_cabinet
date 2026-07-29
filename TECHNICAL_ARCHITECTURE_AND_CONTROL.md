# Technical Architecture and Core Control Document

> 修改代码逻辑前请先阅读本文档。
>
> 目标：避免重复改动、流程分叉、toast 误判、会话状态错乱、GUI/CLI 行为不一致。

---

## 1. 系统目标

本项目是一个基于 Playwright 的 MES 网页自动化程序，主要完成以下工作：

1. 打开浏览器并登录
2. 进入目标业务页面
3. 上传配置文件
4. 对目标文件执行 Apply
5. 删除非目标文件
6. 配置 South Communication
7. 执行 Calibration
8. 检查 Active Alarm
9. 继续执行 Continue 阶段的后续流程
10. 提供 GUI 和 CLI 两种入口

系统需要支持：

- 多轮执行
- Continue 会话复用
- 多 toast 干扰下的正确判定
- 失败后可定位日志、截图和 trace

---

## 2. 顶层代码结构

### 2.1 入口文件

- `gui_app.py`
  - GUI 入口
  - 负责按钮、状态显示、后台线程启动
  - 不直接写业务细节，业务通过 `FlowRunner` 执行
  - 窗口位置 / 大小 / 透明度 / 置顶状态由 `config/settings.yaml` 的 `ui` 配置驱动

- `gui.py`
  - GUI 启动包装器
  - 导入 `App` 并启动 Tk 主循环

- `main.py`
  - CLI 入口
  - 负责命令行参数、配置读取、网络预检、调用 `tasks.flow_task.run_flow()`

### 2.2 核心控制层

- `core/flow_runner.py`
  - GUI 的核心会话控制器
  - 管理 browser / context / page 生命周期
  - 提供 Start / Continue / End 三个主控制动作

### 2.3 业务模块

- `core/auth.py`
  - 登录与验证码处理

- `core/browser.py`
  - 创建 Playwright browser / context / page

- `core/upload.py`
  - 上传文件

- `core/apply.py`
  - Apply 按钮点击与成功判定

- `core/delete.py`
  - 删除记录、批量清理表格

- `core/south_communication.py`
  - South Communication 设置

- `core/calibration.py`
  - Calibration 操作

- `core/navigation.py`
  - 菜单路径点击和页面导航

- `core/toast.py`
  - toast 清理、toast 文本采集、最新 toast 判定

- `core/verify_*.py`
  - 各类页面和结果验证

- `core/screenshot.py`
  - 截图保存

- `core/utils.py`
  - 配置加载、路径处理、日志辅助、文件辅助

### 2.4 CLI 任务编排

- `tasks/flow_task.py`
  - CLI 版完整流程编排
  - 负责上传、Apply、删除、南向、校准、告警、报告输出

---

## 3. 两条执行路径

当前系统有两条业务执行路径。

### 3.1 GUI 路径

`gui_app.App -> core.flow_runner.FlowRunner`

GUI 负责：

- 用户点击按钮
- 展示状态和日志
- 启动后台线程
- 调用 `FlowRunner` 执行真正业务

### 3.2 CLI 路径

`main.py -> tasks.flow_task.run_flow()`

CLI 负责：

- 参数解析
- 配置加载
- 网络预检
- 调用 `run_flow()` 执行一次完整业务流

---

## 4. 当前架构原则

### 4.1 GUI 只管控制，不写细节业务

GUI 文件中不要再堆积：

- 具体页面操作
- 表格扫描
- toast 判定
- 页面按钮定位
- 业务验证逻辑

这些逻辑统一放到 `core/*` 或 `FlowRunner`。

### 4.2 业务成功判断以“当前动作后的新结果”为准

特别是 toast 场景，不能只判断：

- 页面中是否存在成功文本

必须判断：

- 这个 toast 是否是当前动作之后出现的
- 是否是最新 toast
- 是否被旧 toast 干扰

### 4.3 GUI / CLI 逻辑必须保持业务一致

允许实现方式不同，但必须保持：

- 操作顺序一致
- 成功条件一致
- 失败策略一致
- 配置字段含义一致

如果修改了 GUI 的流程，必须确认 CLI 是否也要同步。

---

## 5. 窗口初始化策略

GUI 启动时必须遵守以下策略，避免不同机器、不同分辨率或多显示器环境导致窗口不可见或布局错位。

### 5.1 位置

优先读取：

- `ui.initial_x`
- `ui.initial_y`

#### 规则

- 如果配置了位置，则按配置定位
- 如果未配置位置，则只设置宽高，不强制定位
- 如果配置位置超出当前屏幕范围，自动修正到可见区域

### 5.2 大小

优先读取：

- `ui.initial_width`
- `ui.initial_height`
- `ui.min_width`
- `ui.min_height`

#### 规则

- 初始打开大小按 `initial_width / initial_height`
- 最小尺寸按 `min_width / min_height`
- 不允许缩小到导致控件挤坏

### 5.3 透明度

优先读取：

- `ui.idle_alpha`
- `ui.start_alpha`

#### 规则

- 空闲时使用 `idle_alpha`
- Start 后使用 `start_alpha`
- 失败或恢复时回到 `idle_alpha`

### 5.4 置顶状态

#### 当前策略

- GUI 默认 `topmost = True`
- 用户可自行最小化
- 不自动取消置顶

#### 规则

- 启动后窗口始终浮在浏览器前面
- 便于监控自动化过程
- 不自动抢焦点过久，只保证处于前景层

### 5.5 启动行为

#### 启动时

- 读取配置
- 设置位置
- 设置大小
- 设置最小尺寸
- 设置透明度
- 设置置顶

#### Start 时

- 透明度切到 `start_alpha`
- 保持置顶
- 方便用户盯住流程

#### 失败时

- 自动回 `Idle`
- 透明度回 `idle_alpha`
- 按钮恢复可重试
- 窗口保持打开

### 5.6 修改原则

以后修改窗口行为时，遵循以下原则：

- 窗口大小和位置优先看 `settings.yaml`
- 如果配置超出屏幕范围，要自动修正
- 置顶、透明度、状态色要和运行状态一致
- 失败后一定要回到可重试状态，不能卡死

---

## 6. 按钮状态规则说明

GUI 只有三个主按钮：`Start`、`Continue`、`End`。按钮是否可执行，不只看当前状态名，还要结合后台线程和 session 是否存在。

### 6.1 状态变量说明

- `_state`：GUI 当前状态字符串
- `_worker`：后台执行线程
- `running`：`_worker is not None and _worker.is_alive()`
- `runner.page`：当前 Playwright page 是否存在（有效会话）

### 6.2 `Start`

#### 可执行条件

- `_state == "idle"`
- 且 `running == False`

#### 含义

只有在完全空闲时才能启动新一轮自动化。

#### 代码条件

```python
self._state == "idle" and not running
```

### 6.3 `Continue`

#### 可执行条件

- 当前状态必须是 `active_alarm_done`
- `runner.page` 存在
- `running == False`

#### 含义

Continue 只能在主流程已经完整跑到 `active_alarm_done` 后，且当前没有任务执行中的空档期使用。

#### 代码条件

```python
can_continue = self._state == "active_alarm_done" and not running and bool(self.runner.page)
```

### 6.4 `End`

#### 可执行条件

- 当前状态属于运行中或已完成的阶段
- 或后台 worker 正在运行

#### 含义

只要流程已经启动过，`End` 基本都可用，用于结束浏览器会话，但不关闭 GUI 窗口。

### 6.5 规则总结

| 按钮 | 主要条件 | 作用 |
|------|----------|------|
| `Start` | `idle` 且无 worker | 启动新流程 |
| `Continue` | 有有效 page/session 且无 worker | 继续当前会话 |
| `End` | 运行中或已完成状态 | 关闭浏览器会话，GUI 保持打开 |

### 6.6 规则提醒

- 不要只改按钮样式，不改状态条件
- 不要在没有 `runner.page` 时允许 Continue
- 不要让 End 去关闭 GUI 窗口
- 不要在 worker 运行中允许重复 Start / Continue

---

## 7. 核心运行流程

---

### 7.1 Start 主流程

Start 的正确顺序如下：

1. 创建浏览器
2. 打开登录页
3. 登录
4. 等待页面稳定
5. 导航到 Download/Upload
6. 上传文件
7. Submit Upload
8. 校验上传结果
9. Apply 目标文件
10. 删除非目标文件
11. 配置 South Communication（如启用）
12. Calibration
13. Active Alarm
14. 保持 session 打开，等待 Continue / End

### 5.2 Continue 主流程

Continue 的正确顺序如下：

1. 复用当前 browser/context/page
2. 进入 Continue 的 Download/Upload 页面
3. 对 Continue 目标文件执行 Apply
4. 删除不保留的文件
5. 执行 Other Control
6. 保持 session 打开，等待 End

### 5.3 End 主流程

End 的正确顺序如下：

1. 设置 stop 标志
2. 关闭 context
3. 关闭 browser
4. 停止 Playwright
5. 清理 GUI 状态
6. 回到 idle

---

## 6. 核心控制点

---

### 6.1 `core.flow_runner.FlowRunner`

这是 GUI 的核心控制器。

#### 负责内容

- browser 生命周期
- page/session 持有
- Start / Continue / End
- 状态流转
- 调用各业务模块

#### 不应该做的事

- 不应该在 GUI 中重复实现业务步骤
- 不应该把 toast 判断写在 GUI 内
- 不应该把按钮定位和菜单点击散落在 GUI 中

#### 关键字段

- `self.playwright`
- `self.browser`
- `self.context`
- `self.page`
- `self.state`
- `self.stop_event`

#### 状态意义

- `idle`：空闲
- `starting`：正在创建浏览器/准备启动
- `logged_in`：登录完成
- `navigated`：进入目标页面
- `download_upload_done`：上传完成
- `south_comm_done`：South Communication 完成
- `calibration_done`：Calibration 完成
- `active_alarm_done`：Active Alarm 完成
- `continue_running`：Continue 正在执行
- `continue_done`：Continue 阶段完成

### 6.2 `core.toast`

这是整个项目中非常关键的公共模块。

#### 主要职责

- 清理当前 visible toast
- 采集当前 toast 文本
- 根据 baseline 找出“当前动作之后出现的新 toast”
- 从多个 toast 中挑选最新一个匹配项

#### 为什么重要

Apply、Delete、Other Control 都依赖它。

如果这里逻辑错了，会导致：

- 旧 toast 被误判成当前动作成功
- 当前 toast 漏判
- 多个动作相互污染

#### 修改规则

- 修改 toast 模块前，先确认是否会影响所有动作
- 如果改了 selector，要同时验证 Apply / Delete / Other Control

### 6.3 `core.apply.apply_file`

#### 作用

对目标文件点击 Apply，并确认成功。

#### 成功判断顺序

1. 先清理旧 toast
2. 记录 baseline
3. 点击 Apply
4. 等待页面反应
5. 只认 baseline 之后的新 toast
6. 成功 toast 不明显时，再退回按钮状态检查

#### 风险点

- 多 toast 干扰
- Apply 文案变化
- 按钮选择器变化
- 页面加载慢导致误判

### 6.4 `core.delete.keep_only_uploaded_files`

#### 作用

清理表格，仅保留上传文件。

#### 注意点

- 倒序删除，避免索引偏移
- 删除后刷新 rows
- 删除成功也要关注 toast，但不能只靠 toast 判断最终状态

### 6.5 `FlowRunner.run_continue_flow`

这是多轮循环中最容易出问题的地方。

#### 它依赖

- 当前 page 仍然活着
- 当前 session 没被销毁
- 菜单路径仍正确
- Continue 配置完整
- Other Control 文案和按钮一致

#### 修改时必须特别谨慎

如果这里改坏，多轮生产就会退化。

---

## 7. 配置与代码的绑定关系

### 7.1 `config/settings.yaml`

配置文件是运行逻辑的核心输入。

#### 关键分组

- `app`
  - 浏览器、URL、timeout
- `login`
  - 登录账号、验证码、成功判断文本
- `ui`
  - 页面等待、窗口和延迟
- `navigation`
  - 菜单路径
- `apply`
  - Apply 目标文件、按钮文案、成功 toast
- `delete`
  - 删除按钮、确认按钮、成功消息
- `other_control`
  - YES / Save 按钮和控制项
- `south_communication`
  - 南向配置项
- `calibration`
  - 校准项和延迟
- `timeouts`
  - 所有等待超时
- `flow`
  - 主流程上传文件、Apply 目标、Continue 配置
- `files`
  - 日志、截图、trace 路径

### 7.2 修改配置时的注意事项

如果改了配置里的文案或路径，必须同步检查代码里是否：

- 还在使用旧文本
- 还在依赖旧菜单层级
- 还在依赖旧 toast 文案

---

## 8. 修改代码前必须检查的顺序

修改任何逻辑前，请先按下面顺序检查：

1. `TECHNICAL_ARCHITECTURE_AND_CONTROL.md`
2. 相关 `settings.yaml` 配置
3. 对应 `core/*` 模块
4. `FlowRunner` 或 `tasks/flow_task.py`
5. `gui_app.py` / `main.py`

### 不要直接改的地方

- 不要在 GUI 里直接写业务逻辑
- 不要在多个文件里重复实现 toast 判定
- 不要在多个地方独立写菜单点击和表格扫描
- 不要随意改成功判断文本而不检查配置

---

## 9. 高风险修改项

以下改动属于高风险，改之前必须评估影响：

- 改 toast selector
- 改 Apply 成功判断
- 改 Continue 逻辑
- 改 session 释放逻辑
- 改菜单路径
- 改按钮文案匹配
- 改 `FlowRunner.stop()`
- 改 `run_flow()` 和 `FlowRunner` 的业务顺序
- 改 GUI 线程与状态更新方式

---

## 10. 常见错误模式

### 10.1 旧 toast 误判新动作

表现：

- 动作刚点，系统就认为成功

原因：

- 没清旧 toast
- 没记录 baseline
- 只扫到页面全局文本

### 10.2 Continue 失败

表现：

- 页面找不到
- 菜单点不到
- Other Control 没有正确执行

原因：

- page/session 已失效
- 页面状态不是预期位置
- 配置不完整

### 10.3 二次 Start 不稳定

表现：

- 第二轮启动失败
- 浏览器残留进程
- 页面状态错乱

原因：

- `stop()` 没有完全清理
- GUI 线程与后台线程状态未同步

---

## 11. 推荐的修改原则

### 原则 1：一个能力尽量只在一个地方实现
例如 toast 判定只放 `core/toast.py`。

### 原则 2：GUI 只做控制，不做业务细节
GUI 不写页面操作逻辑。

### 原则 3：同一动作在 GUI / CLI 保持业务一致
实现可以不同，但行为必须一致。

### 原则 4：多轮循环优先保证状态复位
先保证能稳定二次 Start，再优化体验。

### 原则 5：改配置前先改文档
文档中先说明配置的业务意义，再改代码。

---

## 12. 当前项目最核心的三条控制线

### 控制线 1：会话生命周期

`FlowRunner.start_browser()` → `open_home_and_login()` → `run_main_flow()` / `run_continue_flow()` → `stop()`

### 控制线 2：toast 成功判定

`dismiss_toasts()` → 记录 baseline → 动作执行 → `latest_new_toast()` → 后备状态验证

### 控制线 3：GUI / CLI 分工

- GUI：`gui_app.py` → `FlowRunner`
- CLI：`main.py` → `tasks.flow_task.run_flow()`

---

## 13. 结论

本项目当前已经具备较清晰的分层：

- GUI 控制层
- 会话编排层
- 业务动作层
- toast 公共判定层
- CLI 流程层

但修改时仍必须遵守以下原则：

- 不要把业务再写回 GUI
- 不要让 toast 判定再分散
- 不要破坏 Start / Continue / End 的会话边界
- 不要让 GUI 与 CLI 的业务逻辑发生分叉

> **任何修改前，请先读本文档，再读对应模块，再改代码。**
