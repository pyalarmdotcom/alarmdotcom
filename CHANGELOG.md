# Development history and maintenance transition

**November 2026:** The original Alarm.com for Home Assistant integration is being actively revived. This modernization branch starts from the maintained v4 codebase developed by [@ibasebcast](https://github.com/ibasebcast) since March 2026, with the support of original maintainer [@elahd](https://github.com/elahd). We also thank [@uvjustin](https://github.com/uvjustin) for foundational development and all prior contributors.

**Status:** Stable release 2026.11.17 brings the maintained implementation to the original distribution. Check GitHub Releases for published builds. Earlier stable and beta tags remain unchanged.

**History preservation:** Every entry following this note is reproduced from the maintained project's CHANGELOG without removing any release notes or earlier records. Relative issue and PR numbers in those development entries refer to [ibasebcast/ha-alarmdotcom](https://github.com/ibasebcast/ha-alarmdotcom/issues), unless a full repository is specified. The original project's earlier history and MIT notices are preserved in its Git commits and license files.

---

## Unreleased

- Credit kjjohnsen's earlier Alarm.com WebRTC card implementation in the README and both card sources. Its first public commit was February 14, 2026; this project's initial card commit was March 20, 2026.
- Retain `Copyright (c) 2026 kjjohnsen` and the complete MIT notice in both distributed card files. This is an attribution update with no camera behavior changes.

See [next-release notes](release-notes/unreleased.md).

## 2026.11.17 (stable)

- Prepare the maintained implementation for the original distribution's stable channel.
- Combine the original README structure, screenshots and credits with current device support, feature examples, upgrade instructions and known issues.
- Align the configuration flow schema with its existing version-5 migration and add migration/reload regression checks.
- Add HA Core 2026.11.2 compatibility validation and master-branch package/card checks.
- Preserve original history, license notices, existing independent-distribution update paths, and published beta tags.
- Direct live v3 upgrades remain unverified; see backup and known-issue guidance in the README.

See [release notes](release-notes/2026.11.17.md).

## 2026.11.16b1 (upstream modernization beta)

- Prepared the maintained v4-derived implementation for voluntary compatibility testing in the original `pyalarmdotcom/alarmdotcom` repository.
- Restored the original repository's familiar header and live development badges, updated the donation link to support current maintenance at https://buymeacoffee.com/ibasebcast, and retained thanks to Elhad Bar-Shai, Justin Wong (@uvjustin), and other contributors.
- Preserved the full earlier maintained-development history below, as well as original upstream licensing.
- Validation workflows now run on the modernization branch, with final Home Assistant 2026.11.x compatibility checks. A prerelease requires deliberate publication, not a branch push.
- **Community testing:** This is an opt-in prerelease, not a stable rollout. Existing v3 installations, device/entity identities, and automations still need real-world upgrade testing. Please report findings in [original project issue #567](https://github.com/pyalarmdotcom/alarmdotcom/issues/567).

---

## 2026.11.15 (stable)

- Add opt-in debug logging for camera analytics event types and recognized object classes (#195).
- Document how to check live video for SkyBell doorbells such as the ADC-VDB105 (#190).

See [release notes](release-notes/2026.11.15.md).

## 2026.11.14 (stable)

- Log the action that stopped the WebSocket client to help diagnose unexpected disconnects (#176).
- Recheck discovered water valves when the WebSocket first connects so an updated reading can reach Home Assistant before the next scheduled poll (#189).
- Document how to diagnose gray live video using the bundled WebRTC card (#190).

See [release notes](release-notes/2026.11.14.md).

## 2026.11.12 (stable)

- Identify WebSocket token-fetch, handshake, and event-stream failures in debug logs, with elapsed time and exception type (#176).
- Document how to read battery diagnostics when Alarm.com supplies a status or trouble flag instead of a percentage (#184).

See [release notes](release-notes/2026.11.12.md).

## 2026.11.10 (stable)

- Show a dedicated authenticator-app code form with instructions for finding the code (#184).
- Document where to configure silent arming and how to switch HACS repository ownership while keeping the Home Assistant entry (#183, #185).

See [release notes](release-notes/2026.11.10.md).

## 2026.11.09 (stable)

- Restore endToEnd camera preference by default and offer Janus through integration options (#177, #172).
- Preserve retry counts through brief stream connections and card reparenting; add a rolling recovery cap for kiosk use (#177).
- Fetch advertised water valves directly when catalog resources are absent; preserve unknown valve state (#178).
- Audit stable OTP delivery requests and resend behavior with focused tests and add setup troubleshooting guidance.

See [release notes](release-notes/2026.11.09.md). Experimental beta login and arming changes remain excluded.

## 2026.11.06 (stable)

- Prefer advertised Janus camera streams when both transports are available (#172, #106).
- Synchronize camera anti-forgery headers with the shared session cookie before API requests, avoiding a stale-key source of unnecessary authentication failures (#156).
- Remove expired trouble-condition records after a successful refresh, preventing repeated missing-resource warnings and retained condition counts (#173).

See [release notes](release-notes/2026.11.06.md) for validation and remaining investigations.

## 2026.11.04.3 (stable)

Roll back the experimental sign-in and setup changes for #157, retain the other stability and access-control fixes, and reorganize the README. See [release notes](release-notes/2026.11.04.3.md).

## 2026.11.04.2 (stable)

Bound sign-in reads, fall back between identity lookup URLs, and let setup proceed to MFA when optional dealer metadata is unavailable (#157). See [release notes](release-notes/2026.11.04.2.md).

## 2026.11.04.1 (stable)

Show the failing sign-in step in the default Home Assistant setup warning (#157). See [release notes](release-notes/2026.11.04.1.md).

## 2026.11.04 (stable)

- Handle missing session preferences and defer full device discovery until config entry startup. Record safe timing and failure details during setup (#157).
- Show unavailable states during failed authentication refreshes and bound panel commands (#162).
- Require administrator access for temporary schedule writes and redact camera network details and raw events from diagnostics.

See [release notes](release-notes/2026.11.04.md).

## 2026.11.01

Camera reconnect recovery and signed snapshots; SMS/email code resend; temporary-access confirmation correction and read-only schedule action; README install buttons and login-permissions guidance. See [test notes](release-notes/2026.11.01.md). Live validation across camera models and credential provisioning remains in progress.

## 2026.10.30b1 (beta)

- Add count-only raw-versus-parsed light-discovery diagnostics for #115, including numeric system-ID and metadata-count normalization. Discovery behavior is unchanged; this is not a confirmed fix.
- Apply live thermostat ambient-temperature events and display the forwarded/effective temperature when available, preserving paired averages until the coalesced API refresh confirms them.
- Add `alarmdotcom.set_temporary_access` for existing users, with explicit account/system routing, timezone-aware date validation, fresh PIN-preserving updates, and server-response verification (#108).
- Keep weekly schedules, access plans, user creation, and schedule clearing outside the initial temporary-access action.
- Add focused #115 testing instructions and synthetic regression coverage. Extend independent November compatibility checks to 2026.11.0b1 as well as b0.
- Align manifest/library versions and prepare tag-driven prerelease packaging with `alarmdotcom.zip` and version-specific notes. Published b0 remains unchanged.

## 2026.10.30b0 (beta)

- Keep HTTP session keep-alive running after a WebSocket reconnect; cap reconnect waits and token fetch time.
- Harden login repair with a timeout, shared failure results, backoff, and correct separation of outages, rejected credentials, and unsupported endpoints.
- Isolate failed event subscribers, including asynchronous callbacks, and safely remove all entities of a genuinely deleted device.
- Reconcile device state after connection changes and quick open/close events; keep older polling responses from overwriting newer WebSocket state.
- Require three consecutive missing refreshes before removing a device, including when the last device disappears; reset the count when it returns.
- Choose a supported thermostat fan duration, preserving indefinite operation only where the thermostat supports it.
- Add Scene 001/002 event entities and device automation triggers for supported Z-Wave switch taps, multiple taps, holds, and releases.
- Expose RGB and relative white color-temperature controls on capable lights, preserving brightness, device metadata, and existing light IDs.
- Add ten-second person, vehicle, animal, and package detection pulses from supported camera analytics. Repeated detections extend the pulse.
- Add camera fullscreen controls and preserve live streams through brief Lovelace reparenting during phone rotation. Guard late callbacks against replacing newer streams.
- Preserve authenticated WebSocket delivery of camera credentials and the existing policy of omitting HTTP payloads from logs.

Adapted from SeloraHomes, obrint, scottm5443, HA-ADC/alarmdotcom-ha, and HA-ADC/pyadc. See the beta release notes for attribution and hardware testing limitations.

## 2026.10.28 (stable)

Changes since stable 2026.10.26, including beta builds 2026.10.28b0 through b3.

### Sensor events and WebSocket reliability
- Replay Alarm.com's combined quick open/close events (EventType 100) as a two-second contact/motion pulse so history and automations can observe them (#142, #94).
- Cancel a pending pulse when a newer event arrives, and avoid overwriting a newer API refresh. Preserve the existing glass-break restoral handling (#111).
- Rotate WebSocket sessions before token expiry and limit connection handshakes to 10 seconds to reduce gaps in live sensor updates (#94).
- Expand the recent WebSocket diagnostic history from 25 to 500 frames for troubleshooting. Review diagnostic exports before sharing; they can contain sensitive account and location information.

### Home Assistant compatibility
- Fix climate-platform loading by importing UnitOfTemperature from homeassistant.const, including accounts with no thermostats.
- Support November's DeviceInfo dataclass using separately typed constructor arguments. Preserve device identifiers, manufacturer/model information, MAC connections, and valid parent links; omit unresolved parents.
- Use Probatio configuration, service, and WebSocket schemas when available, with a Voluptuous fallback for older installations.
- Use the native-temperature climate API for initialization and live updates. Preserve the older temperature API with cached-property invalidation on earlier Home Assistant releases, including Celsius/Fahrenheit units and single/range setpoints.
- Verify that hub shutdown unloads platforms once; no duplicate unload call is added.

### Camera behavior and credential protection
- Throttle missing-stream warnings to at most once per 30 minutes per camera, resetting the throttle after a successful stream response. Cameras that are not installed or online may legitimately return no stream.
- Improve missing-stream diagnostics with field names and credential-presence indicators rather than credential values.
- Remove stream-response payload dumps entirely, including from the opt-in response logger, so unknown future credential fields cannot leak through that dump.
- Remove request URLs from custom API logs/errors and suppress payload-bearing parser tracebacks. Preserve b2/b3's token-free camera entity state and permission-checked WebSocket credential delivery.
- Add regression coverage for actual HTTP-wrapper password/OTP/cookie/MFA handling and allowed/denied camera credential access.

### Light discovery
- Avoid warnings for normal accounts with no lights (#139); retain discovery details at debug level.
- Use nonempty IDs in the active system's named lights relationship without rejecting them solely because a provider uses a different resource type label (#115).
- Keep encoded ID-scoped requests and exclude unrelated relationships. Add a privacy-safe parsed light-entry count and regression coverage from system-detail deserialization through scoped requests.

### Validation, release metadata, and documentation
- Run the complete suite against Home Assistant 2026.10.4, with matched test-helper versions and the camera test dependency installed.
- Add independent compatibility checks against actual Home Assistant 2026.11.0b0 APIs because the published full-suite helper still targets October. Type-check the integration against November's beta APIs.
- Add a regression test requiring the integration manifest and bundled library version to match.
- Update installation/release guidance, HACS review status, bundled camera-card and snapshot documentation, and device-dependent sensor event reporting.

### Known limitations
- Missing Z-Wave lights on some accounts (#115) remain unconfirmed: the published response structure parses locally, and a provider type-label mismatch is only a candidate explanation. Keep the issue open until the reporter verifies all expected installed lights.
- Home Assistant 2026.11 compatibility is checked against 2026.11.0b0, not a final November release; later upstream changes may require follow-up.
- Camera snapshots depend on device/account support. Live playback requires an installed, online camera and the bundled custom card.

## 2026.10.28b3 (beta)

### Light discovery (#115)
- Use nonempty device IDs advertised by the active system's named `lights` relationship without discarding them because of a differing resource type label.
- Keep the ID-scoped `ids[]` request and exclude IDs from unrelated relationships.
- Add the parsed lights-relationship entry count to diagnostic messages without logging IDs, credentials, or response payloads.
- Add regression tests for canonical and alternate type labels, following system-detail deserialization through the scoped four-light discovery request.

### Status and testing
- Candidate fix only: the reported JSON structure parses correctly in local reproduction, so a type-label mismatch is not yet confirmed as the cause. Issue #115 remains open until the reporter confirms all four installed lights appear.
- Retains the Home Assistant 2026.11 compatibility and credential protections from b2.
- After installing b3, restart Home Assistant or reload Alarm.com and check for the expected light entities. If still missing, temporarily enable `_pyalarmdotcomajax: debug` and share only the `Light discovery:` lines, especially `lights relationship entries`. Disable debug logging afterward.

## 2026.10.28b2 (beta)

### Fixes
- Construct shared Home Assistant DeviceInfo metadata with keyword arguments instead of dictionary mutations for compatibility with Home Assistant 2026.11. Preserve existing device identifiers, manufacturer/model metadata, MAC connections, and resolved parent-device links.
- Reduce repeated camera stream warnings: retain a warning on missing stream info at most once every 30 minutes per camera, and reset the warning after a successful stream response. Keep stream-response payloads out of logs at every level.

### Compatibility review
- Test against Home Assistant 2026.11.0b0 with a dedicated CI job using the beta's real core APIs, alongside the full 2026.10.4 suite. The published custom-component fixture package still targets October, so November runs focused compatibility tests independently of that fixture package.
- Use Probatio schemas for configuration, services, and WebSocket commands when available, with a Voluptuous fallback for older Home Assistant installations.
- Move thermostat initialization and push updates to the native-temperature attributes introduced in November, while retaining the legacy values on older releases. Cover Celsius/Fahrenheit units, temperatures, and single/range setpoints.
- Construct DeviceInfo from separately typed keyword arguments and omit unresolved parent links, supporting both the old TypedDict and November's dataclass without deprecated mapping mutations.
- Preserve the HACS security fixes. Remove stream-response payload dumps, request URLs from custom API errors/logs, and payload-bearing parser tracebacks; add credential and camera-permission regressions.
- Confirmed the climate UnitOfTemperature import fix from b1 remains in place.
- Verified platform unloading is already handled by AlarmHub.close(); no duplicate platform-unload call was added.
- Missing Z-Wave lights (#115) remain under investigation; this beta does not claim a discovery fix.

### Testing requested
- Reload the integration and restart Home Assistant 2026.11 beta; confirm panel, sensors, locks, and camera entities appear without device metadata errors.
- Confirm missing-stream camera warnings no longer repeat on every token refresh, and playback still recovers when stream data becomes available.
- Confirm existing devices retain their names and registry relationships after reload.

## 2026.10.28b1 (beta)

### Fixes
- Fix Home Assistant 2026.11 climate-platform setup failure by importing UnitOfTemperature from homeassistant.const (PR #143). This also prevents the climate import error from blocking the entire integration on accounts without thermostats.
- Fix remaining normal no-light discovery warning by lowering the unscoped fallback message to debug (#139).

### Testing feedback
- Quick open/close sensor events now register in beta b0 according to initial reporter testing (#142); the event pulse behavior is unchanged in this build.
- Missing Z-Wave lights remain unresolved (#115); no new light-discovery fix is claimed in this beta.

## 2026.10.28b0 (beta)

### Fixes and improvements
- Fix quick open/close sensor events (EventType 100) by publishing a cancellable two-second contact/motion pulse (#142, #94).
- Rotate WebSocket sessions before token expiry and bound connection handshakes to 10 seconds to reduce missed events (#94).
- Retain up to 500 recent WebSocket frames for troubleshooting; diagnostic exports may contain sensitive location information and should not be shared publicly without review.
- Avoid warnings for normal no-light accounts (#139); improve camera stream diagnostics without exposing credentials.
- Continue investigation of scoped Z-Wave light discovery (#115); not yet confirmed resolved.

## 2026.10.26 (stable)

### Security
- Removed sensitive request payloads from HTTP exception messages and prevented credentials from being logged in API requests.
- Redacted sensitive camera stream response tokens and TURN credentials from diagnostics; removed WebRTC credentials from camera entity attributes in favor of an authenticated, permission-checked WebSocket request.
- Added automated regression tests covering credential redaction in API error paths and camera stream responses.

### Improvements
- Bundled the WebRTC card with the integration and registered its Lovelace resource automatically for storage-mode dashboards; guarded against duplicate custom element registration.
- Preserved upstream MIT license notices alongside this fork's Apache-2.0 licensing.
- Avoided prepending vendored code to Python's import search path.
- Added privacy-safe diagnostics for missing Alarm.com lights.

### Known issues
- Missing Z-Wave lights on some providers (#115) are still being investigated; light discovery has not been confirmed fixed. Please provide feedback and redacted logs in the issue.
- Beta light discovery, sensor updates (#94), and garage-door reload changes (#136) still need real-world confirmation where applicable.

## 2026.10.25b1 (beta)

### Fixed
- Added privacy-safe diagnostics for the active-system light discovery lookup (#115), including whether the lights relationship is present and how many light IDs were found.
- Prevented duplicate registration errors when the bundled WebRTC card and an older manually installed card are both loaded.

### Testing requested
- Confirm light discovery diagnostic messages and whether previously missing lights appear (#115).
- Confirm WebRTC card loads without duplicate registration errors.

## 2026.10.25b0 (beta)

### Fixed
- Added a direct active-system detail lookup for light IDs when initial discovery omits them (#115).
- Reuses the existing safely encoded ID-scoped light request, avoiding unscoped endpoint restrictions.

### Testing requested
- Confirm lights missing under SuretyDIY and other providers now appear after restart or reload (#115).
- Continue regression testing of sensor updates (#94) and camera card playback.

## 2026.10.24b0 (beta)

### Fixes for validation
- Improved WebSocket reconnection state refresh for intermittent sensor updates (#94).
- Expanded light discovery using known device IDs and safely encoded scoped queries (#115).
- Improved garage-door entity registry cleanup on integration reload (#136).
- Added light-discovery regression tests.
- Corrected HACS packaging configuration to avoid a nonexistent release ZIP asset.

### Testing requested
- Confirm sensor state updates remain reliable after reconnects (#94).
- Confirm previously missing lights appear (#115).
- Confirm garage-door entities survive integration reloads (#136).
- Verify bundled WebRTC camera card loads without manually copying the JavaScript file.

These fixes are pending real-world validation; related issues remain open.

## 2026.10.23 (stable)

### Fixed
- Improved sensor state reconciliation after WebSocket reconnects (#94).
- Corrected glass-break detection when Alarm.com reports an explicit normal status alongside a stale activated state (#111).
- Accepted additional MFA permission values returned by Alarm.com (#133).
- Corrected the integration manifest version (#134).

### Improved
- Added direct light-discovery diagnostics to identify missing Alarm.com lighting devices (#115).

## 2026.10.19 (stable)

### Fixed
- Improved WebSocket reconnect and event processing resilience for intermittent sensor and panel updates (#94, #100, #114).
- Updated device registry handling and orphan cleanup for newer Home Assistant versions (#101, #109, #116).
- Fixed thermostat AUTO fan mode zero handling and combined heating/cooling setpoints (#99).
- Reduced routine authentication log noise and improved session recovery (#91).
- Preserved zero-valued arming options and corrected unsupported disarm option validation.
- Preserved explicit zero brightness for dimmable lights.
- Confirmed configurable camera token refresh is available in integration options (#93).

### Notes
- Issues requiring further Alarm.com account or device diagnostics remain open, including missing lights (#115), alternate force bypass (#95), and glass-break sensor state (#111).

## 2026.8.10.1b0 (beta)

### Fixed
- **Concurrent auth failures on the main `AlarmBridge` triggered independent, uncoordinated re-logins** (#90, #91) - each of several concurrent pollers hitting a 403 called `login()` on its own, and each `login()` reset `ajax_key`, invalidating whatever the previous one had just obtained. Confirmed by two independent reporters (ffumarola, davidfi01) as a self-sustaining storm: one reporter measured ~320 real logins against Alarm.com from a single network blip, enough to trip Alarm.com's own login-notification/lockout behavior; the other measured a 14-minute HA crash-restart cycle from the resulting asyncio transport teardown flood. Fixed with a lock + generation counter on `AlarmBridge`: a task that queues on the lock now checks whether another task already repaired the session before it got there, and skips its own login if so (davidfi01's design). `#91`'s "logging too frequently" report is almost certainly this same storm, not a separate bug.
- **`AuthenticationFailed` discarded its own message** (`exceptions.py`) - `super().__init__()` dropped `*args` entirely, so every traceback ended in a bare exception with no detail, and 401 ("logged out") vs 403 ("invalid anti-forgery") - two completely different problems routed through the same error-mapping branch - were indistinguishable without it. This one blocked diagnosis of everything else in this release; fixed first.
- **`afg` (anti-forgery) cookie never fell back to the session cookie jar** the way the MFA cookie already did (`__init__.py`) - aiohttp only exposes the last hop's `Set-Cookie` headers on `resp.cookies` when a request follows a redirect chain, so a stale `afg`/`ajax_key` could persist and get rejected by the server as `403 Invalid Anti Forgery`. Mirrors the existing MFA cookie handling. Reduces 403 frequency; does not eliminate it alone (confirmed by ffumarola's own before/after measurement) - needed alongside the login-storm fix above, not instead of it.
- **`AlarmBridge.close()` left the bridge unusable** - it closed the underlying `aiohttp.ClientSession` but never cleared `_websession`/`_initialized`, so `hub.py`'s reconnect path (`close()` then `initialize()`) silently no-opped on the `if self._initialized: return` guard, and every subsequent request tried to reuse an already-closed session.
- **4 simultaneous real Alarm.com logins every ~30 minutes** (#89) - a separate, previously-unaffected auth path from the fixes above. All camera entities on a config entry share one `AlarmCameraSession` (extracted from the bridge's own HTTP session), but each schedules its *own* independent 30-minute WebRTC token-refresh timer starting at entity setup, so the timers fire in near-lockstep. When the shared session aged out, every camera hit 401/403 at once and, with no coordination, each independently created and logged into its own brand-new replacement session. Added `AlarmCameraSession.repair_shared_session()` (same lock + generation pattern as the `AlarmBridge` fix): the first camera to fail performs the real login and caches the replacement session; every other camera on that generation adopts the cached replacement instead of creating its own.
- **A failed camera-list re-login attempt during setup could take down entity setup for the whole config entry** (#90, reported separately as "camera platform setup fails with 403 and blocks the integration") - `camera.py`'s `async_setup_entry` retried a failed camera-list fetch with a re-login, but the retry itself had no exception handling, so if the re-login *also* failed (as in the original report's traceback), the exception propagated unhandled out of platform setup instead of being caught and logged. Now wrapped so a persistent camera-specific auth failure - including on accounts with no cameras configured - can't block the rest of the integration's entities.
- **Inverted debug-logging condition** (`_pyalarmdotcomajax/__init__.py`, `websocket/client.py`) - `if log.level < logging.DEBUG` is backwards: `log.level` defaults to `0` (`NOTSET`), and `0 < 10` is `True`, so full unredacted request/response dumps were emitted *by default*, and explicitly turning DEBUG logging on actually silenced them. Fixed to `log.isEnabledFor(logging.DEBUG)`. Likely a contributing factor in #91's log volume independent of the auth storm itself.

### Under the hood
- `ruff`/`mypy` both clean on every file touched in this release - the handful of pre-existing warnings elsewhere (a duplicate `__all__` entry, one `None | X` ordering nit, a positional-argument-count lint on `AlarmCameraSession.__init__`, three `no-any-return` mypy notes in `auto_off.py`/`activity_history.py`/`camera.py`) all predate this release and weren't touched.
- **No new automated tests were added to `tests/` in this release** - the auth-storm and camera-session fixes were verified with standalone async simulations exercising the lock/generation-counter logic in isolation (concurrent-failure collapse, single-login convergence), not against the real 106-test suite, which needs Python 3.14.2/`homeassistant` and could not be run in the environment this beta was prepared in. **Run `pytest` locally against this beta before tagging**, and real regression tests for `AlarmBridge`'s and `AlarmCameraSession`'s single-flight repair logic (e.g. mocking concurrent 401/403s and asserting exactly one login call) should be added before this graduates past beta.

## 2026.7.14.6b0 (beta)

### Added
- **`PARALLEL_UPDATES = 0` added to all ten platform files** (alarm_control_panel, binary_sensor, button, camera, climate, cover, light, lock, sensor, valve) - the correct, explicit signal for a push-based (websocket) integration, previously unset entirely.
- **A "Removal" section in the README**, covering both the config-entry removal and cleaning up the WebRTC Lovelace card if one was added.
- **`quality_scale.yaml` re-audited against the real current state of the repo** - a genuinely stale bookkeeping gap, not new functionality: 15 items previously marked `todo` (docs-actions, docs-high-level-description, docs-installation-instructions, docs-removal-instructions, docs-configuration-parameters, docs-installation-parameters, docs-data-update, docs-examples, docs-known-limitations, docs-supported-devices, docs-supported-functions, docs-use-cases, plus parallel-updates above) were already satisfied by documentation and code from earlier in this same beta cycle and are now marked `done` with accurate comments pointing at what satisfies each. `test-coverage`'s comment was flatly wrong (written when the suite had ~35 tests covering only setup/unload; it's 106 now, covering nearly every feature shipped this cycle) and has been rewritten to reflect what's actually covered and what still genuinely isn't (the platform entity classes themselves, and hub.py's websocket reconnect logic).
- **New `last_unlock_method` attribute on lock entities** (`keypad`/`manual`/`remote`), in direct response to real user feedback on GitHub issue #79. `last_unlocked_by` alone isn't reliable for gating an automation on "was this actually a keypad entry": not every unlock method generates its own loggable Alarm.com event for every lock model, so `last_unlocked_by` can remain stuck showing an earlier keypad user's name well after a different, unattributed unlock happens. `last_unlock_method` reflects whatever the most recently tracked unlock actually was, independent of that staleness - confirmed the underlying data already distinguishes this via `unlock_method=ManualUnlock`/`ZwaveUnlock` and `lockedByKeypad=true` in the same raw activity data this feature already parses, so no new endpoint or permission was needed.
- **Documented a real prerequisite discovered by a user**: the Alarm.com account used by this integration needs the "Activity" read-only permission enabled, or `last_unlocked_by`/`last_unlock_method`/`last_unlocked_at` never populate at all. Not documented anywhere by Alarm.com itself.

### Under the hood
- `ActivityFeedTracker`'s internal unlock-tracking storage moved from a positional `(name, timestamp)` tuple to a `LockUnlockRecord` TypedDict (matching `RecentActivityEntry`'s existing convention) now that it carries three fields - avoids fragile positional unpacking as this keeps growing.
- 5 new tests covering `unlock_method` directly (keypad/manual/remote/unknown, and confirming it's derived independently of `unlocked_by_name` rather than one implying the other), plus 4 existing tests updated for the new `LockUnlockRecord` shape - 106 total, `mypy`/`ruff` both clean.

## 2026.7.14.5b0 (beta)

### Added
- **Garage door open/close now appears in the activity feed**, resolving the disambiguation problem flagged when the activity feed first shipped (`2026.7.14.4b0`): Alarm.com's activity data uses the same event type for a garage door as for an ordinary window/door sensor, so the two couldn't be told apart by event type alone. Resolved the same way lock unlock attribution already does - cross-referencing the event's device ID against this account's actual known garage door resources (`hub.api.garage_doors`, the same controller the garage door cover entity is built from), rather than guessing from the event data alone. Ordinary window/door sensors remain correctly excluded, since their device IDs never match.
- 4 new tests covering the disambiguation directly - a known garage door event is included, an ordinary sensor sharing the same event type is excluded, the event lands in the recent-activity list, and an account with no garage doors configured correctly matches nothing. 101 tests total, `mypy`/`ruff` both clean.

## 2026.7.14.4b0 (beta)

### Added
- **A general activity feed** (extends the polling infrastructure originally built for #79). `LockActivityTracker` is renamed `ActivityFeedTracker` and now, alongside lock unlock attribution, fires a curated `alarmdotcom_activity` event on Home Assistant's event bus for other significant activity - system armed/disarmed, lock/unlock, and camera motion triggers - plus a new **"Recent Activity"** sensor with a short rolling history attribute. Built on the same poller and poll cycle as lock unlock attribution - no additional requests against the undocumented endpoint.
  - The curated allow-list is a deliberate, documented choice, not a claim of completeness: real captured data showed noisy event types (paired light on/off command+state events, constant motion/button-press events) that add little automation value since Alarm.com doesn't attribute any of them to a user either. Garage door open/close is deliberately excluded for now - Alarm.com's activity data doesn't reliably distinguish a garage door from an ordinary window/door sensor by event type alone.
- **Configurable polling intervals.** The options flow gained a third step: both the activity poll interval (default 15s) and the full-state safety-net poll interval (default 5min, previously a hardcoded constant in `hub.py`) can now be tuned via **Configure**, rather than requiring a code change. Existing users get the same defaults automatically; changing either triggers the existing config-entry reload, no extra plumbing needed.

### Under the hood
- `ActivityFeedTracker` gained `get_recent_activity()` and a `RecentActivityEntry` shape alongside its existing lock-attribution and listener-notification mechanisms.
- 13 new tests covering the curated feed (bus event firing, the recent-activity rolling list and its bounded length, non-curated events correctly excluded) and the configurable interval (reading a configured value, falling back to the default) - 97 total, `mypy`/`ruff` both clean.

## 2026.7.14.3b0 (beta)

### Fixed
- **`bypass_sensor`/`unbypass_sensor` crashed with `'PartitionController' object has no attribute 'values'`** whenever called without an explicit `partition_id` (GitHub issue #80) - the auto-resolve-partition-from-sensor path incorrectly treated `hub.api.partitions` as dict-like. It isn't: like every other controller in this integration, it's iterable directly. `alarm_control_panel.py` already did this correctly; `__init__.py`'s bypass handler was simply missed when that convention was established.
  - There was previously zero test coverage for either service at all, which is exactly how this shipped unnoticed. Added 6 regression tests, deliberately using a real list subclass (not a dict, not a permissive mock) to stand in for the partition controller - a mock that happened to support `.values()` would have defeated the entire point of testing this. Confirmed these tests actually catch the reported bug by temporarily reintroducing it and watching the test fail, before re-fixing it.

## 2026.7.14.2b0 (beta)

### Changed
- **Lock activity poll interval reduced from 60 seconds to 15 seconds** (follow-up to #79), for a faster welcome-home automation response. A deliberate tradeoff, not a free improvement: this is 4x the request volume against an entirely undocumented endpoint with no confirmed rate-limit information. Reasonable given the web app's own request carries `debounceTimeMs=1000` (suggesting the endpoint tolerates fairly frequent calls), but that's an inference from one observed request, not a guarantee - worth reverting toward 60s if this ever causes problems.

### Added
- **Lock activity polling now logs meaningfully**, closing a real gap from `2026.7.14.1b0`: previously only a *failed* poll produced any log output, so there was no way to confirm the poller was working short of a live unlock test.
  - A real new unlock now logs at INFO level (e.g. "Lock activity: 110353471-1201 unlocked (attributed to: Chris Pulliam)") - deliberately INFO, not debug, since it only fires on an actual new unlock rather than every 15-second poll, so it's a genuine confirmation signal rather than log noise.
  - Every poll additionally logs a DEBUG-level summary (events fetched, how many matched a known lock, the time window covered) - not useful at normal log levels, but confirms the poller is alive and fetching successfully once debug logging is turned on to investigate something.
  - Covered by 2 new tests confirming the INFO line fires on real new attribution and stays silent otherwise.

## 2026.7.14.1b0 (beta)

### Added
- **New: `last_unlocked_by` / `last_unlocked_at` attributes on lock entities**, addressing GitHub issue #79 - a welcome-home automation (custom TTS depending on who unlocked the door) is now genuinely possible for keypad-code unlocks.
  - Built on top of an entirely undocumented Alarm.com endpoint (`activity/activityDays`), reverse-engineered from the Alarm.com web app's own Activity page network traffic rather than guessed - confirmed working against real captured request/response data before any code was written, including the specific distinction that matters here: Alarm.com attributes a keypad-code unlock to a real name, but does *not* attribute a web/app-session or manual unlock to anyone - both of those correctly show as unattributed (`None`), not a parsing gap.
  - This required a genuinely new architecture within the vendored library: `AlarmBridge.get_activity_history()`, the first data source in this integration that has no persistent state and never arrives over the live websocket stream - it has to be actively polled. A new `LockActivityTracker` handles this on its own 60-second interval, independent of the existing 5-minute full-state refresh.
  - Lights and switches are deliberately not covered - confirmed (not guessed) that Alarm.com's own system does not attribute those to a specific user at all, only that a device was turned on.
  - Covered by 22 new tests across the model, the fetch method, and the tracker's polling/filtering/deduplication logic - including a real regression test using the actual data captured from the issue's investigation.

## 2026.7.9.5b0 (beta)

### Added
- **New: "Active Auto-Off Timers" sensor**, showing how many auto-off timers (from `2026.7.9.4b0`'s `set_auto_off` service) are currently pending, account-wide, with a `timers` attribute listing each affected light's friendly name and scheduled off-time.
  - Same account-wide singleton pattern as the existing battery summary sensors, but reacting to a genuinely different source of change: `AutoOffManager` gained its own listener mechanism (`add_listener`/`get_all_active`), since a timer being set or cancelled via a service call isn't an Alarm.com resource event at all - the existing `hub.api.subscribe` mechanism the battery sensors use would never see it.
  - Updates live: setting, cancelling, or a timer actually firing all notify this sensor immediately, not just on the next reload.
  - Covered by `tests/test_sensor_active_auto_off_timers.py`, including a dedicated test that the sensor's state actually changes in response to a live notification, not just at construction time.

## 2026.7.9.4b0 (beta)

### Added
- **New: auto-off timers for lights**, via two new services - `alarmdotcom.set_auto_off` and `alarmdotcom.cancel_auto_off`. Target any Alarm.com light entity (or several at once, using the standard entity target picker) and a duration; the light turns off automatically once that duration elapses.
  - Deliberately more than a plain "wait then turn off" automation can do on its own: the scheduled off-time is persisted, so it **survives a Home Assistant restart** - a timer that was already due while Home Assistant was offline fires immediately on startup, and one still pending is rescheduled for its remaining time rather than being lost. The scheduled off-time is also exposed as an `auto_off_at` attribute directly on the light entity, so "time remaining" is available to templates and other automations without a separate helper entity.
  - If a light is turned off some other way before its timer fires - manually, from the Alarm.com app, from an unrelated automation - the timer is automatically cleared rather than lingering with a stale `auto_off_at` attribute.
  - Checked first whether Alarm.com's own API supports this natively at the device level (which would be more robust still, working even through a Home Assistant outage) - it does not, at least not in what this integration currently models; this is a Home Assistant-side implementation.
  - Covered by `tests/test_auto_off.py`, including the two restart-survival scenarios (catch-up on a missed past time, reschedule on a still-pending future time) that are the actual point of this feature over a plain automation.

## 2026.7.9.3 (stable)

This release consolidates everything from the `2026.7.6.1b0` through `2026.7.9.3b0` beta cycle into a single stable release. Every item below has been verified either through the automated test suite, a clean `mypy`/`ruff`/CI run, or a real diagnostics download / log capture from a live account - the full beta-by-beta detail (including what didn't work on the first attempt) is preserved further down in this file for anyone who wants it.

### Security

- **Arm/disarm code was never actually validated.** The most important fix in this release: entering *any* correctly-formatted code - not necessarily the one you configured - would successfully arm or disarm through Home Assistant. Home Assistant's own code-format check only validates that an entered code *looks* right (numeric vs. text), not that it matches what's actually configured; this integration's own comparison was silently missing. Anyone relying on "require a code" to mean something was not actually protected by it. Fixed: an incorrect code now raises a validation error, matching how it always should have behaved. Covered by 4 new regression tests.

### Fixed

- **Two real, previously-unreported bugs found while adding test coverage**, both now covered by regression tests so they can't silently return:
  - Duplicate config entries were never prevented - the same Alarm.com system could be added a second time as a separate integration entry.
  - A crash-on-exhausted-reconnect bug in `hub.py`: after enough failed reconnect attempts, the recovery code itself would raise an error instead of successfully reloading.
- **Two long-standing camera/state bugs from `2026.7.6`**, carried forward from that release's own fixes:
  - Black screen specifically on iPhone/iPad/Safari when viewing a camera - an Apple decoder incompatibility with the WebRTC video codec profile Alarm.com's signaling sends by default.
  - State (arm/disarm, sensor changes, etc.) could silently stop updating in Home Assistant until a full integration reload, unrelated to "Smart Arming" despite how it presented - a periodic background refresh was silently failing after its first run.
- **Live camera credentials (session tokens, TURN server credentials) were being written to Home Assistant's logs** every 20-30 seconds per camera whenever debug logging was enabled at all. Now off by default regardless of general debug-logging state, opt-in only, and separately redacted wherever this data appears elsewhere (diagnostics, in particular - see below).
- Several smaller correctness fixes: an undefined-name bug in `lock.py` that only survived because of how Python defers type-annotation evaluation, and a handful of type-safety gaps only became visible once static type checking could run cleanly for the first time (see CI section).

### Added

- **A diagnostics page.** Home Assistant's native diagnostics platform is now implemented - a downloadable snapshot of everything the integration currently knows about your account or a specific device, available from **Settings → Devices & Services → Alarm.com → Download diagnostics**. All credentials and session tokens (including camera stream tokens) are redacted before the file is ever assembled, verified against a real download from a live account with real cameras.
- **Account-wide low/critical battery count sensors** (`Low Battery Count`, `Critical Battery Count`) - a running count of devices needing a battery change, with the specific device names listed as an attribute, so you don't have to check every individual sensor's battery status separately. These update live as device battery status changes, not just at startup.
- **A real, automated test suite**, run in CI on every push and pull request: config flow (every login/2FA/duplicate-entry path), setup/unload lifecycle, the arm-code validation fix, diagnostics (including the redaction itself), and the battery summary sensors.

### Changed / Architecture

- **The `pyalarmdotcomajax` Alarm.com API client is now vendored directly into this repository** (as `_pyalarmdotcomajax`, a deliberately collision-proof name - see the "Architecture Note" section of the README for the full rationale) instead of being installed from a separate repository via a `git+` dependency. This was previously a real HACS/hassfest compliance blocker and a source of duplicated bug reports across two repos for what users experienced as one integration. No functional behavior change is intended by this move on its own.
- Startup logging now confirms which copy of the vendored library loaded and warns if it's not the expected bundled copy (rather than silently continuing) - useful for confirming a clean install and diagnosing a rare leftover-package scenario from before this change.
- A handful of internal naming/encapsulation cleanups in `camera_api.py` with no behavior change (see the full `2026.7.8.1b0` entry below for specifics).

### Upcoming Home Assistant compatibility

- **Preemptively fixed a Home Assistant deprecation that becomes a hard error in December 2026** (using a config-entry update listener together with a reloading method in a config flow - Home Assistant's own reauth flow pattern). Confirmed against Home Assistant's real, current source before writing the fix, and confirmed via CI that it resolves correctly against the actual `homeassistant` version this integration targets.

### CI / Internal Quality

- **`mypy` now reports zero issues across the entire codebase** (previously silently broken - `pre-commit` never even completed a full run before this cycle, due to an unrelated Python-interpreter-discovery error masking everything downstream). Getting here surfaced several real, if minor, type-safety issues alongside the two real bugs mentioned above.
- `codespell`, `ruff`, `taplo`, and `yamllint` all pass cleanly; a genuinely flaky external network dependency in `taplo`'s config (an inline schema-fetch directive) was identified and removed.
- Full details on the mypy investigation, the three approaches that were tried and rejected before finding the real fix, and every individual fix along the way are preserved in the `2026.7.7.x`/`2026.7.8.1b0` entries below, for anyone who wants the complete story rather than the summary.

## 2026.7.9.3b0 (beta)

### Fixed
- **Preemptive fix for a Home Assistant deprecation that becomes a hard error in December 2026.** Home Assistant 2026.6 deprecated using a config-entry update listener together with any reloading method in a config flow, because the combination can trigger the same config entry to reload twice at once - a race condition, not just wasted work. Verified directly against `home-assistant/core`'s real source (not just the changelog): our reauth flow called `async_update_entry(data=...)` and then explicitly `async_reload()` right after - and `async_update_entry` itself schedules every registered update listener (we have one, in `hub.py`, registered for the options flow) as soon as *any* field changes, `data` included. So reauth was firing two reload paths for the same entry nearly simultaneously.
  - Fixed by switching the reauth path to `async_update_and_abort()` - confirmed via `home-assistant/core`'s actual `2026.7.1` source that this method updates the entry and aborts with no reload of its own, leaving the existing listener to do the one necessary reload. The options flow, which relies entirely on that same listener and never reloads explicitly itself, is unaffected and still correct.
  - **One thing worth verifying before this goes out**: this specific change couldn't be checked with `mypy` in the environment used to verify everything else this cycle - that environment is capped at an older Python version whose available `homeassistant` package predates this method entirely, so its `mypy` run reports a false `attr-defined` error on a method that provably exists in the real, current `homeassistant` release. Please confirm a clean `pre-commit run mypy` (which correctly pulls `homeassistant >= 2026.7.1`) before considering this fully verified.

## 2026.7.9.2b0 (beta)

### Added
- **New: account-wide low/critical battery count sensors** (`sensor.Low Battery Count`, `sensor.Critical Battery Count`). Unlike every other sensor in this integration, these are single, permanent entities per account rather than one per device - they recount and update live whenever any device's battery status changes, not just at startup. Each sensor's state is the count of matching devices; a `devices` attribute lists which ones by name, so you don't need to go hunting through every individual device's battery sensor to find out which one actually needs a new battery. Both attach to the account's System device. Covered by `tests/test_sensor_battery_summary.py`.

### Fixed
- **Diagnostics downloads were silently missing all camera data.** Found by inspecting an actual diagnostics download from a live account: `CameraController` showed `0 items` despite the account having real, working cameras, while every other controller (lights, locks, sensors, thermostat) showed correct real counts. Root cause: cameras aren't discovered through the standard `resource_controllers` system the rest of the integration uses - `camera.py` fetches them through a separate session (`AlarmCameraSession`) entirely, so the standard `CameraController` is never actually populated. `diagnostics.py` now pulls camera data from that real source: a summary list (`get_camera_list()`) plus per-camera stream/connectivity info (`get_stream_info()`) for both the whole-account and per-device diagnostics views.
  - `get_stream_info()`'s raw response includes live session tokens - the exact data already redacted for debug logging (see `2026.7.6.1b0`) - so this only went in because it flows through the same redaction as everything else in the diagnostics dump, not a separate, easier-to-miss path. Covered by a dedicated test asserting the tokens actually come back redacted, not just that the feature runs without error.
  - No camera session (e.g. camera login never completed) and a failed camera-list fetch are both reported as a clean status in the output rather than raising and breaking the rest of the diagnostics download.

## 2026.7.9.1b0 (beta)

### Added
- **New: a diagnostics page.** Home Assistant's native diagnostics platform is now implemented (`diagnostics.py`) - a downloadable snapshot of everything the integration currently knows, available from **Settings → Devices & Services → Alarm.com → Download diagnostics** (whole account) or from any individual device's own page (that device only).
  - The whole-account dump includes config entry data, connection/websocket health, and a raw JSON:API dump of every resource across every controller (locks, sensors, thermostats, cameras, partitions, everything) - the same raw data the per-sensor "Debug" button already logs one device at a time, but comprehensive and available as one file instead of digging through logs device-by-device.
  - The per-device version is the same data, filtered to just that device - useful for reporting an issue with one sensor without needing to share the whole account's data.
  - **All known-sensitive fields are redacted before the data is ever assembled** - credentials, session tokens, and specifically the live camera stream tokens (`proxyUrl`, `janusToken`, `signallingServerToken`, `cameraAuthToken`, TURN credentials) using the same sensitive-field list built for the camera logging fix earlier. Covered by `tests/test_diagnostics.py`, including explicit regression tests asserting these specific tokens come back redacted, not just that the feature runs without error.
  - This closes the `diagnostics` item in `quality_scale.yaml`, previously `todo`.

## 2026.7.8.1b0 (beta)

### Fixed
- **`hub.py`: a genuine, previously-undiscovered runtime bug in the "all reconnect attempts exhausted" path.** `async_schedule_reload()` is a synchronous `@callback` that returns `None` and already schedules its own task internally - it was being wrapped in `async_create_task()` anyway, which would raise `TypeError` immediately after the reload had already correctly fired as a side effect. This would have hit every time Alarm.com connectivity failed enough times to exhaust all reconnect attempts - a real, reachable error path, not a hypothetical. Fixed: call it directly.
- **Arm/disarm code was never actually validated** (found while clearing a pre-commit lint backlog, not previously reported - this is the most important fix in this release): `alarm_control_panel.py`'s `control_fn` computed both the configured arm code and the user-entered code, but never compared them. Home Assistant core's `_attr_code_arm_required`/`_attr_code_format` mechanism only validates that an entered code matches the expected *format* (numeric vs. text) before this function is even called - it does not check the code against what's actually configured. Net effect: **anyone could arm or disarm by entering any correctly-formatted code, not necessarily the one you configured** - the "require a code" option looked like it was enforcing something it wasn't. Fixed: entering the wrong (or no) code now raises a validation error instead of silently succeeding. Covered by 4 new tests in `tests/test_alarm_control_panel.py`, including a regression test that specifically fails against the old (unfixed) behavior.
- **`lock.py` referenced an undefined name** (`CodeFormat`, `F821`): never imported, only survived because `from __future__ import annotations` makes type annotations lazy. `alarm_control_panel.py` already imports this correctly from `homeassistant.components.alarm_control_panel`; `lock.py` was just missing the same import. Not a live runtime bug (annotations are never evaluated), but a real static-analysis gap - fixed.

### Changed
- **`camera_api.py`: `_get` renamed to `get`, and a proper `owns_session` property added.** Both were being accessed from outside `AlarmCameraSession` already (by `__init__.py` and `camera.py`), so the leading underscore was misleading rather than enforcing real encapsulation. No behavior change, just properly public names for what were already effectively public interfaces.
- **`camera_api.py`: the three silent `except Exception: continue` blocks in session/ajax-key/MFA-cookie candidate extraction now log at debug level** instead of swallowing failures with zero trace. Still tries the next candidate on any failure (unchanged behavior) - just no longer invisible when everything fails.
- **`__init__.py`: extracted the pyalarmdotcomajax-location diagnostic check into its own sync function**, since it's pure path-string manipulation with no real async/await need - was flagged as doing blocking-style calls inside an async function.
- Minor control-flow clarity fixes in `hub.py` (moving a success-path `return` into an `else` block; `contextlib.suppress` instead of `try/except/pass` for a cancellation) - no behavior change.
- Removed one genuinely unused variable in `binary_sensor.py`.

### CI / tooling
- **This is the release where `pre-commit` actually completes a full run for the first time** - every previous run died at a Python-interpreter-discovery error before ever reaching the linters. Everything below was invisible until now, not new debt:
  - Fixed a real mypy config gap: `explicit_package_bases`/`mypy_path` were never set, causing "source file found twice under different module names" once mypy could actually run against the vendored package.
  - Fixed mypy's `python_version` setting (still `3.13`, causing a hard parse failure against Home Assistant's own 3.14-only syntax) and removed a stale external `pyalarmdotcomajax` dependency from the mypy hook's config, left over from before vendoring.
  - Fixed `codespell`'s exclusion path for vendored JSON:API files, silently broken by the `_pyalarmdotcomajax` rename.
  - Standardized on Python 3.14 throughout `.pre-commit-config.yaml` and its workflow, matching what `homeassistant>=2026.7.1` actually requires - previously mixed 3.13/3.14 pins were fighting each other.
  - Added scoped `ruff` ignores with documented reasoning: `S101`/`SLF001` for test files (assert and mock-attribute setup are normal there), `A002`/`A004`/`FBT001` for the vendored third-party library (not ours to restyle), and `E402` specifically for `__init__.py` (its `sys.path` shim must run before the imports that depend on it - intentional, not an oversight).
  - Deliberately, explicitly opted out of PEP 695 generic syntax modernization (`UP046`/`UP047`) for now - purely cosmetic, zero runtime difference, but converting 14 class declarations correctly needs live `mypy` verification this environment can't fully provide. Tracked as a real future PR, not left as unexplained lint noise.
  - **Added `custom_components/__init__.py` as a marker file.** Without it, mypy's directory-walk stopped at `alarmdotcom/` (which has its own `__init__.py`) while `explicit_package_bases`/`mypy_path` separately resolved the same files through `custom_components/` - two valid module names for one file, causing "Source file found twice" errors that kept resurfacing for whichever file happened to be checked. Zero effect on how Home Assistant actually loads the integration.
  - **Found the real, complete fix for the `_pyalarmdotcomajax`-resolves-to-`Any` gap**, via `mypy --verbose` rather than guessing: every file under `custom_components/alarmdotcom/` actually resolves as bare `alarmdotcom.X` for mypy's purposes (not `custom_components.alarmdotcom.X`, despite import statements elsewhere suggesting otherwise). Three earlier attempts at a global fix (changing `mypy_path`, changing import statements two different ways) were tried and rejected because each one reintroduced a worse, sometimes fatal, module-resolution error. The actual fix is one clearly-commented `[[tool.mypy.overrides]]` block in `pyproject.toml`, using the confirmed real module names, rather than either scattering `# type: ignore` everywhere or continuing to guess at global config changes. `mypy` now reports zero issues across the full codebase (down from 57 errors when this cleanup started).
  - Fixed several genuinely real type-safety gaps surfaced once `mypy` could actually check the codebase for the first time: a `SensorSubtype._missing_` classmethod with an imprecise `cls` type, `camera.py` annotating a field as the `callback` decorator instead of the real `CALLBACK_TYPE`, five `self.bridge` null-safety gaps in `config_flow.py` (now explicit, documented `assert` statements - the flow's own step ordering already guaranteed these were set, this just makes it provable), and a `binary_sensor.py` return type that didn't account for `None` entries it could legitimately return.
  - **Fixed `taplo-lint`'s intermittent network failures** - the actual cause was an inline `#:schema` directive in `.taplo.toml` forcing an external fetch to json.schemastore.org on every run, confirmed by reproducing the failure locally (where it manifested differently - a TLS cert error rather than CI's JSON-parsing mismatch - proving it really was an unreliable external dependency, not a config problem). Removed the directive and added `--no-schema` to the hook as defense-in-depth.
  - Fixed a real unused-variable bug in `scripts/sync_versions.py`, surfaced once `ruff` could run cleanly enough to reach it.
- Added `tests/test_alarm_control_panel.py` (4 tests covering the arm-code fix above).

## 2026.7.7.2b0 (beta)

### Fixed
- **Duplicate config entries were not prevented** (found while adding test coverage, not previously reported): `config_flow.py` set the unique ID for a system via `async_set_unique_id()`, but never actually called `_abort_if_unique_id_configured()` afterward. In practice this meant nothing stopped the same Alarm.com system from being added as a second, separate config entry - the unique ID was being set but never enforced. Fixed: adding a system that's already configured now correctly aborts with `already_configured`, the same as any other Home Assistant integration. Does not affect reauth (a matching unique ID during reauth is expected and still works normally).

### Added
- **First real automated test suite** (`tests/`), wired into CI via `.github/workflows/tests.yaml`:
  - `test_config_flow.py` - the initial login step, all three login failure modes (`cannot_connect`/`invalid_auth`/`unknown`), the `must_enable_2fa` abort, OTP method selection (including the auto-skip-when-only-authenticator-app-is-enabled case), OTP submission (including invalid code), the duplicate-system abort (see Fixed above), and both steps of the options flow.
  - `test_init.py` - the setup/unload lifecycle: successful setup, auth failure correctly triggering reauth, connection failure correctly triggering a retry (not a hard failure), and unload correctly closing both the hub and the camera session.
  - 17 tests, currently covering config flow comprehensively and the core setup/teardown lifecycle. Platform files (climate, sensors, camera, etc.), the bypass/unbypass services, and hub.py's websocket reconnect logic aren't covered yet.

## 2026.7.7.1b0 (beta)

### Changed
- **Vendored `pyalarmdotcomajax` renamed to `_pyalarmdotcomajax`** (`custom_components/alarmdotcom/_pyalarmdotcomajax/`), and every import updated to match. This is a deliberate, collision-proof name: no legitimate PyPI package can use a leading underscore, so this can never again share a name with any pip-installed package - including the leftover pip-installed `pyalarmdotcomajax` some of you will have from before `2026.7.6.1b0`. Previously, if the vendored copy were ever missing or misconfigured, Python could silently fall back to a stale pip-installed copy of the same name instead of failing - this is exactly what surfaced during beta testing of `2026.7.6.1b0`, where a leftover `2026.5.3` copy silently satisfied the import when the vendored folder was renamed away for testing. With the rename, that fallback is no longer possible: if `_pyalarmdotcomajax` isn't on the path, importing it can only raise `ModuleNotFoundError`, never silently resolve to the wrong thing.
- No functional/behavioral changes beyond the rename itself and the fixes below, carried over from unreleased work on top of `2026.7.6.1b0`:
  - Startup now logs which copy of the library loaded (version + file path), and warns (rather than silently continuing) if it's not the expected bundled copy.
  - Camera `get_stream_info` raw-response logging - which included live, unexpired session credentials (`janusToken`, `cameraAuthToken`, `signallingServerToken`, TURN credentials) and fired every 20-30 seconds per camera - is now off by default regardless of the integration's general debug-logging state. Opt in via `configuration.yaml`:
    ```yaml
    logger:
      logs:
        custom_components.alarmdotcom.camera_api.raw_responses: info    # redacted summary
        custom_components.alarmdotcom.camera_api.raw_responses: debug   # full raw response
    ```

### Beta notice
Continuing beta testing of the vendoring change from `2026.7.6.1b0`. Please report any errors on first startup (check **Settings → System → Logs** for anything mentioning `alarmdotcom` or `_pyalarmdotcomajax`) or anything that previously worked and now doesn't.

## 2026.7.6.1b0 (beta)

### Changed
- **`pyalarmdotcomajax` is now vendored directly in this repo** (`custom_components/alarmdotcom/pyalarmdotcomajax/`) instead of installed via a `git+` dependency in `manifest.json`. This eliminates the `git+` URL that blocked full HACS/hassfest compliance, and removes the need to coordinate version bumps across two separate repos for every fix. The library's own runtime dependencies (`mashumaro`, `phonenumbers`, `pyhumps`, `typer`) are now declared directly in this integration's `manifest.json`.
- No functional/behavioral changes from `2026.7.6` — this release is purely a packaging change. If you notice anything different at runtime (not just on first install/restart), please open an issue.

### Beta notice
This is a **pre-release** for testing the vendoring change specifically. Please report:
- Any errors on first startup after updating (check **Settings → System → Logs** for anything mentioning `alarmdotcom` or `pyalarmdotcomajax`)
- Anything that previously worked and now doesn't

If you don't need to help test this, wait for the next stable release instead.

### Known issue: leftover pip-installed `pyalarmdotcomajax`
Updating to this release does **not** remove the previous `pyalarmdotcomajax` package that was installed via the old `git+` dependency — Home Assistant's dependency installer only adds packages a `manifest.json` currently requires, it doesn't remove ones that used to be required. This leftover is harmless (the integration's own `sys.path` handling ensures the bundled copy is what actually loads), but if you want to confirm this or clean it up:
- On startup, check **Settings → System → Logs** for a line like `pyalarmdotcomajax <version> loaded from the bundled copy: ...`. If you instead see a **warning** saying it loaded from an unexpected location, something's wrong — please open an issue with that log line.
- To remove the leftover package (optional, cosmetic only): `pip uninstall pyalarmdotcomajax` from a shell with access to Home Assistant's Python environment.

## 2026.7.6

### Fixed
- **Black screen on iPhone/iPad/Safari with alarm-webrtc-card** (#38): The SDP offer from Alarm.com's WebRTC signaling can carry an H.264 `profile-level-id` that Apple's hardware decoder accepts without error but never actually renders — video stayed black with nothing surfaced anywhere in the pipeline, while Chrome and Android were unaffected. Root cause and initial fix identified by @Raul-7-7; the version shipped here generalizes it further based on mixed results reported in the thread: it matches *any* `profile-level-id` value (not just the one literal value seen on one test camera, which silently did nothing for other camera models), covers macOS Safari in addition to iOS (some users only saw the failure in Safari on Mac, not iOS), and patches both the legacy and Janus/proxy SDP code paths (the original fix only covered the legacy path). The offer is patched to `profile-level-id=42e01f` (Baseline Profile, Level 3.1) before `setRemoteDescription()`, which is the profile most consistently supported by Apple's decoders.
- **"Smart arming" seems to break the integration / state stops updating until reload** (#42): Not actually related to Smart Arming specifically — any state change could go unreflected in Home Assistant indefinitely (arm/disarm from the Alarm.com app, from HA itself, or from automations), correcting only after a full integration reload. Root cause was in `pyalarmdotcomajax`: the periodic 5-minute "safety net" poll (meant to catch state missed by a dropped WebSocket event) called `fetch_full_state()`, which silently did nothing on every call after the first — no error, no log line. Fixed in `pyalarmdotcomajax` 2026.7.6 with a new `refresh_all_resources()` method that actually re-fetches and re-publishes state every time it runs. Bumped dependency pin accordingly.

## 2026.7.5

### Fixed
- **OTP "Failed to Connect" still occurring after 2026.5.3 (reopened #21)**: The 2026.5.3 fix in `pyalarmdotcomajax` turned out to be a regression, not a fix — it checked for the MFA cookie before `trustTwoFactorDevice` ran, but Alarm.com reliably sets that cookie on the *trust* response, not the verify response. Since HA's config flow always provides a device name, this made the failure happen on every login. There was also a second, independent bug: aiohttp only exposes cookies from the last response in a redirect chain, so the cookie could be invisible even when present in the redirect history. Both fixed upstream in `pyalarmdotcomajax` 2026.7.5 (contributed by @jsight, confirmed independently by @lwimble). Bumped dependency pin accordingly.
- **Thermostat still shows only one temperature bar in auto mode** (#22): The 2026.5.3 fix corrected `target_temperature_high_fn`/`target_temperature_low_fn`, but `target_temperature_fn` (the single-setpoint attribute) was still inferring and returning a heat or cool setpoint while in `AUTO` state. Home Assistant's climate entity model treats `temperature` and the `target_temperature_high`/`target_temperature_low` pair as mutually exclusive — populating both at once caused the frontend to keep falling back to a single-setpoint control instead of the dual-bar range control. Fix: `target_temperature_fn` now returns `None` while in `AUTO` state, matching the high/low callbacks.
- **Bypassing sensors, resource ID undiscoverable** (#14): Bypass/unbypass services worked but required finding the Alarm.com resource ID via a Developer Tools -> Template lookup. The sensor entity now exposes `resource_id` as a plain attribute, and the bypass/unbypass service handlers now raise `ServiceValidationError`/`HomeAssistantError` instead of silently logging a warning and returning on failure.

### Dependency
- Updated `pyalarmdotcomajax` to `2026.7.5`, which fixes the OTP device-trust ordering regression and MFA/AFG cookie capture across redirects.

## 2026.5.3

### Fixed
- **Alarm panel state not updating on push events** (#20, #23): The alarm control panel entity was writing state updates to `self.alarm_state` — a plain instance attribute that Home Assistant never reads — instead of `self._attr_alarm_state`. Every websocket push event was silently discarded, so state only ever updated via the 5-minute polling fallback. Users would see delays of 10+ minutes or no update at all after arming/disarming at the keypad. Fix: corrected the attribute name in `update_state()`.
- **Thermostat shows only one temperature bar in auto mode** (#22): The `target_temperature_high_fn` and `target_temperature_low_fn` callbacks returned the cool and heat setpoints in all non-OFF states. Because both values were always non-`None`, Home Assistant rendered a range control even in HEAT/COOL mode — but with both bars collapsed to a single point, producing the "one yellow bar" symptom. Fix: high/low callbacks now return `None` unless the thermostat is in `AUTO` state, so HA renders a single-target slider in HEAT/COOL and a proper range control in AUTO/HEAT_COOL.
- **`supported_features` stale after mode change** (#22): `update_state()` was not refreshing `_attr_supported_features` on websocket events. If a thermostat switched from AUTO to HEAT/COOL at the panel, the `TARGET_TEMPERATURE_RANGE` flag would remain set in HA indefinitely. Fix: `supported_features` is now refreshed on every state update event.
- **OTP "Failed to Connect" on SMS and email** (#21): Handled by updated `pyalarmdotcomajax` dependency. The MFA cookie was being checked after the device-trust registration step rather than immediately after OTP verification, causing a spurious failure when Alarm.com set the cookie on the verify response.
- **`Task exception was never retrieved` log spam from imageSensors** (#23): On every websocket reconnect, the image sensor controller attempted a refresh and received a 423 (Not Authorized) from Alarm.com for accounts without that feature. The unhandled exception produced repeated errors in the HA log. Fixed in updated `pyalarmdotcomajax` — the base controller now catches 423 on reconnect refresh and logs it at DEBUG level only.

### Dependency
- Updated `pyalarmdotcomajax` to `2026.5.3`, which fixes OTP submission failures, makes device-trust registration best-effort, and silences repeated 423 log errors from unsupported resource types on reconnect.

---

## 2026.4.22

### Fixed
- Fixed thermostat entity writes so heat and cool setpoints can be updated together
- Fixed thermostat fan mode writes that used duration `0` for auto or indefinite modes
- Fixed arm night feature detection when Alarm.com returns nested arming option combinations
- Fixed controller resource parsing so one bad device payload no longer breaks an entire refresh
- Fixed sensor parsing when `open_closed_status` is returned as `null`
- Fixed thermostat parsing by using concrete enum types for thermostat state fields

### Improved
- Improved partition command errors so they report the command that failed
- Updated Home Assistant dependency pin to `pyalarmdotcomajax` `2026.4.22`

# Changelog

All notable changes to the Alarm.com Home Assistant integration will be documented in this file.

---
## 2026.3.30

### Added
- **Janus proxy camera support**: Cameras that use the Alarm.com Janus WebRTC gateway are now fully supported. The backend resolves the Janus mountpoint ID from the API response — first trying the HD quality stream entry, falling back to SD, and finally deriving it from the camera ID suffix for cameras that don't include quality message entries. The Lovelace card supports a `janusStreamId` override in card config for cases where the API does not expose the correct mountpoint.
- **Janus proxy mountpoint creation**: For cameras served via a proxy URL, the card automatically creates the Janus mountpoint (using the `proxyUrl` as the media source) before issuing the watch request. The mountpoint ID is dynamic per session and is captured from the Janus create response.
- **Lovelace card debug logging**: Internal card diagnostics now use `console.debug` so they are only visible when browser debug logging is enabled.

### Fixed
- **Camera stream reconnect**: The Lovelace card now automatically reconnects when a WebRTC stream drops. ICE disconnection, failure, and closure events trigger a retry sequence with up to 5 attempts at 4-second intervals. After exhausting retries a manual reconnect button is shown. Janus hangup, detach, and error events also trigger the retry path. A token request safety timeout prevents the card from freezing indefinitely if the backend does not respond.
- **Documentation**: Corrected token refresh interval in README from 45 minutes to 30 minutes to match the actual value in `camera.py`.

---
## 2026.3.27

### Fixed
- **Lock**: Removed incorrect code requirement on lock/unlock actions. The integration was applying the alarm panel arm code to locks, causing HA to reject lock/unlock commands with "The code for {device} doesn't match pattern number" for any user without an arm code configured, or whose arm code didn't match. Locks no longer require a code to operate — the arm code option applies to the alarm control panel only.
- **Lock**: Removed incorrect code requirement on lock/unlock actions. The integration was applying the alarm panel arm code to locks, causing HA to reject lock/unlock commands with "The code for {device} doesn't match pattern number." Locks no longer require a code — the arm code option applies to the alarm control panel only.
- **Websocket reconnect**: When the Alarm.com websocket died, the integration would silently stop receiving all state updates with no recovery path. Users had to manually reload or reboot HA. The hub now automatically attempts to reconnect with exponential backoff (up to 5 attempts, 30–150 second delays). If all attempts fail it schedules a full integration reload automatically.
- **Stale state after reconnect**: Added a periodic full state poll every 5 minutes as a safety net. Any state changes that occurred during a websocket gap are now caught and reflected in HA.
- **Camera session recovery**: Camera session re-login on auth failure now correctly checks whether it owns the session before attempting an independent login, preventing incorrect login attempts when sharing the pyalarmdotcomajax session.

### Improved
- Websocket death no longer raises `ConfigEntryNotReady` into a void — it now triggers a managed reconnect task with proper logging at each attempt
- Reconnect task is cleanly cancelled on integration unload

---

## 2026.3.21

Builds on 2026.3.18.2 with camera support, a full bug fix pass across all platforms, and HACS readiness improvements.

### Added
- **Camera support**: WebRTC live-streaming for Alarm.com cameras via a custom Lovelace card (`www/alarm-webrtc-card.js`)
- Camera entities automatically refresh WebRTC tokens every 45 minutes so streams are always ready without manual intervention
- Still image snapshots now supported — camera thumbnails display correctly in the HA media browser and picture-glance dashboard cards
- `brand/logo.png` added for HACS integration detail page display
- `info.md` added for HACS store listing

### Fixed

#### Platforms
- **Thermostat**: `async_set_temperature` was silently doing nothing — it read `kwargs.get("target_temp")` but HA sends `"temperature"` (`ATTR_TEMPERATURE`). Single-target temperature changes now work correctly
- **Thermostat**: High/low setpoints now sent in a single API call instead of two sequential calls, avoiding potential race conditions and rate limiting
- **Thermostat**: Fixed mismatched `# fmt: off` / `# fmt: on` comment pair in `initiate_state`
- **Lock**: `code_format_fn` now correctly returns `CodeFormat.NUMBER` / `CodeFormat.TEXT` instead of raw regex strings that HA doesn't understand, fixing silent failure of lock code format enforcement
- **Lock**: Removed `import re` buried inside a function body — moved to top-level import
- **Alarm Panel**: Removed duplicate arm code validation that ran twice on every arm/disarm command (once silently, once raising an exception)
- **Cover**: Gates now correctly use `CoverDeviceClass.GATE` instead of `CoverDeviceClass.GARAGE` — gate entities now show the correct icon and label in HA
- **Entity**: Removed unreachable duplicate `return device_info` statement in `device_info_fn`

#### Infrastructure
- **Orphan cleanup** (`util.py`): Entities without a `unique_id` were incorrectly deleted on every HA restart because the match condition was inverted. They are now matched solely by `entity_id` as intended
- **Camera session** (`camera_api.py`): Auth retries now only trigger on HTTP 401/403 responses instead of catching all exceptions blindly
- **Camera import** (`__init__.py`): Fixed `NameError` — `CONF_MFA_TOKEN`, `CONF_USERNAME`, and `CONF_PASSWORD` were referenced before being imported
- **Config flow** (`config_flow.py`): Replaced deprecated `async_timeout` package (removed in HA 2024.x) with `asyncio.timeout`

#### Lovelace Card (`www/alarm-webrtc-card.js`)
- Fixed `visibilitychange` event listener leak — a new listener was added on every stream restart and never removed. Listeners are now stored and cleaned up in `disconnectedCallback`
- Fixed `_requesting` flag deadlock — if HA never responded to a `camera.turn_on` call the card would freeze on "Refreshing session..." indefinitely. A 15-second safety timeout now resets the flag automatically
- `callService` failures now immediately reset `_requesting` instead of leaving the card frozen

### Improved
- Camera session reuses the authenticated `pyalarmdotcomajax` HTTP session where possible, avoiding a second full login on every HA startup. Falls back gracefully to an independent login if session internals are not accessible
- README updated with full camera setup instructions, Lovelace card configuration example, and camera added to supported devices table
- Camera removed from roadmap in README since it is now implemented
- Cleaned up dead commented-out platform stubs (`Platform.NUMBER`, `Platform.SWITCH`, `Platform.SELECT`) from `const.py`

---

## 2026.3.18.2

### Fixed
- Resolved issue where one-time password (OTP) was not sent during initial login when only a single 2FA method was available
- Fixed config flow skipping OTP request step, causing users to be stuck on verification screen
- Corrected OTP handling logic to properly request codes for SMS and email methods

### Improved
- Enhanced multi-factor authentication flow to handle all supported Alarm.com verification methods correctly
- Added safeguards for lost or invalid OTP method state during login
- Improved error handling and user feedback during authentication process
- Updated device registry identifiers to ensure compatibility with Home Assistant requirements

### Changed
- Updated pyalarmdotcomajax dependency to custom GitHub version with OTP fixes
- Cleaned up config flow logic for better reliability and maintainability

### Other
- Reordered manifest.json fields to meet Home Assistant and hassfest validation requirements
- General code cleanup and logging improvements

## 2026.3.16

Expanded Alarm.com entity coverage with new diagnostic sensors, system actions, trouble reporting, and bypass services.

### Added

- Added Home Assistant `sensor` platform to the integration
- Added diagnostic battery percentage sensors where Alarm.com exposes battery data
- Added diagnostic battery status enum sensors where Alarm.com exposes battery classification data
- Added diagnostic bypass state binary sensors for supported sensors
- Added system action buttons:
  - Stop Alarms
  - Clear Alarms In Memory
- Added smoke reset button support for smoke detector resources
- Added system-level trouble condition binary sensors
- Added per-device trouble mapping binary sensors
- Added `alarmdotcom.bypass_sensor` and `alarmdotcom.unbypass_sensor` services
- Added `services.yaml` definitions for the new bypass services

### Improved

- Expanded diagnostic visibility for Alarm.com systems and managed devices
- Integration now surfaces additional diagnostic and system state information
- Improved cleanup handling for newly created sensor entities
- Included the new `sensor` platform in the integration platform loader

### Dependency Updates

- Updated `pyalarmdotcomajax` dependency to `2026.3.15`
- Integration now pulls the library directly from the GitHub tag to ensure compatibility

### Notes

- Battery percentage and battery status only appear for device types where Alarm.com returns usable battery data
- Many panel sensors currently report no battery value and no bypass capability through the available Alarm.com payloads
- Bypass services will only work for sensors where Alarm.com reports `supportsBypass: true`

---

## 2026.3.14

Initial stabilization release for the maintained fork of the Alarm.com Home Assistant integration.

### Added

- Forked and modernized Alarm.com integration
- Updated codebase for compatibility with recent Home Assistant versions
- Initial repository structure cleanup and documentation improvements

### Improved

- Improved reliability and entity initialization
- Updated internal structure to better align with modern Home Assistant integration patterns

---

## Earlier Versions

Earlier development history was inherited from the original Alarm.com integration project and may not reflect the current maintained codebase.
