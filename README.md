# Bot Web Cabinet

用于 MES Web Cabinet 配置操作的 Python + Playwright 自动化工具，提供 GUI 与 CLI 两种运行方式。

## 运行

### GUI

```bash
python gui_app.py
```

### CLI

```bash
python main.py
```

## 安装

```bash
pip install -r requirements.txt
playwright install chromium
```

## 主要功能

- 自动登录、验证码处理与人工回退
- 文件上传、Apply 和文件清理
- South Communication 设置
- 校准参数重置与告警页面导航
- Start / Continue / End GUI 工作流
- 关键步骤截图、Playwright trace 和日志记录

## 验证码样本

每次登录都会将验证码原图保存到：

```text
debug/captcha_samples/
```

人工确认正确答案后，将文件重命名为：

```text
原文件名__正确验证码.png
```

例如：

```text
captcha_20260722_155548_280271__8802.png
```

已标注样本会在后续运行时自动加入模板库。当前识别流程采用 OpenCV 预处理、连通域分割和模板匹配。

## Apply 成功判断

Apply 成功优先依据页面 toast：

- `Apply Para Success`
- `Start Application`

Apply 按钮是否变灰仅作为后备检查。

## 输出目录

- `logs/`：GUI 显示的日志同时写入按启动时间命名的 `.log` 文件。
- `screenshots/`：自动化过程截图。
- `traces/`：Playwright trace 文件。
- `debug/captcha_samples/`：验证码原始样本和已标注样本。

## 配置

编辑 `config/settings.yaml` 可配置：

- MES 地址和登录信息
- 上传/Apply 目标文件
- 菜单路径与页面元素文本
- 超时参数
- CAPTCHA 行为
- 日志、截图和 trace 目录

## 文档

- `PROJECT_GUIDE.md`：业务、验证码、配置和运行细节汇总。
- `QUICK_REFERENCE.md`：日常操作速查。
- `DEVELOPER_GUIDE.md`：开发和流程说明。
- `ARCHITECTURE.md`：系统架构和状态流程图。
- `TROUBLESHOOTING.md`：故障排查。

## 许可

仅限内部使用。
