from __future__ import annotations

import asyncio
import re
from collections.abc import KeysView
from dataclasses import dataclass, field
from operator import and_, sub
from typing import TYPE_CHECKING, cast, overload

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

from ..utils import ordered_set

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Mapping, Sequence, Set
    from typing import Literal, TypeVar

    from httpx import AsyncClient

    T = TypeVar("T")


__all__ = ["URL_PAT", "msg_update"]

URL_PAT = re.compile(r"https://pypi.org/project/(?P<name>[\w-]*)/(?P<version>[\d.]+)/")


async def msg_update(
    http_client: AsyncClient, pypi_name: str, versions: tuple[str, str]
) -> str:
    reqs = await get_all_reqs(http_client, pypi_name, versions)
    return str(PyPIDepChanges(pypi_name, reqs))


async def get_all_reqs(
    http_client: AsyncClient, pypi_name: str, versions: Iterable[str]
) -> dict[str, KeysView[Requirement]]:
    async with asyncio.TaskGroup() as tg:
        tasks = {
            version: tg.create_task(get_reqs(http_client, pypi_name, version))
            for version in versions
        }
    return {version: task.result() for version, task in tasks.items()}


async def get_reqs(
    http_client: AsyncClient, pypi_name: str, version: str
) -> KeysView[Requirement]:
    url = f"https://pypi.org/pypi/{pypi_name}/{version}/json"
    resp = await http_client.get(url)
    return ordered_set(map(Requirement, resp.json()["info"]["requires_dist"]))


@dataclass
class PyPIDepChanges:
    pypi_name: str
    reqs: Mapping[str, KeysView[Requirement]]

    removed: KeysView[Requirement] = field(init=False)
    added: KeysView[Requirement] = field(init=False)
    changed: Sequence[tuple[Requirement, Requirement]] = field(init=False)

    def __post_init__(self) -> None:
        bare_reqs = {
            v: ordered_set(prune_reqs(self.reqs[v], extras=set(), remove_vers=True))
            for v in self.reqs
        }
        self.removed = sub(*bare_reqs.values())
        self.added = sub(*reversed(bare_reqs.values()))
        reqs_in_both = cast(KeysView[Requirement], and_(*bare_reqs.values()))
        self.changed = [  # type: ignore
            tuple(find_req(req.name, reqs) for reqs in self.reqs.values())
            for req in reqs_in_both
        ]

    def __str__(self) -> str:
        v0, v1 = self.reqs.keys()
        msg = f"PyPI update: {self.pypi_name} ({v0} -> {v1})"
        if self.removed:
            msg += f"\n- { {str(req) for req in self.removed} }"
        if self.added:
            msg += f"\n+ { {str(req) for req in self.added} }"
        if self.changed:
            msg += f"\n~ { {f"{v0} -> {v1}" for v0, v1 in self.changed} }"
        return msg


@overload
def find_req(
    name: str, reqs: Iterable[Requirement], *, strict: Literal[True] = True
) -> Requirement: ...
@overload
def find_req(
    name: str, reqs: Iterable[Requirement], *, strict: Literal[False]
) -> Requirement | None: ...
def find_req(
    name: str, reqs: Iterable[Requirement], *, strict: bool = True
) -> Requirement | None:
    for req in reqs:
        if req.name == name:
            return req
    if strict:
        raise ValueError(f"{name} not found in {reqs}")


def prune_reqs(
    reqs: Iterable[Requirement],
    *,
    extras: Set[str] | None = None,
    remove_vers: bool = False,
) -> Generator[Requirement, None, None]:
    """Remove version specifiers from requirements and prune extras if specified.

    Parameters
    ----------
    extras
        If `None`, do not prune extras.
        If specified, prune requirements with only extras that are not in the set.
    """
    for req in reqs:
        req = Requirement(str(req))  # noqa: PLW2901
        if (
            extras is not None
            and req.marker
            and not any(req.marker.evaluate({"extra": extra}) for extra in extras)
        ):
            continue  # skip if extra not in set
        if remove_vers and len(req.specifier):
            req.specifier = SpecifierSet()
        yield req