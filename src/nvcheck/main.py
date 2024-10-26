from __future__ import annotations

from argparse import ArgumentParser, Namespace
from asyncio import run
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .nvchecker import FileLoadError, run_nvchecker, setup_logging
from .srcinfo import read_vers
from .sync import sync_maintained_pkgbuilds
from .update import update_pkgbuilds

if TYPE_CHECKING:
    from collections.abc import Sequence


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
    old_vers = read_vers(pkgs_dir)

    try:
        new_vers, has_failures = run_nvchecker(nvchecker_path, old_vers)
    except FileLoadError as e:
        return str(e)
    if has_failures:
        return "could not update versions"

    updated = {
        name: (old_vers[name], new)
        for name, new in new_vers.items()
        if new.version != old_vers[name]
    }

    run(sync_maintained_pkgbuilds(nvchecker_path))
    run(update_pkgbuilds(updated, repo_dir=args.dir, pkgs_dir=pkgs_dir))
