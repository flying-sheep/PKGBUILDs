from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


__all__ = ["URL_PAT", "msg_update"]

URL_PAT = re.compile(
    r"https://github\.com/[^/]+/(?P<name>[^/]+)/releases/tag/v?(?P<version>[\d.]+)"
)


async def msg_update(
    http_client: AsyncClient, name: str, versions: tuple[str, str]
) -> str:
    return f"github.com update: {name} ({versions[0]} -> {versions[1]})"
