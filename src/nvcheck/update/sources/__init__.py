from __future__ import annotations

from typing import TYPE_CHECKING

from . import cratesio, github, pypi

if TYPE_CHECKING:
    from httpx import AsyncClient

    from . import _source


__all__ = ["msg_update"]

SOURCES: tuple[type[_source.Source], ...] = (
    github.Source,
    pypi.Source,
    cratesio.Source,
)


async def msg_update(http_client: AsyncClient, url: str, oldver: str) -> str | None:
    for source_cls in SOURCES:
        source = source_cls(http_client)
        if match := source.url_pat.fullmatch(url):
            return await source.msg_update(match["name"], (oldver, match["version"]))
    return None
