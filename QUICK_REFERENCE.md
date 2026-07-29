# Quick Reference

## 1. How to run it

```bash
python gui_app.py
python main.py
```

## 2. What matters most during maintenance

### Apply success rule

When checking whether Apply worked, trust the toast first:

- `Apply Para Success`
- `Start Application`

The Apply button turning gray or disabled is only a fallback signal.

### CAPTCHA samples

- Every login automatically saves the CAPTCHA image to `debug/captcha_samples/`
- Rename a sample as `原文件名__正确验证码.png`
- Example: `captcha_20260722_155548_280271__8802.png`
- Labeled samples are loaded into the template library automatically

### Logs

- Logs are visible in the GUI
- Logs are also written to timestamped `.log` files under `logs/`

## 3. Where to look first when something fails

1. Latest log file in `logs/`
2. Relevant screenshot in `screenshots/`
3. Trace file in `traces/`
4. CAPTCHA sample directory `debug/captcha_samples/`

## 4. Common paths

- `config/settings.yaml`
- `logs/`
- `screenshots/`
- `traces/`
- `debug/captcha_samples/`

## 5. Fast troubleshooting notes

### Apply did not turn gray

That is acceptable if the success toast already appeared.

### CAPTCHA recognition is unstable

Add more labeled samples to `debug/captcha_samples/`.

### Need to verify a parameter quickly

Check `PROJECT_GUIDE.md` for the meaning of each `settings.yaml` group, or `DEVELOPER_GUIDE.md` for how the code uses it.
