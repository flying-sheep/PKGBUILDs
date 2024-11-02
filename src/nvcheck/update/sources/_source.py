from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

from httpx import AsyncClient

if TYPE_CHECKING:
    import re

    from nvchecker.util import RichResult


__all__ = ["Source", "SimpleSource"]


@dataclass
class Source(ABC):
    http_client: AsyncClient = field(default_factory=lambda: AsyncClient(http2=True))

    url_pat: ClassVar[re.Pattern[str]]

    @property
    def name(self) -> str:
        return type(self).__module__.split(".")[-1]

    @abstractmethod
    async def msg_update(self, oldver: str, new: RichResult) -> str | None:
        raise NotImplementedError


class SimpleSource(Source):
    async def msg_update(self, oldver: str, new: RichResult) -> str | None:
        assert new.url is not None
        if not (match := self.url_pat.fullmatch(new.url)):
            return None
        return f"{self.name} update: {match['name']} ({oldver} -> {new.version})"
