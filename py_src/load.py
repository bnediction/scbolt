import seqParser as sp
from pathlib import Path

args = {
    "data_path":{
        "ctrl":Path(f"../data/raw/ct"),
        "treated":Path(f"../data/raw/ra"),
        "merge":Path(f"../data/raw/merge")
    },
    "file_prefix":{
        "ctrl":"GSM5492245_RNA_PLZF_RARA_CT",
        "treated":"GSM5492246_RNA_PLZF_RARA_RA",
        "merge":"barcode_gene_RNA_PLZF_RARA_RA"
    }
}

if not args["data_path"]["merge"].exists():
    args["data_path"]["merge"].mkdir()

print(f"\nLoading data...\n")

_ctrl = Path(f"{args['data_path']['ctrl']}/{args['file_prefix']['ctrl']}").resolve()
ctrl_sp = sp.coordinateListSeqParser(
    counts=Path(f"{_ctrl}_matrix.mtx").as_posix(),
    genes=Path(f"{_ctrl}_genes.tsv").as_posix(),
    barcodes=Path(f"{_ctrl}_barcodes.tsv").as_posix()
)

_treated = Path(f"{args['data_path']['treated']}/{args['file_prefix']['treated']}").resolve()
treated_sp = sp.coordinateListSeqParser(
    counts=Path(f"{_treated}_matrix.mtx").as_posix(),
    genes=Path(f"{_treated}_genes.tsv").as_posix(),
    barcodes=Path(f"{_treated}_barcodes.tsv").as_posix()
)

print(f"Merging and saving data...\n")

sp.to_hdf5(
    ["ctrl","ra"],
    ctrl_sp, treated_sp,
    gene_barcode=False,
    out=Path(f"{args['data_path']['merge']}/{args['file_prefix']['merge']}.h5ad")
)