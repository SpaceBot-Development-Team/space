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

import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Final,
    Iterable,
    List,
    Literal,
    Optional,
    Tuple,
    TypeVar,
    Union,
    overload,
)

import discord
from discord.abc import Snowflake as Object
from discord.enums import Enum

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from .protocols import Stateful, ConnectionState
    from .types import (
        WarnObject as WarnObjectPayload,
        WarnsConfig as WarnsConfigPayload,
        WarnRole as WarnRolePayload,
        WarnKick as WarnKickPayload,
        WarnBan as WarnBanPayload,
        WarnMetadata as WarnMetadataPayload,
        WarnTimeout as WarnTimeoutPayload,
    )

MISSING = discord.utils.MISSING
T = TypeVar("T")
A = TypeVar("A", bound=Object)
S = TypeVar("S", bound=Object)

__all__ = (
    "ActionType",
    "Warn",
    "WarnAction",
    "WarnConfig",
)

WARNS_EPOCH: Final[int] = 1718208605


def get_state(obj: Stateful) -> ConnectionState:
    """Gets the state of an object"""
    return getattr(obj, "_state", obj._connection)  # type: ignore


def gen_id() -> int:
    """Generates a new ID"""
    return int(datetime.datetime.now(datetime.UTC).timestamp()) - WARNS_EPOCH


def find_all(
    iterable: Iterable[T],
    predicate: Callable[[T], bool],
) -> List[T]:
    """Returns all the elements that meet the predicate"""

    to_return: List[T] = []

    for item in iterable:
        if predicate(item):
            to_return.append(item)

    return to_return


