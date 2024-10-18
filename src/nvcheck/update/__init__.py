from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypedDict, cast

import githubkit
import githubkit.exception
import structlog
from githubkit import GitHub
from githubkit.rest import ValidationError
from httpx import AsyncClient

from . import pypi

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableSequence
    from pathlib import Path
    from typing import TypeVar

    from githubkit.rest import PullRequestSimple
    from nvchecker.util import RichResult

    T = TypeVar("T")


logger = cast(
    structlog.types.FilteringBoundLogger, structlog.get_logger(logger_name=__name__)
)


class CommonArgs(TypedDict):
    owner: str
    repo: str


LABEL_COLOR = "e6db74"
COMMON_ARGS = CommonArgs(owner="flying-sheep", repo="pkgbuilds")


async def update_pkgbuilds(
    updated: Mapping[str, tuple[str, RichResult]], *, repo_dir: Path, pkgs_dir: Path
) -> None:
    updater = Updater(repo_dir, pkgs_dir)
    async with updater.http_client, asyncio.TaskGroup() as tg:
        for name, (oldver, new) in updated.items():
            tg.create_task(updater.update(name, oldver, new))


def create_github_client() -> GitHub:
    return GitHub(auth=os.environ.get("GH_TOKEN"))


@dataclass
class Updater:
    repo_dir: Path
    pkgs_dir: Path
    http_client: AsyncClient = field(default_factory=lambda: AsyncClient(http2=True))
    gh_client: GitHub = field(default_factory=create_github_client)
    known_prs: MutableSequence[PullRequestSimple] = field(default_factory=list)

    async def update(self, name: str, oldver: str, new: RichResult) -> None:
        # TODO: do concurrently
        self.known_prs.clear()
        async for pr in self.gh_client.paginate(
            self.gh_client.rest.pulls.async_list,
            **COMMON_ARGS,
            state="open",
        ):
            self.known_prs.append(pr)
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
        label = f"pkgs/{name}"
        pr = next((pr for pr in self.known_prs if label in pr.labels), None)
        try:
            await self.gh_client.rest.issues.async_create_label(
                **COMMON_ARGS, name=label, color=LABEL_COLOR
            )
        except githubkit.exception.RequestFailed as e:
            errors = cast(ValidationError, e.response.parsed_data).errors or []
            if len(errors) != 1 or errors[0].code != "already_exists":
                raise
        logger.info(
            "Creating PR" if pr is None else "Updating PR",
            package=name,
            pr=None if pr is None else pr.number,
        )
        # TODO: actually update
