---

name: Bug report
about: Report a problem with the Alarm.com Home Assistant integration
title: ""
labels: bug
assignees: ""
-------------

## Describe the issue

Provide a clear and concise description of the problem.

---

## Steps to reproduce

1. Go to ...
2. Click on ...
3. Perform action ...
4. Observe the issue

---

## Expected behavior

Describe what you expected to happen.

---

## Home Assistant Information

Home Assistant Version:

Integration Version:

Installation Method:
(HACS / Manual)

---

## Logs

Please include relevant Home Assistant logs.

To enable debug logging for this integration, add the following to your `configuration.yaml`:

```
logger:
  logs:
    custom_components.alarmdotcom: debug
```

Restart Home Assistant and reproduce the issue.

Attach the relevant logs from **Settings → System → Logs**.

After collecting logs you should remove debug logging.

---

## Additional context

Add any additional information, screenshots, or environment details that may help diagnose the issue.
