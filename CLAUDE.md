# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an unofficial Home Assistant custom component that integrates Alarm.com security systems and devices. The integration communicates with Alarm.com's unofficial web API via the `pyalarmdotcomajax` library. It supports alarm panels, sensors, locks, lights, garage doors, thermostats, and other Alarm.com-connected devices.

**Important**: This is a safety-critical integration. Changes must be thoroughly tested and never rely on untested code for security functions.

## Code Architecture

### Component Structure

The integration follows Home Assistant's standard custom component architecture:

- **`custom_components/alarmdotcom/`**: Main integration directory
  - **`__init__.py`**: Integration setup, config entry management, and config entry migrations (v1→v5)
  - **`hub.py`**: Core controller (`AlarmHub`) that manages the pyalarmdotcomajax `AlarmBridge` API connection and WebSocket event monitoring
  - **`entity.py`**: Base classes for all Alarm.com entities
    - `AdcEntity`: Generic base entity with pub/sub event handling
    - `AdcEntityDescription`: Descriptor class using generics for type-safe entity definitions
  - **Platform files** (e.g., `alarm_control_panel.py`, `binary_sensor.py`, `lock.py`, `light.py`, `climate.py`, `cover.py`, `valve.py`, `button.py`): Implement specific Home Assistant platforms
  - **`config_flow.py`**: Configuration UI flow with OTP/2FA support
  - **`const.py`**: Constants and configuration options
  - **`util.py`**: Helper functions

### Data Flow

1. **Initialization** (`hub.py`):
   - `AlarmHub` creates `AlarmBridge` (from pyalarmdotcomajax) with credentials
   - `initialize()` logs into Alarm.com and fetches initial device state
   - WebSocket connection starts via `start_event_monitoring()` for real-time updates

2. **Entity Creation** (platform files):
   - Each platform's `async_setup_entry()` iterates through devices
   - Entities are created using descriptors (`AdcEntityDescription`)
   - Entities subscribe to event broker messages for their device

3. **State Updates**:
   - WebSocket events flow through pyalarmdotcomajax's event broker
   - `AdcEntity.event_handler()` receives messages (RESOURCE_ADDED, RESOURCE_UPDATED, RESOURCE_DELETED, CONNECTION_EVENT)
   - Each entity's `update_state()` method processes relevant changes
   - Entity calls `async_write_ha_state()` to update Home Assistant

4. **Device Control**:
   - User actions trigger entity methods (e.g., `async_alarm_arm_away()`)
   - Methods call controller functions from pyalarmdotcomajax (e.g., `PartitionController.arm_away()`)
   - Controllers send commands to Alarm.com API
   - WebSocket events confirm state changes

### Key Design Patterns

- **Generic Entity System**: Entity descriptors use Python generics (`AdcManagedDeviceT`, `AdcControllerT`) for type safety across device types
- **Event-Driven Architecture**: All state updates flow through pyalarmdotcomajax's pub/sub event broker system
- **Controller Pattern**: Each device type has a controller in pyalarmdotcomajax that handles API calls
- **Config Entry Migrations**: Version migrations in `__init__.py` handle config schema changes (currently at v5)

## Development Commands

### Linting and Type Checking

```bash
# Run all pre-commit hooks
pre-commit run --all-files

# Run Ruff linter with auto-fix
ruff check --fix .

# Run MyPy type checking
mypy .

# Run specific pre-commit hooks
pre-commit run ruff --all-files
pre-commit run mypy --all-files
pre-commit run codespell --all-files
pre-commit run yamllint --all-files
```

### Testing with Home Assistant

