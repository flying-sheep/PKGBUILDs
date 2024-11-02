from __future__ import annotations

from typing import TYPE_CHECKING

from . import cratesio, github, pypi

if TYPE_CHECKING:
    from httpx import AsyncClient
    from nvchecker.util import RichResult

    from ._source import Source


__all__ = ["msg_update", "SOURCES"]

SOURCES: tuple[type[Source], ...] = (
    github.Source,
    pypi.Source,
    cratesio.Source,
)


async def msg_update(
    http_client: AsyncClient, oldver: str, new: RichResult
) -> str | None:
    for source_cls in SOURCES:
        if msg := await source_cls(http_client).msg_update(oldver, new):
            return msg
    return None
