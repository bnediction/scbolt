#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmpdir="$(mktemp -d)"

trap 'rm -rf "${tmpdir}"' EXIT

mock_suppl="${tmpdir}/geo/samples/GSM5492nnn/GSM5492245/suppl"
mkdir -p "${mock_suppl}"

printf 'matrix\n' > "${mock_suppl}/GSM5492245_RNA_PLZF_RARA_CT_matrix.mtx.gz"
printf 'barcodes\n' > "${mock_suppl}/GSM5492245_RNA_PLZF_RARA_CT_barcodes.tsv.gz"
printf 'genes\n' > "${mock_suppl}/GSM5492245_RNA_PLZF_RARA_CT_genes.tsv.gz"
printf 'ignored\n' > "${mock_suppl}/GSM5492245_signal.bw"
printf 'ignored\n' > "${mock_suppl}/GSM5492245_ATAC.h5"
printf 'ignored\n' > "${mock_suppl}/GSM5492245_fragments.tsv.gz"
printf 'ignored\n' > "${mock_suppl}/GSM5492245_bulk.csv.gz"

cat > "${mock_suppl}/index.html" <<'HTML'
<a href="GSM5492245_RNA_PLZF_RARA_CT_matrix.mtx.gz">matrix</a>
<a href="GSM5492245_RNA_PLZF_RARA_CT_barcodes.tsv.gz">barcodes</a>
<a href="GSM5492245_RNA_PLZF_RARA_CT_genes.tsv.gz">genes</a>
<a href="GSM5492245_signal.bw">bigwig</a>
<a href="GSM5492245_ATAC.h5">atac</a>
<a href="GSM5492245_fragments.tsv.gz">fragments</a>
<a href="GSM5492245_bulk.csv.gz">csv</a>
HTML

GEO_FTP_BASE="file://${tmpdir}/geo" \
    bash "${repo_root}/scripts/download/download_gsm.sh" GSM5492245 "${tmpdir}/out"

test -f "${tmpdir}/out/matrix.mtx.gz"
test -f "${tmpdir}/out/barcodes.tsv.gz"
test -f "${tmpdir}/out/genes.tsv.gz"
test "$(find "${tmpdir}/out" -type f | wc -l)" -eq 3

if python3 - <<'PY' >/dev/null 2>&1
import anndata  # noqa: F401
import scipy  # noqa: F401
PY
then
    mkdir -p "${tmpdir}/mex"
    gzip -c > "${tmpdir}/mex/matrix.mtx.gz" <<'MTX'
%%MatrixMarket matrix coordinate integer general
%
3 2 3
1 1 1
2 1 2
3 2 3
MTX
    gzip -c > "${tmpdir}/mex/barcodes.tsv.gz" <<'BARCODES'
cell1
cell2
BARCODES
    gzip -c > "${tmpdir}/mex/genes.tsv.gz" <<'GENES'
gene_id_1	Gene1
gene_id_2	Gene2
gene_id_3	Gene3
GENES
    PYTHONPATH="${repo_root}/lib" python3 "${repo_root}/scripts/download/import_matrix.py" \
        "${tmpdir}/mex/matrix.mtx.gz" \
        "${tmpdir}/mex/barcodes.tsv.gz" \
        "${tmpdir}/mex/genes.tsv.gz" \
        "${tmpdir}/counts.h5ad" \
        --gsm GSM5492245
    python3 - "${tmpdir}/counts.h5ad" <<'PY'
from pathlib import Path
import sys

import anndata as ad

adata = ad.read_h5ad(Path(sys.argv[1]))
assert adata.shape == (2, 3)
assert "counts" in adata.layers
assert adata.uns["scbolt"]["gsm"] == "GSM5492245"
PY

fi

dry_run="$(
    make -C "${repo_root}" --always-make --dry-run LOGGING=false \
        __filtering PARAMS=tests/fixtures/params-matrix.mk
)"
grep -q 'download_gsm.sh' <<< "${dry_run}"
grep -q 'download/import_matrix.py' <<< "${dry_run}"
! grep -q 'parallel-fastq-dump' <<< "${dry_run}"
! grep -q 'velocyto run' <<< "${dry_run}"

conflict_params="${tmpdir}/conflict.mk"
cat > "${conflict_params}" <<'MK'
RESULTS_DIR = tests/output-matrix
PUBLIC_DIR = tests/public
CONDITIONS = ctrl
ORGANISM = human
SRA_CTRL = SRR000001
GSM_CTRL = GSM5492245
MK

if make -C "${repo_root}" check TARGET=load-matrix PARAMS="${conflict_params}" \
        __check_externals__=false > "${tmpdir}/conflict.out" 2>&1; then
    printf '%s\n' "expected SRA/GSM conflict check to fail" >&2
    exit 1
fi
grep -q "variable conflict: input routes are mutually exclusive" \
    "${tmpdir}/conflict.out"
grep -q "specified: SRA_\\*, GSM_\\*" "${tmpdir}/conflict.out"

cat > "${conflict_params}" <<'MK'
RESULTS_DIR = tests/output-matrix
PUBLIC_DIR = tests/public
CONDITIONS = ctrl
ORGANISM = human
GSM_CTRL = GSM5492245
COUNT_FILES = counts.h5ad
MK

if make -C "${repo_root}" check TARGET=load-matrix PARAMS="${conflict_params}" \
        __check_externals__=false > "${tmpdir}/conflict-count.out" 2>&1; then
    printf '%s\n' "expected GSM/COUNT_FILES conflict check to fail" >&2
    exit 1
fi
grep -q "specified: GSM_\\*, COUNT_FILES" "${tmpdir}/conflict-count.out"

if make -C "${repo_root}" check TARGET=velocity PARAMS=tests/fixtures/params-matrix.mk \
        __check_externals__=false > "${tmpdir}/velocity.out" 2>&1; then
    printf '%s\n' "expected matrix-mode velocity check to fail" >&2
    exit 1
fi
grep -q "matrix input mode does not provide spliced/unspliced layers" \
    "${tmpdir}/velocity.out"

help_output="$(
    make -C "${repo_root}" module-help TARGET=load-matrix \
        PARAMS=tests/fixtures/params-matrix.mk SCBOLT_CLI=true
)"
grep -q 'GSM_CTRL' <<< "${help_output}"

printf '%s\n' "matrix entry tests passed"
