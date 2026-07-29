# Troubleshooting

## 1. How to use this file

When something fails, start with the visible symptom, then follow the checks below in order:

1. Log file
2. Screenshot
3. Trace file
4. Relevant configuration in `settings.yaml`
5. Related code module

This document is written for handover and maintenance, so each section explains both the symptom and the likely fix.

---

## 2. Login finished, but the workflow did not continue

### What you will see

- Browser reaches the main page, but later steps do not start
- No upload, no Apply, or no navigation happens

### What to check

- Confirm the login really succeeded
- Confirm the page menu text still matches `settings.yaml`
- Confirm the browser page has finished loading and stabilizing
- Check whether the state machine is still in the expected state

### Files to inspect

- Latest log file under `logs/`
- Screenshot after login under `screenshots/`

### Related code

- `gui_app.py`
- `tasks/flow_task.py`
- `core/navigation.py`

---

## 3. Apply was not recognized as successful

### What you will see

- Apply was clicked, but the workflow still reports a warning or failure
- The Apply button may still look clickable

### Current success rule

Apply is considered successful when the page shows either of these toast messages:

- `Apply Para Success`
- `Start Application`

Button gray/disabled state is only a fallback signal.

### What to check

- Check whether the toast actually appeared on the page
- Check whether the toast text matches the value in `settings.yaml`
- Check whether the target file row is still present and visible
- Check whether the page is slow and needs a longer wait

### Files to inspect

- Latest log file under `logs/`
- Screenshot after Apply under `screenshots/`
- Trace file under `traces/`

### Related code

- `core/apply.py`
- `core/verify_apply.py`
- `tasks/flow_task.py`

---

## 4. CAPTCHA recognition failed

### What you will see

- Login reaches the CAPTCHA step, but auto recognition does not fill the value correctly
- The workflow may fall back to manual input

### What to check

- Confirm `login.auto_captcha` is enabled
- Confirm `login.manual_captcha` is not forcing manual mode
- Confirm there are enough samples in `debug/captcha_samples/`
- Confirm some samples are correctly labeled with `__正确验证码`
- Confirm the CAPTCHA style has not changed too much compared with the saved samples

### Files to inspect

- `debug/captcha_samples/`
- Latest log file under `logs/`
- CAPTCHA screenshot under `screenshots/`

### Related code

- `core/captcha_ocr.py`
- `core/auth.py`

### Maintenance action

If recognition quality drops, the first fix is usually to add more labeled samples rather than changing code.

---

## 5. Logs, screenshots, and traces

### Logs

Look at the newest timestamped `.log` file under `logs/`.

### Screenshots

Look under `screenshots/` for step-by-step visual evidence.

### Traces

Look under `traces/` for Playwright execution traces.

---

## 6. Configuration-related issues

If behavior is wrong but the code looks healthy, check `config/settings.yaml` first.

### Common areas

- `login.*` for login and CAPTCHA behavior
- `apply.*` for Apply button text and success toast text
- `navigation.*` for menu paths
- `timeouts.*` for wait and retry timing
- `files.*` for log, screenshot, and trace directories

---

## 7. Fast escalation checklist

If the issue is still unclear after the checks above, provide:

- The latest log file
- The relevant screenshot
- The trace file if available
- The exact `settings.yaml` values that affect the step
- The module name where the failure happened
