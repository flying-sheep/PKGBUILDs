from __future__ import annotations

from argparse import ArgumentParser, Namespace
from asyncio import run
from dataclasses import dataclass, field
from itertools import groupby
from pathlib import Path
from typing import TYPE_CHECKING, cast

import structlog

from .nvchecker import FileLoadError, run_nvchecker, setup_logging
from .srcinfo import read_vers
from .sync import sync_maintained_pkgbuilds
from .update import update_pkgbuilds
from .utils import vercmp

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = cast(
    structlog.types.FilteringBoundLogger, structlog.get_logger(logger_name=__name__)
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


def main(argv: Sequence[str] | None = None) -> int | str | None:
    args = get_parser().parse_args(argv, Args())

    setup_logging()

    nvchecker_path = args.dir / "nvchecker.toml"
    pkgs_dir = args.dir / "pkgs"

    run(sync_maintained_pkgbuilds(nvchecker_path, repo_dir=args.dir))

    old_vers = read_vers(pkgs_dir)
    try:
        new_vers, has_failures = run_nvchecker(nvchecker_path, old_vers)
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
            ((name, (old_vers[name], new)) for name, new in new_vers.items()),
            key=lambda i: vercmp(i[1][1].version, i[1][0]),
        )
    }
    assert groups.keys() <= {-1, 0, 1}

    if groups[-1]:
        pkgs = {
            name: f"{old} > {new.version}" for name, (old, new) in groups[-1].items()
        }
        logger.warning("Packages with higher version than upstream", pkgs=pkgs)
    run(update_pkgbuilds(groups[1], repo_dir=args.dir, pkgs_dir=pkgs_dir))
