from __future__ import annotations

import asyncio
import re
from collections.abc import KeysView
from dataclasses import dataclass, field
from operator import and_, sub
from typing import TYPE_CHECKING, cast, overload

from packaging.metadata import parse_email
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

from ...utils import ordered_set
from . import _source

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Mapping, Sequence, Set
    from typing import Literal, TypeVar

    from httpx import AsyncClient

    T = TypeVar("T")


__all__ = ["Source"]


class Source(_source.Source):
    url_pat = re.compile(
        r"https://pypi\.org/project/(?P<name>[\w-]*)/(?P<version>[\d.]+)/"
    )

    async def msg_update(self, name: str, versions: tuple[str, str]) -> str:
        reqs = await get_all_reqs(self.http_client, name, versions)
        return str(PyPIDepChanges(name, reqs))


async def get_all_reqs(
    http_client: AsyncClient, name: str, versions: Iterable[str]
) -> dict[str, KeysView[Requirement]]:
    async with asyncio.TaskGroup() as tg:
        tasks = {
            version: tg.create_task(get_reqs(http_client, name, version))
            for version in versions
        }
    return {version: task.result() for version, task in tasks.items()}


async def get_reqs(
    http_client: AsyncClient, name: str, version: str
) -> KeysView[Requirement]:
    url = f"https://pypi.org/simple/{name}/"
    headers = {"accept": "application/vnd.pypi.simple.v1+json"}
    resp = await http_client.get(url, headers=headers)
    resp.raise_for_status()
    resp_json = resp.json()

    url_gen = (
        cast(str, f["url"])
        for f in resp_json["files"]
        if f["filename"].startswith(f"{name.replace('-', '_')}-{version}")
        and f["data-dist-info-metadata"]
    )
    if (url := next(url_gen, None)) is None:
        msg = f"no metadata for {name} {version} at {url}"
        raise RuntimeError(msg)
    resp = await http_client.get(f"{url}.metadata", headers=headers)
    resp.raise_for_status()
    metadata, _ = parse_email(resp.text)

    # legacy API would be:
    # url = f"https://pypi.org/pypi/{pypi_name}/{version}/json"
    # resp = await http_client.get(url)
    # resp.raise_for_status()
    # metadata = cast(packaging.metadata.RawMetadata, resp.json()["info"])

    return ordered_set(map(Requirement, metadata.get("requires_dist", [])))


@dataclass
class PyPIDepChanges:
    name: str
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
        self.changed = [
            (old, new)
            for old, new in [
                tuple(find_req(req.name, reqs) for reqs in self.reqs.values())
                for req in reqs_in_both
            ]
            if old != new
        ]

    def __str__(self) -> str:
        v0, v1 = self.reqs.keys()
        msg = f"PyPI update: {self.name} ({v0} -> {v1})"
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
