from __future__ import annotations

from pathlib import Path

from nvchecker.core import load_file

HERE = Path(__file__).parent
NVCHECKER_TOML, _ = load_file(str(HERE.parent / "nvchecker.toml"), use_keymanager=False)


def test_source_names() -> None:
    from nvcheck.update.sources import SOURCES

    source_names = {source_cls().name for source_cls in SOURCES}
    conf_names = {
        info["source"]
        for table, info in NVCHECKER_TOML.items()
        if table != "__config__"
    }
    assert source_names >= conf_names
