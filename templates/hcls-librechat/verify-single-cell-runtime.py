"""Build/runtime regression: bounded backed H5AD slicing must actually work."""
import importlib.metadata
import json
from pathlib import Path
import tempfile

import anndata as ad
import numpy as np
from scipy import sparse


def main():
    matrix = np.arange(60, dtype=np.float32).reshape(12, 5)
    with tempfile.TemporaryDirectory(prefix='verify-backed-h5ad-') as directory:
        for name, source in (('dense', matrix), ('csr', sparse.csr_matrix(matrix)),
                             ('csc', sparse.csc_matrix(matrix))):
            path = Path(directory) / (name + '.h5ad')
            ad.AnnData(source).write_h5ad(path)
            backed = ad.read_h5ad(path, backed='r')
            try:
                for first in range(0, len(matrix), 4):
                    chunk = backed.X[first:first + 4, :]
                    actual = chunk.toarray() if sparse.issparse(chunk) else chunk
                    np.testing.assert_array_equal(actual, matrix[first:first + 4])
            finally:
                backed.file.close()
    print(json.dumps({'backed_h5ad_dense_csr_csc': 'passed', 'versions': {
        name: importlib.metadata.version(name) for name in ('anndata', 'scipy', 'numpy', 'h5py')}}))


if __name__ == '__main__':
    main()
