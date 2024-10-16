from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from httpx import AsyncClient

from . import pypi

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path
    from typing import TypeVar

    from nvchecker.util import RichResult

    T = TypeVar("T")


async def update_pkgbuilds(
    updated: Mapping[str, tuple[str, RichResult]], *, repo_dir: Path, pkgs_dir: Path
) -> None:
    updater = Updater(repo_dir, pkgs_dir)
    async with updater.http_client, asyncio.TaskGroup() as tg:
        for name, (oldver, new) in updated.items():
            tg.create_task(updater.update(name, oldver, new))


@dataclass
class Updater:
    repo_dir: Path
    pkgs_dir: Path
    http_client: AsyncClient = field(default_factory=lambda: AsyncClient(http2=True))

    async def update(self, name: str, oldver: str, new: RichResult) -> None:
        msg = await self.msg_update(name, oldver, new)
        print(msg)

    async def msg_update(self, name, oldver, new):
        match new.url:
            case str() if (match := re.fullmatch(pypi.URL_PAT, new.url)):
                msg = await pypi.msg_update(
                    self.http_client, match["name"], (oldver, match["version"])
                )
            case None:
                msg = f"no url for {name}"
                raise RuntimeError(msg)
            case _:
                msg = f"unknown URL pattern for {name}: {new.url}"
                raise RuntimeError(msg)
        return msg
