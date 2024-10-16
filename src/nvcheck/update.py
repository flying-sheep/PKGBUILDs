from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from nvchecker.util import RichResult


PYPI_PAT = re.compile(r"https://pypi.org/project/(?P<name>[\w-]*)/(?P<version>[\d.]+)/")


def update_pkgbuilds(updated: Mapping[str, tuple[str, RichResult]]) -> None:
    for name, (oldver, new) in updated.items():
        match new.url:
            case str() if (match := re.fullmatch(PYPI_PAT, new.url)):
                update_pypi(name, match["name"], (oldver, match["version"]))
            case None:
                msg = f"no url for {name}"
                raise RuntimeError(msg)
            case _:
                msg = f"unknown URL pattern for {name}: {new.url}"
                raise RuntimeError(msg)


def update_pypi(arch_name: str, pypi_name: str, versions: tuple[str, str]) -> None:
    print("PyPI update:", arch_name, pypi_name, versions[0], "→", versions[1])
