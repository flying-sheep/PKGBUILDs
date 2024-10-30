from __future__ import annotations

from pathlib import Path
from typing import cast

from srcinfo.parse import parse_srcinfo


def read_vers(dir: Path | None = None) -> dict[str, str]:
    if dir is None:
        dir = Path()
    vers: dict[str, str] = {}
    for d in dir.iterdir():
        if d.name.startswith(".") or not d.is_dir():
            continue
        srcinfo, errors = parse_srcinfo((d / ".SRCINFO").read_text())
        if errors:
            raise RuntimeError(f"Error parsing {d}:\n{errors}")
        vers[d.name] = cast(str, srcinfo["pkgver"])
    return vers
