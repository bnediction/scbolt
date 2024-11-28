#!/usr/bin/env python

from typing import Optional
from pathlib import Path

import argparse

from itertools import combinations

parser = argparse.ArgumentParser(
    prog="Convert text file(s) describing trajectories into comprehensible text for bonesis package",
    description="""Text file conversion for describing the trajectories where each line is in the form: `node_1 -> ... -> node_k`. \
    The output stream provides specifications comprehensible for bonesis.""",
    usage="python design_bo.py [-h] <path>"
)

parser.add_argument(
    dest="infiles",
    type=lambda x: Path(x).resolve(),
    metavar="FILE",
    nargs="+",
    help="txt file(s) describing trajectories"
)

parser.add_argument(
    "--conditions",
    dest="conditions",
    type=str,
    required=False,
    nargs="+",
    metavar="LITERAL",
    default=None,
    help="conditions related to each input txt files, in the same order (mandatory when there are multiple input txt files)"
)

args = parser.parse_args()

def read_trajectories(
    file: Path
) -> list:
    trajectories = list()
    with open(file, "r") as file:
        for line in file:
            trajectory = line.replace("\n", "").split(" -> ")
            trajectories.append(trajectory)
    return trajectories

def write_bonesis_model(
    trajectories: list,
    condition: Optional[str] = None
) -> None:
    stable_states = list()
    for trajectory in trajectories:
        if len(trajectory) == 1:
            continue
        bo_trajectory = str()
        fp = trajectory[-1]
        for config in trajectory:
            if config != fp:
                bo_trajectory += f"~bo.obs('{config}{f'_{condition}' if condition is not None else ''}') >= "
            else:
                bo_trajectory += f"bo.fixed(~bo.obs('{config}{f'_{condition}' if condition is not None else ''}'))"
                stable_states.append(fp)
        print(bo_trajectory)
    for a, b in combinations(stable_states, 2):
        print(f"~bo.obs('{a}{f'_{condition}' if condition is not None else ''}') != ~bo.obs('{b}{f'_{condition}' if condition is not None else ''}')")
    return None

if args.conditions is None:
    if len(args.infiles) == 1:
        trajectories = read_trajectories(args.infiles[0])
        write_bonesis_model(trajectories)
    else:
        raise argparse.ArgumentError(None, "--conditions is required when there are multiple infiles passed in argument")
else:
    if len(args.infiles) == len(args.conditions):
        for infile, condition in zip(args.infiles, args.conditions):
            trajectories = read_trajectories(infile)
            write_bonesis_model(trajectories, condition)
    else:
        raise argparse.ArgumentError(None, "infiles and --conditions require the same number of values")
