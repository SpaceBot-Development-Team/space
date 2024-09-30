"""Command utilities"""

from __future__ import annotations

from typing import Any, Callable, ParamSpec, TypeVar, Optional
from typing_extensions import Concatenate

from .context import Context

from discord.utils import MISSING
from discord.ext.commands.cog import Cog
from discord.app_commands.translator import locale_str
from discord.ext.commands._types import Coro
from discord.ext.commands.core import Command
from discord.ext.commands.hybrid import (
    HybridCommand as HCBase,
    HybridGroup as HGBase,
)

CogT = TypeVar("CogT", bound="Optional[Cog]")
ContextT = TypeVar("ContextT", bound="Context[Any]")  # type: ignore
P = ParamSpec("P")
T = TypeVar("T")
CommandCallback = (
    Callable[Concatenate[CogT, ContextT, P], Coro[T]]  # type: ignore
    | Callable[Concatenate[ContextT, P], Coro[T]]  # type: ignore
)


class HybridCommand(HCBase):
    def __init__(
        self,
        func: CommandCallback[CogT, Context[Any], P, T],  # type: ignore
        /,
        *,
        name: str | locale_str = MISSING,
        description: str | locale_str = MISSING,
        **kwargs: Any,
    ) -> None:
        if isinstance(name, locale_str):
            resolved_name = locale_str(name.message.replace(".", "_"), **name.extras)
            after_name = name.message
            locale_name = name
        else:
            resolved_name = name.replace(".", "_")
            after_name = name
            locale_name = None
        super().__init__(func, name=resolved_name, description=description, **kwargs)  # type: ignore

        self.name = after_name
        self._locale_name = locale_name


class HybridGroup(HGBase):
    def __init__(
        self,
        *args: Any,
        name: str | locale_str = MISSING,
        description: str | locale_str = MISSING,
        fallback: str | locale_str | None = None,
        **attrs: Any,
    ) -> None:
        if isinstance(name, locale_str):
            resolved_name = locale_str(name.message.replace(".", "_"), **name.extras)
            after_name = name.message
            locale_name = name
        else:
            resolved_name = name.replace(".", "_")
            after_name = name
            locale_name = None

        if fallback is not None:
            if isinstance(fallback, locale_str):
                resolved_fallback = locale_str(
                    fallback.message.replace(".", "_"), **fallback.extras
                )
                after_fallback = fallback.message
                locale_fallback = fallback
            else:
                resolved_fallback = fallback.replace(".", "_")
                after_fallback = fallback
                locale_fallback = None
        else:
            resolved_fallback = None
            after_fallback = None
            locale_fallback = None

        super().__init__(
            *args,
            name=resolved_name,
            description=description,
            fallback=resolved_fallback,
            **attrs,
        )

        self.name = after_name
        self._locale_name = locale_name
        self.fallback = after_fallback
        self.fallback_locale = locale_fallback

    def command(
        self,
        name: str | locale_str = MISSING,
        *args: Any,
        with_app_command: bool = True,
        **kwargs: Any,
    ):
        def decorator(func: CommandCallback):
            kwargs.setdefault("parent", self)
            result = command(
                name=name, *args, with_app_command=with_app_command, **kwargs
            )(func)
            self.add_command(result)
            return result

        return decorator

    def group(
        self,
        name: str | locale_str = MISSING,
        *args: Any,
        with_app_command: bool = True,
        **kwargs: Any,
    ):
        def decorator(func: CommandCallback):
            kwargs.setdefault("parent", self)
            result = group(
                name=name, *args, with_app_command=with_app_command, **kwargs
            )(func)
            self.add_command(result)
            return result

        return decorator


def command(
    name: str | locale_str = MISSING,
    *,
    with_app_command: bool = True,
    **kwargs,
) -> Callable[[CommandCallback[CogT, ContextT, P, T]], HybridCommand[CogT, P, T]]:  # type: ignore
    def decorator(func: CommandCallback[CogT, ContextT, P, T]) -> HybridCommand[CogT, P, T]:  # type: ignore
        if isinstance(func, Command):
            raise TypeError("Callback is already a command.")
        if name is MISSING:
            resolved_name = func.__name__
        else:
            resolved_name = name
        return HybridCommand(func, name=resolved_name, with_app_command=with_app_command, **kwargs)  # type: ignore

    return decorator


def group(
    name: str | locale_str = MISSING,
    *,
    with_app_command: bool = True,
    **kwargs,
) -> Callable[[CommandCallback[CogT, ContextT, P, T]], HybridGroup[CogT, P, T]]:  # type: ignore
    def decorator(func: CommandCallback[CogT, ContextT, P, T]) -> HybridGroup[CogT, P, T]:  # type: ignore
        if isinstance(func, Command):
            raise TypeError("Callback is already is command.")
        if name is MISSING:
            resolved_name = func.__name__
        else:
            resolved_name = name
        return HybridGroup(
            func, name=resolved_name, with_app_command=with_app_command, **kwargs
        )

    return decorator
