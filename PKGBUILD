# Maintainer: Philipp A. <flying-sheep@web.de>
_name=connection_pool
pkgname=python-$_name
pkgver=0.0.3
pkgrel=1
pkgdesc='Thread-safe connection pool for Python'
arch=(any)
url='https://github.com/zhouyl/ConnectionPool'
license=(MIT)
depends=(python)
makedepends=(python-setuptools)
source=("https://files.pythonhosted.org/packages/source/${_name::1}/$_name/$_name-$pkgver.tar.gz")
sha256sums=('bf429e7aef65921c69b4ed48f3d48d3eac1383b05d2df91884705842d974d0dc')

package() {
	cd "$srcdir/$_name-$pkgver"
	python setup.py install --root="$pkgdir" --optimize=1
}
