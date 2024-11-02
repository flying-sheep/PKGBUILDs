from __future__ import annotations

import re

from . import _source

__all__ = ["Source"]


class Source(_source.SimpleSource):
    url_pat = re.compile(
        r"https://crates\.io/crates/(?P<name>[\w-]+)/(?P<version>[\d.]+)"
    )
