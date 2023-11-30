from pathlib import Path
import pandas as pd
import json

args = {
    "inpath":Path(f"../data/public"),
    "outpath":Path(f"../data/signatures"),
#    "gene_filename":"geiger_signatures.xls",
    "signature_filename":"chambers_signatures.xls"
}

# gene_file = Path(f"{args['inpath']}/{args['gene_filename']}").resolve()
signature_file = Path(f"{args['inpath']}/{args['signature_filename']}").resolve()

if not args["outpath"].resolve().exists():
    args["outpath"].resolve().mkdir()

def get_signatures(file_xls):
    signature_dict = dict()
    for sheetname, signature in file_xls.items():
        if not sheetname=="Description":
            cell_type = sheetname.split(".txt", 1)[0]
            gene_symbols = [gene for gene in list(signature["Gene Symbol"]) if isinstance(gene, str)]
            signature_dict[cell_type] = gene_symbols
    return signature_dict

print(f"\nComputing micro array signatures...\n")

signature_xls = pd.read_excel(io=signature_file, sheet_name=None)
signature_dict = get_signatures(signature_xls)

with open(f"{args['outpath']}/signatures.json", "w") as file:
    json.dump(signature_dict, file, indent=2)
