from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

import structlog

if TYPE_CHECKING:
    import os
    from collections.abc import Iterable, KeysView, Sequence
    from typing import TypeVar

    StrOrBytesPath = str | bytes | os.PathLike[str] | os.PathLike[bytes]

    T = TypeVar("T")


logger = cast(
    structlog.types.FilteringBoundLogger, structlog.get_logger(logger_name=__name__)
)


def ordered_set(iterable: Iterable[T]) -> KeysView[T]:
    return dict.fromkeys(iterable).keys()


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
        raise subprocess.CalledProcessError(proc.returncode, cmd_name, out, err)
    if log:
        logger.info(f"Command {cmd_name} ran", out=out.decode(), err=err.decode())
    return out.decode()
