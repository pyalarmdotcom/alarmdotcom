[Alarm.com Custom Component](https://github.com/uvjustin/alarmdotcomajax) for homeassistant

# What This Is:
This is a custom component to allow Home Assistant to interface with the [Alarm.com](https://www.alarm.com/) site by scraping the Alarm.com web portal. This component is designed to integrate the Alarm.com security system functionality only - it requires an Alarm.com package which includes security system support, and it does not integrate any Alarm.com home automation functionality. Please note that Alarm.com may remove access at any time.


## Installation / Usage with Home Assistant

1. Download this project as a zip file using GitHub's Clone or Download button at the top-right corner of the main project page.
2. Extract the contents locally.
3. Copy directory alarmdotcomajax to config/custom_components/alarmdotcomajax on your HA installation.
4. Add an alarm_control_panel section to your HA configuration.yaml similar as documented in the configuration section below.


## Configuration

To enable this, download the contents of custom_components/ into the config/custom_components/ folder in your HA installation. Add the following lines to your `configuration.yaml`:

```yaml
# Example configuration.yaml entry
alarm_control_panel:
  - platform: alarmdotcomajax
    username: YOUR_USERNAME
    password: YOUR_PASSWORD
    code: "01234"
    force_bypass: "true"
    no_entry_delay: "home"
    silent_arming: "false"
```

<b>NOTE: It is recommended that you use !secret to specify credentials and codes.</b>

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
      

## Additional Features

Aside from control and alarm status information (disarmed/armed home/armed away) the plugin also publishes the status of individual sensors (contact/motion/glass break) as a comma-separated string within variable sensor_status.  This information can be parsed into individual binary sensors within the Home Assistant configuration.yaml as follows:

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

This module will not function directly with an Alarm.com account that is associated with multiple alarm systems.  In the event that your account is associated to multiple alarm systems it is recommended that you create one new sub-account per alarm system, and only provide access to a single system to each sub-account.  The sub-account credentials can then be used within multiple alarmdotcomajax sections in the configuration.yaml.

For example:

```yaml
# Example configuration.yaml entry
alarm_control_panel:
  - platform: alarmdotcomajax
    name: work
    username: YOUR_WORK_ACCOUNT_USERNAME
    password: YOUR_WORK_ACCOUNT_PASSWORD
    force_bypass: "true"
    no_entry_delay: "home"
    silent_arming: "false"
  - platform: alarmdotcomajax
    name: home
    username: YOUR_HOME_ACCOUNT_USERNAME
    password: YOUR_HOME_ACCOUNT_PASSWORD
    force_bypass: "true"
    no_entry_delay: "home"
    silent_arming: "false"
```

<b>NOTE: It is recommended that you use !secret to specify credentials and codes.</b>
