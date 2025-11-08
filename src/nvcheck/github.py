from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from typing import Literal


@overload
async def get_token(from_gh: Literal[True]) -> str: ...
@overload
async def get_token(from_gh: Literal[False] = False) -> str | None: ...
async def get_token(from_gh: bool = False) -> str | None:
    token = os.environ.get("GH_TOKEN")
    if not from_gh or token is not None:
        return token
    proc = await asyncio.create_subprocess_exec(
        *("gh", "auth", "token"),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode())
    return stdout.decode().strip()