This integration is tested by installing it in a Home Assistant instance (there's no standalone pytest suite in this repo):

1. Copy `custom_components/alarmdotcom/` to a Home Assistant installation
2. Configure via Home Assistant UI: Configuration → Integrations → Add Integration → Alarm.com
3. Test with real Alarm.com credentials or use Home Assistant's test environment

### CI/CD

- **pre-commit**: Runs on all commits (via GitHub Actions on PRs and master)
- **hassfest**: Home Assistant's integration validation tool (runs daily and on PRs)
- **HACS validation**: Ensures HACS compatibility

## Important Technical Details

### Configuration Entry Versions

The integration uses config entry migrations to handle schema changes. Current version is 5. When adding new options:
- Update version in `config_flow.py`: `VERSION = X`
- Add migration logic in `__init__.py`: `async_migrate_entry()`
- Update `CONF_OPTIONS_DEFAULT` in `const.py` if needed

### WebSocket Connection Management

- WebSocket state is managed by pyalarmdotcomajax
- State handler (`_ws_state_handler` in `hub.py`) monitors connection health
- DEAD state raises `ConfigEntryNotReady` to trigger reconnection
- All state updates flow through WebSocket; HTTP polling is not used

### Arming Options

Three arming modes (home/away/night) each support three options:
- `force_bypass`: Bypass open zones when arming
- `silent_arming`: No beeps, double delay
- `no_entry_delay`: Skip entry delay

These are stored as lists in config options (e.g., `CONF_ARM_HOME = ["force_bypass", "silent_arming"]`).

### Entity Subsensors

Each device creates multiple entities:
- Primary entity (e.g., alarm panel, lock, sensor)
- Battery status entity (via `sensor_battery.py` or platform-specific implementations)
- Malfunction status entity (reported via device attributes)

### pyalarmdotcomajax Dependency

This integration is a thin wrapper around `pyalarmdotcomajax`. Most API logic lives in that library:
- Device resource management
- API authentication and session handling
- WebSocket connection
- Command execution

When adding support for new device types, changes often require updates to both repositories.

## Code Quality Standards

### Type Hints

- All functions must have type hints (enforced by MyPy with `disallow_untyped_defs = true`)
- Use `from __future__ import annotations` for forward references
- Import types under `if TYPE_CHECKING:` to avoid circular imports

### Logging

- Use module-level logger: `log = logging.getLogger(__name__)`
- Log levels:
  - `log.debug()`: Routine state changes, entity initialization
  - `log.info()`: Integration startup, connection events
  - `log.warning()`: Unexpected but recoverable issues
  - `log.error()`: Errors requiring user attention
- Include context in log messages (device names, IDs)

### Formatting

- Max line length: 120 characters
- Use Ruff for formatting and linting (config in `pyproject.toml`)
- Double quotes for strings
- Follow Home Assistant's entity naming conventions

## Common Workflows

### Adding Support for a New Device Type

1. Verify device appears in pyalarmdotcomajax's device list
2. If not, add to pyalarmdotcomajax first (device model, controller)
3. Create platform file in `custom_components/alarmdotcom/` (e.g., `switch.py`)
4. Define entity description(s) with controller function
5. Implement entity class extending `AdcEntity`
6. Add platform to `PLATFORMS` list in `const.py`
7. Test with real Alarm.com device

### Debugging Entity Issues

1. Enable debug logging in Home Assistant:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.alarmdotcom: debug
       pyalarmdotcomajax: debug
   ```
2. Fire debug event to dump device data:
   ```yaml
   service: homeassistant.fire_event
   data:
     event_type: alarmdotcom_debug_request
     event_data:
       resource_id: "<device_id>"
   ```
3. Check WebSocket connection state in logs
4. Verify device state in pyalarmdotcomajax resource manager

### Updating Dependencies

- **pyalarmdotcomajax**: Update version in `manifest.json` requirements and `.pre-commit-config.yaml` mypy additional_dependencies
- **Home Assistant**: Update in `requirements-dev.txt` and `.pre-commit-config.yaml` mypy additional_dependencies
- Version constraints use `>=` for minimum versions

## Related Resources

- **Main Repository**: https://github.com/pyalarmdotcom/alarmdotcom
- **pyalarmdotcomajax Library**: Separate package for Alarm.com API
- **Home Assistant Integration Docs**: https://developers.home-assistant.io/docs/creating_component_index/
- **Issue Tracker**: https://github.com/pyalarmdotcom/alarmdotcom/issues
