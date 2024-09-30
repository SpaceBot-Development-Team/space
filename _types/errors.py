"""
The MIT License (MIT)

Copyright (c) 2024-present Developer Anonymous

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext.commands.errors import CheckFailure


class Failure(CheckFailure):
    """Base exception hierarchy"""

    if TYPE_CHECKING:
        message: str

    def __str__(self) -> str:
        return self.message


class VouchFailure(Failure):
    """Base exception for vouchs fails"""

    def __init__(self, message: str, *args) -> None:
        self.message: str = message
        super().__init__(message, *args)


class NoVouchConfig(VouchFailure):
    """Exception raised when no vouch config is found"""

    def __init__(self) -> None:
        super().__init__(
            "No hay configuración de vouchs o no hay un rol de alter establecido en este servidor",
        )


class VouchsDisabled(VouchFailure):
    """Exception raised when vouchs are disabled"""

    def __init__(self) -> None:
        super().__init__(
            "Los vouchs están deshabilitados en este servidor",
        )


class NoVouchCommand(VouchFailure):
    """Exception raised when vouchs aren't added via command but rather added automatically"""

    def __init__(self) -> None:
        super().__init__(
            "Los vouchs están configurados para añadirse automáticamente, no por comando."
        )


class NotAllowedVouchChannel(VouchFailure):
    """Exception raised when the vouch was invoked in a non-whitelisted channel.

    THIS IS ONLY RAISED WHEN VOUCH IS ADDED VIA COMMAND
    """

    def __init__(self, whitelisted: list[int]) -> None:
        super().__init__(
            (
                "No puedes añadir vouchs desde este canal, pero en cambio puedes ir a alguno de estos:\n"
                f'{",".join(["<#" + str(channel) + ">" for channel in whitelisted])}'
            )
        )


class SuggestionFailure(Failure):
    """Base exception for suggestions fails"""

    def __init__(self, message: str, *args) -> None:
        self.message: str = message
        super().__init__(message, *args)


class SuggestionsNotEnabled(SuggestionFailure):
    """Exception raised when suggestions are not enabled"""

    def __init__(self) -> None:
        super().__init__(
            "Las sugerencias están deshabilitadas en este servidor",
        )


class NoSuggestionsChannel(SuggestionFailure):
    """Exception raised when suggestions are enabled, but no suggestion channel is set"""

    def __init__(self) -> None:
        super().__init__(
            (
                "Las sugerencias están habilitadas, pero no hay un canal para enviar las aprobadas."
                " Avisa a algún administrador."
            ),
        )


class NoReviewChannel(SuggestionFailure):
    """Exception raised when reviews are enabled but no review channel is set"""

    def __init__(self) -> None:
        super().__init__(
            (
                "La revisión de sugerencias está activa en este servidor, pero no hay un canal donde enviar"
                " las sugerencias a revisar. Avisa a algún administrador."
            ),
        )


class MissingSuggestionStaffRole(SuggestionFailure):
    """Exception raised when a user tries to interact with a suggestion review without
    having the staff role.
    """

    def __init__(self, role: int, /) -> None:
        super().__init__(
            f"Requieres del rol de staff (<@&{role}>) para poder realizar esta acción.",
        )
