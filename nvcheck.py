from __future__ import annotations

from argparse import Namespace
import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, cast
from warnings import warn

from srcinfo.parse import parse_srcinfo
import nvchecker.core
from nvchecker.util import ResultData, RawResult, EntryWaiter, RichResult
from nvchecker.ctxvars import proxy as ctx_proxy

if TYPE_CHECKING:
    from typing import Literal, IO
    from collections.abc import Coroutine


class NVCheckerArgs(Namespace):
    logger: Literal["both", "pretty", "json"] = "pretty"
    logging: Literal["debug", "info", "warning", "error"] = "info"
    version: bool = False
    json_log_fd: IO[str] | None = None


def read_vers(dir: Path | None = None) -> ResultData:
    if dir is None:
        dir = Path()
    vers: ResultData = {}
    for d in dir.iterdir():
        if d.name.startswith(".") or not d.is_dir():
            continue
        srcinfo, errors = parse_srcinfo((d / ".SRCINFO").read_text())
        if errors:
            raise RuntimeError(f"Error parsing {d}:\n{errors}")
        vers[d.name] = RichResult(version=cast(str, srcinfo["pkgver"]))
    return vers


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


def main() -> int | str:
    here = Path()
    oldvers = read_vers(here)

    # setup logging
    nvchecker.core.process_common_arguments(NVCheckerArgs())

    try:
        newvers, has_failures = run_nvchecker(here / "nvchecker.toml", oldvers)
    except nvchecker.core.FileLoadError as e:
        return str(e)

    updated = {
        name: result
        for name, result in newvers.items()
        if result.version != oldvers[name].version
    }
    print(json.dumps(updated, default=nvchecker.core.json_encode))

    return 3 if has_failures else 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
