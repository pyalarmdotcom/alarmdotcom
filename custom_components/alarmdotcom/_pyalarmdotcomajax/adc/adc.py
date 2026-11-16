"""adc core CLI functions."""

# ruff: noqa: FBT002
import asyncio
import logging
import sys
from functools import partial
from typing import TYPE_CHECKING, Annotated

import typer
from _pyalarmdotcomajax._version import __version__
from _pyalarmdotcomajax.adc.common import bridge, collect_params
from _pyalarmdotcomajax.adc.util import (
    AsyncTyper,
    summarize_cli_actions,
    with_paremeters,
)
from _pyalarmdotcomajax.events import ResourceEventMessage
from _pyalarmdotcomajax.util import resources_pretty, resources_raw, slug_to_title
from _pyalarmdotcomajax.websocket.client import ConnectionEvent, WebSocketState
from rich import print
from rich.console import Group
from rich.logging import RichHandler
from rich.panel import Panel

if TYPE_CHECKING:
    from _pyalarmdotcomajax import AlarmBridge
    from _pyalarmdotcomajax.events import EventBrokerMessage

logging.basicConfig(
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[RichHandler(rich_tracebacks=True)],
)

############
# MAIN APP #
############

app = AsyncTyper(
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def version_callback(value: bool) -> None:
    """Print the version and exit."""
    if value:
        print(f"pyalarmdotcomajax version: {__version__}")
        raise typer.Exit()


@app.callback()
def adc_callback(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            help="Get installed pyalarmdotcom version.",
            callback=version_callback,
            is_eager=True,
            show_default=False,
        ),
    ] = False,
) -> None:
    """Interact with your Alarm.com alarm system from the command line."""


############
# COMMANDS #
############


@app.command(
    short_help="Monitor alarm.com for real time updates. Use '[bright_cyan]adc stream --help[/bright_cyan]' for details.",
    add_help_option=True,
)
@with_paremeters(collect_params)
async def stream(
    ctx: typer.Context,
) -> None:
    """Monitor alarm.com for real time updates. Command takes no options."""

    bridge: AlarmBridge = ctx.obj["bridge"]

    print("\n")

    print(
        Panel(
            "[black on yellow bold]EVENT MONITOR[/black on yellow bold]",
            border_style="black",
            style="black on yellow",
        )
    )
    print("\n[bold](Press Ctrl+C to exit.)\n\n")

    async with bridge:
        bridge.subscribe(partial(handle_event, ctx.params["json"]))

        try:
            # Keep event loop alive until cancelled.
            while True:  # noqa: ASYNC110
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass


@app.command(
    add_help_option=True,
    short_help="Get a snapshot of system and device states. Use '[bright_cyan]adc get --help[/bright_cyan]' for details.",
)
@with_paremeters(collect_params)
async def get(
    ctx: typer.Context,
    include_unsupported: Annotated[
        bool | None,
        typer.Option(
            "--include-unsupported",
            "-x",
            help="Return basic data for all known unsupported devices. Always outputs in verbose format.",
            show_default=False,
        ),
    ] = False,
) -> None:
    """Get a snapshot of system and device states."""

    bridge: AlarmBridge = ctx.obj["bridge"]

    print("\n")

    print(
        Panel(
            "[black on yellow bold]GET SYSTEM STATUS[/black on yellow bold]",
            border_style="black",
            style="black on yellow",
        )
    )

    if include_unsupported:
        output = bridge.device_catalogs.included_raw_str
    elif ctx.params["json"]:
        output = bridge.resources_raw
    else:
        output = bridge.resources_pretty

    print(Group(output, ""))


###########
# HELPERS #
###########


def handle_event(json: bool, message: "EventBrokerMessage") -> None:
    """Handle event broker events."""

    if isinstance(message, ResourceEventMessage):
        event_printer(json, message)

    if isinstance(message, ConnectionEvent):
        ws_state_printer(message)


def ws_state_printer(message: "EventBrokerMessage") -> None:
    """Print WebSocket state."""

    if not isinstance(message, ConnectionEvent):
        return

    if message.current_state in [WebSocketState.RECONNECTED]:
        print("[green]Reconnected to Alarm.com...")
    elif message.current_state == WebSocketState.CONNECTING:
        print("[orange1]Connecting to Alarm.com...")
    elif message.current_state == WebSocketState.DISCONNECTED:
        print(
            f"[red]Disconnected from Alarm.com. Next reconnect attempt in {message.next_attempt_s} seconds."
        )
    elif message.current_state == WebSocketState.DEAD:
        print("[red]Streaming stopped. Connection to Alarm.com is dead.")
        typer.Exit(1)
    elif message.current_state == WebSocketState.CONNECTED:
        print("[green]Connected to Alarm.com.")
        print("[yellow]Streaming real-time updates...")


def event_printer(verbose: bool, message: ResourceEventMessage) -> None:
    """Print event."""

    if message.resource:
        title = (
            f"Event Notification > {slug_to_title(message.topic.name)} > {message.id}"
        )
        if verbose:
            print(resources_raw(title, [message.resource]))
        else:
            print(resources_pretty(title, [message.resource]))


##############
# ACTION APP #
##############

action_app = AsyncTyper(
    no_args_is_help=True,
    add_completion=False,
    add_help_option=True,
    subcommand_metavar="DEVICE_TYPE",
    short_help="Perform an action on a device in your alarm system. Use '[bright_cyan]adc action --help[/bright_cyan]' for details.",  # Redundancy required to prevent cropping in Typer markdown output.
    help="Perform an action on a device in your alarm system.",
)


# Dynamically add device types and their @cli_action() methods from each AlarmBridge device controller.
for controller in bridge.resource_controllers:
    if len(summary := summarize_cli_actions(controller, include_params=False)):
        # Create device type command group
        # (e.g.: Thermostat)
        device_type_app = AsyncTyper(
            help=f"Perform an action on a {slug_to_title(controller.resource_type.name).lower()}.",
            short_help=f"Perform an action on a {slug_to_title(controller.resource_type.name).lower()}. Use '[bright_cyan]adc {controller.resource_type.name.lower()} --help[/bright_cyan]' for details.",
            add_help_option=True,
            no_args_is_help=True,
        )

        # Create commands within device type command group
        # e.g.: Set State
        cmd_meta: dict
        cmd_name: str
        for cmd_name, cmd_meta in summary.items():
            device_command = device_type_app.command(
                name=f"{cmd_name}",
                add_help_option=True,
                no_args_is_help=True,
            )(with_paremeters(collect_params, show_success=True)(cmd_meta["method"]))

        # Register device type command as typer sub-app
        action_app.add_typer(
            device_type_app,
            name=controller.resource_type.name.lower(),
            rich_help_panel="Device Types",
        )

# Add action app to main app
app.add_typer(
    action_app,
    name="action",
)


if __name__ == "__main__":
    # Below is necessary to prevent asyncio "Event loop is closed" error in Windows.
    if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    app()
