# `adc`

Interact with your Alarm.com alarm system from the command line.

**Usage**:

```console
$ adc [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--version`: Get installed pyalarmdotcom version.
* `--help`: Show this message and exit.

**Commands**:

* `stream`: Monitor alarm.com for real time updates. Use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc stream --help</span>&#x27; for details.
* `get`: Get a snapshot of system and device states. Use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get --help</span>&#x27; for details.
* `action`: Perform an action on a device in your alarm system. Use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc action --help</span>&#x27; for details.

## `adc stream`

Monitor alarm.com for real time updates. Command takes no options.

**Usage**:

```console
$ adc stream [OPTIONS]
```

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

## `adc get`

Get a snapshot of system and device states.

**Usage**:

```console
$ adc get [OPTIONS]
```

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-x, --include-unsupported`: Return basic data for all known unsupported devices. Always outputs in verbose format.
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

## `adc action`

Perform an action on a device in your alarm system.

**Usage**:

```console
$ adc action [OPTIONS] DEVICE_TYPE
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `system`: Perform an action on a system. Use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc system --help</span>&#x27; for details.
* `garage_door`: Perform an action on a garage door. Use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc garage_door --help</span>&#x27; for details.
* `light`: Perform an action on a light. Use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc light --help</span>&#x27; for details.
* `gate`: Perform an action on a gate. Use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc gate --help</span>&#x27; for details.
* `lock`: Perform an action on a lock. Use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc lock --help</span>&#x27; for details.
* `partition`: Perform an action on a partition. Use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc partition --help</span>&#x27; for details.
* `thermostat`: Perform an action on a thermostat. Use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc thermostat --help</span>&#x27; for details.
* `water_valve`: Perform an action on a water valve. Use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc water_valve --help</span>&#x27; for details.
* `image_sensor`: Perform an action on a image sensor. Use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc image_sensor --help</span>&#x27; for details.

### `adc action system`

Perform an action on a system.

**Usage**:

