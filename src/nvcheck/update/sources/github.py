from __future__ import annotations

import re

from . import _source

__all__ = ["Source"]


class Source(_source.Source):
    url_pat = re.compile(
        r"https://github\.com/[^/]+/(?P<name>[^/]+)/releases/tag/v?(?P<version>[\d.]+)"
    )

    async def msg_update(self, name: str, versions: tuple[str, str]) -> str:
        return f"github.com update: {name} ({versions[0]} -> {versions[1]})"
