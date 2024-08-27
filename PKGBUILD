# Maintainer: Philipp A. <flying-sheep@web.de>
_name=numcodecs
pkgname=python-numcodecs
pkgver=0.13.0
pkgrel=1
pkgdesc='A Python package providing buffer compression and transformation codecs for use in data storage and communication applications'
arch=(x86_64)
url="https://github.com/zarr-developers/$_name"
license=(MIT)
depends=(python-numpy python-msgpack)
makedepends=(cython python-py-cpuinfo python-setuptools python-setuptools-scm python-build python-installer python-wheel)
optdepends=(python-zfpy python-pcodec)
source=("https://files.pythonhosted.org/packages/source/${_name::1}/$_name/$_name-$pkgver.tar.gz")
sha256sums=('ba4fac7036ea5a078c7afe1d4dffeb9685080d42f19c9c16b12dad866703aa2e')

build() {
	cd "$_name-$pkgver"
	export CFLAGS="$CFLAGS -march=native"
	python -m build --wheel --no-isolation
}

package() {
	cd "$_name-$pkgver"
	python -m installer --destdir="$pkgdir" dist/*.whl
	install -Dm644 LICENSE.txt "$pkgdir"/usr/share/licenses/$pkgname/LICENSE.txt
}
