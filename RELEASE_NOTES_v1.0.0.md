# Release Notes · v1.0.0

## 版本定位

**Bot tester for cabinet · v1.0.0**

这是本项目的第一个完整可用版本。

- 可作为正式 release 基线
- 后续优化和功能扩展都在本版本基础上进行
- 不再建议推翻主流程结构

---

## 本版包含什么

### 1. 完整 GUI 控制台
- 专业深色控制台风格
- 窗口标题：`Bot tester for cabinet`
- Start / Continue / End 三个主按钮
- 状态徽章、运行指示、日志区
- 失败后可回 Idle 并重试

### 2. 会话控制层
- `core/flow_runner.py`
- 管理 browser / context / page 生命周期
- 支持：
  - Start：完整主流程
  - Continue：复用会话继续执行
  - End：关闭浏览器会话，**不关闭 GUI**

### 3. 主流程能力
Start 后自动完成：
1. 打开浏览器
2. 登录
3. 导航到目标页面
4. 上传文件
5. Apply
6. 删除非目标文件
7. South Communication
8. Calibration
9. Active Alarm
10. 保持会话，等待 Continue / End

### 4. Continue 能力
- 仅在主流程完整到达 `active_alarm_done` 后开放
- 复用当前会话
- 进入 Continue 的 Download/Upload
- Apply 目标文件
- 清理文件
- 执行 Other Control

### Continue 可执行条件
- 当前状态必须是 `active_alarm_done`
- 后台 worker 不在运行
- `runner.page` 仍然存在

这保证 Continue 只会在主流程完整完成后才可触发，避免在中途误操作。
### 5. toast 统一判定
- `core/toast.py`
- 统一清理旧 toast
- 记录 baseline
- 优先识别当前动作后的新 toast
- 降低多 toast 干扰风险

### 6. 配置驱动窗口行为
由 `config/settings.yaml` 的 `ui` 控制：
- `initial_width` / `initial_height`
- `min_width` / `min_height`
- `initial_x` / `initial_y`
- `idle_alpha` / `start_alpha`
- 超出屏幕时自动修正到可见范围
- 默认置顶，用户自行最小化

### 7. 文档
- `TECHNICAL_ARCHITECTURE_AND_CONTROL.md`
  - 架构说明
  - 核心控制逻辑
  - 窗口初始化策略
  - 修改约束

---

## 本版入口

### GUI
```bash
python gui_app.py
```
或：
```bash
python gui.py
```

### CLI
```bash
python main.py
```

说明：
- GUI 走 `FlowRunner`
- CLI 走 `tasks/flow_task.run_flow()`
- 业务目标应保持一致，但实现路径不同

---

## 已知限制

### 1. 依赖现场页面结构
菜单文案、按钮文案、toast 文案变化后，可能需要同步改配置。

### 2. 网络与页面可达性
如果目标站点超时或不可达，Start 会失败。  
当前版本已支持失败后回 Idle 并重试。

### 3. Continue 依赖 Start 成功留下的会话
- Start 失败后不能 Continue
- End 后不能 Continue
- 必须先有有效 session

### 4. GUI 与 CLI 仍是双路径
- 适合分别使用
- 后续应尽量保持业务一致，避免分叉

### 5. 多轮生产稳定性仍需现场验证
代码链路已完整，但真实环境多轮回归仍建议执行：
- Start → End → Start
- Start → Continue → End
- 连续多轮运行

---

## 建议的后续优化方向

### 优先级高
1. 现场多轮回归验证
2. toast 误判场景压测
3. Continue 多轮稳定性验证
4. 失败提示与恢复体验再细化

### 优先级中
1. 把更多业务步骤做成更小的可测试单元
2. 统一 GUI / CLI 底层步骤
3. 增加更明确的执行报告

### 优先级低
1. 进一步打磨 UI 细节
2. 增加更细的状态文案
3. 增加可选的操作统计面板

---

## 版本边界说明

### 本版以后不再建议做的事
- 不要再把业务逻辑写回 `gui_app.py`
- 不要再分散实现 toast 判定
- 不要破坏 Start / Continue / End 的会话边界
- 不要让 GUI 与 CLI 业务顺序明显分叉

### 本版以后建议怎么改
- 小步优化
- 先改文档，再改代码
- 每次改动后做一次 Start / Continue / End 回归
- 保持 `settings.yaml` 与代码同步

---

## 发布建议

### 版本号
- `v1.0.0`

### 基线文件
- `gui_app.py`
- `core/flow_runner.py`
- `core/toast.py`
- `config/settings.yaml`
- `TECHNICAL_ARCHITECTURE_AND_CONTROL.md`
- `RELEASE_NOTES_v1.0.0.md`

### 发布说明一句话
> 本版本为 Bot tester for cabinet 的首个完整可运行版本，包含 GUI 控制台、会话控制、主流程、Continue 流程、toast 统一判定和窗口初始化策略，可作为后续迭代基线。

---

## 结论

**v1.0.0 可作为第一个完整 release。**

后续所有修改，建议都在这个版本基础上进行优化，不再推倒重来。
