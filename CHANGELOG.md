# alarmdotcom CHANGELOG

## Version 0.2.0

### 💡 New Features

1. Alarm panel, locks, garage doors, and sensors now appear as individual devices in Home Assistant.
2. Support for opening and closing garage doors.
3. Support for _multiple_ locks, alarm panels, and garage doors.
4. Removes requirement to BYO two-factor authentication cookie. Integration now asks for a one-time password when logging in and gets the two-factor cookie for you.
5. Locks, alarm panels, and sensors each have malfunction sub-sensors.
6. Locks and sensors each have low battery sub-sensors.
7. Configuration now handled via Home Assistant's UI instead of configuration.yaml.

### ⚠️ Breaking Changes

1. Rolled back support for thermostats. We need more information to roll out full support. Have an Alarm.com thermostat and want to help? Open a GitHub issue!

### ⬆️ Upgrading from v0.1?

Your settings will be copied over to the new configuration interface automatically. Check that your settings have copied over correctly, then delete the existing alarmdotcom entry from your configuration.yaml file.

Verify that your options (including your arming code) have copied over correctly by clicking on the "Configure" button on the Alarm.com card on the Home Assistant integrations page.

![image](https://user-images.githubusercontent.com/466460/150624822-10e83560-d888-4bc1-9b2b-7024b97cae2d.png)

### ❤️ Thanks for Contributing
#### Code
@kevin-david, @vegardengen, @AritroSaha10 
#### Beta Testers
@mjmicks, @Somapolice, @AdventureAhead, @robin-vandaele, @nicocoetzee, @kitracer, @DannoPeters, @insideoud, @BinaryShrub

## Version 0.1.12
- Add lock support

## Version 0.1.11
2021-12-13
- Use version 0.1.12 of the pyalarmdotcomajax library: sensor json field rename
- Use extra_state_attributes instead of deprecated device_state_attributes

## Version 0.1.10
2021-03-31
- Use version 0.1.11 of the pyalarmdotcomajax library: add armed night state

## Version 0.1.9
2020-12-22
- Use version 0.1.10 of the pyalarmdotcomajax library: fix login problem from 0.1.7 refactoring

## Version 0.1.8
2020-12-15
- Use version 0.1.8 of the pyalarmdotcomajax library: add 2FA cookie

## Version 0.1.7
2020-12-13
- Use version 0.1.7 of the pyalarmdotcomajax library: add workaround for Protection1 and add garage status

## Version 0.1.6
2020-11-22
- Rename component to alarmdotcom

## Version 0.1.5
2020-11-16
- Use version 0.1.6 of the pyalarmdotcomajax library: add thermostat status

## Version 0.1.4
2020-11-14
- Use version 0.1.4 of the pyalarmdotcomajax library: add workaround for ADT logins

## Version 0.1.3
2020-09-02
- Use version 0.1.3 of the pyalarmdotcomajax library: omit arming parameters when false and only relogin on 403 error.

## Version 0.1.2
2020-05-21
- Change AlarmControlPanel to AlarmControlPanelEntity

## Version 0.1.1
2020-03-22
- Added option for silent arming and differentiated home and away treatment for forcebypass/noentrydelay/silentarming settings.

## Version 0.1.0
2020-03-19
- Initial release.
