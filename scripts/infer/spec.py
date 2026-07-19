#!/usr/bin/env python

import argparse
import os
from pathlib import Path

import bonesis
import bonesistools as bt
import pandas as pd
import yaml
from utils import get_cfg, load_bonesis_code, load_prior_network

from scbolt import cli, console

bonesis.settings["quiet"] = True
script_name = Path(__file__).name


parser = argparse.ArgumentParser(
    prog="spec",
    description="""Check whether BoNesis properties are well defined and convert model specifications (format: yml) and binarized macrostates (format: csv) into four files:
    - model (txt): dynamical Boolean properties
    - metastates (csv): partially binarized metastates
    - important-nodes (txt): nodes prioritized to appear in Boolean network solutions
    - mandatory-nodes (txt): nodes forced to appear in Boolean network solutions

The model specification file (format: yml) must contain:
    - dynamical_constraints (list of dynamical Boolean properties in BoNesis syntax)
    - important_nodes (list of nodes prioritized to appear in Boolean network solutions)
    - mandatory_nodes (list of nodes forced to appear in Boolean network solutions)
""",
    usage=(
        f"python {script_name} <FILE> <FILE> --model <FILE> --metastates <FILE> "
        "--mandatory-nodes <FILE> --important-nodes <FILE> [<args>]"
    ),
    formatter_class=cli.HelpFormatter,
)

parser.add_argument(
    dest="model_specification",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing model specifications for BoNesis (format: yml)",
)

parser.add_argument(
    "macrostates",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    help="input file storing partially binarized macrostates (format: csv)",
)

parser.add_argument(
    "--model",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    required=True,
    help="output file storing dynamical Boolean properties (format: txt)",
)

parser.add_argument(
    "--metastates",
    dest="metastates",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="FILE",
    help="output file storing partially binarized metastates (format: csv)",
)

parser.add_argument(
    "--important-nodes",
    dest="important_nodes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help=(
        "output file storing important nodes prioritized to appear (format: json or "
        "txt)"
    ),
)

parser.add_argument(
    "--mandatory-nodes",
    dest="mandatory_nodes",
    type=lambda x: Path(x).resolve(),
    required=False,
    metavar="FILE",
    help="output file storing mandatory nodes forced to appear (format: json or txt)",
)

parser.add_argument(
    "--domain",
    dest="domain",
    action=cli.Bonesis_domain,
    required=False,
    default="collectri",
)

parser.add_argument(
    "--sep",
    dest="sep",
    type=str,
    required=False,
    default=",",
    metavar="CHAR",
    help="field delimiter for csv format (default: ',')",
)

parser.add_argument(
    "--organism",
    dest="organism",
    action=cli.Store_organism,
    default="mouse",
    required=False,
)

parser.add_argument(
    "--dorothea-levels",
    dest="dorothea_levels",
    nargs="+",
    choices=["A", "B", "C", "D"],
    default=None,
    metavar="[A | B | C | D]",
    help=(
        "DoRothEA confidence levels used when --domain dorothea "
        "(default: A B C for modern API; A B C D for legacy API)"
    ),
)

parser.add_argument(
    "--geneinfo-version",
    dest="geneinfo_version",
    action=cli.Store_version,
    allow_current=False,
    allow_bundled=True,
    allow_date=False,
    allow_path=True,
    required=False,
    default="bundled",
    help="NCBI gene_info source used for gene name standardization (default: bundled)",
)

parser.add_argument(
    "--omnipath-version",
    dest="omnipath_version",
    action=cli.Store_version,
    allow_current=False,
    required=False,
    default="latest",
    help=(
        "OmniPath resource version used when --domain is collectri or dorothea "
        "(default: latest)"
    ),
)

parser.add_argument(
    "--hcop-version",
    dest="hcop_version",
    type=str,
    required=False,
    default="bundled",
    help=(
        "HCOP orthology version used when --domain is collectri or dorothea (default: "
        "bundled)"
    ),
)

parser.add_argument(
    "--dorothea-api",
    dest="dorothea_api",
    choices=["modern", "legacy"],
    required=False,
    default="modern",
    help="DoRothEA API flavor used when --domain dorothea (default: modern)",
)

