"""Common commands for the adc CLI."""

# ruff: noqa: FBT002

import asyncio
import logging
from functools import partial
from typing import Annotated

import aiohttp
import typer
from _pyalarmdotcomajax import AlarmBridge
from _pyalarmdotcomajax.adc.util import ValueEnum
from _pyalarmdotcomajax.exceptions import (
    AuthenticationFailed,
    MustConfigureMfa,
    NotAuthorized,
    OtpRequired,
    UnexpectedResponse,
)
from _pyalarmdotcomajax.models.auth import OtpType
from rich import print
from rich.panel import Panel
from rich.prompt import InvalidResponse, Prompt, PromptBase
from rich.table import Table

# RICH OUTPUT PANELS
MAIN_MFA = "Multi-factor Authentication Options"
MAIN_OUTPUT = "Output Flags"
CREDENTIALS = "User Credentials"


log = logging.getLogger(__name__)

#########
# TYPES #
#########


class OtpPrompt(PromptBase[OtpType]):
    """
    A prompt that returns an OTP type.

    Overloads the Rich PromptBase class.
    """

    response_type = OtpType
    validate_error_message = "[prompt.invalid]Please enter an available OTP type"

    def process_response(self, value: str) -> OtpType:
        """Convert choices to an OtpType."""
        value = value.strip().lower()

        try:
            return OtpType[value]
        except KeyError as err:
            raise InvalidResponse(self.validate_error_message) from err


###########
# HELPERS #
###########


async def async_handle_otp_workflow(
    alarm: AlarmBridge,
    enabled_2fa_methods: list[OtpType],
    email: str | None = None,
    sms_number: str | None = None,
    otp: str | None = None,
    otpmethod: OtpType | None = None,
    device_name: str | None = None,
) -> None:
    """Handle two-factor authentication workflow."""

    #
    # Determine which OTP method to use
    #

    code: str | None
    selected_otpmethod: OtpType
    if otp or (otpmethod == OtpType.app):
        # If an OTP is provided directly in the CLI, it's from an OTP app.
        selected_otpmethod = OtpType.app
    else:
        print(
            "[bold]Two factor authentication is enabled for this account.",
        )

        # Get list of enabled OTP methods.
        if len(enabled_2fa_methods) == 1:
            # If only one OTP method is enabled, use it without prompting user.
            selected_otpmethod = enabled_2fa_methods[0]
            print(f"Using {selected_otpmethod.name} for One-Time Password.")
        elif cli_otpmethod := otpmethod:
            # If multiple OTP methods are enabled, but the user provided one via CLI, use it.
            selected_otpmethod = OtpType(cli_otpmethod)
            print(f"Using {selected_otpmethod.name} for One-Time Password.")
        else:
            try:
                selected_otpmethod = OtpPrompt.ask(
                    "[magenta bold underline]Which OTP method would you like to use?[/magenta bold underline]",
                    choices=[x.name for x in enabled_2fa_methods],
                )
            except InvalidResponse as err:
                print("[bold red]Valid OTP method was not entered.")
                raise AuthenticationFailed from err

        #
        # Request OTP
        #

        if selected_otpmethod in (OtpType.email, OtpType.sms):
            # Ask Alarm.com to send OTP if selected method is EMAIL or SMS.
            print(
                f"[bold yellow]Requesting One-Time Password via {selected_otpmethod.name} at {email if selected_otpmethod == OtpType.email else sms_number}..."
            )
            await alarm.auth_controller.request_otp(selected_otpmethod)

    #
    # Prompt user for OTP
    #

    code = Prompt.ask("[magenta bold underline]Enter One-Time Password[/magenta bold underline]")

    if mfa_cookie := await alarm.auth_controller.submit_otp(
        code=code, method=selected_otpmethod, device_name=device_name or "ADC CLI"
    ):
        print(f"Two-factor authentication cookie: {mfa_cookie}")


#############
# CALLBACKS #
#############


def debug_callback(value: bool) -> None:
    """Set log level based on whether user requested debugging."""
    logging.basicConfig()
    if value:
        print("Debugging enabled.")
        logging.getLogger("pyalarmdotcomajax").setLevel(5)
    else:
        logging.getLogger("pyalarmdotcomajax").setLevel(logging.ERROR)


# We need to be careful to use the same bridge for initialization that we do for generating the action
# sub-commands.
# The action sub-commands will be tied to this specific bridge, so this is the bridge that we need to initialize.
bridge = AlarmBridge()


