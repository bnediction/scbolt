# scBOLT Quickstart

This directory contains a small, complete scBOLT example derived from the
Nestorowa hematopoiesis case study. Its inputs are already prepared, so the
example starts directly from Boolean macrostates and a signed regulatory
domain. No download, single-cell preprocessing, or spectral embedding is
required.

## Run

From the scBOLT repository root:

```bash
cd quickstart
scbolt check bn-submin
scbolt bn-submin
```

The reference laptop completes the full run in about 25 seconds. Runtime varies
with the machine, but this example is intended to finish in well under a minute
on a typical recent workstation.

These commands validate the project, perform staged gene selection under the
soft, relaxed, and complete specifications, and enumerates 10 subset-minimal
Boolean networks. Clause and domain continuation are disabled because the
tutorial domain is already small. The selected full domain is optimized with
`opt` and `bb,inc`; the bundled example reaches and certifies its 80-node
objective ceiling.

## Inputs

| File | Content |
| --- | --- |
| `data/mstates_bin.csv` | Six consensus Boolean macrostates, `S0` to `S5`, restricted to the tutorial genes. |
| `data/interactions.csv` | 139 signed interactions forming an 80-gene regulatory domain. |
| `spec.yml` | The hematopoiesis dynamical constraints and prioritized genes. |
| `scbolt.yml` | Runtime, solver, and inference settings. |

The 80 genes comprise 37 ensemble feedback nodes and 43 adjacent genes sampled
deterministically with seed 10. Feedback membership was computed in each of the
1,000 inferred case-study networks before taking the union; it was not inferred
from feedback structures that only appear after graph aggregation. The signed
interaction table is then the subgraph induced by these genes in the aggregate
union topology.

This compact domain is a pedagogical fixture selected from case-study outputs.
It is not independent biological evidence and does not reproduce the full
manuscript analysis. Use the separate scBOLT case-study repository for that
purpose.

## Results

The main outputs are written below `project/infer/`:

| Path | Content |
| --- | --- |
| `genes/lock/comps.txt` | Final selected regulatory components. |
| `bn/submin/<n>/model.bnet` | Individual subset-minimal Boolean networks. |
| `bn/submin/influence_graph/` | Aggregate influence-graph exports. |

Run `scbolt bn-submin --reset-target=spec` to rebuild the example from its
Boolean specification.
