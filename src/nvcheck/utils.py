from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Iterable
from textwrap import indent
from typing import TYPE_CHECKING, cast

import structlog

if TYPE_CHECKING:
    import os
    from collections.abc import Iterable, KeysView, Sequence
    from typing import Literal, TypeVar

    StrOrBytesPath = str | bytes | os.PathLike[str] | os.PathLike[bytes]

    T = TypeVar("T")


logger = cast(
    structlog.types.FilteringBoundLogger,
    structlog.get_logger(logger_name="nvcheck.utils"),
)


def ordered_set(iterable: Iterable[T]) -> KeysView[T]:
    return dict.fromkeys(iterable).keys()


class VerboseCalledProcessError(subprocess.CalledProcessError, RuntimeError):
    def __str__(self) -> str:
        return f"{super().__str__()}\n{self._fmt('stdout')}\n{self._fmt('stderr')}"

    def _fmt(self, what: Literal["stdout", "stderr"]) -> str:
        decoded = getattr(self, what).decode("utf-8", "backslashreplace")
        if len(decoded) < 80:
            return f"{what}: {decoded}"
        return f"{what}:\n{indent(decoded, '\t')}"


async def run_checked(
    cmd: StrOrBytesPath,
    *args: StrOrBytesPath,
    cmd_name: StrOrBytesPath | Sequence[StrOrBytesPath] | None = None,
    log: bool | None = True,
    cwd: StrOrBytesPath | None = None,
) -> str:
    if log is None:
        log = cmd_name is not None
    if cmd_name is None:
        cmd_name = cmd
    proc = await asyncio.create_subprocess_exec(
        cmd,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    out, err = await proc.communicate()
    assert proc.returncode is not None
    if proc.returncode != 0:
        raise VerboseCalledProcessError(proc.returncode, cmd_name, out, err)
    if log:
        logger.info(f"Command {cmd_name} ran", out=out.decode(), err=err.decode())
    return out.decode()


def vercmp(a: str, b: str, /) -> Literal[-1, 0, 1]:
    from pyalpm import vercmp

    return vercmp(a, b)
