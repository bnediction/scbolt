#!/usr/bin/python3

from pathlib import Path
import json

import pandas as pd

def file2signatures(file):
    signatures_d = dict()
    for sheetname, signature in file.items():
        if not sheetname=="Description":
            cell_type = sheetname.split(".txt", 1)[0]
            gene_symbols = [gene for gene in list(signature["Gene Symbol"]) if isinstance(gene, str)]
            signatures_d[cell_type] = gene_symbols
    return signatures_d

def df2signatures(df):
    signatures_d = dict()
    for cell_type, signatures in df.items():
        gene_symbols = [gene for gene in signatures if isinstance(gene, str)]
        signatures_d[cell_type] = gene_symbols
    return signatures_d

args = {
    "type_signatures_infile": Path(f"data/public/signatures/chambers.xls").resolve(),
    "list_signatures_infile": Path(f"data/public/signatures/geiger.xls").resolve(),
    "outpath": Path(f"data/public/signatures").resolve()
}

if not args["outpath"].resolve().exists():
    args["outpath"].resolve().mkdir()

type_signatures_df = pd.read_excel(io=args["type_signatures_infile"], sheet_name=None)
type_signatures_d = file2signatures(type_signatures_df)

list_signatures_df = pd.read_excel(io=args["list_signatures_infile"], sheet_name=0)
list_signatures_df.columns = list(list_signatures_df.iloc[0])
list_signatures_df.drop([0, 1], axis=0, inplace=True)
list_signatures_d = df2signatures(list_signatures_df)

signatures_d = {
    **type_signatures_d,
    **list_signatures_d
}

with open(f"{args['outpath']}/signatures.json", "w") as file:
    json.dump(signatures_d, file, indent=2)
