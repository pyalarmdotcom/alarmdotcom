> [!IMPORTANT]
> **Maintenance has resumed. Stable release candidate: `2026.11.17`.**
>
> This update brings the maintained v4-derived implementation back to the original repository. Check [Releases](https://github.com/pyalarmdotcom/alarmdotcom/releases) for published builds; a candidate branch is not a published stable release. See the [release notes](release-notes/2026.11.17.md) and [known issues](#known-issues-and-limitations) before upgrading.
>
> **Back up Home Assistant first and keep your existing Alarm.com configuration entry.** Community reports confirm upgrades from the original v4 beta, including operation on Home Assistant 2026.11.2. Direct v3 upgrades have not been verified on a live installation. Check your device/entity IDs, dashboards, and automations after upgrading.
>
> Existing users of [ibasebcast/ha-alarmdotcom](https://github.com/ibasebcast/ha-alarmdotcom) can keep their current update channel. Both distributions use the `alarmdotcom` directory; install only one at a time.

<hr>
<p align="center"><img src="https://user-images.githubusercontent.com/466460/175781161-dd70c5b4-d45a-4cdb-bf57-d4fd7fbedb0b.png" width="125"></p>
<h1 align="center">Alarm.com for Home Assistant</h1>
<p align="center">This is an unofficial project that is not affiliated with Alarm.com</p>
<br />
<p align="center">
  <!-- <a href="https://www.codacy.com/gh/pyalarmdotcom/alarmdotcom/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=pyalarmdotcom/alarmdotcom&amp;utm_campaign=Badge_Grade"><img src="https://app.codacy.com/project/badge/Grade/6f557fbc58914ef5914a81ed5e1c3391"/></a> -->
  <a href="https://github.com/pyalarmdotcom/alarmdotcom/actions/workflows/hassfest.yaml"><img alt="HACS/Hassfest validation" src="https://github.com/pyalarmdotcom/alarmdotcom/actions/workflows/hassfest.yaml/badge.svg?branch=master"></a>
  <a href="https://github.com/pyalarmdotcom/alarmdotcom/actions/workflows/pre-commit.yaml"><img alt="Pre-commit checks" src="https://github.com/pyalarmdotcom/alarmdotcom/actions/workflows/pre-commit.yaml/badge.svg?branch=master" /></a>
  <a href="https://github.com/pyalarmdotcom/alarmdotcom/commits/master"><img src="https://img.shields.io/github/commit-activity/y/pyalarmdotcom/alarmdotcom.svg" /></a>
  <a href="https://buymeacoffee.com/ibasebcast"><img alt="Support ongoing integration maintenance" src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-Support%20Maintenance-FFDD00?logo=buymeacoffee&amp;logoColor=black"></a>
</p>
<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Default-41BDF5.svg" /></a>
  <img alt="HACS Downloads" src="https://img.shields.io/endpoint?url=https%3A%2F%2Flauwbier.nl%2Fhacs%2Falarmdotcom" />
  <a href="https://github.com/pyalarmdotcom/alarmdotcom/releases"><img src="https://img.shields.io/github/release/pyalarmdotcom/alarmdotcom.svg" /></a>
  <a href="https://github.com/pyalarmdotcom/alarmdotcom/blob/master/LICENSE.md"><img alt="GitHub" src="https://img.shields.io/github/license/pyalarmdotcom/alarmdotcom"></a>
</p>

<hr />

This is a custom component that allows Home Assistant to interface with [Alarm.com](https://www.alarm.com/) by using the Alarm.com website's unofficial API. This component is designed primarily to integrate the Alarm.com security system functions; as such, it requires an Alarm.com package which includes security system support.

Please note that Alarm.com may break functionality at any time.

![image](https://user-images.githubusercontent.com/466460/171702200-c5edd68b-c54f-4ca4-82b3-d5a0bb97702b.png)

![image](https://user-images.githubusercontent.com/466460/171701963-e5b5f765-6817-4313-8fa1-6035f4c453e9.png)

## Safety Warnings

This integration is great for casual use within Home Assistant but... **do not rely on this integration to keep you safe.**

1. This integration communicates with Alarm.com over an unofficial channel that can be broken or shut down at any time.
2. It may take several minutes for this integration to receive a status update from Alarm.com's servers.
3. Your automations may be buggy.
4. This code may be buggy. It's written by volunteers in their free time and testing is spotty.

You should use Alarm.com's official apps, devices, and services for notifications of all kinds related to safety, break-ins, property damage (e.g.: freeze sensors), etc.

Where possible, use local control for smart home devices that are natively supported by Home Assistant (lights, garage door openers, etc.). Locally controlled devices will continue to work during internet outages whereas this integration will not.

## Details

### Supported Devices

Support depends on the device, service plan, provider, and permissions of the Alarm.com login used by Home Assistant. A supported device category does not mean every model or function has been tested.

| Device Type | Actions | View Status | Diagnostics | Notes |
| --- | --- | --- | --- | --- |
| Alarm System | Arm Away, Arm Stay/Home, Arm Night, Disarm | Yes | Battery and trouble conditions when supplied | Arming options depend on panel/provider support. |
| Garage Door | Open, Close | Yes | When supplied | Includes MyQ doors exposed through Alarm.com. |
| Gate | Open, Close | Yes | When supplied | Requires remote-control permission in Alarm.com. |
| Light | On, Off, Brightness | Yes | When supplied | Dimming requires a dimmable device. Color/RGB control is not implemented. |
| Lock | Lock, Unlock | Yes | When supplied | Activity-based unlock attribution is available with Activity permission. |
| Sensor | Read state; bypass/unbypass when supported | Yes | Low battery, malfunction, bypass and battery data when supplied | Updates depend on events and state data supplied by Alarm.com. |
| Thermostat | Heat, Cool, Auto heat/cool, Fan | Yes | When supplied | Supported modes vary. Fan-only uses the maximum duration provided by Alarm.com. |
| Water Valve | Open, Close | When supplied | When supplied | Moen Flo state reporting has a known issue; see below. |
| Camera / Doorbell | WebRTC live view, snapshot when available | Camera and detection data when supplied | Model-dependent | Live video uses the bundled `custom:alarm-webrtc-card`. SkyBell has limitations. |
| Z-Wave Central Scene | Paddle/button event entities and automation triggers | Events | Not applicable | Only when Alarm.com sends supported scene events for a discovered light/switch. These are not Alarm.com scene activation entities. |

### Supported Sensor Types

| Sensor Type | Notes |
| --- | --- |
| Contact | Doors, windows, and other open/close sensors. Quick combined OpenedClosed events produce a brief open pulse. |
| Freeze | Threshold state, not general-purpose temperature measurement. |
| Glass Break / Vibration | Standalone and panel-integrated sensors when reported. State/reset behavior varies by panel. |
| Motion | Standalone and panel motion sensors. |
| Vibration Contact | Doors, windows, safes, etc. |
| Water | Leak/moisture state when exposed by Alarm.com. |
| Smoke | State and reset action when the device/API supplies them; not a replacement for official fire monitoring. |
| Carbon Monoxide | State when supplied by the device/API; not a replacement for official CO monitoring. |
| Panic Button | Reported state when available; fixed-panic devices remain excluded. Triggering a panic alarm is not implemented. |
| Camera Analytics | Person, vehicle, animal and package detections where events are provided. Classification accuracy is under investigation. |

Alarm.com uses multiple internal designations for sensors. If an expected device does not appear, [open an issue](https://github.com/pyalarmdotcom/alarmdotcom/issues/new/choose) with its model, integration version, and sanitized diagnostics.

#### Subsensors

Devices can expose low-battery, malfunction, bypass, battery percentage, and battery-status entities, depending on the data Alarm.com returns. A battery status of `None` is Alarm.com's NONE classification, not a percentage or a confirmed healthy battery. System trouble indicators can provide additional low-battery information.

### Future Support

#### Roadmapped and Help Wanted Devices

| Device Type | Current Limit / Help Needed |
| --- | --- |
| Image Sensor | The bundled library has image-sensor resource support, but a complete Home Assistant photo/peek-in interface is not exposed. Panel image-sensor binary entities remain excluded. |
| RGB Light | On/off and brightness may be available; color control needs device/API examples and implementation. |
| Remote Temperature Sensor | General-purpose remote temperature entities are not implemented. Freeze threshold support is separate. |
| Water Meter | Consumption/flow metering is not implemented, even if the same device exposes a controllable valve. |
| User Access Management | Temporary access read/write actions exist for a known user/system ID. User discovery, weekly schedules, and unrestricted-access management are not implemented. |
| Alarm.com Scenes | Portal scene discovery/activation is not implemented. Z-Wave Central Scene events are a separate feature. |

To help with a device, start with a model description and sanitized integration diagnostics. If more API evidence is needed, maintainers will request a specific capture. Never attach unredacted network archives or account credentials.

#### Device Blacklist and Unsupported Categories

| Device Type | Reason / Current Status |
| --- | --- |
| Audio Systems | No entity platform; use the device's direct Home Assistant integration where available. |
| Blinds and Shades | No entity platform; use a direct integration where available. |
| Irrigation Systems | No entity platform. |
| Mobile Phones | Panel-paired Bluetooth phones do not expose useful state through this integration and are excluded. |
| Sirens | Excluded as standalone sensor entities. System alarm-control actions are separate. |
| Panel Image Sensor | Excluded from binary-sensor discovery; full image support remains incomplete. |
| Fixed Panic | Excluded pending usable state support. |

## Using the Integration

### Installation

1. Use [HACS](https://hacs.xyz/) (or **Settings > Marketplace**, if that is how it appears on your system) to find **Alarm.com**, repository `pyalarmdotcom/alarmdotcom`, and install the latest published stable release.
2. Restart Home Assistant after installation or an update.
3. For a new setup, open **Settings > Devices & Services > Add Integration > Alarm.com**.
4. Enter your Alarm.com username, password, and verification code when requested.

[![Open Alarm.com in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=pyalarmdotcom&repository=alarmdotcom&category=integration)

#### Upgrading an existing original installation

- Make a full Home Assistant backup before updating, particularly from v3 or the old v4 beta.
- Update the existing repository installation and restart Home Assistant. Keep the existing integration entry, devices, and entities.
- If prompted to authenticate, use the existing entry's authentication flow rather than adding a second entry.
- Verify entity IDs and your existing automations/dashboard cards. The included configuration migrations are tested automatically, but a complete live v3 upgrade has not been verified.
- Recheck arming profiles and any v3 device-specific controls. The v4-derived implementation does not reproduce every old switch, select, or number entity.
- For rollback after a configuration migration, restore the full backup, including configuration and registries. Reinstalling older code alone may not undo the migration.

#### Switching between repository distributions

Users of the maintained independent distribution can continue using it. If you choose to switch, back up first and change only the installed repository source. Do not delete your Alarm.com entry, and do not install both distributions in the same directory.

If Marketplace reports that `custom_components/alarmdotcom` belongs to another repository, follow the [verified Marketplace Repository Repair procedure](https://github.com/ibasebcast/ha-alarmdotcom#switching-from-the-original-alarmcom-repository). The documented live test was from the original repository to the maintained distribution and back on earlier builds; it is not proof of v3 configuration compatibility. This candidate uses configuration schema 5. Before switching to another distribution or older release, confirm it supports schema 5, or restore your full pre-upgrade backup.

### Configuration

You'll be prompted to enter these parameters when configuring the integration.

| Parameter         | Required | Description                                                   |
| ----------------- | -------- | ------------------------------------------------------------- |
| Username          | Yes      | Username for your Alarm.com account.                          |
| Password          | Yes      | Password for your Alarm.com account.                          |
| One-Time Password | Maybe    | Required for accounts with two-factor authentication enabled. |

#### Additional Options

These options can be set using the "Configure" button on the Alarm.com card on Home Assistant's Integrations page:

![image](https://user-images.githubusercontent.com/466460/150607393-e057d445-a882-4fbd-a455-acf155083327.png)

| Parameter      | Description                                                                                                                                                                                                                                                                                      |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Code           | Specifies a code to arm/disarm your alarm or lock/unlock your locks in the Home Assistant frontend. This is not necessarily the code you use to arm/disarm your panel. This is a separate frontend code used by the Home Assistant [alarm panel card](https://www.home-assistant.io/dashboards/alarm-panel/). |
| Force Bypass   | Bypass open zones (windows, doors, etc.) when arming.                                                                                                                                                                                                                                            |
| No Entry Delay | Bypass the entry delay normally applied to entrance sensors.                                                                                                                                                                                                                                     |
| Silent Arming  | Suppress beeps when arming and double arming delay length.                                                                                                                                                                                                                                       |

_The three arming options are not available on all systems/providers. Also, some combinations of these options are incompatible. If arming does not work with a combination of options, please check that you are able to arm via the web portal using those same options._


### Permissions for a dedicated Alarm.com login

Sign into the Alarm.com website using the **exact credentials configured in Home Assistant**. Confirm that this login can see and control the devices you want to use. Your main login's permissions do not automatically apply to a separate HA login.

In Alarm.com's login management, grant access to the required device categories. In particular, enable **Lights/Thermostats** if you expect those devices in HA. Enable the **Activity** read permission for activity-history features. Reload the integration after changing permissions.

Missing permissions can produce empty device lists or HTTP 423 responses while other device categories continue working. In #115, enabling Lights/Thermostats for the dedicated HA login immediately restored all four lights. Check permissions before reinstalling, capturing network traffic, or trying another build.


### If a setup verification code does not arrive

For SMS or email, select the delivery method and submit to request a code. On the code form, select **Send another code (SMS/email)** and submit once if needed. Leave the code blank when requesting a resend. Check the selected email mailbox and junk folder. The **Authenticator App Code** screen asks for the current code from the app linked to your Alarm.com account. If you want email or SMS, enable that method in Alarm.com and start setup again. A successful request does not establish delivery by Alarm.com or the provider.

If delivery still fails, report the exact installed integration version, Home Assistant version, provider, offered methods, and whether the initial request or one resend produced a sanitized error. Do not post passwords, verification codes, cookies, tokens, email addresses or account identifiers. A functioning installation does not need to be removed solely to test setup.


For silent arming, continue past **General Settings** to **Arming Mode Profiles**, select **Arm Silently** for the desired mode, and continue through the final screen to save.

## Services

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

## Camera Support

This integration includes WebRTC live-streaming support for Alarm.com cameras.

### Setup

1. The camera card is bundled with the integration and served from `/alarmdotcom/alarm-webrtc-card.js`.
2. In storage-mode dashboards the integration attempts to register the JavaScript module automatically. If you manage resources in YAML or automatic registration is unavailable, add that URL as a **JavaScript module** in your dashboard resources.
3. Add the card to any Lovelace dashboard:

```yaml
type: custom:alarm-webrtc-card
entity: camera.your_camera_name
```

### How it works

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

## Auto-Off Timers

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

## Lock Unlock Attribution

Lock entities expose three additional attributes: `last_unlocked_by`, `last_unlock_method`, and `last_unlocked_at`.

This is sourced from Alarm.com's own activity history, polled roughly every 15 seconds - a separate data path from this integration's live state updates, since "who unlocked this" isn't part of the lock's ongoing state, only its history.

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

## Activity Feed

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

## Data Updates

This integration uses both Cloud Push and Cloud Polling.

Two things are polled on a timer rather than arriving live over the websocket, and both are configurable via the **Configure** button on the Alarm.com integration card:

| Setting                       | Default    | What it affects                                                              |
| ------------------------------ | ---------- | ------------------------------------------------------------------------------ |
| Activity poll interval         | 15 seconds | How quickly lock unlock attribution and the activity feed reflect real events |
| Full state poll interval       | 5 minutes  | A safety net that re-syncs everything in case a websocket event was ever missed |

The activity poll interval in particular is worth understanding before turning it down further: it hits an entirely undocumented Alarm.com endpoint with no confirmed rate-limit information. The default of 15 seconds is a deliberate tradeoff for a prompt welcome-home automation experience, not a guarantee it's safe at any value - if you ever run into problems, this is the first thing worth dialing back up.

The rest of the entities in this integration are Cloud Push.

---

## Removing This Integration

Removing this integration is the same as most HACS integrations:

- Go to **Settings** → **Devices & Services**
- Find the **Alarm.com** integration card
- Click the **three-dot menu** on the card and select **Delete**
- Repeat for any additional Alarm.com entries
- Go to HACS, select the three-dot menu for this integration, then select **Remove**.
- Then restart Home Assistant to clear the cache

---


## Known Issues and Limitations

These reports remain open as of November 17, 2026. Links below point to the maintained distribution's investigation threads, which apply to the shared implementation. An open report is not a claim that every installation is affected.

| Area | Known behavior / What to do | Tracking |
| --- | --- | --- |
| Direct v3 upgrades | Automated configuration migration checks do not establish preservation of every live device/entity or v3-only control. Back up, keep the entry, and verify dashboards/automations after updating. | [Upstream upgrade feedback #567](https://github.com/pyalarmdotcom/alarmdotcom/issues/567) |
| Slow sign-in / arming failures | Provider/network-dependent sign-in and declined commands remain under investigation. Compare with the same login in the official portal; do not repeatedly reinstall or create duplicate entries. The experimental sign-in branch is not included in this stable candidate. | [#157](https://github.com/ibasebcast/ha-alarmdotcom/issues/157) |
| Water valve discovery | Some accounts report no valve entity. A discovery fix is under investigation; do not assume a valve is supported merely because its model appears in Alarm.com. | [#178](https://github.com/ibasebcast/ha-alarmdotcom/issues/178) |
| Moen Flo valve state | Can show Closed while physically Open and while Alarm.com reports Open, including payloads with `has_state=False`. Do not use the displayed state as confirmation of flow or shutoff. Startup refresh does not resolve all cases. | [#189](https://github.com/ibasebcast/ha-alarmdotcom/issues/189) |
| Camera analytics | Person/animal/vehicle sensors can activate together when the app labels only a vehicle. Opt-in debug logging records event type and recognized classes; a classification fix is not yet confirmed. | [#195](https://github.com/ibasebcast/ha-alarmdotcom/issues/195) |
| Camera live view | ADC-V723x and ADC-VDB105 gray-view reports remain open. Use the bundled card; compare against official Live Video. SkyBell live video is documented as mobile-app only. Discovery does not guarantee live-view support. | [#190](https://github.com/ibasebcast/ha-alarmdotcom/issues/190) |
| Continuous camera kiosks | Multi-camera continuous playback/reloads have caused instability. The current code restores endToEnd as default, offers Janus selection, and caps retries. Long-running recovery still needs confirmation on affected hardware. | [#177](https://github.com/ibasebcast/ha-alarmdotcom/issues/177) |
| WebSocket interruptions | Irregular disconnects/retries can occur even while HTTPS polling and commands work. Full-state polling is a fallback; it does not make all sensor updates immediate. | [#176](https://github.com/ibasebcast/ha-alarmdotcom/issues/176) |
| Login notifications | Frequent official Alarm.com login notifications during camera use remain under investigation. Session synchronization fixes do not establish that notification frequency is resolved. | [#175](https://github.com/ibasebcast/ha-alarmdotcom/issues/175) |
| Doorbell press / capture | Motion detections and snapshots depend on camera/account events. A dedicated doorbell-press trigger or automatic recording/capture is not guaranteed. | [#110](https://github.com/ibasebcast/ha-alarmdotcom/issues/110) |
| Missing lights or thermostats | Check the exact integration login's device permissions, particularly Lights/Thermostats, before reinstalling. Activity permission is also needed for history features. | [Permissions](#permissions-for-a-dedicated-alarmcom-login) |
| Sensor timing and battery | Alarm.com may suppress, combine, or delay events, and may omit battery percentages. Diagnostic entities reflect supplied data, not independent measurements. | [Subsensors](#subsensors) |

## Troubleshooting and Contributing

Use **Settings > Devices & Services > Alarm.com** to download diagnostics or enable debug logging, reproduce the problem once, then disable logging. For camera analytics classification reports, enable `custom_components.alarmdotcom.camera_detection` at debug level.

[Open an issue](https://github.com/pyalarmdotcom/alarmdotcom/issues/new/choose) with your Home Assistant version, integration version, previous version/repository, device model, reproduction steps, and sanitized logs/diagnostics. Check the known issues above first and add evidence to an existing matching report when possible. Issues and pull requests are welcome.

Remove passwords, verification codes, session cookies, authentication headers, tokens, camera URLs, account/device IDs, email addresses, and personal details before posting. Review diagnostics even when automatic redaction is enabled.

## Maintainership, Credits, and History

Thanks to **Elhad Bar-Shai ([@elahd](https://github.com/elahd))**, **Justin Wong ([@uvjustin](https://github.com/uvjustin))**, and all original contributors for the foundation of this project. Current maintenance and modernization are led by [@ibasebcast](https://github.com/ibasebcast), building on the original v4 work and the maintained distribution developed since March 2026.

The original repository history, screenshots, contributor credits, and license notices remain preserved. See [CHANGELOG.md](CHANGELOG.md) for the full maintained development history and [release-notes/](release-notes/) for individual release notes. Older unqualified issue numbers there refer to the maintained repository unless stated otherwise.

If this work helps you, [Buy Me a Coffee](https://buymeacoffee.com/ibasebcast) supports ongoing maintenance.

## License

Original integration and library code retain their MIT notices in [LICENSE.md](LICENSE.md) and [LICENSE-upstream](LICENSE-upstream). Maintained contributions are distributed under the terms documented in [LICENSE](LICENSE) (Apache-2.0), subject to those retained upstream MIT notices.
