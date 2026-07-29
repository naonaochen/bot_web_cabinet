# Architecture

## 系统分层

- UI 层：`gui_app.py` / `main.py`
- 应用层：`App`、`FlowRunner`
- 业务层：`core/` 与 `tasks/`
- 外部系统：MES 页面、文件系统、截图、日志

## 主要模块

- `browser.py`：浏览器启动与管理
- `auth.py`：登录与验证码流程
- `navigation.py`：页面导航
- `upload.py`：文件上传
- `apply.py`：Apply 操作和 toast 成功判断
- `delete.py`：文件清理
- `south_communication.py`：南向通信设置
- `calibration.py`：参数重置
- `verify_*.py`：验证逻辑
- `captcha_ocr.py`：验证码样本、OpenCV 分割、模板匹配

## 流程状态

典型状态：

- `idle`
- `starting`
- `logged_in`
- `download_upload_done`
- `south_comm_done`
- `calibration_done`
- `active_alarm_done`

Continue 模式在现有会话基础上继续执行后续任务。

## Apply 成功判定

Apply 成功以 toast 为准：

- `Apply Para Success`
- `Start Application`

按钮变灰只作为后备检查。

## 验证码流程

```text
截图验证码
→ 保存样本到 debug/captcha_samples/
→ OpenCV 预处理
→ 连通域/轮廓分割
→ 28×28 标准化
→ 模板匹配识别
```

## 日志与截图

- 日志：GUI 显示，同时写入 `logs/` 下的时间戳文件
- 截图：关键步骤写入 `screenshots/`
- Trace：必要时保存到 `traces/`
