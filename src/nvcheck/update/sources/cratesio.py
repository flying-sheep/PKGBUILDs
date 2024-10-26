from __future__ import annotations

import re
from typing import TYPE_CHECKING

from . import _source

if TYPE_CHECKING:
    from httpx import AsyncClient


__all__ = ["Source"]


class Source(_source.Source):
    url_pat = re.compile(
        r"https://crates\.io/crates/(?P<name>[\w-]+)/(?P<version>[\d.]+)"
    )

    async def msg_update(
        self, http_client: AsyncClient, name: str, versions: tuple[str, str]
    ) -> str:
        return f"crates.io update: {name} ({versions[0]} -> {versions[1]})"
