from __future__ import annotations

import json
from pathlib import Path
from subprocess import run

from srcinfo.parse import parse_srcinfo

vers = {}
for d in Path().iterdir():
    if d.name.startswith(".") or not d.is_dir():
        continue
    srcinfo, errors = parse_srcinfo((d / ".SRCINFO").read_text())
    if errors:
        raise RuntimeError(f"Error parsing {d}:\n{errors}")
    vers[d.name] = srcinfo["pkgver"]

Path("versions.json").write_text(json.dumps(vers))

run(["nvchecker", "-c", "nvchecker.toml"], check=True)
