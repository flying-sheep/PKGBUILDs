# Maintainer: Philipp A. <flying-sheep@web.de>

pkgname=scanpy
pkgver=1.10.2
pkgrel=1
pkgdesc='Single-Cell Analysis in Python'
arch=(any)
provides=(scanpy python-scanpy)
url='https://github.com/theislab/scanpy'
license=(BSD)
depends=(
	'python-anndata>=0.8'
	'python-numpy>=1.23'
	'python-matplotlib>=3.6'
	'python-pandas>=1.5'
	'python-scipy>=1.8'
	'python-seaborn>=0.13'
	'python-h5py>=3.1'
	python-tqdm
	'python-scikit-learn>=0.24'
	'python-statsmodels>=0.13'
	python-patsy
	'python-networkx>=2.7'
	python-natsort
	python-joblib
	'python-numba>=0.56'
	'python-umap-learn>=0.5.1'
	'python-pynndescent>=0.5.13'
	'python-packaging>=21.3'
	python-session-info
	'python-legacy-api-wrap>=1.4'
)
optdepends=(
	'python-igraph: PAGA support (also transitively needed for Louvain/Leiden)'
	'python-louvain-igraph: Louvain clustering'
	'python-leidenalg: leiden community detection'
	'python-bbknn: Batch balanced KNN (batch correction)'
	'python-rapids: GPU-driven calculation of neighbors'
	'python-magic-impute: MAGIC imputation method'
	'python-skmisc: For seurat_v3 highly_variable_genes method'
	'python-harmonypy: Harmony dataset integration algorithm'
	'python-scanorama: Scanorama dataset integration algorithm'
	'python-scikit-image: Cell doublet detection with scrublet'
	'rapids-cudf: NVIDIA RAPIDS acceleration'
	'rapids-cuml: NVIDIA RAPIDS acceleration'
	'rapids-cugraph: NVIDIA RAPIDS acceleration'
	'python-dask: Dask parallelization'
)
makedepends=(python-hatch python-hatch-vcs python-build python-installer python-wheel)
source=("https://files.pythonhosted.org/packages/source/${pkgname::1}/$pkgname/$pkgname-$pkgver.tar.gz")
sha256sums=('5d1649e73ac35e3ad02b455d8a16fdb16d4c8dc27330e696f4cd4e27f2d879be')

build() {
	cd "$pkgname-$pkgver"
	python -m build --wheel --no-isolation
}

package() {
	cd "$pkgname-$pkgver"
	python -m installer --destdir="$pkgdir" dist/*.whl
}
