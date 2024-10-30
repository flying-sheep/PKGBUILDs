from __future__ import annotations

from itertools import chain, pairwise
from typing import TYPE_CHECKING, cast, overload

import structlog
from nvchecker.core import load_file

from aurweb_client import Client
from aurweb_client.api.package_search import get_rpc_v5_search_arg as search
from aurweb_client.models.get_rpc_v5_search_arg_by import GetRpcV5SearchArgBy as By
from aurweb_client.types import Unset

from .update import COMMON_ARGS
from .utils import run_checked

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet
    from pathlib import Path
    from typing import Literal

    SourceName = Literal["pypi", "cratesio", "github"]


logger = cast(
    structlog.types.FilteringBoundLogger, structlog.get_logger(logger_name=__name__)
)


async def sync_maintained_pkgbuilds(nvchecker_path: Path, *, repo_dir: Path) -> None:
    entries, _ = load_file(str(nvchecker_path), use_keymanager=False)

    client = Client("https://aur.archlinux.org/", raise_on_unexpected_status=True)
    resp = await search.asyncio(COMMON_ARGS["owner"], client=client, by=By.MAINTAINER)
    if resp is None or isinstance(resp.results, Unset):
        return

    maintained = {
        result.name for result in resp.results if isinstance(result.name, str)
    }
    tracked = entries.keys()

    # these are run sequentially since the git operations can have race conditions
    if untracked := maintained - tracked:
        logger.warn("Found untracked packages", untracked=untracked)
        await add_untracked(untracked, repo_dir=repo_dir, nvchecker_path=nvchecker_path)
    if unmaintained := tracked - maintained:
        logger.warn("Found unmaintained packages", unmaintained=unmaintained)
        await remove_unmaintained(
            unmaintained, repo_dir=repo_dir, nvchecker_path=nvchecker_path
        )


async def add_untracked(
    untracked: AbstractSet[str], *, repo_dir: Path, nvchecker_path: Path
) -> None:
    # run sequentially since the git operations can have race conditions
    unhandled: set[str] = set()
    for pkg in untracked:
        if (source := infer_source(pkg)) is None:
            unhandled.add(pkg)
            continue
        await pkg_mod(
            pkg, "add", source=source, repo_dir=repo_dir, nvchecker_path=nvchecker_path
        )
    if unhandled:
        logger.critical("Source could not inferred for packages", unhandled=unhandled)


def infer_source(name: str) -> SourceName | None:
    if name.startswith("python-") or name.startswith("jupyter-"):
        return "pypi"
    return None


async def remove_unmaintained(
    unmaintained: AbstractSet[str], *, repo_dir: Path, nvchecker_path: Path
) -> None:
    # run sequentially since the git operations can have race conditions
    for pkg in unmaintained:
        await pkg_mod(pkg, "remove", repo_dir=repo_dir, nvchecker_path=nvchecker_path)


@overload
async def pkg_mod(
    name: str,
    cmd: Literal["add"],
    *,
    source: SourceName,
    repo_dir: Path,
    nvchecker_path: Path,
) -> None: ...
@overload
async def pkg_mod(
    name: str,
    cmd: Literal["push", "remove"],
    *,
    source: None = None,
    repo_dir: Path,
    nvchecker_path: Path,
) -> None: ...
async def pkg_mod(
    name: str,
    cmd: Literal["add", "push", "remove"],
    *,
    source: SourceName | None = None,
    repo_dir: Path,
    nvchecker_path: Path,
) -> None:
    match cmd:
        case "remove":
            for args in [
                ("git", "rm", "-rf", f"pkgs/{name}"),
                ("git", "commit", "-m", f"remove {name}"),
            ]:
                await run_checked(*args, cmd_name=args[:2], cwd=repo_dir)
        case "add" | "push":
            await run_checked(
                *(cmd_name := ("git", "subtree", cmd)),
                f"--prefix=pkgs/{name}",
                f"ssh://aur@aur.archlinux.org/{name}.git",
                "master",
                cmd_name=cmd_name,
                cwd=repo_dir,
            )
        case _:
            msg = f"unknown cmd: {cmd}"
            raise RuntimeError(msg)

    if cmd not in {"add", "remove"}:
        assert source is None
        return

    segments = parse_nvchecker_toml(nvchecker_path)
    segment_list = list(segments.values())
    if cmd == "add":
        assert source is not None
        insert_idx = sorted(chain(segments.keys(), name)).index(name)
        segment_list.insert(insert_idx, f"[{name}]\nsource = '{source}'")
    elif cmd == "remove":
        assert source is None
        remove_idx = list(segments.keys()).index(name)
        segment_list.pop(remove_idx)
    nvchecker_path.write_text("\n\n".join(segment_list))


def parse_nvchecker_toml(
    nvchecker_path: Path,
) -> dict[str, str]:
    lines = nvchecker_path.read_text().splitlines()
    name2start = {line[1:-1]: i for i, line in enumerate(lines) if line.startswith("[")}
    segments = {
        prev: "\n".join(lines[prevstart:nextstart])
        for (prev, prevstart), (_, nextstart) in pairwise(
            chain(name2start.items(), [("", len(lines))])
        )
        if prev != "__config__"
    }
    if sorted(segments.keys()) != list(segments.keys()):
        msg = "unsorted tables in nvchecker.toml"
        raise RuntimeError(msg)
    return segments
