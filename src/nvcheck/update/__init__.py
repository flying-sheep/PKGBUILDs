from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from functools import partial
from typing import TYPE_CHECKING, TypedDict, cast

import githubkit
import githubkit.exception
import structlog
from githubkit import GitHub
from githubkit.rest import ValidationError
from httpx import AsyncClient

from . import cratesio, pypi
from .branch import create_branch

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


class PrUpdateable(TypedDict):
    title: str
    base: str
    body: str


LABEL_COLOR = "e6db74"
COMMON_ARGS = CommonArgs(owner="flying-sheep", repo="pkgbuilds")


async def update_pkgbuilds(
    updated: Mapping[str, tuple[str, RichResult]], *, repo_dir: Path, pkgs_dir: Path
) -> None:
    updater = Updater(repo_dir, pkgs_dir)
    async with updater.http_client, asyncio.TaskGroup() as tg:
        for name, (oldver, new) in updated.items():
            tg.create_task(updater.update(name, oldver, new))


def get_token() -> str | None:
    return os.environ.get("GH_TOKEN")


def create_github_client() -> GitHub:
    return GitHub(auth=get_token())


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
            case str() if (match := re.fullmatch(cratesio.URL_PAT, new.url)):
                return await cratesio.msg_update(
                    self.http_client, match["name"], (oldver, match["version"])
                )
            case None:
                msg = f"no url for {name}"
                raise RuntimeError(msg)
            case _:
                msg = f"unknown URL pattern for {name}: {new.url}"
                raise RuntimeError(msg)

    def find_pr(
        self, number: int | None = None, *, labels: set[str]
    ) -> PullRequestSimple | None:
        for pr in self.known_prs:
            if number is not None and pr.number != number:
                continue
            if not (labels <= {label.name for label in pr.labels}):
                continue
            return pr
        return None

    async def upsert_pr(
        self, name: str, oldver: str, new: RichResult, msg: str
    ) -> None:
        label = f"pkgs/{name}"
        try:
            await self.gh_client.rest.issues.async_create_label(
                **COMMON_ARGS, name=label, color=LABEL_COLOR
            )
        except githubkit.exception.RequestFailed as e:
            errors = cast(ValidationError, e.response.parsed_data).errors or []
            if len(errors) != 1 or errors[0].code != "already_exists":
                raise

        pr = self.find_pr(labels={label})
        branch = await self.create_branch(name, new.version)
        logger.info(
            "Creating PR" if pr is None else "Updating PR",
            package=name,
            pr=None if pr is None else pr.number,
            branch=branch,
        )
        do_req = (
            partial(self.gh_client.rest.pulls.async_create, head=branch)
            if pr is None
            else partial(self.gh_client.rest.pulls.async_update, pull_number=pr.number)
        )
        title = f"Update package {name} from {oldver} to {new.version}"
        data = PrUpdateable(title=title, base="main", body=msg)
        pr = (await do_req(**COMMON_ARGS, **data)).parsed_data
        await self.gh_client.rest.issues.async_add_labels(
            **COMMON_ARGS, issue_number=pr.number, labels=[label]
        )

    async def create_branch(self, name: str, newver: str) -> str:
        branch = f"update-{name}-to-{newver}"
        await create_branch(self.repo_dir, self.pkgs_dir / name, branch, newver)
        return branch
