from __future__ import annotations

from pathlib import Path

import nvchecker.core
from nvchecker.util import RichResult

from .update import update_pkgbuilds
from .nvchecker import NVCheckerArgs, run_nvchecker
from .srcinfo import read_vers


def main() -> int | str | None:
    here = Path()

    # setup logging
    nvchecker.core.process_common_arguments(NVCheckerArgs())

    oldvers = read_vers(here)

    try:
        newvers, has_failures = run_nvchecker(
            here / "nvchecker.toml",
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
