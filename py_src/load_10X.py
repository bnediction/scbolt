from pathlib import Path
from datetime import date

import os
import scanpy as sc

args = {
    "inpath":Path(f"data/scRNA/raw/ct").resolve(),
    "outfile":Path(f"data/scRNA/raw/ct/ct.h5ad").resolve(),
    "sample info":{
        "age":"adult",
        "date":str(date(2020, 9, 29)),
        "sample name":"ctrl",
        "condition":"control"
    },
}

outpath = Path(os.path.split(args["outfile"])[0]).resolve()

if not outpath.exists():
    os.makedirs(outpath)

adata = sc.read_10x_mtx(path=args["inpath"])
adata.var["symbol"] = list(adata.var.index)

for key, value in args["sample info"].items():
    adata.uns[key] = value

adata.write_h5ad(filename=args["outfile"], compression="gzip")