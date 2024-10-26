from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    import re

    from httpx import AsyncClient


@dataclass
class Source(ABC):
    http_client: AsyncClient

    url_pat: ClassVar[re.Pattern[str]]

    @abstractmethod
    async def msg_update(self, name: str, version: tuple[str, str]) -> str | None:
        raise NotImplementedError
