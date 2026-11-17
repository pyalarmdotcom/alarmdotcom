"""Helpers for adc CLI."""


import asyncio
import inspect
from collections.abc import Callable
from enum import Enum
from functools import wraps
from itertools import chain, compress, groupby
from operator import attrgetter
from typing import Annotated, Any, TypeVar, get_type_hints

import click
import typer
from rich import print

# Generic type variable for functions
F = TypeVar("F", bound=Callable[..., Any])
#########
# TYPES #
#########

Param_Id = Annotated[
    str,
    typer.Argument(
        metavar="DEVICE_ID",
        show_default=False,
        help="A device's ID. To view a list of device IDs, use '[bright_cyan]adc get[/bright_cyan]'.",
    ),
]


class AsyncTyper(typer.Typer):
    """
    Define a Typer subclass with async command support.

    https://github.com/tiangolo/typer/issues/88#issuecomment-1627386014
    """

    def universal(self, func: Callable, *args: Any, **kwargs: Any) -> Callable[[F], F]:
        """Wrap the command function to support async execution."""
        decorator = func(*args, **kwargs)

        def add_runner(f: F) -> F:
            """Wrap the function with an async runner if it's async."""

            @wraps(f)
            def runner(*args: Any, **kwargs: Any) -> Any:
                """Execute the async function using asyncio.run."""
                asyncio.get_event_loop().run_until_complete(f(*args, **kwargs))

            if inspect.iscoroutinefunction(f):
                return decorator(runner)
            return decorator(f)

        return add_runner

    def command(self, *args: Any, **kwargs: Any) -> Callable[[F], F]:
        """Wrap the command function to support async execution."""

        return self.universal(super().command, *args, **kwargs)

    def callback(self, *args: Any, **kwargs: Any) -> Callable[[F], F]:
        """Wrap the command function to support async execution."""

        return self.universal(super().callback, *args, **kwargs)


##############
# DECORATORS #
##############


def cli_action() -> Callable[[F], F]:
    """
    Decorate a method to mark it as a CLI action with a given description.

    This decorator adds the method and its description to a `__cli_actions__` attribute
    on the method, used for identifying CLI actions within a class.

    Args:
        func: The method to decorate.
        description: Human-readable description of the CLI action.

    Returns:
        The decorated method.

    """

    def decorator(func: F) -> F:
        if not hasattr(func, "__cli_actions__"):
            func.__cli_actions__ = {}  # type: ignore
        func.__cli_actions__[func.__name__] = {func.__name__: func.__doc__}  # type: ignore
        return func

    return decorator


###########
# HELPERS #
###########


def summarize_cli_actions(
    cls: Any, *, include_params: bool = False
) -> dict[str, dict[str, Any]]:
    """
    Summarize CLI action methods within a class, including their descriptions.

    Optionally include a summary of each method's parameters if `include_params` is True.

    Args:
        cls: The class to inspect.
        include_params: If True, include a summary of each method's parameters.

    Returns:
        A dictionary with method names as keys and methods (and optionally parameter summaries) as values.

    """
    cli_actions_summary = {}
    for attr_name in dir(cls):
        attr = getattr(cls, attr_name)
        if callable(attr) and hasattr(attr, "__cli_actions__"):
            method_info = {"method": attr}
            if include_params:
                params_summary = summarize_method_params(attr)
                method_info["params"] = params_summary
            cli_actions_summary[attr_name] = method_info
    return cli_actions_summary


def summarize_method_params(
    method: Callable[..., Any],
) -> list[dict[str, str | list[str] | list[type] | bool]]:
    """
    Summarize method parameters, excluding 'self' and 'return'. Handle unions and Enums properly.

    Args:
        method: The method to summarize.

    Returns:
        A list of dictionaries with parameter names and their types or enum member names.

    """
    params_summary: list[dict[str, str | list[str] | list[type] | bool]] = []
    type_hints = get_type_hints(method)
    for name, param_type in type_hints.items():
        if name in ["self", "return"]:
            continue  # Skip 'self' and 'return' members

        type_info: list[type]
        required_param: bool = True

        # Initialize type info with direct type name if available
        type_info = [getattr(param_type, "__name__", param_type)]

        # Initialize choices for Enum members
        # choices = []

        # Check and expand for Enum members
        if isinstance(param_type, type) and issubclass(param_type, Enum):
            type_info = [param_type]
            # choices = list(param_type.__members__)
        elif hasattr(param_type, "__args__"):  # Handle Union types
            type_info = []
            for arg in param_type.__args__:
                if arg is type(None):
                    required_param = False
                elif issubclass(arg, Enum):
                    # choices = list(arg.__members__)
                    type_info.append(getattr(arg, "__name__", arg))
                # elif isinstance(arg, type):
                else:
                    type_info.append(getattr(arg, "__name__", arg))

        params_summary.append(
            {
                "name": str(name),
                "types": type_info,
                # "choices": choices,
                "required": bool(required_param),
            }
        )

    return params_summary


