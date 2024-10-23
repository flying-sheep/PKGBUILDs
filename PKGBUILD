# Maintainer: Brian Thompson <brianrobt@pm.me>
# Contributor: Daniel Maslowski <info@orangecms.org>
# Contributor: Ke Liu <specter119@gmail.com>

pkgname=python-conda
_name=${pkgname#python-}
pkgver=24.9.2
pkgrel=1
pkgdesc="OS-agnostic, system-level binary package manager and ecosystem https://conda.io"
arch=('any')
url="https://github.com/conda/conda"
license=('BSD-3-Clause')
depends=(
  'python>=3.7'
  'python-archspec'
  'python-boltons'
  'python-boto3'
  'python-botocore'
  'python-conda-package-handling'
  'python-conda-libmamba-solver'
  'python-pluggy>=1.0.0'
  'python-pycosat>=0.6.3'
  'python-requests>=2.20.1'
  'python-ruamel-yaml>=0.11.14'
  'python-tqdm'
)
checkdepends=(
  'python-pytest'
  'python-pytest-mock'
)
makedepends=(
  'python-build'
  'python-installer'
  'python-hatchling'
  'python-hatch-vcs'
  'python-wheel'
)
provides=('python-conda' 'python-conda-env')
options=(!emptydirs)
backup=(etc/conda/condarc)
source=("$_name-$pkgver.tar.gz::$url/archive/$pkgver.tar.gz")
sha512sums=('b293253eb8174580dfd63142863c7652c285912fb64253bef5bf7994bfa9ee6dec71af926f7082613d44b9c97d966877d86815b6b19f45319b9edf844978f3ee')

prepare() {
  cd "$srcdir/$_name-$pkgver"

  sed -i '3s/^/set _CONDA_EXE=\/usr\/bin\/conda\n/' conda/shell/etc/profile.d/conda.csh
  sed -i '3s/^/export CONDA_EXE=\/usr\/bin\/conda\n/' conda/shell/etc/profile.d/conda.sh
  sed -i '8s/^/set -l CONDA_EXE \/usr\/bin\/conda\n/' conda/shell/etc/fish/conf.d/conda.fish
  echo -e 'envs_dirs:\n  - ~/.conda/envs\npkgs_dirs:\n  - ~/.conda/pkgs' > condarc
}

build() {
  cd "$srcdir/$_name-$pkgver"

  python -m build --wheel --no-isolation
}

package() {
  cd "$srcdir/$_name-$pkgver"
  
  # install package contents
  python -m installer --destdir "$pkgdir" "$srcdir/$_name-$pkgver/dist/$_name-$pkgver-"*.whl
  # patch binary
  sed -i 's/conda\.cli\.main_pip/conda.cli.main/' "$pkgdir/usr/bin/conda"
  # install completions and conda shell function
  mkdir -p "$pkgdir/"{usr/share/fish/functions,etc/profile.d}
  _site_packages="$(python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
  ln -s "$_site_packages/conda/shell/etc/fish/conf.d/conda.fish" "$pkgdir/usr/share/fish/functions/conda.fish"
  ln -s "$_site_packages/conda/shell/etc/profile.d/conda.csh" "$pkgdir/etc/profile.d/conda.csh"
  ln -s "$_site_packages/conda/shell/etc/profile.d/conda.sh" "$pkgdir/etc/profile.d/conda.sh"
  # install config and license
  install -Dm 644 condarc "$pkgdir/etc/conda/condarc"
  install -Dm 644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}

# vim:set ts=2 sw=2 et:
