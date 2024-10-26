from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast, overload

import structlog
from nvchecker.core import load_file

from aurweb_client import Client
from aurweb_client.api.package_search import get_rpc_v5_search_arg as search
from aurweb_client.models.get_rpc_v5_search_arg_by import GetRpcV5SearchArgBy as By
from aurweb_client.types import Unset

from .update import COMMON_ARGS

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet
    from pathlib import Path
    from typing import Literal

    Type = Literal["pypi", "cratesio", "github"]


logger = cast(
    structlog.types.FilteringBoundLogger, structlog.get_logger(logger_name=__name__)
)


async def sync_maintained_pkgbuilds(nvchecker_path: Path, *, repo_dir: Path) -> None:
    entries, _ = load_file(str(nvchecker_path), use_keymanager=False)

    client = Client("https://aur.archlinux.org/", raise_on_unexpected_status=True)
    resp = await search.asyncio(COMMON_ARGS["owner"], client=client, by=By.MAINTAINER)
    if resp is None or isinstance(resp.results, Unset):
        return

    maintained = {result.name for result in resp.results}
    tracked = entries.keys()

    if untracked := maintained - tracked:
        logger.critical("Found untracked packages", untracked=untracked)
        await add_untracked(untracked, repo_dir=repo_dir, nvchecker_path=nvchecker_path)
    if unmaintained := tracked - maintained:
        logger.critical("Found unmaintained packages", unmaintained=unmaintained)


async def add_untracked(
    untracked: AbstractSet[str], *, repo_dir: Path, nvchecker_path: Path
) -> None:
    raise NotImplementedError("add_untracked not implemented")  # TODO


@overload
async def pkg_mod(
    name: str,
    cmd: Literal["add"],
    *,
    type: Type,
    repo_dir: Path,
    nvchecker_path: Path,
) -> None: ...
@overload
async def pkg_mod(
    name: str,
    cmd: Literal["push", "remove"],
    *,
    type: None,
    repo_dir: Path,
    nvchecker_path: Path,
) -> None: ...
async def pkg_mod(
    name: str,
    cmd: Literal["add", "push", "remove"],
    *,
    type: Type | None,
    repo_dir: Path,
    nvchecker_path: Path,
) -> None:
    assert (type is not None) is (cmd == "add")
    if type == "remove":
        raise NotImplementedError("remove not implemented")  # TODO
    proc = await asyncio.subprocess.create_subprocess_exec(
        "git",
        "subtree",
        cmd,
        f"--prefix=pkgs/{name}",
        f"ssh://aur@aur.archlinux.org/{name}.git",
        "master",
        cwd=repo_dir,
    )
    if (await proc.wait()) != 0:
        raise RuntimeError(f"git subtree {cmd} failed")

    # TODO: modify nvchecker.toml
