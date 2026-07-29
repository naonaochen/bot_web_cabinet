# Project Guide

This guide is written for handover and maintenance. It focuses on what the program does at runtime, why each setting matters, and what a maintainer should check when behavior changes.

## 1. How the program runs

The automation is organized as a stateful workflow. In practice it behaves like this:

1. Read configuration from `config/settings.yaml`
2. Start the browser and open the MES login page
3. Log in, including CAPTCHA handling when enabled
4. Wait for the main page to stabilize
5. Navigate to the working page, usually `Download/Upload`
6. Upload the configured files
7. Apply the target file
8. Confirm Apply success using page toast text
9. Delete files that should not remain
10. Continue with South Communication, Calibration, and Active Alarm as required
11. In Continue mode, reuse the current browser session instead of restarting from scratch

### Why this matters for maintenance

If the flow stops at a certain step, the first thing to check is not the browser itself, but the current state of the workflow, the latest log file, and the screenshot taken at the failed step. Most issues are caused by:

- page text changed
- selector changed
- timeout too short
- toast message wording changed
- CAPTCHA samples not matching the current image style

---

## 2. Apply success rule

Apply is considered successful when the page shows one of the following toast messages:

- `Apply Para Success`
- `Start Application`

The button becoming gray or disabled is only a fallback check.

### Maintenance note

If the page layout changes but the success toast remains the same, Apply logic will usually keep working. If the toast text changes, update `apply.success_toast_text` and `apply.started_toast_text` in `settings.yaml`.

---

## 3. CAPTCHA sample workflow

### 3.1 What happens during login

When CAPTCHA automation is enabled, the program:

1. Captures the CAPTCHA image from the page
2. Saves the raw image to `debug/captcha_samples/`
3. Tries recognition using the current template library
4. Fills the CAPTCHA input if a result is found
5. Falls back to manual input if recognition fails

### 3.2 Sample naming rule

Use this format for labeled samples:

```text
original_filename__correct_captcha.png
```

Example:

```text
captcha_20260722_155548_280271__8802.png
```

### 3.3 Why the sample directory matters

The sample directory is the main source of maintenance improvement for CAPTCHA recognition. If recognition accuracy drops, the fastest fix is usually to collect and label more samples from the current CAPTCHA style.

### 3.4 Recognition pipeline

```text
Raw image → OpenCV preprocessing → connected-component segmentation → 28×28 standardization → template matching
```

### Maintenance note

If recognition gets worse after a UI update, first compare:

- screenshot of the original CAPTCHA
- screenshot of the processed CAPTCHA
- the current sample library in `debug/captcha_samples/`

This usually tells you whether the problem is preprocessing, segmentation, or missing samples.

---

## 4. `settings.yaml` parameter guide

This section explains what each group of settings controls and what to change when a workflow issue appears.

### 4.1 Recommended documentation split

- `PROJECT_GUIDE.md`
  - Practical meaning of settings and how they affect the workflow.
- `DEVELOPER_GUIDE.md`
  - Code-path details: how the settings are used in the implementation.
- `QUICK_REFERENCE.md`
  - The few settings you usually change during normal work.
- `TROUBLESHOOTING.md`
  - What to inspect when a setting seems not to work.

### 4.2 `app`

These settings define how the browser connects to the MES system.

- `url`
  - Target MES login URL.
  - Change this when the environment or IP address changes.
- `headless`
  - Whether the browser window is visible.
  - Keep `false` for maintenance and debugging.
- `timeout_ms`
  - Global browser timeout.
  - Increase this if the environment is slow.
- `browser`
  - Browser engine name.
- `browser_channel`
  - Browser channel, usually `chrome`.

### 4.3 `login`

These settings control the login form, CAPTCHA behavior, and success detection.

- `username` / `password`
  - Login credentials.
- `login_type`
  - Login mode shown on the page.
- `captcha_value`
  - Manual fallback value.
- `username_placeholder` / `password_placeholder` / `captcha_placeholder`
  - Text used to locate the inputs.
- `login_button_name`
  - Text of the login button.
- `login_type_selector`
  - Selector for the login type control.
- `success_url_fragment`
  - URL fragment used to confirm login success.
