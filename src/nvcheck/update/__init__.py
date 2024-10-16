from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gidgethub.httpx import GitHubAPI
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
    gh_client: GitHubAPI = field(default=None)  # type: ignore

    def __post_init__(self):
        if self.gh_client is None:
            self.gh_client = GitHubAPI(self.http_client, "flying-sheep/pkgbuilds")

    async def update(self, name: str, oldver: str, new: RichResult) -> None:
        # TODO: do concurrently
        msg = await self.msg_update(name, oldver, new)
        await self.upsert_pr(name, oldver, new, msg)

    async def msg_update(self, name: str, oldver: str, new: RichResult) -> str:
        match new.url:
            case str() if (match := re.fullmatch(pypi.URL_PAT, new.url)):
                return await pypi.msg_update(
                    self.http_client, match["name"], (oldver, match["version"])
                )
            case None:
                msg = f"no url for {name}"
                raise RuntimeError(msg)
            case _:
                msg = f"unknown URL pattern for {name}: {new.url}"
                raise RuntimeError(msg)

    async def upsert_pr(
        self, name: str, oldver: str, new: RichResult, msg: str
    ) -> None:
        async for x in self.gh_client.getiter(
            f"/repos/{self.repo_dir.name}/pulls",
        ):
            pass
