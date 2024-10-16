from __future__ import annotations

from argparse import Namespace
import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import re
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


def read_vers(dir: Path | None = None) -> dict[str, str]:
    if dir is None:
        dir = Path()
    vers: dict[str, str] = {}
    for d in dir.iterdir():
        if d.name.startswith(".") or not d.is_dir():
            continue
        srcinfo, errors = parse_srcinfo((d / ".SRCINFO").read_text())
        if errors:
            raise RuntimeError(f"Error parsing {d}:\n{errors}")
        vers[d.name] = cast(str, srcinfo["pkgver"])
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


PYPI_PAT = re.compile(r"https://pypi.org/project/(?P<name>[\w-]*)/(?P<version>[\d.]+)/")


def update_pkgbuilds(updated: Mapping[str, tuple[str, RichResult]]) -> None:
    for name, (oldver, new) in updated.items():
        match new.url:
            case str() if (match := re.fullmatch(PYPI_PAT, new.url)):
                update_pypi(name, match["name"], (oldver, match["version"]))
            case None:
                msg = f"no url for {name}"
                raise RuntimeError(msg)
            case _:
                msg = f"unknown URL pattern for {name}: {new.url}"
                raise RuntimeError(msg)


def update_pypi(arch_name: str, pypi_name: str, versions: tuple[str, str]) -> None:
    print("PyPI update:", arch_name, pypi_name, versions[0], "→", versions[1])


def main() -> int | str | None:
    here = Path()

    # setup logging
    nvchecker.core.process_common_arguments(NVCheckerArgs())

    oldvers = read_vers(here)

    try:
        newvers, has_failures = run_nvchecker(
            here / "nvchecker.toml",
            {n: RichResult(version=v) for n, v in oldvers.items()},
        )
    except nvchecker.core.FileLoadError as e:
        return str(e)
    if has_failures:
        return "could not update versions"

    updated = {
        name: (oldver, new)
        for name, new in newvers.items()
        if new.version != (oldver := oldvers[name])
    }

    update_pkgbuilds(updated)


if __name__ == "__main__":
    import sys

    sys.exit(main())
