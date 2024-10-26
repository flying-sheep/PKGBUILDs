from __future__ import annotations

import tomllib
from pathlib import Path

HERE = Path(__file__).parent
NVCHECKER_TOML = tomllib.loads((HERE.parent / "nvchecker.toml").read_text())


def test_source_names() -> None:
    from nvcheck.update.sources import SOURCES

    source_names = {source_cls().name for source_cls in SOURCES}
    conf_names = {
        info["source"]
        for table, info in NVCHECKER_TOML.items()
        if table != "__config__"
    }
    assert source_names >= conf_names
