from __future__ import annotations

from typing import Literal, TypedDict


class ApplyQuestion(TypedDict):
    label: str
    placeholder: str | None
    type: Literal["short", "long"]
    default: str | None
    required: bool
    min_length: int | None
    max_length: int | None
