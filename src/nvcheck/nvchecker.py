from __future__ import annotations

from argparse import Namespace
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING
from warnings import warn

import nvchecker.core
from nvchecker.util import ResultData, RawResult, EntryWaiter
from nvchecker.ctxvars import proxy as ctx_proxy

if TYPE_CHECKING:
    from typing import Literal, IO
    from collections.abc import Coroutine


class NVCheckerArgs(Namespace):
    logger: Literal["both", "pretty", "json"] = "pretty"
    logging: Literal["debug", "info", "warning", "error"] = "info"
    version: bool = False
    json_log_fd: IO[str] | None = None


def run_nvchecker(cfg_file: Path, oldvers: ResultData) -> tuple[ResultData, bool]:
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

    result_coro = nvchecker.core.process_result(
        oldvers, result_q, entry_waiter, verbose=False
    )
    runner_coro = nvchecker.core.run_tasks(futures)

    return asyncio.run(run(result_coro, runner_coro))


async def run(
    result_coro: Coroutine[None, None, tuple[ResultData, bool]],
    runner_coro: Coroutine[None, None, None],
) -> tuple[ResultData, bool]:
    result_fu = asyncio.create_task(result_coro)
    runner_fu = asyncio.create_task(runner_coro)
    await runner_fu
    result_fu.cancel()
    return await result_fu
