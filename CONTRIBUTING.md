# Contributing

Thank you for helping improve the Alarm.com integration for Home Assistant.

## Before starting

Search existing issues and pull requests to avoid duplicate work. For significant changes, open an issue first to discuss scope. Keep pull requests focused and explain the user-visible impact.

## Development

1. Fork the repository and create a descriptive feature or fix branch.
2. Follow the existing Python style and Home Assistant integration conventions.
3. Keep code readable, with comments where behavior is not obvious.
4. Add or update tests for behavior changes, especially authentication, MFA, polling, entities, and error handling.
5. Run relevant tests and lint checks available in the repository. State explicitly what you could not test.
6. Submit a pull request using the template, linking any related issues.

Do not modify release version numbers, release notes, or publish tags unless coordinated with the maintainer. Stable and beta releases are maintained separately.

## Bug reports

Use the bug report form and provide Home Assistant and integration versions, affected device or entity type, reproduction steps, expected and actual results, and **redacted** logs when available. Confirm whether the behavior occurs in the Alarm.com website or app, if relevant.

## Security and privacy

Follow [SECURITY.md](SECURITY.md). Never submit passwords, MFA codes, session cookies, tokens, account numbers, addresses, camera URLs, or raw diagnostic exports. Review all logs before sharing.

## Review

Maintainers may request changes, defer a feature, or close stale contributions. Be constructive and respectful, and avoid unrelated formatting changes in functional pull requests.
