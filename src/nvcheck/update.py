from __future__ import annotations

import asyncio
import re
from collections.abc import KeysView
from dataclasses import dataclass, field
from operator import and_, sub
from typing import TYPE_CHECKING, cast, overload

from httpx import AsyncClient
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Mapping, Sequence, Set
    from pathlib import Path
    from typing import Literal, TypeVar

    from nvchecker.util import RichResult

    T = TypeVar("T")


PYPI_PAT = re.compile(r"https://pypi.org/project/(?P<name>[\w-]*)/(?P<version>[\d.]+)/")


def ordered_set(iterable: Iterable[T]) -> KeysView[T]:
    return dict.fromkeys(iterable).keys()


async def update_pkgbuilds(
    updated: Mapping[str, tuple[str, RichResult]], *, repo_dir: Path, pkgs_dir: Path
) -> None:
    updater = Updater(repo_dir, pkgs_dir)
    async with asyncio.TaskGroup() as tg:
        for name, (oldver, new) in updated.items():
            tg.create_task(updater.update(name, oldver, new))


@dataclass
class Updater:
    repo_dir: Path
    pkgs_dir: Path
    http_client: AsyncClient = field(default_factory=AsyncClient)

    async def update(self, name: str, oldver: str, new: RichResult) -> None:
        async with self.http_client:
            match new.url:
                case str() if (match := re.fullmatch(PYPI_PAT, new.url)):
                    await self.update_pypi(
                        name, match["name"], (oldver, match["version"])
                    )
                case None:
                    msg = f"no url for {name}"
                    raise RuntimeError(msg)
                case _:
                    msg = f"unknown URL pattern for {name}: {new.url}"
                    raise RuntimeError(msg)

    async def update_pypi(
        self, arch_name: str, pypi_name: str, versions: tuple[str, str]
    ) -> None:
        async with asyncio.TaskGroup() as tg:
            tasks = {
                version: tg.create_task(self.get_deps(pypi_name, version))
                for version in versions
            }
        reqs = {version: task.result() for version, task in tasks.items()}

        print(PyPIDepChanges(pypi_name, reqs))

    async def get_deps(self, pypi_name: str, version: str) -> KeysView[Requirement]:
        url = f"https://pypi.org/pypi/{pypi_name}/{version}/json"
        resp = await self.http_client.get(url)
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
        self.changed = [
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
