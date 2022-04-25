---
name: Request support for a new device
about: Help us support new Alarm.com devices
title: "[NEW DEVICE] "
labels: new device
assignees: ""
---

The alarmdotcom maintainers don't have direct access to all Alarm.com devices. We need your help to support new devices.

Please open one issue per device.

**Which device would you like us to support?**
Provide the device name and a link to a page with device details.
(E.g.: Intelligent Thermostat: https://suretyhome.com/product/intelligent-thermostat/)

**Where does this device appear in the Alarm.com mobile app?**
Security System, Images, Locks, Garage Doors, etc.

**What types of actions does this device support?**
E.g.: Garage doors support opening and closing. Alarm systems support arming (home, away, and night modes) and disarming.

**Which provider do you use?**
E.g.: Alarm Net, ADT, Surety Home, etc.

**Include pyalarmdotcomajax Server Output**
This is an important step. It's helpful for us to see how this device is represented on the Alarm.com server. We have a tool for dumping this data via the command line.

1. Install [Python >= 3.9](https://www.python.org/downloads/).
2. Install [pyalarmdotcomajax](https://github.com/uvjustin/pyalarmdotcomajax) via pip: `pip install pyalarmdotcomajax`.
3. Run `adc -u YOUR_USERNAME -p YOUR_PASSWORD -c YOUR_2FA_COOKIE -vx`
4. The above command dumps server data for all devices that are known to ADC developers, including a few devices that are currently unsupported. **Heads Up!** This command may leak sensitive information. It does _not_ dump your email address, address, or any other account information, but it may output coordinates from GPS devices (like an Alarm.com car sensor) and names of family members (e.g.: Michael's Room Window Sensor). Be sure to review the data before posting to scrub anything that you're not comfortable posting online.

**Include Action Endpoints**
This is a more technical than the last step, but in order to support actions for devices we need you to use a tool like [Wireshark](https://www.wireshark.org/) of [Fiddler Classic](https://www.telerik.com/fiddler/fiddler-classic) to tell use which endpoints the Alarm.com app uses to control these devices. For example, for a garage door, we would need the following information:

> Base URL: `https://www.alarm.com/web/api/devices/garageDoors/`
> Open Suffix: `open`
> Close Suffix: `close`

(Opening a garage door requires submitting a request to `https://www.alarm.com/web/api/devices/garageDoors/open`.)
