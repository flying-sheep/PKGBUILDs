from __future__ import annotations

import asyncio
import logging
from argparse import Namespace
from typing import TYPE_CHECKING
from warnings import warn

import nvchecker.core
import nvchecker.slogconf
import structlog
from nvchecker.core import FileLoadError
from nvchecker.ctxvars import proxy as ctx_proxy
from nvchecker.util import EntryWaiter, RichResult

if TYPE_CHECKING:
    from collections.abc import Mapping
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
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO)
    )
    # nvchecker.core.process_common_arguments(NVCheckerArgs())
    # processors = list(structlog.get_config()["processors"])
    # processors.insert(
    #    processors.index(nvchecker.slogconf.stdlib_renderer), _downgrade_http
    # )
    # structlog.configure(processors=processors)


def _downgrade_http(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: structlog.typing.EventDict,
) -> structlog.typing.ProcessorReturnValue:
    assert False, event_dict

    return event_dict
    raise structlog.DropEvent


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
    result_task = asyncio.create_task(
        nvchecker.core.process_result(
            oldvers_rich, result_q, entry_waiter, verbose=False
        )
    )
    for runner_coro in asyncio.as_completed(futures):
        await runner_coro

    result_task.cancel()
    return await result_task
