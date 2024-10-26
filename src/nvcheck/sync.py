from __future__ import annotations

from aurweb_client import Client
from aurweb_client.api.package_search import get_rpc_v5_search_arg as search
from aurweb_client.models.get_rpc_v5_search_arg_by import GetRpcV5SearchArgBy as By
from aurweb_client.types import Unset

from .update import COMMON_ARGS


async def sync_maintained_pkgbuilds() -> None:
    client = Client("https://aur.archlinux.org/", raise_on_unexpected_status=True)
    resp = await search.asyncio(COMMON_ARGS["owner"], client=client, by=By.MAINTAINER)
    if resp is None or isinstance(resp.results, Unset):
        return

    print(resp.resultcount or 0)
    for result in resp.results:
        print(result.name)