###############################################
###############################################
## ARGUMENT & OPTION SHARING ACROSS COMMANDS ##
###############################################
###############################################
#
# Source: https://github.com/tiangolo/typer/issues/153#issuecomment-2002389855
#


def merge_signatures(
    signature: inspect.Signature,
    other: inspect.Signature,
    drop: list[str] | None = None,
    *,
    strict: bool = True,
) -> tuple[inspect.Signature, list[int], list[int]]:
    """
    Merge two signatures.

    Returns a new signature where the parameters of the second signature have been
    injected in the first if they weren't already there (i.e. same name not found).
    Also returns two maps that can be used to find out if a parameter in the new
    signature was present in the originals (or can be used to recover the original
    signatures).

    If `strict` is true, parameters with same name in both original signatures must
    be of same kind (positional only, keyword only or maybe keyword). Otherwise a
    ValueError is raised.
    """
    # Split parameters by kind
    groups = {
        k: list(g)
        for k, g in groupby(signature.parameters.values(), attrgetter("kind"))
    }

    # Append parameters from other signature
    for name, param in other.parameters.items():
        if drop and name in drop:
            continue
        if name in signature.parameters:
            if strict and param.kind != signature.parameters[name].kind:
                raise ValueError(
                    f"Both signature have same parameter {name!r} but with different kind"
                )
            continue

        # Variadic args (*args or **kwargs)
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            if param.kind not in groups:
                groups[param.kind] = [param]
            elif param.name != groups[param.kind][0].name:
                raise ValueError(
                    f"Variadic args must have same name when present "
                    f"on both signatures: got {groups[param.kind][0].name!r} "
                    f"and {param.name!r}"
                )
        # Non variadic args
        else:
            groups.setdefault(param.kind, []).append(param)

    # Depending on input signatures, the resulting one can be invalid as the
    # insertion order could yield to a parameter with a default value being in
    # front of a parameter without default value.
    #
    # Make sure params with default values are put after params without default.
    # This is done on a per kind basis (?) and can lead to unintuitive parameter
    # reordering...
    for params in groups.values():
        if params:
            params.sort(key=lambda p: bool(p.default != inspect.Parameter.empty))

    # Merged parameters list
    parameters = sorted(chain(*(groups.values())), key=attrgetter("kind"))

    # Memoize if parameters were present in original signatures
    sel_0 = [1 if p.name in signature.parameters else 0 for p in parameters]
    sel_1 = [1 if p.name in other.parameters else 0 for p in parameters]

    return signature.replace(parameters=parameters), sel_0, sel_1


def with_paremeters(shared: Callable, *, show_success: bool = False) -> Callable:
    """Share parameters between commands with this decorator."""

    def wrapper(command: Callable) -> Callable:
        """Wrap the command with shared parameters."""
        signature, sel_0, sel_1 = merge_signatures(
            inspect.signature(command), inspect.signature(shared)
        )

        @wraps(command)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            """Wrap this function."""
            # Bind values
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()

            # Call outer function with a set of selected parameters
            if inspect.iscoroutinefunction(shared):
                asyncio.get_event_loop().run_until_complete(
                    shared(*compress(bound.args, sel_1))
                )
            else:
                shared(*compress(bound.args, sel_1))

            try:
                # Call inner function with another set of selected parameters
                if inspect.iscoroutinefunction(command):
                    result = asyncio.get_event_loop().run_until_complete(
                        command(*compress(bound.args, sel_0))
                    )
                else:
                    result = command(*compress(bound.args, sel_0))
            except Exception:
                print("[red]Error")
                raise

            if not show_success:
                return result

            print("\n[green]Success!\n")

            return None

        wrapped.__signature__ = signature  # type: ignore
        return wrapped

    return wrapper


class ValueEnum(click.Choice):
    """click.ParamType for enums for which the user should interact with the member name instead of the member value."""

    name = "value_enum"

    def __init__(
        self, target_type: type[Enum], exclude: list[str] | None = None
    ) -> None:
        """Initialize the OtpParamType class."""

        self.target_type = target_type

        super().__init__(
            choices=[x.name for x in target_type if x.name not in (exclude or [])],
            case_sensitive=False,
        )

    def convert(
        self,
        value: Any,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> Any:
        """Convert the selection to the enum member's value to meet Typer conventions."""

        try:
            return self.target_type[value].value
        except ValueError:
            self.fail(
                f"{value!r} is not a valid {self.target_type.name} type", param, ctx
            )

    @property
    def metavar(self) -> str:
        """Get the metavar string for the enum choices."""
        choices_str = "|".join(self.choices)

        return f"[{choices_str}]"
