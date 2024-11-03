from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from srcinfo.parse import parse_srcinfo

if TYPE_CHECKING:
    from collections.abc import Generator


def read_vers(dir: Path | None = None) -> dict[str, str]:
    if dir is None:
        dir = Path()
    return dict(_read_vers(dir))


def _read_vers(dir: Path) -> Generator[tuple[str, str], None, None]:
    for d in dir.iterdir():
        if d.name.startswith(".") or not d.is_dir():
            continue
        srcinfo, errors = parse_srcinfo((d / ".SRCINFO").read_text())
        if errors:
            raise RuntimeError(f"Error parsing {d}:\n{errors}")
        yield d.name, cast(str, srcinfo["pkgver"])
