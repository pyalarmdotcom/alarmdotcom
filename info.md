# Version 0.2.0

## 💡 New Features

1. Alarm panel, locks, garage doors, and sensors now appear as individual devices in Home Assistant.
2. Support for opening and closing garage doors.
3. Support for _multiple_ locks, alarm panels, and garage doors.
4. Removes requirement to BYO two-factor authentication cookie. Integration now asks for a one-time password when logging in and gets the two-factor cookie for you.
5. Locks, alarm panels, and sensors each have malfunction sub-sensors.
6. Locks and sensors each have low battery sub-sensors.
7. Configuration now handled via Home Assistant's UI instead of configuration.yaml.

## ⚠️ Breaking Changes

1. Rolled back support for thermostats. We need more information to roll out full support. Have an Alarm.com thermostat and want to help? Open a GitHub issue!

## ⬆️ Upgrading from v0.1?

Your settings will be copied over to the new configuration interface automatically. Check that your settings have copied over correctly, then delete the existing alarmdotcom entry from your configuration.yaml file.

Verify that your options (including your arming code) have copied over correctly by clicking on the "Configure" button on the Alarm.com card on the Home Assistant integrations page.

![image](https://user-images.githubusercontent.com/466460/150624822-10e83560-d888-4bc1-9b2b-7024b97cae2d.png)

## ❤️ Thanks for Contributing
### Code
@kevin-david, @vegardengen, @AritroSaha10 
### Beta Testers
@mjmicks, @Somapolice, @AdventureAhead, @robin-vandaele, @nicocoetzee, @kitracer, @DannoPeters, @insideoud, @BinaryShrub
