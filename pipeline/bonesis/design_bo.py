#!/usr/bin/env python

import sys
from pathlib import Path

import argparse

from itertools import combinations

parser = argparse.ArgumentParser(
    prog="Convert a text file describing trajectories into text readable by bonesis package",
    description="""conversion of a text file describing the trajectories where each line is in the form: `node1 -> ... -> node_k`.\n
    The output stream provides specifications understandable by bonesis.\n""",
    usage="python design_bo -i <path> [-o <path>]")

parser.add_argument(
    "-i", "--infile",
    dest="infile",
    type=lambda x: Path(x).resolve(),
    required=True,
    metavar="PATH",
    help="path to text infile"
)

parser.add_argument(
    "-o", "--outfile",
    dest="outfile",
    type=lambda x: Path(x).resolve(),
    required=False,
    default=None,
    metavar="PATH",
    help="path to text outfile. If not specified, print results into stdout."
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
    file: Path = None
):
    if file is not None:
        sys.stdout = open(file, "w")
    stable_states = list()
    for trajectory in trajectories:
        if len(trajectory) == 1:
            continue
        bo_trajectory = str()
        fp = trajectory[-1]
        for state in trajectory:
            if state != fp:
                bo_trajectory += f"~bo.obs('{state}') >= "
            else:
                bo_trajectory += f"bo.fixed(~bo.obs('{state}'))"
                stable_states.append(fp)
        print(bo_trajectory)
    for a, b in combinations(stable_states, 2):
        print(f"~bo.obs({a}) != ~bo.obs({b})")
    sys.stdout.close()
    return None

trajectories = read_trajectories(args.infile)
write_bonesis_model(trajectories, args.outfile)
