# Maintainer: Philipp A. <flying-sheep@web.de>

_name=conda-libmamba-solver
pkgname=python-$_name
pkgver=24.7.0
pkgrel=1
pkgdesc='The libmamba based solver for conda.'
arch=(any)
url="https://github.com/conda/$_name"
license=(BSD-3-Clause)
depends=(python-libmamba python-conda python-boltons)
makedepends=(python-hatch-vcs python-build python-installer python-wheel)
source=("$pkgname-$pkgver.tar.gz::$url/archive/$pkgver.tar.gz")
sha256sums=('3eec3df72f7faa3c469b17ea1c540fa47ffc50b751a661bdf22c8e96bfb78abb')

build() {
	cd "$_name-$pkgver"
    export SETUPTOOLS_SCM_PRETEND_VERSION="${pkgver}"
	python -m build --wheel --no-isolation
}

package() {
	cd "$_name-$pkgver"
	python -m installer --destdir="$pkgdir" dist/*.whl
	install -Dm0644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