- `success_texts`
  - Page texts that can also indicate success.
- `manual_captcha`
  - Force manual CAPTCHA entry.
- `auto_captcha`
  - Enable automatic CAPTCHA recognition.
- `captcha_confidence_threshold`
  - Confidence threshold used when deciding whether to accept a result early.
- `captcha_early_accept`
  - Whether the program may accept a result before all fallback checks finish.
- `captcha_min_length`
  - Minimum accepted CAPTCHA length.
- `captcha_max_attempts`
  - How many recognition attempts are allowed.
- `captcha_retry_delay_ms`
  - Delay between attempts.

### Maintenance note

If login works manually but not automatically, check `auto_captcha`, the current sample library, and the page selector texts first.

### 4.4 `ui`

These settings affect the GUI look and timing, not the MES business logic itself.

- `page_zoom_percent`
  - Browser zoom level.
- `initial_width` / `initial_height`
  - Initial GUI size.
- `min_width` / `min_height`
  - Minimum GUI size.
- `loading_wait_ms`
  - Wait after page load.
- `upload_gap_ms`
  - Delay between upload actions.
- `apply_processing_wait_ms`
  - Wait after clicking Apply.
- `south_comm_ready_wait_ms`
  - Wait before South Communication steps.
- `active_alarm_nav_wait_ms`
  - Wait before navigating to Active Alarm.
- `continue_stage_nav_wait_ms`
  - Wait before Continue-stage navigation.
- `delete_confirm_wait_ms`
  - Wait for delete confirmation.
- `delete_between_rows_wait_ms`
  - Delay between deleting rows.
- `initial_x` / `initial_y`
  - Initial window position.
- `start_shrink_width` / `start_shrink_height`
  - Window size after auto-start shrink.
- `start_shrink_x` / `start_shrink_y`
  - Window position after auto-start shrink.
- `start_alpha`
  - Transparency during active workflow.
- `idle_alpha`
  - Transparency while idle.
- `toast_close_wait_ms`
  - Pause after closing a toast.
- `toast_settle_wait_ms`
  - Pause for toast animations.
- `dialog_settle_wait_ms`
  - Pause for dialog animations.
- `start_flow_delay_ms`
  - Delay before the workflow begins.
- `restore_banner_delay_ms`
  - Delay before restoring the banner state.
- `state_poll_interval_ms`
  - Poll interval for the UI state machine.
- `continue_wait_poll_ms`
  - Poll interval used in Continue mode.
- `closing_wait_timeout_s`
  - Timeout for closing actions.

### 4.5 `navigation`

These settings determine how page menus are found and clicked.

- `overview_menu_text`
  - Text used to find the overview area after login.
- `main_menu_texts`
  - Top-level menu labels that the navigation helper can search.
- `menus`
  - Common menu path items.
- `calibration_menu_path`
  - Path to the Calibration page.
- `active_alarm_menu_path`
  - Path to the Active Alarm page.
- `settings_menu_path`
  - Path to Setting → South Communication.
- `other_control_menu_path`
  - Path to Other Control.

### 4.6 `other_control`

These settings control the actions on the Other Control page.

- `controls`
  - List of control actions to execute.
- `yes_button_text`
  - Confirmation button text.
- `save_button_text`
  - Save button text.
- `row_selector`
  - Selector for the control table rows.
- `post_success_toast_cleanup`
  - Whether to clean up success toasts after a control completes.

### 4.7 `south_communication`

These settings control South Communication page editing.

- `device_type_select_label`
  - Label of the device type field.
- `device_type_value`
  - Target device type value.
- `target_row_fields`
  - Field values that identify the correct row.
- `port_select_label`
  - Label of the port field.
- `baud_rate_select_label`
  - Label of the baud rate field.
- `stop_bit_select_label`
  - Label of the stop bit field.
- `data_bit_select_label`
  - Label of the data bit field.
- `check_bit_select_label`
  - Label of the parity/check field.
- `save_button_text`
  - Save button text.
- `cancel_button_text`
  - Cancel button text.
- `delete_button_text`
  - Delete button text.
- `target_row_device_type`
  - Device type used to identify the row.

