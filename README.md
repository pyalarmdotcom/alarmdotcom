[Alarm.com Custom Component](https://github.com/uvjustin/alarmdotcomajax) for homeassistant

# What This Is:
This is a custom component to allow Home Assistant to interface with the [Alarm.com](https://www.alarm.com/) site by scraping the Alarm.com web portal. Please note that Alarm.com may remove access at any time.

## Configuration

To enable this, download the contents of custom_components/ into the config/custom_components/ folder in your HA installation. Add the following lines to your `configuration.yaml`:

```yaml
# Example configuration.yaml entry
alarm_control_panel:
  platform: alarmdotcomajax
  username: YOUR_USERNAME
  password: YOUR_PASSWORD
```

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
      type: integer

    force_bypass:
      description: Specifies whether to use the force_bypass setting when arming.
      required: false
      default: false
      type: boolean

    no_entry_delay:
      description: Specifies whether to use the no_entry_delay setting when arming.
      required: false
      default: false
      type: boolean
