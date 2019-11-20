#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
import json
import asyncio
from itertools import islice
from datetime import timedelta, datetime
from pathlib import Path
from warnings import warn
from types import ModuleType
from typing import TypeVar, Union, Any, Optional, get_type_hints
from typing import Iterable, Generator, Awaitable
from typing import NamedTuple, Tuple, List, Dict

import requests
import requests_cache
from packaging import version
from wheel_inspect import inspect_wheel


blacklist = {
    'python-tbvaccine',  # https://github.com/pypa/warehouse/issues/5535
}
categories = {
    'CLI': {
        'git-archive-all-git',
        'hisat2',
        'kallisto',
        'ftree',
        'dindent',
    },
    'KDE': {
        'desktop-privileges',
        'desktop-privileges-nogroups',
        'kcm-pointing-devices-git',
        'kwin-scripts-forceblur',
    },
    'Fonts': {
        'otf-texgyre-pagella-math',
        'ttf-roboto-fontconfig',
    },
    'GUI': {
        'unicodemoticon',
        'terrafirma',
        'freedesktop-templates-libreoffice',
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
        'install-wheel-scripts',
        'snakemake',
        'scanpy',
        'scanpy-git',
        'scanpy-scripts',
        'sphobjinv',
    },
    'Rust': {
        lambda x: x.startswith('cargo-'),
        'diesel_cli',
        'resvg',
        'resvg-cairo',
        'resvg-qt',
    },
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
    def category(self) -> str:
        return pkg2cat(self.name)
    
    @classmethod
    def from_json(cls, data: dict) -> Package:
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
                warn(f'Error trying to convert {value!r} to {typ}:')
                raise
        
        kv = {}
        types = get_type_hints(cls)
        for k_camel, v_raw in data.items():
            k = camel_to_snake(k_camel)
            v = typeconv(v_raw, types[k])
            kv[k] = v
        return cls(**kv)


def get_pkgs() -> List[Package]:
    search = requests.get('https://aur.archlinux.org/rpc/?v=5&type=search&by=maintainer&arg=flying-sheep').json()
    pkgs = [
        pkg
        for pkg in map(Package.from_json, search['results'])
        if pkg.name == pkg.package_base
    ]

    superfluous = set(_pkg2cat_str.keys())
    nocat = set()
    for pkg_info in pkgs:
        name = pkg_info.name
        if not pkg_info.category: nocat.add(name)
        superfluous -= {name}
    if superfluous: warn(f'Superfluous packages: {superfluous}')
    if nocat:
        raise RuntimeError(f'No category for: {nocat}')
    return pkgs


T = TypeVar('T')


def limited_as_completed(coros: Iterable[Awaitable[T]], limit: int) -> Generator[Awaitable[T]]:
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
    if rc == 0 and path.is_dir():
        path.touch()
    return path, rc, stdout, stderr


def pkg_path(pkg: Package) -> Path:
    return Path(f'checkouts/{pkg.category}/{pkg.package_base}')


def pkg_url(pkg: Package) -> str:
    return f'ssh://aur@aur.archlinux.org/{pkg.package_base}.git'


async def sync_submodules(pkgs: Iterable[Package], *, expire_after: timedelta):
    coros = [clone_or_pull(pkg_path(pkg), pkg_url(pkg), expire_after=expire_after) for pkg in pkgs]
    for f in limited_as_completed(iter(coros), 4):
        path, rc, stdout, stderr = await f
        if rc != 0:
            if stdout: print(f'{path} errored ({rc}): {stdout.decode("utf-8").strip()}')
            if stderr: print(f'{path} errored ({rc}): {stderr.decode("utf-8").strip()}', file=sys.stderr)
    
    not_yours = {d.name for d in Path('checkouts').glob('*/*')} - {p.package_base for p in pkgs}
    if not_yours:
        warn(f'You do no longer maintain the package(s) {sorted(not_yours)}')


def import_from_path(path: Path, name: Optional[str] = None) -> ModuleType:
    if name is None:
        name = path.with_suffix('').name
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def get_scripts(whl: Path) -> Dict[str, Dict[str, Union[str, List[str]]]]:
    if whl is None:
        return {}
    entry_points = inspect_wheel(whl)['dist_info'].get('entry_points')
    # e.g.: {'flit': {'module': 'flit', 'attr': 'main', 'extras': []}}
    return entry_points.get('console_scripts', {}) if entry_points else {}


def check_python_package(pkg: Package):
    p = pkg_path(pkg)
    pkgbuild = (p / 'PKGBUILD').read_text()
    
    # TODO: get from sources array
    scripts = get_scripts(next(iter(p.glob('*.whl')), None))
    if scripts:
        uninstalled = {s: v for s, v in scripts.items() if not f'/bin/{s}' in pkgbuild}
        if uninstalled:
            warn(f'Package {pkg.name} does not install scripts {uninstalled}', stacklevel=2)
    
    if re.search(r'^makedepends=.*python-pip', pkgbuild, re.MULTILINE):
        warn(f'Package {pkg.name} contains pip as makedepends', stacklevel=2)


re_pkg_url = re.compile(r'https://(files|pypi).python(hosted)?.org/packages/[\w.]+/[a-z]/(?P<dist>[^/]+)/[^/]+')


def get_python_version(pkg: Package):
    p = pkg_path(pkg)
    prefix = '\tsource = '
    src_lines = [l[len(prefix):] for l in (p / '.SRCINFO').read_text().split('\n') if l.startswith(prefix)]
    assert src_lines, f'no sources in {pkg.name}'
    versions = {}
    for src_line in src_lines:
        if 'https://' not in src_line:
            continue
        m = re_pkg_url.match(src_line)
        if not m:
            raise RuntimeError(f'Could not match source line {src_line!r}')
        dist = m['dist']
        try:
            version = requests.get(f'https://pypi.org/pypi/{dist}/json').json()['info']['version']
        except Exception:
            warn(f'Error downloading/extracting version from {dist}')
            raise
        versions[dist] = version
    if len(set(versions.values())) > 1:  # There’s auxiliary packages. Try getting the one matching the package name.
        n = pkg.name.replace('python-', '')
        v = versions.get(n, versions.get(pkg.name))
        if v is not None:
            versions = {pkg.name: v}
        else:
            raise RuntimeError(f'Multiple ambiguous versions found for {pkg.name}')
    return next(iter(versions.values()), None)


def get_versions(pkgs: Iterable[Package]) -> Generator[Tuple[Package, str], None, None]:
    undetermined = set()
    for pkg in pkgs:
        if pkg.package_base.endswith('-git') or pkg.name in blacklist:
            continue
        
        p = pkg_path(pkg)
        v = None
        if (p / 'version.py').is_file():
            v = import_from_path(p / 'version.py').version()
        elif pkg.category == 'Python':
            check_python_package(pkg)
            v = get_python_version(pkg)
        elif pkg.category == 'JS':
            pass # Node lookup
        
        if v is None:
            undetermined.add(pkg.package_base)
            continue
        
        pkg_ver, _pkg_rel = pkg.version.split('-')
        if version.parse(v) > version.parse(pkg_ver):
            print(f'Newer version available for {pkg.name}: {v} > {pkg_ver}')
    if undetermined:
        raise RuntimeError(f'Could not determine version of {undetermined}')


expire = timedelta(minutes=20)


async def main():
    requests_cache.install_cache('update', expire_after=expire)
    pkgs = get_pkgs()
    await sync_submodules(pkgs, expire_after=expire)
    get_versions(pkgs)


if __name__ == '__main__':
    asyncio.run(main())
