# Alarm.com for Home Assistant

> **Maintenance update, November 2026:** This project is being actively revived. [@ibasebcast](https://github.com/ibasebcast) has joined the [pyalarmdotcom](https://github.com/pyalarmdotcom) organization as an owner and is preparing the maintained v4 codebase for an official upstream release.
>
> **Important:** This branch is a modernization and compatibility-testing branch, **not a published stable or beta release**. The original v3.0.15 installation currently has known compatibility problems with modern Home Assistant. No existing user installation has been updated by this branch.

## Thank you to the original maintainers and contributors

**Elhad Bar-Shai ([@elahd](https://github.com/elahd))** deserves our sincere thanks for his many years of leadership, maintenance, and work on this integration and its Python ecosystem. His decision to help pass the project forward makes this next phase possible.

**Justin Wong ([@uvjustin](https://github.com/uvjustin))** also deserves explicit recognition for his foundational contributions and development work. The original MIT copyright notice names Justin Wong (2020), and those attribution and license notices remain preserved in this repository.

Thank you as well to every past contributor, tester, issue reporter, and community member who has kept the project useful.

## What happens next?

The maintained integration built on the original **v4.0.1-beta.2** foundation has received substantial updates since March 2026, including compatibility fixes, more reliable state handling, more device support, cameras, diagnostics, tests, and setup improvements. The full development history is preserved in [CHANGELOG.md](CHANGELOG.md), the [release notes](release-notes/), and the maintained repository's [Git history](https://github.com/ibasebcast/ha-alarmdotcom).

Our priority is to verify existing v3/v4 configuration upgrades, entity IDs, devices, and automations before replacing the original published integration. **Users who switched to the maintained fork will not be forced to move back.**

The project is **not abandoned**. We intend to maintain it going forward, review the existing issues respectfully, and publish upstream releases only when the compatibility work is ready. No release date is promised.

This is an unofficial community project with no affiliation to Alarm.com.

---

# Overview

This custom integration allows Home Assistant to interface with [**Alarm.com**](https://Alarm.com) using the Alarm.com web platform.

The integration focuses primarily on Alarm.com security system functionality and requires an Alarm.com service package that includes security system support.

Because this integration communicates with Alarm.com cloud services, functionality may change if Alarm.com modifies their platform.

---
> [!WARNING]
> # Safety Notice
>
>This integration is designed for **convenience and automation**, but it should **not be relied upon for safety-critical functions.**
>
>Reasons include:
>
>1. This integration communicates with Alarm.com using unofficial endpoints.
>2. Alarm.com status updates may take time to propagate.
>3. Home Assistant automations may introduce unintended behavior.
>4. This code is community developed and may contain bugs.
>
>For critical alerts such as:
>
>* Break-ins
>* Fire
>* Carbon monoxide
>* Water leaks
>* Freeze warnings
>
>You should rely on **Alarm.com's official monitoring services and mobile applications.**
>
>Where possible, use **locally controlled Home Assistant integrations** for automation. Local integrations continue functioning during internet outages, while this integration requires cloud communication.

> [!TIP]
> Some alarm.com devices use Z-Wave, so if you have a Z-Wave dongle then you can move the devices from alarm.com to Home Assistant's [native Z-Wave integration](https://www.home-assistant.io/integrations/zwave_js/)
---

# Installation and Setup

## Current release status

- **Original default-catalog installation:** The last published stable release is v3.0.15 and has known failures on current Home Assistant versions. Installing or updating from this **development branch** is not a supported recovery procedure.
- **Maintained working distribution:** The independently published [maintained integration](https://github.com/ibasebcast/ha-alarmdotcom) remains available. Its [installation and migration guide](https://github.com/ibasebcast/ha-alarmdotcom#installation-and-setup) includes the verified Marketplace Repository Repair procedure for users switching repositories.
- **Official upstream modernization:** This branch is preparing the maintained implementation for validation and eventual publication through the original repository. No official upstream modernization release has been published yet.

Before testing any integration transition, **make a full Home Assistant backup** and verify that existing alarm entities and automations survive. Please do not delete your existing Alarm.com configuration entry simply to change the installed source repository.

For an *existing* maintained-fork installation, keep using its normal update channel while this integration is tested. Do not install two different copies of the `alarmdotcom` integration simultaneously.

---

## Prerequisites
Before setting up this integration you need the following

1. An active alarm.com account
2. Know the login for the alarm.com and be able to fill the One-Time Password
3. Have a device connected to alarm.com

### Permissions for a dedicated Alarm.com login

Sign into the Alarm.com website using the **exact credentials configured in Home Assistant**. Confirm that this login can see and control the devices you want to use. Your main login's permissions do not automatically apply to a separate HA login.

In Alarm.com's login management, grant access to the required device categories. In particular, enable **Lights/Thermostats** if you expect those devices in HA. Enable the **Activity** read permission for activity-history features. Reload the integration after changing permissions.

Missing permissions can produce empty device lists or HTTP 423 responses while other device categories continue working. In #115, enabling Lights/Thermostats for the dedicated HA login immediately restored all four lights. Check permissions before reinstalling, capturing network traffic, or trying another build.

## Setup

When adding the integration you will be prompted for:

| Parameter         | Required | Description                                             |
| ----------------- | -------- | ------------------------------------------------------- |
| Username          | Yes      | Alarm.com account username                              |
| Password          | Yes      | Alarm.com account password                              |
| One-Time Password | Maybe    | Required if your account uses two-factor authentication |

### If a setup verification code does not arrive

For SMS or email, select the delivery method and submit to request a code. On the code form, select **Send another code (SMS/email)** and submit once if needed. Leave the code blank when requesting a resend. Check the selected email mailbox and junk folder. The **Authenticator App Code** screen asks for the current code from the app linked to your Alarm.com account. If you want email or SMS, enable that method in Alarm.com and start setup again. A successful request does not establish delivery by Alarm.com or the provider.

If delivery still fails, report the exact installed integration version, Home Assistant version, provider, offered methods, and whether the initial request or one resend produced a sanitized error. Do not post passwords, verification codes, cookies, tokens, email addresses or account identifiers. A functioning installation does not need to be removed solely to test setup.

---

# Integration Options

These settings can be modified later using the **Configure** button on the Alarm.com integration card.

| Parameter      | Description                                                 |
| -------------- | ----------------------------------------------------------- |
| Code           | Code required for disarming or unlocking via Home Assistant |
| Force Bypass   | Bypass open zones when arming                               |
| No Entry Delay | Skip entry delay sensors                                    |
| Silent Arming  | Suppress panel beeps when arming                            |

For silent arming, continue past **General Settings** to **Arming Mode Profiles**, select **Arm Silently** under the mode you use, then continue through the final screen to save.

Some Alarm.com providers may restrict combinations of these options.

---

# Services

This integration exposes the following services, callable from **Developer Tools → Actions**, automations, or scripts.

| Service                       | Purpose                                                          | Target                        |
| ------------------------------ | ----------------------------------------------------------------- | ------------------------------ |
| `alarmdotcom.bypass_sensor`    | Bypass a supported sensor (e.g. a door left open) for the current arm period | `resource_id` field (see the sensor entity's `resource_id` attribute), optional `partition_id` |
| `alarmdotcom.unbypass_sensor`  | Remove a bypass from a sensor                                    | Same as above                 |
| `alarmdotcom.set_auto_off`     | Schedule one or more lights to turn off after a duration - see [Auto-Off Timers](#auto-off-timers) below | Standard entity target picker, restricted to this integration's lights |
| `alarmdotcom.cancel_auto_off`  | Cancel a pending auto-off timer                                  | Same as above                 |

`bypass_sensor`/`unbypass_sensor` take a `resource_id`, not an `entity_id` - find this in the sensor entity's own `resource_id` attribute (Settings → Devices & Services → Alarm.com → the sensor entity → Attributes). `set_auto_off`/`cancel_auto_off` use Home Assistant's standard entity target selector instead, since they operate on lights specifically and Home Assistant already has a rich picker for that.

### Set a temporary access schedule

The admin-only `alarmdotcom.set_temporary_access` action updates the temporary
schedule for an existing Alarm.com user. Select the integration account and
enter the system ID, the user ID from the portal's user page, and the start
and end times in ISO 8601 with `Z` or an explicit UTC offset.

### Read a temporary user's saved schedule

The response-only `alarmdotcom.get_temporary_user_schedule` action accepts the same account, system ID, and user ID as the write action. In a script:

```yaml
- action: alarmdotcom.get_temporary_user_schedule
  data:
    config_entry_id: YOUR_CONFIG_ENTRY_ID
    system_id: "YOUR_SYSTEM_ID"
    user_id: "YOUR_USER_ID"
  response_variable: saved_access
```

Response fields are `temporary_schedule` (an object with UTC `begin`/`end`, or null) and `credential_status` (Alarm.com's numeric status, or null). No PIN, raw access document, or arbitrary server description is returned. Status values are not translated into undocumented synchronization guarantees. A null temporary schedule does not mean access is unrestricted; another access type may apply.

This is a standard HA action with response data. An existing MCP connection that supports those actions can call it without integration-specific MCP code. Reading confirms what Alarm.com reports, not enforcement or completed synchronization on every lock/panel. User/system name pickers and unrestricted/weekly access management remain outside this build.

---

# Supported Devices

| Device Type  | Actions                               | Status | Low Battery | Malfunction | Notes                                                                     |
| ------------ | ------------------------------------- | ------ | ----------- | ----------- | ------------------------------------------------------------------------- |
| Alarm System | Arm Away, Arm Stay, Arm Night, Disarm | ✔      | ✔           | ✔           |                                                                           |
| Garage Door  | Open, Close                           | ✔      | ✔           | ✔           | See MyQ / Security+ 3.0 note below                                       |
| Gate         | Open, Close                           | ✔      | ✔           | ✔           | See MyQ note below                                                        |
| Light        | On / Off / Brightness                 | ✔      | ✔           | ✔           |                                                                           |
| Lock         | Lock, Unlock                          | ✔      | ✔           | ✔           |                                                                           |
| Sensor       | None                                  | ✔      | ✔           | ✔           | Updates depend on the device events reported by Alarm.com |
| Thermostat   | Heat, Cool, Auto, Fan                 | ✔      | ✔           | ✔           | Fan-only mode runs for the maximum duration supported by Alarm.com        |
| Camera       | Live WebRTC stream, Snapshot          | ✔      | -           |-           | Live playback uses the bundled `custom:alarm-webrtc-card`; snapshots depend on camera support                    |

Alarm.com reports battery data by device. **Battery** shows a percentage when the device supplies one.
**Battery Status** shows the classification returned by Alarm.com. A status of `None` means Alarm.com
reported its `NONE` classification, so it does not indicate a percentage or a confirmed healthy battery.
Where supported, check **Low Battery** and the system’s **Sensor Low Battery** or **Panel Low Battery** trouble indicators.

> [!NOTE]
> **Garage Doors (MyQ):** MyQ garage doors don't natively integrate with Home Assistant, but they do through Alarm.com, making this integration useful if that's what you have. A dedicated local solution like [RATGDO](https://paulwieland.github.io/ratgdo/) is generally preferable for local control.
>
>  However, if your opener uses **Security+ 3.0** (newer Chamberlain and LiftMaster models), no local solution currently supports it. This integration may be your only path to Home Assistant control.
>
> **Gates (MyQ):** MyQ gates use Security+ 2.0 with dry-contact wiring, there is no Security+ 3.0 gate. RATGDO and similar adapters can work with them, see the [RATGDO wiring guide](https://ratcloud.llc/pages/wiring) for specifics.

---

# Supported Sensor Types

| Sensor Type             | Description                    |
| ----------------------- | ------------------------------ |
| Contact                 | Doors and windows              |
| Freeze                  | Temperature threshold sensors  |
| Glass Break / Vibration | Standalone or panel-integrated |
| Motion                  | Motion detection sensors       |
| Vibration Contact       | Doors, safes, windows          |
| Water                   | Leak sensors                   |

Alarm.com may use different internal identifiers for some sensors.
If a supported sensor does not appear in Home Assistant, please open an issue.

https://github.com/pyalarmdotcom/alarmdotcom/issues

---

# Camera Support

This integration includes WebRTC live-streaming support for Alarm.com cameras.

## Setup

1. The camera card is bundled with the integration and served from `/alarmdotcom/alarm-webrtc-card.js`.
2. In storage-mode dashboards the integration attempts to register the JavaScript module automatically. If you manage resources in YAML or automatic registration is unavailable, add that URL as a **JavaScript module** in your dashboard resources.
3. Add the card to any Lovelace dashboard:

```yaml
type: custom:alarm-webrtc-card
entity: camera.your_camera_name
```

## How it works

When the card loads it requests WebRTC credentials through an authenticated Home Assistant websocket command, with camera entity read-permission checks. Tokens are never exposed as entity attributes or stored in recorder history. The card requests refreshed credentials when reconnecting.

Still-image snapshots are requested when supported by the camera and Alarm.com endpoint. Snapshot availability varies by device and account.

### If live video is gray or the camera shows Inactive

The built-in Home Assistant camera view can show a still image when snapshots are available. For live video, use the bundled `custom:alarm-webrtc-card` shown above.

1. Open **Live Video** on the Alarm.com website and try the same camera.
2. Open the bundled card in Home Assistant. If the card shows **Reconnect**, try it once to request fresh stream credentials.
3. If the camera plays on the website but the bundled card still fails, report the camera model, the integration version, and the exact message shown by the card. Leave out account and device IDs, signed URLs, and tokens.

For SkyBell doorbells such as the ADC-VDB105, check live video in the Alarm.com mobile app. [Alarm.com documents SkyBell live video as mobile-app only](https://answers.alarm.com/Customer/Website_and_App/Video/Live_Video/View_live_video).

A camera can still appear in the device list and report motion events when live video is unavailable. An `Empty stream info returned` warning means Alarm.com did not supply usable stream information for that request. The warning is throttled per camera.

### Camera transport and kiosk recovery

The default camera transport is `endToEnd`. Janus-only cameras continue to use Janus. If a camera never starts with endToEnd, open **Settings → Devices & Services → Alarm.com → Configure**, continue to **Polling & Refresh Intervals**, and select **Preferred camera transport → Janus proxy**. The preference applies to this Alarm.com entry; a camera uses the other transport if the preferred one is not advertised. Changing the option reloads the integration.

After updating, restart Home Assistant and fully reload every browser/app dashboard to load the updated card. Test a single camera first, then the normal multi-camera dashboard and page reloads. Kiosk users should also verify normal continuous viewing over at least 24 hours. A connection that stays live for 30 seconds resets its consecutive retry count. Automatic recovery stops after five consecutive retries or ten retries within ten minutes, then displays **Reconnect** for a manual retry.

---

# Auto-Off Timers

Any light can be scheduled to turn off automatically after a duration, using the `alarmdotcom.set_auto_off` service - useful for things like "turn on for 30 minutes" without building a full automation for every light.

This is deliberately more capable than a plain automation using a "wait, then turn off" action:

* **Survives a Home Assistant restart.** The scheduled off-time is persisted. If Home Assistant was offline when a timer was due, the light turns off immediately on startup instead of the timer being silently lost; a timer still in the future is rescheduled for its exact remaining time.
* **The scheduled off-time is visible.** Every light with a pending timer shows it directly in its own `auto_off_at` attribute - no separate helper entity needed to check "how much time is left."
* **A summary sensor** ("Active Auto-Off Timers", found on the account's System device) shows how many timers are currently pending account-wide, with a `timers` attribute listing each affected light and its scheduled off-time.
* If a light is turned off some other way before its timer fires - manually, from the Alarm.com app, from an unrelated automation - the timer clears itself automatically.

**Example: turn on a light for one hour**

```yaml
action: alarmdotcom.set_auto_off
target:
  entity_id: light.front_porch
data:
  duration:
    hours: 1
```

**Example: automatically time out any of a group of lights whenever they're turned on**

```yaml
alias: Auto-off lights after 1 hour
triggers:
  - trigger: state
    entity_id:
      - light.front_porch
      - light.back_porch
      - light.garage
    to: "on"
actions:
  - action: alarmdotcom.set_auto_off
    target:
      entity_id: "{{ trigger.entity_id }}"
    data:
      duration:
        hours: 1
mode: queued
```

To cancel a pending timer early, call `alarmdotcom.cancel_auto_off` with the same target.

---

# Lock Unlock Attribution

Lock entities expose three additional attributes: `last_unlocked_by`, `last_unlock_method`, and `last_unlocked_at`.

This is sourced from Alarm.com's own activity history, polled roughly every 15 seconds - a genuinely separate data path from this integration's live state updates, since "who unlocked this" isn't part of the lock's ongoing state, only its history.

**Prerequisite:** the Alarm.com account/login used by this integration needs the **"Activity" read-only permission** enabled, or these attributes will never populate at all. Confirmed by a real user - this isn't documented anywhere by Alarm.com itself, so it's easy to miss if the integration's account was set up before this feature existed, or was scoped narrowly on purpose.

**Important limitation, confirmed directly from Alarm.com's own data, not a gap in this integration:** Alarm.com only attributes a keypad-code unlock to a specific person. Unlocking from the Alarm.com app, the web portal, or manually at the door is **not** attributed to anyone - `last_unlocked_by` correctly shows as unset for those, since Alarm.com itself doesn't know who performed them. Lights and switches have no equivalent - Alarm.com does not attribute those to a user at all under any circumstance.

**`last_unlocked_by` doesn't necessarily reflect the most recent unlock, and that's also not a bug.** Not every unlock method generates its own distinct, loggable Alarm.com event for every lock model - a manual/inside turn may not be logged at all on some hardware. When that happens, `last_unlocked_by` simply keeps showing whoever the last *keypad* unlock was attributed to, even after a more recent manual or remote unlock, since there's no newer event for the poller to ever see. **`last_unlock_method`** exists specifically to sidestep this: it reports `"keypad"`, `"manual"`, or `"remote"` for whatever the most recently *tracked* unlock actually was, so an automation can gate on "was this actually a keypad entry" directly, rather than relying on a name that might be stale.

**Example: a welcome-home announcement that varies by person, gated on method to avoid the staleness pitfall above**

```yaml
alias: Welcome home TTS
triggers:
  - trigger: state
    entity_id: lock.front_door
    attribute: last_unlocked_by
conditions:
  - condition: template
    value_template: "{{ trigger.to_state.attributes.last_unlock_method == 'keypad' }}"
actions:
  - action: tts.speak
    target:
      entity_id: tts.google_translate
    data:
      media_player_entity_id: media_player.living_room_speaker
      message: "Welcome home, {{ trigger.to_state.attributes.last_unlocked_by }}."
```

---

# Activity Feed

Beyond lock unlock attribution, this integration also fires a curated event on Home Assistant's event bus for other significant Alarm.com activity - arm/disarm, lock/unlock, and camera motion triggers - and keeps a short rolling list of the most recent ones on a **"Recent Activity"** sensor (found on the account's System device).

This uses the same underlying poll as lock unlock attribution - nothing extra to configure, no additional load on Alarm.com's servers.

**What's included by default**, and why the list is deliberately curated rather than exhaustive: real captured activity data showed roughly one event every 2-3 minutes during ordinary use, much of it genuinely noisy for automation purposes - every light interaction fires twice (a command event and a state-change event), motion and button presses fire constantly. Alarm.com does not attribute any of those to a specific person either (see [Lock Unlock Attribution](#lock-unlock-attribution) above), so they carry less unique automation value than the events below:

* System armed (any mode) or disarmed
* A lock locked or unlocked
* A camera detected motion/a person
* A garage door opened or closed

Garage door events specifically are cross-referenced against this account's known garage door devices (the same ones the garage door cover entity is built from) before being included - this is what lets them in while ordinary window/door sensors, which share the exact same event data shape, stay excluded as noise.

**Example: catch any curated event in an automation**

```yaml
alias: Log all significant Alarm.com activity
triggers:
  - trigger: event
    event_type: alarmdotcom_activity
actions:
  - action: logbook.log
    data:
      name: Alarm.com
      message: "{{ trigger.event.data.description }}"
```

Filter by `trigger.event.data.event_type_name` (e.g. `ArmedStay`, `DoorUnlocked`, `VideoCameraTriggered`) if you only want to react to specific kinds of activity.

---

# Data Updates

This integrations uses both Cloud Push and Cloud Polling.

Two things are polled on a timer rather than arriving live over the websocket, and both are configurable via the **Configure** button on the Alarm.com integration card:

| Setting                       | Default    | What it affects                                                              |
| ------------------------------ | ---------- | ------------------------------------------------------------------------------ |
| Activity poll interval         | 15 seconds | How quickly lock unlock attribution and the activity feed reflect real events |
| Full state poll interval       | 5 minutes  | A safety net that re-syncs everything in case a websocket event was ever missed |

The activity poll interval in particular is worth understanding before turning it down further: it hits an entirely undocumented Alarm.com endpoint with no confirmed rate-limit information. The default of 15 seconds is a deliberate tradeoff for a prompt welcome-home automation experience, not a guarantee it's safe at any value - if you ever run into problems, this is the first thing worth dialing back up.

The rest of the entities in this integration are Cloud Push.

---

# Removing This Integration

Removing this integration is the same as most HACS integrations:

- Go to **Settings** → **Devices & Services**
- Find the **Alarm.com** integration card
- Click the **three-dot menu** on the card and select **Delete**
- Repeat for any additional Alarm.com entries
- Go to HACS, select the three-dot menu for this integration, then select **Remove**.
- Then restart Home Assistant to clear the cache

---

# Development Status

This integration is under active maintenance.

See the [changelog](CHANGELOG.md) for compatibility checks and recent changes.

---

# Project Roadmap

Planned areas of development include:

* Expanded device coverage across the Alarm.com ecosystem
* Improved websocket reliability and reconnection handling
* Expanded automation and scene support
* Additional device diagnostics and status reporting
* Continued compatibility updates for new Home Assistant releases
* Maybe submission of this custom integration as a core integration

Community testing and feedback help guide development priorities.

---

# Contributing

Issues and pull requests are welcome.

Please report bugs or feature requests here:

https://github.com/ibasebcast/ha-alarmdotcom/issues

When reporting issues include:

* Home Assistant version
* Integration version
* Relevant Home Assistant logs
* Diagnostics of your alarm.com config entry

---

# Maintainership and Attribution

The active modernization work is maintained by [@ibasebcast](https://github.com/ibasebcast), working within the original pyalarmdotcom organization.

We gratefully recognize **Elhad Bar-Shai ([@elahd](https://github.com/elahd))** for sustaining the project, **Justin Wong ([@uvjustin](https://github.com/uvjustin))** for foundational contributions, and everyone whose work is preserved in Git history and license notices.

The maintained [independent distribution](https://github.com/ibasebcast/ha-alarmdotcom) remains supported throughout the transition. Original users will not be required to move to it once a safe official upgrade is ready.


# License and History

The original integration and upstream library originated under the **MIT License**, with copyright and attribution preserved in [LICENSE.md](LICENSE.md) and [LICENSE-upstream](LICENSE-upstream). The newer maintained contributions are distributed under the terms documented in [LICENSE](LICENSE) (Apache-2.0), subject to the retained upstream MIT notices. See the complete [changelog](CHANGELOG.md) for the modernization history.

The [original project's Git history](https://github.com/pyalarmdotcom/alarmdotcom/commits/master) and [the maintained project's Git history](https://github.com/ibasebcast/ha-alarmdotcom/commits/main) remain available.
