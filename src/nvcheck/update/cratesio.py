from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


__all__ = ["URL_PAT", "msg_update"]

URL_PAT = re.compile(r"https://crates.io/crates/(?P<name>[\w-]*)/(?P<version>[\d.]+)")


async def msg_update(
    http_client: AsyncClient, name: str, versions: tuple[str, str]
) -> str:
    return f"crates.io update: {name} ({versions[0]} -> {versions[1]})"
