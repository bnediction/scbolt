#!/usr/bin/env python

from typing import (
    Optional,
    Union,
    Dict
)
from pathlib import Path

import argparse

import itertools

parser = argparse.ArgumentParser(
    prog="Bonesis specification",
    description="""Convert file(s) describing trajectories into comprehensible text for bonesis package. \
    Lines in the input file(s) are in the form: `node_1 -> ... -> node_k`. \
    The output stream provides model specifications in Bonesis langage.""",
    usage="python bonesis_specification.py [-h] <FILE ...> [--conditions <LITERAL ...>]"
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
    file: Path,
) -> list:
    trajectories = list()
    with open(file, "r") as file:
        for line in file:
            trajectory = line.replace("\n", "").split(" -> ")
            trajectories.append(trajectory)
    return trajectories

def write_bonesis_model(
    trajectories: Union[list, Dict[str, list]],
) -> None:
    
    def write_bonesis_model_from_one_condition(
        trajectories: Union[list, Dict[str, list]],
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
        for s1, s2 in itertools.combinations(stable_states, 2):
            print(f"~bo.obs('{s1}{f'_{condition}' if condition is not None else ''}') != ~bo.obs('{s2}{f'_{condition}' if condition is not None else ''}')")
        return None
    
    if isinstance(trajectories, list):
        write_bonesis_model_from_one_condition(
            trajectories=trajectories,
            condition=None
        )
    elif isinstance(trajectories, Dict):
        initial_states = {}
        for condition, trajectories_for_one_condition in trajectories.items():
            write_bonesis_model_from_one_condition(
                trajectories=trajectories_for_one_condition,
                condition=condition
            )
            initial_states[condition] = {trajectory[0] for trajectory in trajectories_for_one_condition}
        for condition1, condition2 in itertools.combinations(trajectories.keys(), 2):
            for initial_state_c1 in initial_states[condition1]:
                for initial_state_c2 in initial_states[condition2]:
                    print(f"~bo.obs('{initial_state_c1}_{condition1}') != ~bo.obs('{initial_state_c2}_{condition2}')")
    else:
        raise ValueError("`trajectories` must be a list or a dict")
    return None

if args.conditions is None:
    if len(args.infiles) == 1:
        trajectories = read_trajectories(args.infiles[0])
        write_bonesis_model(trajectories)
    else:
        raise argparse.ArgumentError(None, "--conditions is required when there are multiple infiles passed in argument")
else:
    if len(args.infiles) == len(args.conditions):
        trajectories = dict()
        for infile, condition in zip(args.infiles, args.conditions):
            trajectories[condition] = read_trajectories(infile)
        write_bonesis_model(trajectories)
    else:
        raise argparse.ArgumentError(None, "infiles and --conditions require the same number of values")
