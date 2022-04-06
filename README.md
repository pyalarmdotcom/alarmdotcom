# Alarm.com Custom Component for [Home Assistant](https://www.home-assistant.io/)

![hacs installs](https://img.shields.io/endpoint?url=https%3A%2F%2Flauwbier.nl%2Fhacs%2Falarmdotcom)

![image](https://user-images.githubusercontent.com/466460/150609027-55be3eba-8364-4508-ad8d-835407e8782e.png)

## Intro

This is a custom component to allow Home Assistant to interface with the [Alarm.com](https://www.alarm.com/) site by scraping the Alarm.com web portal. This component is designed primarily integrate the Alarm.com security system functions, so it requires an Alarm.com package which includes security system support. We're just starting to add support for smart devices like lights, garage doors, etc.

Please note that Alarm.com may break functionality at any time.

## Safety Warnings

This integration is great for casual use within Home Assistant but... **do not rely on this integration to keep you safe.**

1. This integration communicates with Alarm.com over an unofficial channel that can be broken or shut down at any time.
2. It may take several minutes for this device to receive a status update from Alarm.com's servers.
3. Your automations may be buggy.
4. This code may be buggy. It's written by volunteers in their free time and testing is spotty.

You should use Alarm.com's official apps, devices, and services for notifications of all kinds related to safety, break-ins, property damage (i.e.: freeze sensors), etc.

Where possible, use local control for smart home devices that are natively supported by Home Assistant (lights, garage door openers, etc.). Locally controlled devices will continue to work during internet outages whereas this integraiton will not.

## Details

### Supported Devices

| Device Type  | Actions                               | View Status | Low Battery Sub-Sensor | Malfunction Sub-Sensor |
| ------------ | ------------------------------------- | ----------- | ---------------------- | ---------------------- |
| Alarm System | arm away, arm stay, arm night, disarm | ✔           |                        | ✔                      |
| Sensor       | _(none)_                              | ✔           | ✔                      | ✔                      |
| Lock         | lock, unlock                          | ✔           | ✔                      | ✔                      |
| Garage Door  | open, close                           | ✔           |                        |                        |
| Light        | turn on / set brightness, turn off    | ✔           |                        |                        |

As of v0.2.0, multiples of all of the above devices are supported.

### Supported Sensor Types

| Sensor Type             | Notes                                                                                                                                                                                                                                                                                                                                           |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Contact Sensor          | Doors, windows, etc.                                                                                                                                                                                                                                                                                                                            |
| Smoke                   | Both integrated units (i.e.: [First Alert ZCOMBO](https://www.firstalert.com/smoke-carbon-monoxide-alarms/combo-smoke-carbon-monoxide-alarms/wireless-smoke-carbon-monoxide-alarm-works-with-zwave-ring/SAP_ZCOMBO.html)) and listeners (i.e. [Encore FireFighter [PDF]](https://2gig.com/wp-content/uploads/Encore-Firefighter-specs-345.pdf)) |
| Carbon Monoxide         | _(See above.)_                                                                                                                                                                                                                                                                                                                                  |
| Panic                   |                                                                                                                                                                                                                                                                                                                                                 |
| Glass Break / Vibration | Both standalone listeners (i.e.: [DSC PGx922](https://www.dsc.com/?n=products&o=view&id=2585)) & control-panel built-ins (i.e. [Qolsys IQ Panel 4](https://qolsys.com/panel-glass-break/)).                                                                                                                                                     |

Note that Alarm.com can has multiple designations for each sensor and not all are known to the developers of this integration. If you have one of the above listed devices but don't see it in Home Assistant, [open an issue on GitHub](https://github.com/uvjustin/alarmdotcom/issues/new/choose).

#### Subsensors

Each sensor in your system is created as both a device and as an entity within Home Assistant. Each sensor and lock has an associated low battery sensor that activates when the device's battery is low. Each sensor, lock, and control panel has an associated malfunction sensor that activates when either Alarm.com reports an issue or when this integration is unable to process data for a sensor.

![image](https://user-images.githubusercontent.com/466460/150608118-ac6fa640-48c0-41ca-8cbf-4cbc4b142b91.png)

### Future Support

#### Roadmapped Devices

The developers have access to the devices listed below and plan to add support in a future release.

| Device Type  | Notes                                                                                                                                                 |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Image Sensor | _Not_ video cameras. Image sensors (i.e.: [Qolsys Image Sensor](https://qolsys.com/image-sensor/)) take still photos when triggered by motion events. |

#### Help Wanted Devices

If you own one of the below devices and want to help build support, [open an issue on GitHub](https://github.com/uvjustin/alarmdotcom/issues/new/choose).

| Device Type        | Notes                                                                                                                    | Help Needed |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------ | ----------- |
| RGB Light          | i.e.: [Inovelli RGBW Smart Bulb](https://inovelli.com/rgbw-smart-bulb-z-wave/)                                           | A lot.      |
| Video Camera       | i.e.: [Alarm.com ADC-V515](https://www.alarmgrid.com/products/alarm-com-adc-v515)                                        | A lot.      |
| Water Valve        | i.e.: [Dome Water Main Shut-off](https://www.domeha.com/z-wave-water-main-shut-off-valve)                                | A lot.      |
| Thermostat         | i.e.: [Alarm.com Intelligent Thermostat](https://suretyhome.com/product/intelligent-thermostat/)                         | A lot.      |
| Leak Sensor        | i.e.: [Dome Leak Sensor](https://www.domeha.com/z-wave-leak-sensor)                                                      | A little.   |
| Temperature Sensor | i.e.: [Alarm.com PowerG Wireless Temperature Sensor](https://suretyhome.com/product/powerg-wireless-temperature-sensor/) | A little.   |

##### Help Needed Scale

- **A lot:** You'll need to know how to capture web traffic. We'll ask you to log into Alarm.com and use your web browser's network inspector tool to capture requests for all of your device's functions.
- **A little:** We'll ask you to run a Python script to dump metadata for your devices. This is straightforward and doesn't require much technical skill.

#### Device Blacklist

These devices are known but blocked from appearing in Home Assistant. If you disagree with any of these blacklisting reasons, please [open an issue on GitHub](https://github.com/uvjustin/alarmdotcom/issues/new/choose)!

| Device Type        | Reason                                                                                                                                                                                                                                                                                                                                                      |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Motion Sensors     | This integration receives updates from Alarm.com on a delay, meaning that many motion detection events will be missed. This update paradaigm is too unreliable to use in automations. Note that we do still plan to show battery and malfunction subsensors for motion sensors, as discussed in [#106](https://github.com/uvjustin/alarmdotcom/issues/106). |
| Mobile Phones      | Some control panels support PIN-less proximity unlocking via bluetooth (i.e.: [Qolsys IQ Panel 4](https://qolsys.com/bluetooth/)). Paired mobile phones appear in Alarm.com as sensors, but don't provide any useful functions or information for use in Home Assistant (not even malfunction or battery level).                                            |
| Audio Systems      | Alarm.com supports Sonos systems, but Home Assistant has a better, built-in integration for these devices.                                                                                                                                                                                                                                                  |
| Irrigation Systems | Like above, Home Assistant probably has better direct integrations for these devices.                                                                                                                                                                                                                                                                       |
| Blinds and Shades  | _(See above.)_                                                                                                                                                                                                                                                                                                                                              |

## Using the Integration

### Installation

1. Use [HACS](https://hacs.xyz/) to download this integration.
2. Configure the integration via Home Assistant's Integrations page. (Configuration -> Add Integration -> Alarm.com)
3. When prompted, enter your Alarm.com username, password, and two-factor authentication one-time password.

### Configuration

You'll be prompted to enter these parameters when configuring the integration.

| Parameter         | Required | Description                                                   |
| ----------------- | -------- | ------------------------------------------------------------- |
| Username          | Yes      | Username for your Alarm.com account.                          |
| Password          | Yes      | Password for your Alarm.com account.                          |
| One-Time Password | Maybe    | Required for accounts with two-factor authentication enabled. |

#### Two-Factor Authentication Cookie

As of v0.2.7, this integration prompts for a one-time password during log in and retrieves a two-factor cookie automatically.

#### Additional Options

These options can be set using the "Configure" button on the Alarm.com card on Home Assistant's Integrations page:

![image](https://user-images.githubusercontent.com/466460/150607393-e057d445-a882-4fbd-a455-acf155083327.png)

| Parameter       | Description                                                                                                                                                                                                                                                                                    |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Code            | Specifies a code to arm/disarm your alarm or lock/unlock your locks in the Home Assistant frontend. This is not necessarily the code you use to arm/disarm your panel. This is a separate code that Home Assistant in [alarm panel card](https://www.home-assistant.io/lovelace/alarm-panel/). |
| Force Bypass    | Bypass open zones (windows, doors, etc.) when arming.                                                                                                                                                                                                                                          |
| Arming Delay    | Wait after issuing arm command to give you time to exit.                                                                                                                                                                                                                                       |
| Silent Arming   | Suppress beeps when arming and double arming delay.                                                                                                                                                                                                                                            |
| Update Interval | Frequency with which this integration should poll Alarm.com servers for updated status.                                                                                                                                                                                                        |

_The three arming options are not available on all systems/providers. Also, some combinations of these options are incompatible. If arming does not work with a combination of options, please check that you are able to arm via the web portal using those same options._
