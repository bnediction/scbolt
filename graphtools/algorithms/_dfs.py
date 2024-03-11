#!/usr/bin/env python

from typing import Any
from collections import deque

import networkx as nx

def dfs_path_sampling(graph: nx.Graph, source: Any, limit_depth: int=3) -> list:
    """
    Search for all existing paths from a node within a distance
    by a recursive implementation of depth-first search (DFS) algorithm.
    Contrary to NetworkX python module, do not verify if nodes have been
    visited previously, hence allowing to sample every possible paths.

    Parameters
    ----------
    graph
        NetworkX graph
    source
        node
    limit_depth
        specify the maximum search depth.
    
    Returns
    -------
    Return a list of paths from source within a distance.
    """

    def dfs_exploration(graph, source, stack, depth):
        for _target in graph.successors(source):
            stack.append(_target)
            __paths.append(list(stack))
            if depth < __limit_depth:
                dfs_exploration(graph, _target, stack, depth=depth+1)
            del stack[-1]
            
    global __paths, __limit_depth
    __paths = list()
    __limit_depth = limit_depth
    stack = deque()
    stack.append(source)
    dfs_exploration(graph, source=source, stack=stack, depth=1)
    paths = __paths
    del __limit_depth, __paths
    return paths
