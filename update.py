#!/usr/bin/env python3

import sys
import asyncio
from itertools import islice
from datetime import timedelta, datetime
from pathlib import Path

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
def pkg2cat(pkg: str) -> str:
    cat = _pkg2cat_str.get(pkg)
    if cat is not None: return cat
    for f, c in _pkg2cat_fn:
        if f(pkg): return c


def get_pkgs():
    search = requests.get('https://aur.archlinux.org/rpc/?v=5&type=search&by=maintainer&arg=flying-sheep').json()
    pkgs = [
        pkg_info
        for pkg_info in search['results']
        if pkg_info['Name'] not in blacklist and pkg_info['Name'] == pkg_info['PackageBase']
    ]

    superfluous = set(_pkg2cat_str.keys())
    nocat = set()
    for pkg_info in pkgs:
        name = pkg_info['Name']
        cat = pkg_info['Category'] = pkg2cat(name)
        if not cat: nocat.add(name)
        superfluous -= {name}
    if nocat: print('No category for:', nocat)
    if superfluous: print('Superfluous packages:', superfluous)

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
        rc = proc.returncode
        stdout, stderr = await proc.communicate()
    else:
        rc, stdout, stderr = 0, b'', b''
    if rc == 0:
        path.touch()
    return path, rc, stdout, stderr


async def sync_submodules(pkgs, *, expire_after: timedelta):
    coros = [
        clone_or_pull(
            Path(f'checkouts/{p["Category"]}/{p["Name"]}'),
            f'ssh://aur@aur.archlinux.org/{p["Name"]}.git',
            expire_after=expire_after,
        ) for p in pkgs
    ]
    for f in limited_as_completed(iter(coros), 4):
        path, rc, stdout, stderr = await f
        if rc != 0:
            if stdout: print(path, 'errored:', stdout)
            if stderr: print(path, 'errored:', stderr, file=sys.stderr)


expire = timedelta(minutes=20)


async def main():
    requests_cache.install_cache('update', expire_after=expire)
    pkgs = get_pkgs()
    await sync_submodules(pkgs, expire_after=expire)


if __name__ == '__main__':
    asyncio.run(main())
