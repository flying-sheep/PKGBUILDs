from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, KeysView
    from typing import TypeVar

    T = TypeVar("T")


def ordered_set(iterable: Iterable[T]) -> KeysView[T]:
    return dict.fromkeys(iterable).keys()
