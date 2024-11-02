from __future__ import annotations

import re

from . import _source

__all__ = ["Source"]


class Source(_source.SimpleSource):
    url_pat = re.compile(
        r"https://github\.com/[^/]+/(?P<name>[^/]+)/releases/tag/v?(?P<version>[\d.]+)"
    )
