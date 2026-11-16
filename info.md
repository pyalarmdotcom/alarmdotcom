# Alarm.com for Home Assistant

A maintained custom integration for Alarm.com security systems.

## Supported Devices

| Device | Actions |
|--------|---------|
| Alarm Panel | Arm Away, Arm Stay, Arm Night, Disarm |
| Garage Door / Gate | Open, Close |
| Lock | Lock, Unlock |
| Light | On, Off, Brightness |
| Thermostat | Heat, Cool, Auto, Fan, Schedule |
| Water Valve | Open, Close |
| Sensor | Contact, Motion, Smoke, CO, Water, Glass Break, Freeze |
| Camera | WebRTC live stream, Snapshot |

## Camera Setup

After installing, copy `www/alarm-webrtc-card.js` to your HA `www/` folder and add it as a Lovelace resource:

```yaml
url: /local/alarm-webrtc-card.js
type: module
```

Then add to any dashboard:

```yaml
type: custom:alarm-webrtc-card
entity: camera.your_camera_name
```

## Requirements

- Home Assistant 2025.5.0 or newer
- An active Alarm.com account with security system access
