from __future__ import annotations

from typing import TYPE_CHECKING, cast

import structlog
from nvchecker.core import load_file

from aurweb_client import Client
from aurweb_client.api.package_search import get_rpc_v5_search_arg as search
from aurweb_client.models.get_rpc_v5_search_arg_by import GetRpcV5SearchArgBy as By
from aurweb_client.types import Unset

from .update import COMMON_ARGS

if TYPE_CHECKING:
    from pathlib import Path


logger = cast(
    structlog.types.FilteringBoundLogger, structlog.get_logger(logger_name=__name__)
)


async def sync_maintained_pkgbuilds(nvchecker_path: Path) -> None:
    entries, _ = load_file(str(nvchecker_path), use_keymanager=False)

    client = Client("https://aur.archlinux.org/", raise_on_unexpected_status=True)
    resp = await search.asyncio(COMMON_ARGS["owner"], client=client, by=By.MAINTAINER)
    if resp is None or isinstance(resp.results, Unset):
        return

    maintained = {result.name for result in resp.results}
    tracked = entries.keys()

    untracked = maintained - tracked
    unmaintained = tracked - maintained

    if untracked:
        logger.critical("Found untracked packages", untracked=untracked)
    if unmaintained:
        logger.critical("Found unmaintained packages", unmaintained=unmaintained)
