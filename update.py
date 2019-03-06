#!/usr/bin/env python3

import re
import sys
import json
import asyncio
from itertools import islice
from datetime import timedelta, datetime
from pathlib import Path
from typing import Any, Union, Optional, NamedTuple

import requests
import requests_cache

blacklist = {'kuiviewer-git', 'libgtextutils', 'kgraphviewer-frameworks-git'}
categories = {
    'CLI': {
        'git-archive-all-git',
        'hisat2',
        'kallisto',
        'ftree',
    },
    'KDE': {
        'desktop-privileges',
        'desktop-privileges-nogroups',
        'kcm-pointing-devices-git',
    },
    'Fonts': {
        'otf-texgyre-pagella-math',
        'ttf-roboto-fontconfig',
    },
    'GUI': {
        'unicodemoticon',
        'terrafirma',
        'rambox',
    },
    'Devtools': {
        'qt-inspector-qt5-git',
        'h5pyviewer',
        'pycharm-community-eap',
        'rstudio-desktop',
    },
    # Language libs and language-specific tools
    'C': {'libxcb-git', 'cmake-modules-libr'},
    'C++': {'coan', 'qmake-mimetypes'},
    'Java': {'assertj-core'},
    'JS': {
        lambda x: x.startswith('nodejs-'),
        'gulp-cli',
        'sencha-cmd-6',
        'v8-3.14-bin',
    },
    'Jupyter': {
        lambda x: x.startswith('jupyter_') or x.startswith('jupyter-'),
        'nbmanager-git',
        'nbopen',
    },
    'Python': {
        lambda x: x.startswith('python-') or x.startswith('python2-'),
        'auditwheel',
        'flit',
        'flit-git',
        'snakemake',
        'scanpy',
        'scanpy-git',
    },
    'Rust': {'diesel_cli', 'resvg', 'resvg-cairo', 'resvg-qt'},
}
_pkg2cat_str = {
    p: c
    for c, pkgs in categories.items()
    for p in pkgs
    if isinstance(p, str)
}
_pkg2cat_fn = [
    (p, c)
    for c, pkgs in categories.items()
    for p in pkgs
    if callable(p)
]
def pkg2cat(pkg_name: str) -> str:
    cat = _pkg2cat_str.get(pkg_name)
    if cat is not None: return cat
    for f, c in _pkg2cat_fn:
        if f(pkg_name): return c


class Package(NamedTuple):
    id: int
    name: str
    package_base_id: int
    package_base: str
    version: str
    description: str
    url: str
    num_votes: int
    popularity: int
    out_of_date: Optional[datetime]
    maintainer: str
    first_submitted: datetime
    last_modified: datetime
    url_path: Path
    
    @property
    def category(self):
        return pkg2cat(self.name)
    
    @classmethod
    def from_json(cls, data: dict):
        def camel_to_snake(camel: str) -> str:
            first_converted = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', camel)
            return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', first_converted).lower()
            #return re.sub(r'(?<=^_)(u_r_l|i_d)(?=_$)', lambda x: x.replace('_', ''), exploded_snake)
        
        def typeconv(value: Any, typ: type) -> Any:
            if getattr(typ, '__origin__', None) is Union:
                args = set(getattr(typ, '__args__', ()))
                if len(args) == 2 and type(None) in args:
                    if value is None:
                        typ = lambda n: n
                    else:
                        typ = next(iter(args - {type(None)}))
            if typ is datetime:
                typ = datetime.fromtimestamp
            try:
                return typ(value)
            except Exception:
                print(f'Error trying to convert {value!r} to {typ}:', file=sys.stderr)
                raise
        
        kv = {}
        for k_camel, v_raw in data.items():
            k = camel_to_snake(k_camel)
            v = typeconv(v_raw, cls._field_types[k])
            kv[k] = v
        return cls(**kv)


def get_pkgs():
    search = requests.get('https://aur.archlinux.org/rpc/?v=5&type=search&by=maintainer&arg=flying-sheep').json()
    pkgs = [
        pkg_info
        for pkg_info in map(Package.from_json, search['results'])
        if pkg_info.name not in blacklist and pkg_info.name == pkg_info.package_base
    ]

    superfluous = set(_pkg2cat_str.keys())
    nocat = set()
    for pkg_info in pkgs:
        name = pkg_info.name
        if not pkg_info.category: nocat.add(name)
        superfluous -= {name}
    if superfluous: print('Superfluous packages:', superfluous, file=sys.stderr)
    if nocat:
        raise RuntimeError(f'No category for: {nocat}')
    return pkgs


def limited_as_completed(coros, limit: int):
    futures = [
        asyncio.ensure_future(c)
        for c in islice(coros, 0, limit)
    ]
    async def first_to_finish():
        while True:
            await asyncio.sleep(0)
            for f in futures:
                if f.done():
                    futures.remove(f)
                    try:
                        newf = next(coros)
                        futures.append(asyncio.ensure_future(newf))
                    except StopIteration:
                        pass
                    return f.result()
    while futures:
        yield first_to_finish()


async def clone_or_pull(path: Path, repo: str, *, expire_after: timedelta):
    if path.is_dir():
        modified = datetime.utcfromtimestamp(path.stat().st_mtime)
        update = datetime.utcnow() - modified > expire_after
        args = ('-C', str(path), 'pull', '--rebase')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        update = True
        args = ('clone', repo, str(path))
    if update:
        proc = await asyncio.create_subprocess_exec(
            'git', *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        await proc.wait()
        rc = proc.returncode
    else:
        rc, stdout, stderr = 0, b'', b''
    if rc == 0:
        path.touch()
    return path, rc, stdout, stderr


def pkg_path(pkg):
    return Path(f'checkouts/{pkg.category}/{pkg.package_base}')


def pkg_url(pkg):
    return f'ssh://aur@aur.archlinux.org/{pkg.package_base}.git'


async def sync_submodules(pkgs, *, expire_after: timedelta):
    coros = [clone_or_pull(pkg_path(pkg), pkg_url(pkg), expire_after=expire_after) for pkg in pkgs]
    for f in limited_as_completed(iter(coros), 4):
        path, rc, stdout, stderr = await f
        if rc != 0:
            if stdout: print(f'{path} errored ({rc}): {stdout.decode("utf-8").strip()}')
            if stderr: print(f'{path} errored ({rc}): {stderr.decode("utf-8").strip()}', file=sys.stderr)


def import_from_path(path: Path, name: Optional[str] = None):
    if name is None:
        name = path.with_suffix('').name
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def get_versions(pkgs):
    for pkg in pkgs:
        p = pkg_path(pkg)
        v = None
        if (p / 'version.py').is_file():
            v = import_from_path(p / 'version.py').version()
        elif pkg.category == 'Python':
            pass # PIP lookup
        elif pkg.category == 'JS':
            pass # Node lookup
        
        if v is None:
            raise RuntimeError(f'Could not determine version of {pkg.package_base}')


expire = timedelta(minutes=20)


async def main():
    requests_cache.install_cache('update', expire_after=expire)
    pkgs = get_pkgs()
    await sync_submodules(pkgs, expire_after=expire)
    get_versions(pkgs)


if __name__ == '__main__':
    asyncio.run(main())
