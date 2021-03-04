[Alarm.com Custom Component](https://github.com/uvjustin/alarmdotcom) for Home Assistant

# What This Is:
This is a custom component to allow Home Assistant to interface with the [Alarm.com](https://www.alarm.com/) site by scraping the Alarm.com web portal. This component is designed to integrate the Alarm.com security system functionality only - it requires an Alarm.com package which includes security system support, and it does not integrate any Alarm.com home automation functionality. Please note that Alarm.com may remove access at any time.

* Note that some providers are now requiring 2FA. If you have problem signing in and your web portal keeps nagging you to setup 2FA, please follow the instructions in the Two Factor Authentication section below.

## Installation / Usage with Home Assistant

1. Download this project as a zip file using GitHub's Clone or Download button at the top-right corner of the main project page.
2. Extract the contents locally.
3. Copy the directory alarmdotcom to config/custom_components/alarmdotcom on your HA installation.
4. Add an alarm_control_panel section to your HA configuration.yaml similar as documented in the configuration section below.


## Configuration

To enable this, download the contents of custom_components/ into the config/custom_components/ folder in your HA installation. Add the following lines to your `configuration.yaml`:

```yaml
# Example configuration.yaml entry
alarm_control_panel:
  - platform: alarmdotcom
    username: YOUR_USERNAME
    password: YOUR_PASSWORD
    # The below parameters are optional
    code: "01234"
    # force_bypass, no_entry_delay, and silent_arming are not supported on all systems/providers. See the description section below.
    force_bypass: "true"
    no_entry_delay: "home"
    silent_arming: "false"
    # two_factor_cookie is only used if your portal is forcing 2FA
    two_factor_cookie: "0000111122223333444455556666777788889999AAAABBBBCCCCDDDDEEEEFFFF0000"
```

<b>NOTE: It is recommended that you use !secret to specify credentials and codes. For more information on using secrets in HA click [here](https://www.home-assistant.io/docs/configuration/secrets/).</b>

## Description of configuration parameters
    username:
      description: Username for the Alarm.com account.
      required: true
      type: string

    password:
      description: Password for the Alarm.com account.
      required: true
      type: string

    name:
      description: The name of the alarm.
      required: false
      default: Alarm.com
      type: string
    
    code:
      description: Specifies a code to enable or disable the alarm in the frontend.
      required: false
      type: string

    #  The three options below are not available on all systems/providers. Also, some combinations of these options are incompatible. If arming does not work with some options, please check that you are able to arm via the web portal using those same options.

    force_bypass:
      description: Specifies when to use the "force bypass" setting when arming. Accepted values are "home", "away", "false" (never), "true" (always).
      required: false
      default: false
      type: string

    no_entry_delay:
      description: Specifies when to use the "no entry delay" setting when arming. Accepted values are "home", "away", "false" (never), "true" (always).
      required: false
      default: false
      type: string

    silent_arming:
      description: Specifies when to use the "silent arming" setting when arming. Accepted values are "home", "away", "false" (never), "true" (always).
      required: false
      default: false
      type: string

    #  The two_factor_cookie parameter below is for use with two factor authentication. See the Two Factor Authentication section.

    two_factor_cookie:
      description: Two factor authentication cookie used to bypass 2FA nag screens.
      required: false
      type: string

    #  The two parameters below are deprecated and will be removed in a future version.

    adt:
      description: Specifies whether or not to use the ADT login method to work around problems logging in to ADT accounts.
      required: false
      default: false
      type: boolean

    protection1:
      description: Specifies whether or not to use the Protection1 login method to work around problems logging in to Protection1 accounts.
      required: false
      default: false
      type: boolean
      

## Two Factor Authentication

Some providers (ADT and Protection1) are starting to require 2FA for logins. This can be worked around by getting the `twoFactorAuthenticationId` cookie from an already authenticated browser and entering it as a configuration parameter.

Simple steps to get the cookie:

    1) Temporarily remove your alarmdotcom config from configuration.yaml. (If the component is enabled it will keep trying to log in which will disrupt your initial 2FA setup.
    2) Log in to your account on the Alarm.com website: https://www.alarm.com/login.aspx
    3) You may be asked to enable Two Factor Authentication. Click Skip.
    4) Even after skipping the prior step, you will be asked for a one-time 2FA to register your device. Complete the 2FA process with your phone or email address. Note: For some reason, you may be required to complete this 2FA process twice.
    5) Once you are fully logged in to the alarm.com portal without any more 2FA nag screens, go into the developer tools in your browser and locate the twoFactorAuthenticationId cookie. Instructions for locating the cookie in Chrome can be found here: https://developers.google.com/web/tools/chrome-devtools/storage/cookies
    6) Copy the cookie string into your config under the `two_factor_cookie` parameter.
    7) Re-add the alarmdotcom config to your configuration.yaml and restart Home Assistant.


## Additional Features

Aside from control and alarm status information (disarmed/armed home/armed away), the plugin also publishes the status of individual sensors (contact/motion/glass break) as a comma-separated string within variable sensor_status.  This information can be parsed into individual binary sensors within the Home Assistant configuration.yaml as follows:

```yaml
# Example configuration.yaml entry for Binary Sensors
    binary_sensor:
      - platform: template
        sensors:
          # Contact Sensor
            alarm_front_door:
              friendly_name: "Front Door"
              device_class: door
              value_template: "{{ state_attr('alarm_control_panel.alarm_com', 'sensor_status')|regex_search('Front Door is Open', ignorecase=TRUE) }}"
          # Motion Sensor
            alarm_front_door_motion_detector:
              friendly_name: "Front Door Motion"
              device_class: motion
              value_template: "{{ state_attr('alarm_control_panel.alarm_com', 'sensor_status')|regex_search('Front Door Motion Detector is Activated', ignorecase=TRUE) }}"
```

<b>NOTE: The regex_search string must match the sensor status string exactly.  This information can be gleaned directly from the HA user interface by examining the value of the sensor_status variable using Developer Tools->States after the custom component has been configured</b>


## Multiple Alarm.com Installations

This module will not function directly with an Alarm.com account that is associated with multiple alarm systems.  In the event that your account is associated to multiple alarm systems it is recommended that you create one new sub-account per alarm system and only provide access to a single system to each sub-account.  The sub-account credentials can then be used within multiple alarmdotcom sections in the configuration.yaml.

For example:

```yaml
# Example configuration.yaml entry
alarm_control_panel:
  - platform: alarmdotcom
    name: work
    username: YOUR_WORK_ACCOUNT_USERNAME
    password: YOUR_WORK_ACCOUNT_PASSWORD
    force_bypass: "true"
    no_entry_delay: "home"
    silent_arming: "false"
  - platform: alarmdotcom
    name: home
    username: YOUR_HOME_ACCOUNT_USERNAME
    password: YOUR_HOME_ACCOUNT_PASSWORD
    force_bypass: "true"
    no_entry_delay: "home"
    silent_arming: "false"
```

<b>NOTE: It is recommended that you use !secret to specify credentials and codes.</b>
