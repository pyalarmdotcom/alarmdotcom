"""Alarm.com model for partitions."""

from dataclasses import dataclass, field
from enum import IntEnum

from _pyalarmdotcomajax.models.base import (
    AdcDeviceResource,
    AdcResourceAttributes,
    BaseManagedDeviceAttributes,
    ResourceType,
)
from _pyalarmdotcomajax.util import get_all_related_entity_ids


class PartitionState(IntEnum):
    """Partition states."""

    UNKNOWN = 0
    DISARMED = 1
    ARMED_STAY = 2
    ARMED_AWAY = 3
    ARMED_NIGHT = 4
    HIDDEN = 5

    @classmethod
    def _missing_(cls: type, value: object) -> "PartitionState":
        """Set default enum member if an unknown value is provided."""
        return PartitionState.UNKNOWN


class ExtendedArmingOptionItems(IntEnum):
    """Partition arming options."""

    BYPASS_SENSORS = 0
    NO_ENTRY_DELAY = 1
    SILENT_ARMING = 2
    NIGHT_ARMING = 3
    SELECTIVELY_BYPASS_SENSORS = 4
    FORCE_ARM = 5

    @classmethod
    def _missing_(cls: type, value: object) -> "ExtendedArmingOptionItems":
        """Set default enum member if an unknown value is provided."""
        return ExtendedArmingOptionItems.BYPASS_SENSORS


@dataclass
class ExtendedArmingOptions(AdcResourceAttributes):
    """Extended arming options."""

    disarmed: list[ExtendedArmingOptionItems] | list[list[ExtendedArmingOptionItems]] | None = field(default=None)
    armed_stay: list[ExtendedArmingOptionItems] | list[list[ExtendedArmingOptionItems]] | None = field(default=None)
    armed_away: list[ExtendedArmingOptionItems] | list[list[ExtendedArmingOptionItems]] | None = field(default=None)
    armed_night: list[ExtendedArmingOptionItems] | list[list[ExtendedArmingOptionItems]] | None = field(default=None)


def _flatten_options(
    options: list[ExtendedArmingOptionItems] | list[list[ExtendedArmingOptionItems]] | None,
) -> list[ExtendedArmingOptionItems]:
    """Flatten nested option lists returned by Alarm.com."""

    if not options:
        return []

    flattened: list[ExtendedArmingOptionItems] = []
    for option in options:
        if isinstance(option, list):
            flattened.extend(item for item in option if isinstance(item, ExtendedArmingOptionItems))
        elif isinstance(option, ExtendedArmingOptionItems):
            flattened.append(option)
    return flattened


@dataclass
class PartitionAttributes(BaseManagedDeviceAttributes[PartitionState]):
    """Attributes of partition."""

    desired_state: PartitionState | None = field(
        metadata={"description": "Desired device state."},
        default=None,
    )
    state: PartitionState = field(
        metadata={"description": "Current device state."},
        default=PartitionState.UNKNOWN,
    )

    extended_arming_options: ExtendedArmingOptions = field(
        metadata={"description": "The supported extended arming options for each arming mode."},
        default_factory=ExtendedArmingOptions,
    )
    invalid_extended_arming_options: ExtendedArmingOptions = field(
        metadata={"description": "The combinations of extended arming options that are invalid for each arming mode."},
        default_factory=ExtendedArmingOptions,
    )

    # fmt: off
    can_bypass_sensor_when_armed: bool = field(metadata={"description": "Indicates if the panel supports bypass commands when armed."}, default=False)
    has_open_bypassable_sensors: bool = field(metadata={"description": "Indicates if the partition has any open sensors that can be bypassed."}, default=False)
    has_sensor_in_trouble_condition: bool = field(metadata={"description": "Indicates if the partition has any sensors in a trouble condition."}, default=False)
    hide_force_bypass: bool = field(metadata={"description": "Indicates if the force bypass checkbox should be hidden. If hidden, force bypass is always enabled."}, default=False)
    needs_clear_issues_prompt: bool = field(metadata={"description": "Indicates if the user should be prompted about any present issues before allowing arming."}, default=False)
    partition_id: str = field(metadata={"description": "The ID of this partition."}, default="1")
    has_active_alarm: bool = field(metadata={"description": "Indicates if the partition has an active alarm."}, default=False)
    has_only_arming: bool = field(metadata={"description": "Indicates if the partition only has a generic 'arm' options and not arm away and arm stay."}, default=False)
    # fmt: on

    @property
    def supports_night_arming(self) -> bool:
        """Return whether night arming is supported."""

        return ExtendedArmingOptionItems.NIGHT_ARMING in _flatten_options(
            self.extended_arming_options.armed_night
        )



@dataclass
class Partition(AdcDeviceResource[PartitionAttributes]):
    """Partition resource."""

    resource_type = ResourceType.PARTITION
    attributes_type = PartitionAttributes

    @property
    def items(self) -> set[str]:
        """Return list of child item IDs for this partition."""

        return get_all_related_entity_ids(self.api_resource) - {self.system_id}
