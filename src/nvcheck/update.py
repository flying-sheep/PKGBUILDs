from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from textwrap import dedent
from typing import TYPE_CHECKING

from httpx import AsyncClient
from packaging.requirements import Requirement

if TYPE_CHECKING:
    from collections.abc import KeysView, Mapping
    from pathlib import Path

    from nvchecker.util import RichResult


PYPI_PAT = re.compile(r"https://pypi.org/project/(?P<name>[\w-]*)/(?P<version>[\d.]+)/")


async def update_pkgbuilds(
    updated: Mapping[str, tuple[str, RichResult]], pkgs_dir: Path
) -> None:
    updater = Updater(pkgs_dir)
    async with asyncio.TaskGroup() as tg:
        for name, (oldver, new) in updated.items():
            tg.create_task(updater.update(name, oldver, new))


@dataclass
class Updater:
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
        deps = {version: task.result() for version, task in tasks.items()}

        msg = (
            f"PyPI update: {self.pkgs_dir / arch_name} {pypi_name} "
            f"{versions[0]} → {versions[1]}"
        )
        if removed := deps[versions[0]] - deps[versions[1]]:
            msg += f"\n- {removed}"
        if added := deps[versions[1]] - deps[versions[0]]:
            msg += f"\n+ {added}"
        print(dedent(msg))

    async def get_deps(self, pypi_name: str, version: str) -> KeysView[Requirement]:
        url = f"https://pypi.org/pypi/{pypi_name}/{version}/json"
        resp = await self.http_client.get(url)
        return dict.fromkeys(
            map(Requirement, resp.json()["info"]["requires_dist"])
        ).keys()
