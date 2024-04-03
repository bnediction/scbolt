import os

import networkx as nx
import mpbn

def influence_graph(file):
    if file.split(".")[-1] == "dot":
        return nx.nx_agraph.read_dot(file)
    elif file.split(".")[-1] == "bnet":
        return mpbn.load(file).influence_graph()
    else:
        raise OSError(f"Unable to convert `{file}` (extension .dot or .bnet required)")

path = "data/rna/bonesis"

infile = f"{path}/sub-1.dot"

grn = influence_graph(infile)

nx.drawing.nx_pydot.write_dot(grn, f"{path}/grn.dot")
os.system(f"dot -Tpdf ${path}/grn.dot -o ${path}/grn.pdf")
