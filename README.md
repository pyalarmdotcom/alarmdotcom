# Alarm.com Custom Component for [Home Assistant](https://www.home-assistant.io/)

![hacs installs](https://img.shields.io/endpoint?url=https%3A%2F%2Flauwbier.nl%2Fhacs%2Falarmdotcom)

![image](https://user-images.githubusercontent.com/466460/150609027-55be3eba-8364-4508-ad8d-835407e8782e.png)

## Intro

This is a custom component to allow Home Assistant to interface with the [Alarm.com](https://www.alarm.com/) site by scraping the Alarm.com web portal. This component is designed to integrate the Alarm.com security system functionality only - it requires an Alarm.com package which includes security system support.

Please note that Alarm.com may remove access at any time.

## Safety Warnings

This integration is great for casual use within Home Assistant but... **do not rely on this integration to keep you safe.**

1. This integration communicates with Alarm.com over an unofficial channel that can be broken or shut down at any time.
2. It may take several minutes for this device to receive a status update from Alarm.com's servers.
3. Your automations may be buggy.
4. This code may be buggy.

You should use Alarm.com's official apps, devices, and services for notifications of all kind related to safety, break-ins, property damage (i.e.: freeze sensors), etc.

## Supported Devices

| Device Type  | Actions                               | View Status | Low Battery Sub-Sensor | Malfunction Sub-Sensor |
| ------------ | ------------------------------------- | ----------- | ---------------------- | ---------------------- |
| Alarm System | arm away, arm stay, arm night, disarm | ✔           |                        | ✔                      |
| Sensor       | _(none)_                              | ✔           | ✔                      | ✔                      |
| Lock         | lock, unlock                          | ✔           | ✔                      | ✔                      |
| Garage Door  | open, close                           | ✔           |                        |                        |
| Light        | turn on / set brightness, turn off    | ✔           |                        |                        |

As of v0.2.0, multiples of all of the above devices are supported.

## Supported Sensor Types

1. Contact Sensor
2. Smoke Detector
3. CO Detector
4. Panic Button
5. Glass Break Detector

### Subsensors

<details>
<summary><b>What are subsensors?</b></summary>
Each sensor in your system is created as both a device and as an entity within Home Assistant. Each sensor and lock has an associated low battery sensor that activates when the device's battery is low. Each sensor, lock, and control panel has an associated malfunction sensor that activates when either Alarm.com reports an issue or when this integration is unable to process data for a sensor.

![image](https://user-images.githubusercontent.com/466460/150608118-ac6fa640-48c0-41ca-8cbf-4cbc4b142b91.png)

</details>

## Installation

1. Use [HACS](https://hacs.xyz/) to download this integration.
2. Configure the integration via Home Assistant's Integrations page. (Configuration -> Add Integration -> Alarm.com)
3. When prompted, enter your Alarm.com username, password, and two-factor authentication one-time password.

## Configuration

You'll be prompted to enter these parameters when configuring the integration.

| Parameter         | Required | Description                                                   |
| ----------------- | -------- | ------------------------------------------------------------- |
| Username          | Yes      | Username for your Alarm.com account.                          |
| Password          | Yes      | Password for your Alarm.com account.                          |
| One-Time Password | Maybe    | Required for accounts with two-factor authentication enabled. |

### Two-Factor Authentication Cookie

As of v0.2.7-beta8, this integration prompts for a one-time password during log in and retrieves a two-factor cookie automatically.

### Additional Options

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
