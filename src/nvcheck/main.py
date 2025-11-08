from __future__ import annotations

import asyncio
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from itertools import groupby
from pathlib import Path
from typing import TYPE_CHECKING, cast

import structlog

from .github import get_token
from .nvchecker import FileLoadError, run_nvchecker, setup_logging
from .srcinfo import read_vers
from .sync import sync_maintained_pkgbuilds
from .update import update_pkgbuilds
from .utils import vercmp

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Literal

    from nvchecker.util import RichResult


logger = cast(
    "structlog.types.FilteringBoundLogger", structlog.get_logger(logger_name="nvcheck")
)


@dataclass
class Args(Namespace):
    dir: Path = field(default_factory=Path.cwd)


def get_parser() -> ArgumentParser:
    defaults = Args()

    parser = ArgumentParser(prog="nvcheck")

    parser.add_argument(
        "dir",
        type=Path,
        default=defaults.dir,
        nargs="?",
        help="directory containing `nvchecker.toml` and `pkgs/` subdirectory",
    )

    return parser


def ver_key(item: tuple[str, tuple[str, RichResult]]) -> Literal[0, -1, 1]:
    _, (oldver, new) = item
    return vercmp(new.version, oldver)


async def main_async(argv: Sequence[str] | None = None) -> int | str | None:
    args = get_parser().parse_args(argv, Args())

    setup_logging()

    nvchecker_path = args.dir / "nvchecker.toml"
    pkgs_dir = args.dir / "pkgs"

    _, gh_token = await asyncio.gather(
        sync_maintained_pkgbuilds(nvchecker_path, repo_dir=args.dir),
        get_token(from_gh=True),
    )

    old_vers = read_vers(pkgs_dir, include_vcs=False)
    try:
        new_vers, has_failures = await run_nvchecker(
            nvchecker_path, old_vers, gh_token=gh_token
        )
    except FileLoadError as e:
        return str(e)
    if has_failures:
        failed = old_vers.keys() - new_vers.keys()
        logger.error("some packages failed to update", failed=failed)

    # group by version comparison.
    # -1: upstream is lower, 0: equal, 1: upstream is higher
    groups = {
        group: dict(vers)
        for group, vers in groupby(
            sorted(
                ((name, (old_vers[name], new)) for name, new in new_vers.items()),
                key=ver_key,
            ),
            key=ver_key,
        )
    }
    assert groups.keys() <= {-1, 0, 1}

    if too_new := groups.get(-1):
        pkgs = {name: f"{old} > {new.version}" for name, (old, new) in too_new.items()}
        logger.warning("Higher versions than upstream", pkgs=pkgs)
    if upgraded := groups.get(1):
        await update_pkgbuilds(
            upgraded, repo_dir=args.dir, pkgs_dir=pkgs_dir, gh_token=gh_token
        )


def main(argv: Sequence[str] | None = None) -> int | str | None:
    from asyncio import run

    run(main_async(argv))