```console
$ adc action system [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `clear_alarms_in_memory`: Clear alarms in memory on a system.
* `clear_smoke_sensor`: Change status of a smoke sensor to closed.
* `stop_alarms`: Stop all alarms and disarm a system.

#### `adc action system clear_alarms_in_memory`

Clear alarms in memory on a system.

**Usage**:

```console
$ adc action system clear_alarms_in_memory [OPTIONS] SYSTEM_ID
```

**Arguments**:

* `SYSTEM_ID`: ID of the system on which to clear alarms.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

#### `adc action system clear_smoke_sensor`

Change status of a smoke sensor to closed.

**Usage**:

```console
$ adc action system clear_smoke_sensor [OPTIONS] SYSTEM_ID SMOKE_SENSOR_ID
```

**Arguments**:

* `SYSTEM_ID`: ID of the system to which the smoke system belongs.  [required]
* `SMOKE_SENSOR_ID`: ID of the smoke sensor to be cleared.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

#### `adc action system stop_alarms`

Stop all alarms and disarm a system.

**Usage**:

```console
$ adc action system stop_alarms [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

### `adc action garage_door`

Perform an action on a garage door.

**Usage**:

```console
$ adc action garage_door [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `close`: Close a garage door.
* `open`: Open a garage door.

#### `adc action garage_door close`

Close a garage door.

**Usage**:

```console
$ adc action garage_door close [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

#### `adc action garage_door open`

Open a garage door.

**Usage**:

```console
$ adc action garage_door open [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

### `adc action light`

Perform an action on a light.

**Usage**:

```console
$ adc action light [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `set_brightness`: Turn on a light and set its brightness.
* `turn_off`: Turn off a light.
* `turn_on`: Turn on a light.

#### `adc action light set_brightness`

Turn on a light and set its brightness.

**Usage**:

```console
$ adc action light set_brightness [OPTIONS] DEVICE_ID BRIGHTNESS
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]
* `BRIGHTNESS`: A dimmable light&#x27;s brightness. (Range: 0-100)  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

#### `adc action light turn_off`

Turn off a light.

**Usage**:

```console
$ adc action light turn_off [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

#### `adc action light turn_on`

Turn on a light.

**Usage**:

```console
$ adc action light turn_on [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

### `adc action gate`

Perform an action on a gate.

**Usage**:

```console
$ adc action gate [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `close`: Close a gate.
* `open`: Open a gate.

#### `adc action gate close`

Close a gate.

**Usage**:

```console
$ adc action gate close [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

#### `adc action gate open`

Open a gate.

**Usage**:

```console
$ adc action gate open [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

### `adc action lock`

Perform an action on a lock.

**Usage**:

```console
$ adc action lock [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `lock`: Lock a lock.
* `unlock`: Unlock a lock.

#### `adc action lock lock`

Lock a lock.

**Usage**:

```console
$ adc action lock lock [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

#### `adc action lock unlock`

Unlock a lock.

**Usage**:

```console
$ adc action lock unlock [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

### `adc action partition`

Perform an action on a partition.

**Usage**:

```console
$ adc action partition [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `arm_away`: Arm a partition in away mode.
* `arm_night`: Arm a partition in night mode.
* `arm_stay`: Arm a partition in stay mode.
* `change_sensor_bypass`: Bypass or unbypass sensors on a partition.
* `clear_faults`: Clear all faults on a partition.
* `disarm`: Disarm a partition.

#### `adc action partition arm_away`

Arm a partition in away mode.

**Usage**:

```console
$ adc action partition arm_away [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `--force-bypass / --no-force-bypass`: Bypass all open zones before arming.
* `--no-entry-delay / --no-no-entry-delay`: Bypass entry delay. This will sound the alarm immediately when an entry zone triggers.
* `--silent-arming / --no-silent-arming`: Arm the system without emitting arming \ exit delay tones at the panel.
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

#### `adc action partition arm_night`

Arm a partition in night mode.

**Usage**:

```console
$ adc action partition arm_night [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `--force-bypass / --no-force-bypass`: Bypass all open zones before arming.
* `--no-entry-delay / --no-no-entry-delay`: Bypass entry delay. This will sound the alarm immediately when an entry zone triggers.
* `--silent-arming / --no-silent-arming`: Arm the system without emitting arming \ exit delay tones at the panel.
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

#### `adc action partition arm_stay`

Arm a partition in stay mode.

**Usage**:

```console
$ adc action partition arm_stay [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `--force-bypass / --no-force-bypass`: Bypass all open zones before arming.
* `--no-entry-delay / --no-no-entry-delay`: Bypass entry delay. This will sound the alarm immediately when an entry zone triggers.
* `--silent-arming / --no-silent-arming`: Arm the system without emitting arming \ exit delay tones at the panel.
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

#### `adc action partition change_sensor_bypass`

Bypass or unbypass sensors on a partition.

**Usage**:

```console
$ adc action partition change_sensor_bypass [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `--bypass-ids TEXT`: List of sensors to bypass.
* `--unbypass-ids TEXT`: List of sensors to unbypass.
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

#### `adc action partition clear_faults`

Clear all faults on a partition.

**Usage**:

```console
$ adc action partition clear_faults [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

#### `adc action partition disarm`

Disarm a partition.

**Usage**:

```console
$ adc action partition disarm [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

### `adc action thermostat`

Perform an action on a thermostat.

**Usage**:

```console
$ adc action thermostat [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `set_state`: Set thermostat attributes.

#### `adc action thermostat set_state`

Set thermostat attributes.

Only one attribute can be set at a time, with the exception of --fan-mode and --fan-mode-duration, which must be set together.

**Usage**:

```console
$ adc action thermostat set_state [OPTIONS]
```

**Options**:

* `--id TEXT`: The ID of the thermostat.  [required]
* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `--state [OFF|HEAT|COOL|AUTO|AUXHEAT]`: The desired state of the thermostat.
* `--fan-mode [AUTO|ON|CIRCULATE]`: The desired fan mode.
* `--fan-mode-duration INTEGER`: The duration for which the desired fan mode should run. Fan duration must be in device&#x27;s list of supported durations.
* `--cool-setpoint FLOAT`: The desired cool setpoint.
* `--heat-setpoint FLOAT`: The desired heat setpoint.
* `--schedule-mode [MANUAL_MODE|SCHEDULED|SMART_SCHEDULES]`: The desired schedule mode.
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

### `adc action water_valve`

Perform an action on a water valve.

**Usage**:

```console
$ adc action water_valve [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `close`: Close a water valve.
* `open`: Open a water valve.

#### `adc action water_valve close`

Close a water valve.

**Usage**:

```console
$ adc action water_valve close [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

#### `adc action water_valve open`

Open a water valve.

**Usage**:

```console
$ adc action water_valve open [OPTIONS] DEVICE_ID
```

**Arguments**:

* `DEVICE_ID`: A device&#x27;s ID. To view a list of device IDs, use &#x27;<span style="color: #00ffff; text-decoration-color: #00ffff">adc get</span>&#x27;.  [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.

### `adc action image_sensor`

Perform an action on a image sensor.

**Usage**:

```console
$ adc action image_sensor [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `peek_in`: Take a peek in photo.

#### `adc action image_sensor peek_in`

Take a peek in photo.

**Usage**:

```console
$ adc action image_sensor peek_in [OPTIONS] ID
```

**Arguments**:

* `ID`: [required]

**Options**:

* `-u, --username TEXT`: Alarm.com username  [env var: ADC_USERNAME; required]
* `-p, --password TEXT`: Alarm.com password  [env var: ADC_PASSWORD; required]
* `-c, --cookie TEXT`: Two-factor authentication cookie. (Cannot be used with --otp!)  [env var: ADC_COOKIE]
* `-m, --otp-method [app|sms|email]`: OTP delivery method to use. Cannot be used alongside &quot;cookie&quot; argument. Defaults to <span style="color: #808000; text-decoration-color: #808000">app</span> if --otp is provided, otherwise prompts you for otp.
* `-o, --otp TEXT`: Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!
* `-n, --device-name TEXT`: Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.
* `-d, --debug`: Enable pyalarmdotcomajax&#x27;s debug logging.
* `-j, --json`: Return JSON output from device endpoints instead of formatted output.
* `--help`: Show this message and exit.
