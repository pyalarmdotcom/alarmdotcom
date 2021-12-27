"""Common utility functions."""
from pyalarmdotcomajax import Alarmdotcom, AlarmdotcomADT, AlarmdotcomProtection1


def map_adc_provider(
    provider_name: str,
):
    if provider_name == "ADT":
        return AlarmdotcomADT
    elif provider_name == "Protection1":
        return AlarmdotcomProtection1
    else:
        return Alarmdotcom