async def collect_params(
    ctx: typer.Context,
    #
    # CREDENTIALS
    #
    username: Annotated[
        str,
        typer.Option(
            "--username",
            "-u",
            help="Alarm.com username",
            rich_help_panel=CREDENTIALS,
            show_default=False,
            envvar="ADC_USERNAME",
        ),
    ],
    password: Annotated[
        str,
        typer.Option(
            "--password",
            "-p",
            help="Alarm.com password",
            rich_help_panel=CREDENTIALS,
            show_default=False,
            envvar="ADC_PASSWORD",
        ),
    ],
    cookie: Annotated[
        str | None,
        typer.Option(
            "--cookie",
            "-c",
            help="Two-factor authentication cookie. (Cannot be used with --otp!)",
            show_default=False,
            rich_help_panel=MAIN_MFA,
            envvar="ADC_COOKIE",
        ),
    ] = None,
    #
    # MFA OPTIONS
    #
    otp_method: Annotated[
        OtpType | None,
        typer.Option(
            "--otp-method",
            "-m",
            help='OTP delivery method to use. Cannot be used alongside "cookie" argument. Defaults to [yellow]app[/yellow] if --otp is provided, otherwise prompts you for otp.',
            case_sensitive=False,
            show_choices=True,
            show_default=False,
            rich_help_panel=MAIN_MFA,
            click_type=ValueEnum(OtpType, "disabled"),
        ),
    ] = None,
    otp: Annotated[
        str | None,
        typer.Option(
            "--otp",
            "-o",
            help="Provide app-based OTP for accounts that have two-factor authentication enabled. If not provided here, adc will prompt you for OTP. Cannot be used with --cookie or --otp-method!",
            show_default=False,
            rich_help_panel=MAIN_MFA,
        ),
    ] = None,
    device_name: Annotated[
        str | None,
        typer.Option(
            "--device-name",
            "-n",
            help="Registers a device with this name on alarm.com and requests the two-factor authentication cookie for the device.",
            rich_help_panel=MAIN_MFA,
            show_default=False,
        ),
    ] = None,
    #
    # OUTPUT OPTIONS
    #
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            "-d",
            callback=debug_callback,
            help="Enable pyalarmdotcomajax's debug logging.",
            rich_help_panel=MAIN_OUTPUT,
            is_eager=True,
            show_default=False,
        ),
    ] = False,
    json: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Return JSON output from device endpoints instead of formatted output.",
            rich_help_panel=MAIN_OUTPUT,
            show_default=False,
        ),
    ] = False,
) -> None:
    """Collect shared parameters, validate, and (implicitly) load into Typer context."""

    # Enforce mutual exclusivity of MFA options.
    # Cookie parameter can be entered as "" if env vars are set for all 3 arguments, but we want to test OTP
    # prompts.
    if (otp_method is not None) + (otp is not None) + (cookie not in [None, ""]) > 1:
        raise typer.BadParameter("Cannot use more than one MFA option at a time.")

    # Arguments can be pulled from environment variables. Show to user to reduce confusion.
    login_table = Table.grid(padding=(0, 2, 0, 0))
    login_table.add_column()
    login_table.add_column()
    login_table.add_row("[bold]User:[/bold]", username)
    login_table.add_row(
        "[bold]Password:[/bold]", "****" if password else "[grey58 italic](Not Provided)[/grey58 italic]"
    )
    login_table.add_row("[bold]MFA Cookie:[/bold]", cookie or "[grey58 italic](Not Provided)[/grey58 italic]")

    print("\n")

    print(Panel.fit(login_table, title="[bold][yellow]Logging in as:", border_style="yellow", title_align="left"))

    ctx.ensure_object(dict)
    ctx.obj["bridge"] = bridge

    #####################
    # INITIALIZE BRIDGE #
    #####################

    bridge.auth_controller.set_credentials(ctx.params["username"], ctx.params["password"], ctx.params.get("cookie"))

    # Typer calls bridge.close() when context is closed.
    ctx.call_on_close(partial(asyncio.get_event_loop().run_until_complete, bridge.close()))

    #
    # LOG IN
    #

    try:
        # Initialize the connector
        await bridge.initialize()

    except MustConfigureMfa as err:
        print("[red]Unable to log in. Please set up two-factor authentication for this account.")
        raise typer.Exit(1) from err

    except (TimeoutError, aiohttp.ClientError, UnexpectedResponse, NotAuthorized) as err:
        print("[red]Could not connect to Alarm.com.")
        raise typer.Exit(1) from err

    except AuthenticationFailed as err:
        print("[red]Invalid credentials.")
        raise typer.Exit(1) from err

    #
    # HANDLE MFA
    #

    except OtpRequired as exc:
        try:
            log.debug("OTP Required")

            await async_handle_otp_workflow(
                alarm=bridge,
                enabled_2fa_methods=exc.enabled_2fa_methods,
                email=exc.email,
                sms_number=exc.formatted_sms_number,
                otp=ctx.params.get("otp"),
                otpmethod=ctx.params.get("otp_method"),
                device_name=ctx.params.get("device_name"),
            )

            await bridge.initialize()
        except AuthenticationFailed as err:
            print("[bold red]Invalid OTP.")
            raise typer.Exit(1) from err