parser.add_argument(
    "--dorothea-compatibility",
    dest="dorothea_compatibility",
    action=cli.Store_boolean,
    required=False,
    default=True,
    help="reproduce decoupler DoRothEA duplicated-pair handling (default: true)",
)

args = parser.parse_args()

for outfile in [
    args.macrostates,
    args.model,
    args.mandatory_nodes,
    args.important_nodes,
]:
    if not Path(os.path.dirname(outfile)).exists():
        os.makedirs(Path(os.path.dirname(outfile)))

identifiers = bt.resources.ncbi.identifiers(
    organism=args.organism,
    version=args.geneinfo_version,
)

console.print_task(
    f"loading model specification (file={console.format_path(args.model_specification)})"
)

with open(args.model_specification, "r") as file:
    specification = yaml.safe_load(file) or {}

if not isinstance(specification, dict):
    parser.error("model specification must be a YAML mapping")


def read_specification_list(key: str, *, required: bool = False) -> list[str]:
    if key not in specification:
        if required:
            parser.error(f"missing model specification section: {key}")
        return []

    values = specification[key]
    if values is None:
        return []
    if not isinstance(values, list):
        parser.error(f"model specification section '{key}' must be a list")
    if not all(isinstance(value, str) for value in values):
        parser.error(f"model specification section '{key}' must contain only strings")
    return values


dynamical_constraints = read_specification_list("dynamical_constraints", required=True)
important_nodes = set(read_specification_list("important_nodes"))
mandatory_nodes = set(read_specification_list("mandatory_nodes"))

console.print_task(f"loading CSV table (file={console.format_path(args.macrostates)})")

macrostates_df = identifiers(
    pd.read_csv(args.macrostates, index_col=0, sep=args.sep), axis="columns"
)

console.print_task("getting binarized states")

important_nodes = identifiers(important_nodes)
mandatory_nodes = identifiers(mandatory_nodes)

has_defined_state = macrostates_df.apply(
    lambda values: pd.to_numeric(values, errors="coerce").isin([0, 1]).any(),
    axis=0,
)
removed_nodes = macrostates_df.columns[~has_defined_state]
if len(removed_nodes) > 0:
    kept_nodes = int(has_defined_state.sum())
    total_nodes = len(has_defined_state)
    console.print_info(
        "removing undefined features "
        f"(kept={kept_nodes}/{total_nodes} "
        f"({100 * kept_nodes / total_nodes:.1f}%), "
        f"removed={len(removed_nodes)})"
    )
    macrostates_df = macrostates_df.loc[:, has_defined_state]

macrostates_cfg = get_cfg(macrostates_df, axis="index", identifiers=identifiers)

console.print_info("checking Boolean properties")

grn = load_prior_network(
    args.domain,
    args.organism,
    identifiers,
    args.dorothea_levels,
    args.omnipath_version,
    args.hcop_version,
    args.dorothea_api,
    args.dorothea_compatibility,
)
pkn_options = {
    "canonic": True,
    "maxclause": 8,
}
pkn = bonesis.domains.InfluenceGraph(grn, **pkn_options)
bo = bonesis.BoNesis(pkn, macrostates_cfg)

namespace = {"bo": bo}

for constraint in dynamical_constraints:
    try:
        load_bonesis_code(
            bo,
            constraint,
            filename=str(args.model_specification),
            namespace=namespace,
        )
    except Exception as error:
        raise RuntimeError(
            f"invalid dynamical Boolean constraint: {constraint}"
        ) from error

console.print_task(f"saving Boolean specification (file={console.format_path(args.model)})")

with open(args.model, "w") as file:
    for constraint in dynamical_constraints:
        file.write(f"{constraint}\n")

console.print_task(f"saving CSV table (file={console.format_path(args.metastates)})")

macrostates_df.to_csv(args.metastates, sep=",", index=True)

console.print_task(f"saving node list (file={console.format_path(args.important_nodes)})")

with open(args.important_nodes, "w") as file:
    for node in important_nodes:
        file.write(f"{node}\n")

console.print_task(f"saving node list (file={console.format_path(args.mandatory_nodes)})")

with open(args.mandatory_nodes, "w") as file:
    for node in mandatory_nodes:
        file.write(f"{node}\n")
