# Maintainer: Philipp A. <flying-sheep@web.de>

_name=entry-points-txt
pkgname=python-$_name
pkgver=0.2.1
pkgrel=1
pkgdesc='Read & write entry_points.txt files'
arch=(any)
url="https://github.com/jwodder/$_name"
license=(MIT)
depends=(python)
_pyarch=py3
_wheel="${_name//-/_}-$pkgver-$_pyarch-none-any.whl"
source=("https://files.pythonhosted.org/packages/$_pyarch/${_name::1}/$_name/$_wheel")
sha256sums=('90abc88ac448b19c7ef08388a2ee066e2151da719cd6cbb6437b5deead5c808c')
noextract=("$_wheel")

package() {
	local site="$pkgdir/usr/lib/$(readlink /bin/python3)/site-packages"
	mkdir -p "$site"
	unzip "$_wheel" -d "$site"
}
