import seqParser as sp
from pathlib import Path
# import scanpy as sc
# from umap import umap_ as umap

path_to_data = '../Data'

prefix_file = dict({
    'CT':'GSM5492245_RNA_PLZF_RARA_CT',
    'RA':'GSM5492246_RNA_PLZF_RARA_RA'
})

suffix_file = dict({
    'counts':'matrix.mtx',
    'features':'genes.tsv',
    'barcodes':'barcodes.tsv',
    'out':'filled_matrix.tsv'
})

seqParserCT = sp.coordinateListSeqParser(
    Path(f"{path_to_data}/CT/{prefix_file['CT']}_{suffix_file['counts']}").resolve().as_posix(),
    Path(f"{path_to_data}/CT/{prefix_file['CT']}_{suffix_file['features']}").resolve().as_posix(),
    Path(f"{path_to_data}/CT/{prefix_file['CT']}_{suffix_file['barcodes']}").resolve().as_posix(),
    Path(f"{path_to_data}/CT/{prefix_file['CT']}_{suffix_file['out']}").resolve()
)

seqParserRA = sp.coordinateListSeqParser(
    Path(f"{path_to_data}/RA/{prefix_file['RA']}_{suffix_file['counts']}").resolve().as_posix(),
    Path(f"{path_to_data}/RA/{prefix_file['RA']}_{suffix_file['features']}").resolve().as_posix(),
    Path(f"{path_to_data}/RA/{prefix_file['RA']}_{suffix_file['barcodes']}").resolve().as_posix(),
    Path(f"{path_to_data}/RA/{prefix_file['RA']}_{suffix_file['out']}").resolve()
)

sp.to_xcsv(Path(f"{path_to_data}/Metadata/RNA_PLZF_RARA_barcodes_metadata.csv").resolve(), ["CT","RA"], seqParserCT, seqParserRA)