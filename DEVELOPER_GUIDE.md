# Developer Guide

## 1. 代码结构

- `gui_app.py`：GUI、主状态机、日志分发
- `main.py`：CLI 入口
- `core/`：核心自动化逻辑
- `tasks/`：任务级编排

---

## 2. 程序运行总流程

### 2.1 启动阶段

程序启动后，会先完成以下工作：

1. 读取 `config/settings.yaml`
2. 初始化日志目录、截图目录、trace 目录
3. 创建 GUI 或进入 CLI 流程
4. 建立浏览器启动参数和运行状态
5. 进入主流程入口，等待用户点击 Start 或由 CLI 直接执行

### 2.2 登录阶段

登录阶段的执行顺序通常是：

1. 打开登录页
2. 输入用户名和密码
3. 处理验证码
4. 点击登录
5. 等待页面跳转和主界面稳定

验证码部分当前不是传统 OCR 直读，而是样本库驱动的图像识别流程：

- 每次登录都会保存验证码原图到 `debug/captcha_samples/`
- 已标注样本使用 `原文件名__正确验证码.png`
- `captcha_ocr.py` 使用 OpenCV 做预处理
- 再进行连通域/轮廓分割
- 最后缩放到 28×28 做模板匹配

如果验证码识别失败，会回退到人工输入。

### 2.3 主流程阶段

登录成功后，程序会继续执行主业务步骤：

1. 进入 Download/Upload 页面
2. 上传配置文件
3. 找到目标文件行
4. 点击 Apply
5. 等待成功 toast
6. 删除非目标文件
7. 继续执行 South Communication、Calibration、Active Alarm 等步骤

如果启用了 Continue 模式，程序会复用当前会话继续执行后续动作。

---

## 3. 关键模块执行逻辑

### 3.1 `gui_app.py`

`gui_app.py` 负责整体协调：

- 维护 GUI 按钮状态和流程状态机
- 将日志同时输出到界面和文件
- 启动 `FlowRunner`
- 处理 Start / Continue / End 交互
- 在必要时关闭浏览器与释放资源

它更像“总控层”，不负责具体页面操作。

### 3.2 `tasks/flow_task.py`

`flow_task.py` 负责完整业务流程编排：

1. 登录并验证登录结果
2. 上传文件并校验上传结果
3. 点击 Apply
4. 等待 Apply 成功 toast
5. 删除其他文件
6. 执行后续配置步骤

这个文件更像“任务调度器”，它不直接写复杂的页面操作细节，而是调用 `core/` 的具体函数。

### 3.3 `core/auth.py`

`auth.py` 负责登录动作：

- 定位用户名、密码、验证码输入框
- 调用验证码识别模块
- 自动填写验证码
- 点击登录按钮
- 检查登录是否成功

### 3.4 `core/captcha_ocr.py`

`captcha_ocr.py` 负责验证码的完整识别链路：

- 截图验证码元素
- 保存原始样本到 `debug/captcha_samples/`
- 生成/刷新样本索引
- 加载字体模板和已标注样本
- OpenCV 预处理
- 字符分割
- 模板匹配
- 返回 4 位结果

### 3.5 `core/apply.py`

`apply.py` 负责点击 Apply 和判断成功：

- 定位目标文件行
- 点击 Apply 按钮
- 等待页面响应
- 优先检测 toast：
  - `Apply Para Success`
  - `Start Application`
- 如果没有 toast，再把按钮状态作为后备判断

### 3.6 `core/delete.py`

`delete.py` 负责删除非目标文件：

- 遍历表格行
- 保留需要的文件
- 删除其余文件
- 按需等待删除确认和后续刷新

### 3.7 `core/navigation.py`

`navigation.py` 负责菜单导航：

- 从主界面进入目标页面
- 处理多级菜单点击
- 兼容图标、部分匹配和文本匹配

---

## 4. 运行时的数据流

### 4.1 配置数据流

`config/settings.yaml` 被读取后，会被传递给：

- GUI 层：用于按钮文本、超时、界面尺寸
- `FlowRunner`：用于流程控制
- `core/` 模块：用于定位、等待、识别和验证

### 4.2 日志数据流

日志同时流向两处：

- GUI 窗口
- `logs/` 下按启动时间命名的 `.log` 文件

### 4.3 截图数据流

关键节点会输出到：

- `screenshots/`

验证码原图会额外输出到：

- `debug/captcha_samples/`

---

## 5. 状态机逻辑

程序采用状态机管理按钮和流程阶段：

- `idle`
- `starting`
- `logged_in`
- `download_upload_done`
- `south_comm_done`
- `calibration_done`
- `active_alarm_done`

### 状态切换原则

- Start：从 `idle` 进入新一轮流程
- Continue：在当前会话上继续执行后续任务
- End：关闭浏览器并回到 `idle`

---

## 6. 调试建议

- 看 `screenshots/` 的流程截图
- 看 `logs/` 的详细日志
- 必要时查看 `traces/`
- 如果验证码识别不稳定，先补样本，再微调分割参数

---

## 7. 性能与稳定性

当前优化重点：

1. 减少重复 DOM 查询
2. 避免过多固定等待
3. CAPTCHA 只尝试 1 次，优先保证流程稳定
4. Apply 成功优先看 toast，减少对按钮状态的依赖

---

## 8. 测试场景

### 正常流程

- 登录时自动识别验证码并保存样本
- 上传文件
- Apply 成功后继续删除和后续步骤

### 失败回退

- 验证码识别失败后进入人工输入
- Apply 未出现成功 toast 时再用后备检查
- 仍失败则记录日志并进入人工处理

---

## 9. 扩展建议

新增功能时优先：

- 复用 `core/` 中已有工具函数
- 将验证逻辑放入 `verify_*.py`
- 保持日志、截图和 trace 一致
- 对新的页面状态增加明确的状态命名和过渡条件
