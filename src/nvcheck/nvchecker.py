from __future__ import annotations

import asyncio
from argparse import Namespace
from typing import TYPE_CHECKING
from warnings import warn

import nvchecker.core
from nvchecker.core import FileLoadError
from nvchecker.ctxvars import proxy as ctx_proxy
from nvchecker.util import EntryWaiter, RichResult

if TYPE_CHECKING:
    from collections.abc import Coroutine, Mapping
    from pathlib import Path
    from typing import IO, Literal

    from nvchecker.util import RawResult, ResultData


__all__ = ["NVCheckerArgs", "FileLoadError", "setup_logging", "run_nvchecker"]


class NVCheckerArgs(Namespace):
    logger: Literal["both", "pretty", "json"] = "pretty"
    logging: Literal["debug", "info", "warning", "error"] = "info"
    version: bool = False
    json_log_fd: IO[str] | None = None


def setup_logging() -> None:
    nvchecker.core.process_common_arguments(NVCheckerArgs())


async def run_nvchecker(
    cfg_file: Path, oldvers: Mapping[str, str]
) -> tuple[ResultData, bool]:
    """Run nvchecker and return a tuple of (result, has_failures).

    Raises
    ------
    FileLoadError
        if the config file is not valid
    """
    entries, options = nvchecker.core.load_file(str(cfg_file), use_keymanager=False)

    if options.ver_files is not None:
        msg = "This wrapper doesn’t support oldver/newver"
        warn(msg)

    if options.proxy is not None:
        ctx_proxy.set(options.proxy)

    task_sem = asyncio.Semaphore(options.max_concurrency)
    result_q: asyncio.Queue[RawResult] = asyncio.Queue()
    dispatcher = nvchecker.core.setup_httpclient(
        options.max_concurrency,
        options.httplib,
        options.http_timeout,
    )
    entry_waiter = EntryWaiter()
    futures = dispatcher.dispatch(
        entries=entries,
        task_sem=task_sem,
        result_q=result_q,
        keymanager=options.keymanager,
        entry_waiter=entry_waiter,
        tries=1,
        source_configs=options.source_configs,
    )

    oldvers_rich = {n: RichResult(version=v) for n, v in oldvers.items()}
    result_coro = nvchecker.core.process_result(
        oldvers_rich, result_q, entry_waiter, verbose=False
    )
    runner_coro = nvchecker.core.run_tasks(futures)

    return await run(result_coro, runner_coro)


async def run(
    result_coro: Coroutine[None, None, tuple[ResultData, bool]],
    runner_coro: Coroutine[None, None, None],
) -> tuple[ResultData, bool]:
    result_fu = asyncio.create_task(result_coro)
    runner_fu = asyncio.create_task(runner_coro)
    await runner_fu
    result_fu.cancel()
    return await result_fu
