#!/usr/bin/env python3
import requests
import requests_cache

requests_cache.install_cache('update', expire_after=20*60)  # 20m

blacklist = {'kuiviewer-git', 'libgtextutils'}
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
        'kgraphviewer-frameworks-git',
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


search = requests.get('https://aur.archlinux.org/rpc/?v=5&type=search&by=maintainer&arg=flying-sheep').json()
pkgs = [
    pkg_info
    for pkg_info in search['results']
    if pkg_info['Name'] not in blacklist
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
