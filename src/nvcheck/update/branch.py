from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, cast

import pygit2
import structlog

from ..utils import run_checked

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pygit2.callbacks import _Credentials
    from pygit2.enums import CredentialType
    from pygit2.repository import Repository


logger = cast(
    "structlog.types.FilteringBoundLogger",
    structlog.get_logger(logger_name="nvcheck.update.branch"),
)


async def create_branch(
    repo_dir: Path, pkg_dir: Path, branch: str, newver: str
) -> None:
    original_repo = pygit2.Repository(str(repo_dir))
    origin = original_repo.remotes["origin"]
    if origin.url is None:
        msg = f"no origin URL for {repo_dir}: {origin.url=}"
        raise RuntimeError(msg)

    with TemporaryDirectory() as tmp_dir:
        repo = cast(
            "Repository",
            pygit2.clone_repository(str(repo_dir), tmp_dir, checkout_branch="main"),
        )
        repo.remotes.set_url("origin", origin.url)
        if origin.push_url:
            repo.remotes.set_push_url("origin", origin.push_url)
        pkg_dir_rel = pkg_dir.relative_to(repo_dir)
        pkg_dir = Path(tmp_dir) / pkg_dir_rel
        del tmp_dir

        lines = (pkg_dir / "PKGBUILD").read_text().splitlines()
        for i, line in enumerate(lines):
            if line.startswith("pkgver="):
                lines[i] = line.replace(line.split("=", 1)[1], newver)
            if line.startswith("pkgrel="):
                lines[i] = line.replace(line.split("=", 1)[1], "1")
        (pkg_dir / "PKGBUILD").write_text("\n".join(lines))

        # run in order, “makepkg --printsrcinfo” needs info from “updpkgsums”
        for cmd in [["updpkgsums"], ["makepkg", "--printsrcinfo"]]:
            await run_checked(*cmd, cwd=pkg_dir, log=True)

        parent = repo.head.target
        repo.index.add_all([pkg_dir_rel / p for p in ["PKGBUILD", ".SRCINFO"]])
        repo.index.write()
        tree = repo.index.write_tree()
        if patch := repo.diff(parent, tree).patch:
            logger.debug("Committing", patch=patch)
        else:
            msg = "nothing to commit"
            raise RuntimeError(msg)
        repo.create_commit(
            repo.head.name,
            repo.default_signature,
            repo.default_signature,
            f"v{newver}",
            tree,
            [parent],
        )
        # “+” means force
        await push(repo.remotes["origin"], [f"+{repo.head.name}:refs/heads/{branch}"])


@dataclass
class RemoteCallbacks(pygit2.RemoteCallbacks):
    future: asyncio.Future = field(default_factory=asyncio.Future)

    def credentials(
        self, url: str, username_from_url: str | None, allowed_types: CredentialType
    ) -> _Credentials:
        return pygit2.KeypairFromAgent(username_from_url or "git")

    def push_update_reference(self, refname: str, message: str | None):
        if message is None:
            self.future.set_result(None)
        else:
            msg = f"Error pushing to {refname}: {message}"
            self.future.set_exception(RuntimeError(msg))


async def push(remote: pygit2.Remote, specs: Iterable[str]) -> None:
    cb = RemoteCallbacks()
    remote.push(list(specs), callbacks=cb)
    await cb.future
