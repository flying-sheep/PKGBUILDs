from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from openapi_python_client import config, generate

if TYPE_CHECKING:
    from typing import Any


HERE = Path(__file__).parent


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        cfg = config.Config.from_sources(
            config_file=config.ConfigFile(),
            meta_type=config.MetaType.NONE,
            document_source="https://aur.archlinux.org/rpc/openapi.json",
            file_encoding="utf-8",
            overwrite=True,
            output_path=HERE / "src" / "aurweb_client",
        )
        generate(config=cfg)
