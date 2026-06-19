#!/usr/bin/env bash
set -euo pipefail

usage() {
    printf '%s\n' "usage: download_gsm.sh <GSM> <output-directory>"
}

if [ "$#" -ne 2 ]; then
    usage >&2
    exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
scbolt_root="$(cd "${script_dir}/../.." && pwd)"
scbolt_tool="${scbolt_root}/bin/scbolt-tool"

gsm="$1"
outdir="$2"

case "${gsm}" in
    GSM[0-9]*) ;;
    *)
        printf '%s\n' "invalid GSM accession: ${gsm}" >&2
        exit 1
        ;;
esac

digits="${gsm#GSM}"
case "${digits}" in
    *[!0-9]*|"")
        printf '%s\n' "invalid GSM accession: ${gsm}" >&2
        exit 1
        ;;
esac

if [ "${#digits}" -le 3 ]; then
    series_dir="GSMnnn"
else
    series_dir="GSM${digits:0:${#digits}-3}nnn"
fi

geo_ftp_base="${GEO_FTP_BASE:-https://ftp.ncbi.nlm.nih.gov/geo}"
base_url="${geo_ftp_base%/}/samples/${series_dir}/${gsm}/suppl/"
mkdir -p "${outdir}"

python_command="${PYTHON:-}"
if [ -z "${python_command}" ]; then
    if command -v python3 >/dev/null 2>&1; then
        python_command="python3"
    elif command -v python >/dev/null 2>&1; then
        python_command="python"
    else
        printf '%s\n' "required command not found: python3 or python" >&2
        exit 1
    fi
fi

mapfile -t files < <(
    "${python_command}" - "${base_url}" "${gsm}" <<'PY'
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin
from urllib.error import URLError
from urllib.request import urlopen
import sys

base_url = sys.argv[1]
gsm = sys.argv[2]


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href":
                self.links.append(unquote(value))


parser = LinkParser()
try:
    response = urlopen(base_url)
except (IsADirectoryError, URLError):
    response = urlopen(urljoin(base_url, "index.html"))

with response:
    parser.feed(response.read().decode("utf-8", errors="replace"))

for link in parser.links:
    filename = link.rsplit("/", 1)[-1]
    if not filename.startswith(gsm):
        continue
    if filename.endswith(("_matrix.mtx.gz", "_barcodes.tsv.gz", "_genes.tsv.gz", "_features.tsv.gz")):
        print(urljoin(base_url, link))
PY
)

matrix_url=""
barcodes_url=""
genes_url=""
features_url=""

for url in "${files[@]}"; do
    filename="${url##*/}"
    case "${filename}" in
        *_matrix.mtx.gz)
            if [ -n "${matrix_url}" ]; then
                printf '%s\n' "multiple matrix files found for ${gsm}" >&2
                exit 1
            fi
            matrix_url="${url}"
            ;;
        *_barcodes.tsv.gz)
            if [ -n "${barcodes_url}" ]; then
                printf '%s\n' "multiple barcode files found for ${gsm}" >&2
                exit 1
            fi
            barcodes_url="${url}"
            ;;
        *_genes.tsv.gz)
            genes_url="${url}"
            ;;
        *_features.tsv.gz)
            features_url="${url}"
            ;;
    esac
done

if [ -z "${matrix_url}" ]; then
    printf '%s\n' "matrix file not found for ${gsm}: ${base_url}" >&2
    exit 1
fi

if [ -z "${barcodes_url}" ]; then
    printf '%s\n' "barcode file not found for ${gsm}: ${base_url}" >&2
    exit 1
fi

if [ -z "${genes_url}" ] && [ -z "${features_url}" ]; then
    printf '%s\n' "gene/feature file not found for ${gsm}: ${base_url}" >&2
    exit 1
fi

download() {
    local url="$1"
    local output="$2"
    local tmp="${output}.tmp"

    "${scbolt_tool}" curl --fail --location --silent --show-error --retry 3 --output "${tmp}" "${url}"
    mv "${tmp}" "${output}"
}

download "${matrix_url}" "${outdir}/matrix.mtx.gz"
download "${barcodes_url}" "${outdir}/barcodes.tsv.gz"

if [ -n "${features_url}" ]; then
    download "${features_url}" "${outdir}/genes.tsv.gz"
else
    download "${genes_url}" "${outdir}/genes.tsv.gz"
fi
