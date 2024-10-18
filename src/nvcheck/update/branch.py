from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import pygit2
from pygit2.repository import Repository


async def create_branch(
    repo_dir: Path, pkg_dir: Path, branch: str, newver: str
) -> None:
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
        # TODO: push
        raise AssertionError()
