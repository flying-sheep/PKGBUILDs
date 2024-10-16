from __future__ import annotations

from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TYPE_CHECKING, cast

import nvchecker.core
from nvchecker.util import RichResult

from .update import update_pkgbuilds
from .nvchecker import NVCheckerArgs, run_nvchecker
from .srcinfo import read_vers

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass
class Args(Namespace):
    dir: Path = field(default_factory=Path)


def get_parser() -> ArgumentParser:
    fields_ = {f.name: f for f in fields(Args)}
    parser = ArgumentParser(prog="nvcheck")

    parser.add_argument(
        "dir",
        type=Path,
        default=fields_["dir"].default_factory(),
        nargs="?",
        help="directory containing nvchecker.toml",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int | str | None:
    args = get_parser().parse_args(argv, Args())

    # setup logging
    nvchecker.core.process_common_arguments(NVCheckerArgs())

    oldvers = read_vers(args.dir / "pkgs")

    try:
        newvers, has_failures = run_nvchecker(
            args.dir / "nvchecker.toml",
            {n: RichResult(version=v) for n, v in oldvers.items()},
        )
    except nvchecker.core.FileLoadError as e:
        return str(e)
    if has_failures:
        return "could not update versions"

    updated = {
        name: (oldver, new)
        for name, new in newvers.items()
        if new.version != (oldver := oldvers[name])
    }

    update_pkgbuilds(updated)
