# Maintainer: Philipp A. <flying-sheep@web.de>

_name=session-info2
pkgname=python-$_name
pkgver=0.2
pkgrel=1
pkgdesc='Display information about the current Python session.'
arch=(any)
url="https://github.com/scverse/$_name"
license=(MPL-2.0)
depends=(python)
makedepends=(python-hatch-vcs python-hatch-docstring-description python-build python-installer)
source=("https://files.pythonhosted.org/packages/source/${_name::1}/${_name//-/_}/${_name//-/_}-$pkgver.tar.gz")
sha256sums=('e925d34d0a298afe19421d55287e8fb9ace3c8f6390832aa11c641f01bab4177')

build() {
	cd "${_name//-/_}-$pkgver"
	python -m build --wheel --no-isolation
}

package() {
	cd "${_name//-/_}-$pkgver"
	python -m installer --destdir="$pkgdir" dist/*.whl
}