class Warn:
    """Represents a warn object.

    Parameters
    ----------
    id: :class:`str`
        The warn ID.
    target: :class:`discord.Object`
        A object representing the target of this
        warn.
    staff: :class:`discord.Object`
        The staff that perfomed the action.
    reason: :class:`str`
        The reason why you sanction this member.
    """

    __slots__ = (
        "id",
        "guild",
        "target",
        "staff",
        "reason",
        "_timestamp",
        "_state",
    )

    def __init__(
        self,
        *,
        id: str,
        guild: Object,
        target: Object,
        staff: Object,
        reason: str,
    ) -> None:
        self.id: str = id
        self.guild: Object = guild
        self.target: Object = target
        self.staff: Object = staff
        self.reason: str = reason

        self._timestamp: datetime.datetime = MISSING
        self._state: ConnectionState = MISSING

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: Returns the warn creation
        timestamp.
        """
        return self._timestamp

    @classmethod
    def with_state(cls, obj: Stateful, **kwargs: Any) -> Warn:
        """Creates a warn object with a state.

        Parameters
        ----------
        obj: :class:`Stateful`
            A object with the ``_state`` or ``_connection`` attribute.
        **kwargs
            The kwargs to instate the class with.

        Returns
        -------
        :class:`Warn`
            The warn.
        """

        self = cls(**kwargs)
        self._state = get_state(obj)
        self._update_state()

        return self

    @classmethod
    def from_data(
        cls, *, id: str, data: WarnObjectPayload, state: ConnectionState = MISSING
    ) -> Warn:
        """Creates a new Warn from the warn object payload.

        Parameters
        ----------
        id: :class:`str`
            The warn ID.
        user_id: :class:`int`
            The user ID.
        guild_id: :class:`int`
            The guild ID.
        data: :class:`dict`
            The payload.
        state: :class:`ConnectionState`
            The state to use.

        Returns
        -------
        :class:`Warn`
            The warn.
        """

        self = cls(
            id=id,
            guild=discord.Object(id=data["guild_id"]),
            target=discord.Object(id=data["target"]),
            staff=discord.Object(id=data["author"]),
            reason=data["reason"],
        )
        self._timestamp = datetime.datetime.fromisoformat(data["created_at"])

        if state is not MISSING:
            self._state = state
            self._update_state()

        return self

    def to_dict(self) -> WarnObjectPayload:
        """Converts to a dict the current warn"""

        if self._timestamp is MISSING:
            self._timestamp = datetime.datetime.now(datetime.UTC)

        return {
            "created_at": self._timestamp.isoformat(),
            "author": self.staff.id,
            "reason": self.reason,
            "target": self.target.id,
            "guild_id": self.guild.id,
        }

    def _update_state(self) -> None:
        if self._state is MISSING:
            return

        guild = self._state._get_guild(self.guild.id)

        if guild:
            self.guild = guild
            target = guild.get_member(self.target.id) or self._state.get_user(
                self.target.id
            )
            staff = guild.get_member(self.staff.id) or self._state.get_user(
                self.staff.id
            )

        else:
            target = self._state.get_user(self.target.id)
            staff = self._state.get_user(self.staff.id)

        if target:
            self.target = target
        if staff:
            self.staff = staff


class ActionType(Enum):
    """Represents the action types of ``n`` warns."""

    role = "role"
    timeout = "timeout"
    kick = "kick"
    ban = "ban"


class WarnAction:
    """Represents the punishment of ``n`` warns.

    Attributes
    ----------
    type: :class:`ActionType`
        The action type.
    n: :class:`int`
        The amount of warns for this action to be executed.
    id: :class:`int`
        The unique ID of this warn action.
    """

    __slots__ = (
        "type",
        "n",
        "_role",
        "id",
        "_duration",
    )

    @overload
    def __init__(
        self,
        *,
        data: WarnRolePayload,
        type: Literal[ActionType.role],
    ) -> None: ...

    @overload
    def __init__(
        self,
        *,
        data: WarnTimeoutPayload,
        type: Literal[ActionType.timeout],
    ) -> None: ...

    @overload
    def __init__(
        self,
        *,
        data: Union[WarnKickPayload, WarnBanPayload],
        type: Literal[ActionType.kick, ActionType.ban],
    ) -> None: ...

    def __init__(self, *, data: Dict[str, Any], type: ActionType) -> None:  # type: ignore
        self.type: ActionType = type
        self.n: int = data["n"]
        self.id: int = data["id"]
        self._role: Optional[Object] = None
        self._duration: Optional[datetime.timedelta] = None
        self._update(data)  # type: ignore

    def __repr__(self) -> str:
        string = f"<WarnAction id={self.id} n={self.n} type={self.type!r}"

        if self.type == ActionType.role:
            if not self.role:
                string += " role=None"
            else:
                string += f" role={self.role.id}"

        if self.type == ActionType.timeout:
            if not self._duration:
                string += " duration=None"
            else:
                string += f" duration={self._duration.total_seconds()}"

        return string + ">"

    @overload
    def __getitem__(self, key: Literal["n"]) -> int: ...

    @overload
    def __getitem__(self, key: Literal["type"]) -> ActionType: ...

    @overload
    def __getitem__(self, key: Literal["role"]) -> Optional[Object]: ...

    @overload
    def __getitem__(self, key: Literal["duration"]) -> Optional[datetime.timedelta]: ...

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key, None)

    @overload
    def _update(self, data: WarnRolePayload, /) -> None: ...

    @overload
    def _update(self, data: Union[WarnKickPayload, WarnBanPayload], /) -> None: ...

    def _update(self, data: Dict[str, Any], /) -> None:  # type: ignore
        if self.type == ActionType.role:
            self._role = discord.Object(id=data["role"], type=discord.Role)
        elif self.type == ActionType.timeout:
            self._duration = datetime.timedelta(seconds=data["duration"])

    @property
    def role(self) -> Optional[Object]:
        """Optional[:class:`Object`]: The role that is given when this requirement is met
        or ``None``.
        """
        return self._role

    @property
    def duration(self) -> Optional[datetime.timedelta]:
        """Optional[:class:`datetime.timedelta`]: The duration of the timeout when this requirement
        is met, or ``None``.
        """
        return self._duration

    @overload
    def to_dict(self) -> WarnRolePayload: ...

    @overload
    def to_dict(self) -> WarnTimeoutPayload: ...

    @overload
    def to_dict(self) -> Union[WarnKickPayload, WarnBanPayload]:  # type: ignore
        ...

    def to_dict(self) -> Dict[str, Any]:
        if self.type == ActionType.role:
            if not self.role:
                raise ValueError("role can't be none on role type based warn actions")
            return {
                "role": self.role.id,
                "n": self.n,
                "id": self.id,
            }
        if self.type == ActionType.timeout:
            if not self.duration:
                raise ValueError("duration can't be none on timeout based warn actions")
            return {
                "duration": self.duration.total_seconds(),
                "n": self.n,
                "id": self.id,
            }
        return {
            "n": self.n,
            "id": self.id,
        }


class WarnConfig:
    """Represents the warns config of a guild.

    Attributes
    ----------
    roles: List[:class:`WarnAction`]
        The punishment roles.
    timeouts: List[:class:`WarnAction`]
        The punishment timeouts.
    kicks: List[:class:`WarnAction`]
        The punishment kicks.
    bans: List[:class:`WarnAction`]
        The punishment bans.
    metadata: Optional[:class:`dict`]
        The metadata, or ``None``.
    """

    def __init__(self, *, data: WarnsConfigPayload) -> None:
        self.roles: List[WarnAction] = [
            WarnAction(data=data, type=ActionType.role)
            for data in data.get("roles", [])
        ]
        self.kicks: List[WarnAction] = [
            WarnAction(data=data, type=ActionType.kick)
            for data in data.get("kicks", [])
        ]
        self.bans: List[WarnAction] = [
            WarnAction(data=data, type=ActionType.ban) for data in data.get("bans", [])
        ]
        self.timeouts: List[WarnAction] = [
            WarnAction(data=data, type=ActionType.timeout)
            for data in data.get("timeouts", [])
        ]
        self.metadata: Optional[WarnMetadataPayload] = data.get("metadata", None)

    @classmethod
    def from_params(cls, **kwargs: Unpack[WarnsConfigPayload]) -> WarnConfig:
        """Creates a WarnConfig instance form the parameters that it
        has.

        Parameters
        ----------
        **kwargs
            The kwargs to use.

        Returns
        -------
        :class:`WarnConfig`
            The warn config.
        """

        return cls(data=kwargs)

    @classmethod
    def empty(cls) -> WarnConfig:
        """Creates an empty warn config.

        Returns
        -------
        :class:`WarnConfig`
            The warn config.
        """

        return cls(
            data={
                "bans": [],
                "kicks": [],
                "metadata": None,
                "roles": [],
                "timeouts": [],
            }
        )

    def total_punishments(self) -> int:
        """:class:`int`: Returns the amount of total punishments"""
        return len(self.roles) + len(self.timeouts) + len(self.kicks) + len(self.bans)

    def all_punishments(self) -> List[WarnAction]:
        """List[:class:`WarnAction`]: Returns all the warn actions."""
        return self.roles + self.timeouts + self.kicks + self.bans

    def exists(self, action: WarnAction, /) -> bool:
        """:class:`bool`: Returns whether the provided action already exists or not."""

        roles, tms, k, b = self.get_punishments(action.n)
        others = k + b

        if action.type == ActionType.role:
            return (
                discord.utils.get(
                    roles,
                    role__id=action.role.id,  # type: ignore
                )
                is not None
            )
        elif action.type == ActionType.timeout:
            return (
                discord.utils.get(
                    tms,
                    duration=action.duration,  # type: ignore
                )
                is not None
            )
        else:
            return any(a.n == action.n for a in others)

    def get_punishment(self, id: int, /) -> Optional[WarnAction]:
        """Returns the warn action with the given ID.

        Parameters
        ----------
        id: :class:`int`
            The warn action ID.

        Returns
        -------
        Optional[:class:`WarnAction`]
            The warn action with that ID, or` `None``.
        """
        return discord.utils.get(self.all_punishments(), id=id)

    def get_punishments(
        self, warns: int, /
    ) -> Tuple[List[WarnAction], List[WarnAction], List[WarnAction], List[WarnAction]]:
        """Returns the punishment for ``n`` warns. The tuple returned is organised as
        ``([ROLE_ACTIONS], [TIMEOUTS], [KICK_ACTIONS], [BAN_ACTIONS])``, so this means, the least severe
        punishments are located at index ``0``.

        If not punishments found, warn actions Lists are empty (``([], [], [], [])``).

        Parameters
        ----------
        warns: :class:`int`
            The amount of warns.

        Returns
        -------
        Tuple[
            List[:class:`WarnAction`], List[:class:`WarnAction`], List[:class:`WarnAction`]
        ]
            The punishments.
        """

        return (
            find_all(
                self.roles,
                lambda r: r.n == warns,
            ),
            find_all(
                self.timeouts,
                lambda t: t.n == warns,
            ),
            find_all(
                self.kicks,
                lambda k: k.n == warns,
            ),
            find_all(
                self.bans,
                lambda b: b.n == warns,
            ),
        )

    @overload
    def create_punishment(
        self,
        *,
        n: int,
        type: Literal[
            ActionType.ban,
            ActionType.kick,
        ],
    ) -> WarnAction: ...

    @overload
    def create_punishment(
        self,
        *,
        n: int,
        type: Literal[ActionType.role],
        role: Object,
    ) -> WarnAction: ...

    @overload
    def create_punishment(
        self,
        *,
        n: int,
        type: Literal[ActionType.timeout],
        duration: datetime.timedelta,
    ) -> WarnAction: ...

    def create_punishment(
        self,
        *,
        n: int,
        type: ActionType,
        role: Object = MISSING,
        duration: datetime.timedelta = MISSING,
    ) -> WarnAction:
        """Creates a new punishment.

        Parameter
        ---------
        n: :class:`int`
            The amount of warns that are needed to this requirement to be met.
        type: :class:`ActionType`
            The action type of this punishment.
        role: :class:`Object`
            The role to give, if ``type`` is :attr:`ActionType.role`
        duration: :class:`datetime.timedelta`
            The duration of the timeout, if ``type`` is :attr:`ActionType.timeout`

        Raises
        ------
        ValueError
            An action that is potentially the same already exists.

        Returns
        -------
        :class:`WarnAction`
            The new punishment.
        """

        fake_payload: Dict[str, Union[int, float]] = {
            "n": n,
            "id": gen_id(),
        }

        if role is not MISSING:
            fake_payload["role"] = role.id

        if duration is not MISSING:
            fake_payload["duration"] = duration.total_seconds()

        action = WarnAction(
            data=fake_payload,  # type: ignore
            type=type,  # type: ignore
        )

        if self.exists(action):
            raise ValueError("an action that is potentially the same already exists")

        if type == ActionType.ban:
            self.bans.append(action)
        elif type == ActionType.kick:
            self.kicks.append(action)
        elif type == ActionType.timeout:
            self.timeouts.append(action)
        elif type == ActionType.role:
            self.roles.append(action)
        else:
            raise ValueError(f"unknown action type value {type.value}")

        return action

    def remove_punishment(
        self,
        id: int,
        /,
    ) -> None:
        """Removes a punishment from the selected type array.

        Parameters
        ----------
        id: :class:`int`
            The punishment ID.
        """

        punishment = self.get_punishment(id)

        if not punishment:
            raise LookupError(f"No punishment found with id {id}")

        type = punishment.type
        iterable: List[WarnAction]

        if type == ActionType.role:
            iterable = self.roles
        elif type == ActionType.kick:
            iterable = self.kicks
        elif type == ActionType.ban:
            iterable = self.bans
        elif type == ActionType.timeout:
            iterable = self.timeouts
        else:
            raise ValueError(f"unknown action type value {type.value}")

        iterable.remove(punishment)

    def to_dict(self) -> WarnsConfigPayload:
        return {
            "roles": [r.to_dict() for r in self.roles],
            "timeouts": [t.to_dict() for t in self.timeouts],
            "kicks": [k.to_dict() for k in self.kicks],
            "bans": [b.to_dict() for b in self.bans],
            "metadata": self.metadata,
        }
