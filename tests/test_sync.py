from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).parent
NVCHECKER_PATH = HERE.parent / "nvchecker.toml"


def test_parse_nvchecker_toml() -> None:
    from nvcheck.sync import parse_nvchecker_toml

    segments = list(parse_nvchecker_toml(NVCHECKER_PATH).items())

    conf_segment_name, conf_segment = segments[0]
    assert conf_segment_name == "__config__"
    assert conf_segment == "[__config__]\nhttplib = 'httpx'\n"

    anndata_segment = next(s for n, s in segments if n == "python-anndata")
    assert anndata_segment == "[python-anndata]\nsource = 'pypi'\npypi = 'anndata'\n"