### 4.8 `calibration`

These settings control calibration reset timing.

- `reset_delay_ms`
  - Delay used during reset.
- `visible_progress_ms`
  - Delay used while progress is visible.
- `parameter_names`
  - Names of the calibration parameters to reset.

### 4.9 `timeouts`

These are runtime waiting limits.

- `login_wait_ms`
  - Wait after login-related actions.
- `captcha_timeout_s`
  - CAPTCHA recognition timeout.
- `captcha_check_interval_ms`
  - CAPTCHA polling interval.
- `apply_wait_ms`
  - Wait after Apply.
- `delete_verify_wait_ms`
  - Wait before checking delete results.
- `south_comm_wait_ms`
  - Wait for South Communication operations.
- `row_check_interval_ms`
  - Row polling interval.
- `browser_front_attempts`
  - Number of browser fronting attempts.
- `browser_front_interval_ms`
  - Delay between browser fronting attempts.
- `login_success_check_interval_ms`
  - Poll interval for login success checks.
- `login_success_max_checks`
  - Maximum number of login success checks.
- `login_final_wait_ms`
  - Final wait after login actions.
- `wait_timeout_ms`
  - Generic timeout value.
- `dialog_button_timeout_ms`
  - Timeout for dialog buttons.
- `success_message_timeout_ms`
  - Timeout for success messages.

### 4.10 `search`

These settings help locate table data.

- `result_row_selector`
  - Selector for result rows.
- `filename_column_index`
  - Column index used to read the file name.

### 4.11 `upload`

These settings control upload behavior.

- `add_button_text`
  - Text of the Add button.
- `file_input_selector`
  - Selector for the file input element.
- `success_message_text`
  - Upload success text, if used by the page.

### 4.12 `apply`

These settings control the Apply action.

- `target_file_name`
  - Default file to apply.
- `apply_button_text`
  - Text of the Apply button.
- `success_toast_text`
  - Primary success toast text.
- `started_toast_text`
  - Secondary toast text.
- `applied_button_state`
  - Expected button state used only as fallback.

### 4.13 `delete`

These settings control file deletion.

- `delete_button_text`
  - Text of the Delete button.
- `confirm_button_text`
  - Confirmation button text.
- `cancel_button_text`
  - Cancel button text.
- `success_message_text`
  - Delete success message text.

### 4.14 `flow`

These settings describe the files and extra sequence used by the workflow.

- `upload_files`
  - Files uploaded during the main flow.
- `apply_target_file`
  - Target file for the main Apply step.
- `continue_timeout_s`
  - Maximum time to wait for Continue.
- `continue_wait_poll_ms`
  - Continue polling interval.
- `closing_wait_timeout_s`
  - Timeout used when shutting down.
- `continue.download_upload_menu_path`
  - Continue-stage Download/Upload path.
- `continue.target_file`
  - Continue-stage target file.
- `continue.keep_only_file`
  - File to keep when cleaning up in Continue mode.
- `continue.apply_button_text`
  - Continue-stage Apply text.
- `continue.success_toast_text`
  - Continue-stage success toast text.
- `continue.delete_button_text`
  - Continue-stage Delete text.
- `continue.confirm_button_text`
  - Continue-stage confirmation text.
- `continue.other_control_menu_path`
  - Continue-stage Other Control menu path.

### 4.15 `files`

These settings define output and input directories.

- `input_excel`
  - Source Excel file.
- `screenshot_dir`
  - Screenshot output directory.
- `trace_dir`
  - Trace output directory.
- `log_dir`
  - Log output directory.

---

## 5. What a maintainer should check first

When behavior changes, check in this order:

1. `logs/` for the latest error sequence
2. `screenshots/` for the exact page state
3. `debug/captcha_samples/` if CAPTCHA is involved
4. `settings.yaml` for changed selectors or texts
5. `DEVELOPER_GUIDE.md` for code-path details

---

## 6. Why this document exists

This file is meant to answer the question:

> "What does this setting actually affect, and where should I look when it changes?"

If you need implementation details, go to `DEVELOPER_GUIDE.md`. If you need a quick reminder, go to `QUICK_REFERENCE.md`.
