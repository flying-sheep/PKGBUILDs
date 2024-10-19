from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, cast

import pygit2
from pygit2.repository import Repository

if TYPE_CHECKING:
    from collections.abc import Iterable


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
            Repository,
            pygit2.clone_repository(str(repo_dir), tmp_dir, checkout_branch="main"),
        )
        pkg_dir = Path(tmp_dir) / pkg_dir.relative_to(repo_dir)
        del tmp_dir

        lines = (pkg_dir / "PKGBUILD").read_text().splitlines()
        for i, line in enumerate(lines):
            if line.startswith("pkgver="):
                lines[i] = line.replace(line.split("=", 1)[1], newver)
                break
        (pkg_dir / "PKGBUILD").write_text("\n".join(lines))

        for cmd in ["updpkgsums", "mksrcinfo"]:
            proc = await asyncio.create_subprocess_exec(cmd, cwd=pkg_dir)
            if (await proc.wait()) != 0:
                raise RuntimeError(f"{cmd} failed")

        repo.index.add_all(["PKGBUILD", ".SRCINFO"])
        repo.create_commit(
            "HEAD",
            repo.default_signature,
            repo.default_signature,
            f"v{newver}",
            repo.index.write_tree(),
            [repo.head.target],
        )
        repo.index.write()

        # “+” means force
        repo.remotes.set_url("origin", origin.url)
        if origin.push_url:
            repo.remotes.set_push_url("origin", origin.push_url)
        await push(repo.remotes["origin"], [f"+HEAD:refs/heads/{branch}"])


@dataclass
class RemoteCallbacks(pygit2.RemoteCallbacks):
    future: asyncio.Future = field(default_factory=asyncio.Future)

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
