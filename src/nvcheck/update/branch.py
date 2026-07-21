from __future__ import annotations

import asyncio
import re
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


logger = cast(
    "structlog.types.FilteringBoundLogger",
    structlog.get_logger(logger_name="nvcheck.update.branch"),
)

_SCP_LIKE_URL = re.compile(
    r"^(?:ssh://)?git@(?P<host>[^:/]+)[:/](?P<path>.+?)(?:\.git)?$"
)


def to_https_url(url: str) -> str:
    if url.startswith(("http://", "https://")):
        return url
    if m := _SCP_LIKE_URL.match(url):
        return f"https://{m['host']}/{m['path']}.git"
    msg = f"don't know how to convert to an https:// url: {url}"
    raise RuntimeError(msg)


async def create_branch(
    repo_dir: Path, pkg_dir: Path, branch: str, newver: str, *, gh_token: str
) -> None:
    original_repo = pygit2.Repository(str(repo_dir))
    origin = original_repo.remotes["origin"]
    if origin.url is None:
        msg = f"no origin URL for {repo_dir}: {origin.url=}"
        raise RuntimeError(msg)

    with TemporaryDirectory() as tmp_dir:
        repo = pygit2.clone_repository(str(repo_dir), tmp_dir, checkout_branch="main")
        repo.remotes.set_url("origin", origin.url)
        repo.remotes.set_push_url("origin", to_https_url(origin.url))
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

        await run_checked("updpkgsums", cwd=pkg_dir, log=True)
        src_info = await run_checked("makepkg", "--printsrcinfo", cwd=pkg_dir, log=True)
        Path(pkg_dir / ".SRCINFO").write_text(src_info)

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
        await push(
            repo.remotes["origin"],
            [f"+{repo.head.name}:refs/heads/{branch}"],
            gh_token=gh_token,
        )


@dataclass
class RemoteCallbacks(pygit2.RemoteCallbacks):
    gh_token: str
    future: asyncio.Future = field(default_factory=asyncio.Future)

    def credentials(
        self, url: str, _username_from_url: str | None, _allowed_types: CredentialType
    ) -> _Credentials:
        return pygit2.UserPass("x-access-token", self.gh_token)

    def push_update_reference(self, refname: str, message: str | None):
        if message is None:
            self.future.set_result(None)
        else:
            msg = f"Error pushing to {refname}: {message}"
            self.future.set_exception(RuntimeError(msg))


async def push(remote: pygit2.Remote, specs: Iterable[str], *, gh_token: str) -> None:
    cb = RemoteCallbacks(gh_token=gh_token)
    remote.push(list(specs), callbacks=cb)
    await cb.future
