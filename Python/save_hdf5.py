import seqParser as sp
from pathlib import Path

path_to_data = '../Data'
path_to_results = f'{path_to_data}/Results/hdf5'

prefix_file = dict({
    'CT':'GSM5492245_RNA_PLZF_RARA_CT',
    'RA':'GSM5492246_RNA_PLZF_RARA_RA',
})

suffix_file = dict({
    'counts':'matrix.mtx',
    'features':'genes.tsv',
    'barcodes':'barcodes.tsv',
    'out':'barcode_gene_RNA_PLZF_RARA_RA.h5ad'
})

ct_sp = sp.coordinateListSeqParser(
    Path(f"{path_to_data}/CT/{prefix_file['CT']}_{suffix_file['counts']}").resolve().as_posix(),
    Path(f"{path_to_data}/CT/{prefix_file['CT']}_{suffix_file['features']}").resolve().as_posix(),
    Path(f"{path_to_data}/CT/{prefix_file['CT']}_{suffix_file['barcodes']}").resolve().as_posix(),
    Path(f"{path_to_data}/CT/{prefix_file['CT']}_{suffix_file['out']}").resolve()
)

ra_sp = sp.coordinateListSeqParser(
    Path(f"{path_to_data}/RA/{prefix_file['RA']}_{suffix_file['counts']}").resolve().as_posix(),
    Path(f"{path_to_data}/RA/{prefix_file['RA']}_{suffix_file['features']}").resolve().as_posix(),
    Path(f"{path_to_data}/RA/{prefix_file['RA']}_{suffix_file['barcodes']}").resolve().as_posix(),
    Path(f"{path_to_data}/RA/{prefix_file['RA']}_{suffix_file['out']}").resolve()
)

sp.to_hdf5(["CT","RA"], ct_sp, ra_sp, gene_barcode=False, out=Path(f"{path_to_results}/{suffix_file['out']}"))