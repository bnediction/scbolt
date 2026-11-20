# Solver Strategies

## Scope

Before Boolean network enumeration, scBOLT selects a regulatory domain that is
compatible with the constraints in `spec.yml`. Selection first prioritizes all
`important-nodes`, then maximizes the total number of retained nodes.
`mandatory-nodes` occur in every admissible solution, while `forbidden-nodes`
are excluded before selection.

Three complementary strategies control difficult selection problems:

1. **staged constraint enforcement** progressively introduces more expensive
   dynamical constraints;
2. **clause continuation** progressively increases the number of clauses
   available to Boolean update functions;
3. **domain continuation** first searches tractable subdomains, then expands a
   retained structural witness towards the complete regulatory domain.

These strategies affect different aspects of the problem and may be enabled
independently for each selection stage.

## Solver Outcomes

### `SAT`

`SAT` means that at least one compatible solution was found for the exact
constraints, clause bound, and domain considered. In an optimization problem,
it does not by itself establish optimality.

### `UNSAT`

`UNSAT` means that the solver proved no compatible solution exists for the
exact problem considered. Its scope is limited to that problem:

- an unsatisfiable subdomain does not imply that the complete domain is
  unsatisfiable;
- an unsatisfiable clause bound does not imply that a larger bound is
  unsatisfiable;
- an unsatisfiable relaxed specification says nothing about a different
  constraint level.

### `UNKNOWN`

`UNKNOWN` means that neither a solution nor a proof of unsatisfiability was
obtained within the available search budget. It indicates a computational
limit, not a logical conclusion.

### Certification

A certified solution is optimal for the exact objective vector, constraints,
clause bound, and domain solved. An uncertified `SAT` solution remains a valid
incumbent but may be improved. Time-limited parallel searches may retain
different incumbents on different machines even when they use the same seed.

## Staged Constraint Enforcement

scBOLT introduces constraint classes progressively:

1. **soft constraints:** configuration equality and inequality, reachability,
   and inexpensive attractor-related properties;
2. **intermediate constraints:** non-reachability and final non-reachability;
3. **complete specification:** all preceding constraints plus universal
   properties.

The available selection modules are listed below. Their execution order depends
on `strong-constants-scope`.

| Module | Active constraints | Purpose |
| --- | --- | --- |
| `max-nodes-soft` | Soft | Select nodes under the least expensive constraints. |
| `max-consts` | Configured scope | Remove an optimized set of jointly strong constants. |
| `max-nodes-relaxed` | Soft and intermediate | Add non-reachability constraints. |
| `max-nodes-seed` | Complete specification | Obtain or improve a complete-constraint solution. |
| `max-nodes-lock` | Complete specification | Protect the seed solution while attempting to retain more nodes. |

`max-nodes-relaxed` is relaxed only relative to the complete specification:
soft and intermediate constraints are both active, but hard constraints are
not yet enforced.

### Non-Reachability Bound

`bounded-nonreach` optionally limits the number of certificate refinements used
for ordinary non-reachability constraints. It does not bound the number of
biological state transitions. When omitted, BoNesis uses the regulatory-domain
size. Final non-reachability constraints targeting a fixed point or attractor
retain their tighter bound.

### Strong Constants

Strong constancy is evaluated under the constraints active at the selected
scope. Exactly one `max-consts` pass is used unless it is disabled:

| Scope | Selection order |
| --- | --- |
| `soft` | `max-nodes-soft` -> `max-consts` -> `max-nodes-relaxed` -> `max-nodes-seed` -> `max-nodes-lock` |
| `relaxed` | `max-nodes-soft` -> `max-nodes-relaxed` -> `max-consts` -> `max-nodes-seed` -> `max-nodes-lock` |
| `full` | `max-nodes-soft` -> `max-nodes-relaxed` -> `max-nodes-seed` -> `max-nodes-lock` -> `max-consts` |
| `none` | `max-nodes-soft` -> `max-nodes-relaxed` -> `max-nodes-seed` -> `max-nodes-lock` |

The default `soft` scope favors early domain reduction. `relaxed` includes
intermediate constraints. `full` evaluates strong constancy under the complete
specification. `none` disables only strong-constant elimination.

The `full` scope does not by itself establish a global lexicographic optimum.
Even when node-count optimality is certified, strong-constant optimization is
conditional on the particular node-optimal domain retained unless tied domains
are optimized jointly. After a seed or lock timeout, it is conditional on the
partial retained domain.

### Witness Propagation

A stage with no newly active constraint class forwards the solution and witness
it received. A stage introducing new constraints computes a corresponding
witness. `max-consts` always emits a witness for its reduced domain.

| Intermediate constraints | Hard constraints | `max-nodes-relaxed` | `max-nodes-seed` |
| --- | --- | --- | --- |
| Absent | Absent | Forward input. | Forward immediate predecessor. |
| Present | Absent | Compute a new solution. | Forward immediate predecessor. |
| Absent | Present | Forward input. | Compute a new solution. |
| Present | Present | Compute a new solution. | Compute a new solution. |

When `strong-constants-scope: relaxed`, the immediate predecessor of
`max-nodes-seed` is `max-consts`. Components removed by any earlier stage are
never reintroduced downstream.

`max-nodes-lock` protects nodes retained by a seed witness and attempts to
improve coverage within the complete seed input domain. If no hard constraints
were introduced, no structural seed witness exists, or `timeout-lock: 0`, the
seed result is retained without another solve.

## Clause Continuation

`max-clauses` controls the maximum number of conjunctive terms joined by OR in
each Boolean update function. Clause continuation replaces one direct solve at
that bound with progressively more expressive problems:

```text
1 -> 2 -> ... -> max-clauses
```

A witness found at one bound guides the next bound without restricting its
admissible solutions. A certified optimum at an intermediate bound remains
specific to that bound; scBOLT continues unless the theoretical objective
ceiling has already been reached.

`clause-bound-patience` limits stagnation at intermediate bounds. Every strict
objective improvement resets it. The target `max-clauses` bound is governed by
the stage timeout rather than clause-bound patience.

Clause continuation is available for `soft`, `relaxed`, `seed`, and `lock`. It
is enabled by default for `relaxed`, `seed`, and `lock`, and disabled by default
for `soft`. It does not apply to `max-consts`.

When an anytime strategy stalls before reaching the complete domain, scBOLT may
retry the same clause bound once with `opt` and `bb,lin` from the best retained
witness. No redundant retry is made when that strategy is already active or
optimization objectives are disabled.

## Domain Continuation

Domain continuation addresses regulatory domains that are too difficult to
optimize directly. It may include four observable phases:

1. **acquisition:** search alternative subdomains for an initial witness;
2. **expansion:** enlarge the best witnessed domain progressively;
3. **completion:** evaluate the complete regulatory domain;
4. **refinement:** when needed, retry the complete domain with `opt` and
   `bb,lin` from the best retained witness.

`jobs` limits the number of concurrent portfolio workers. Domain-continuation
workers use one Clingo thread each, so `jobs` and `clingo-threads` are not
multiplied. When domain continuation is disabled, `clingo-threads` controls the
ordinary complete-domain solve.

### Patience and Progress

`domain-wave-patience` controls stagnation within soft, relaxed, and seed waves;
`domain-wave-patience-lock` controls lock waves. Grounding time does not consume
this patience. The first solution and every strict objective improvement reset
the wave clock.

Interactive progress reports `queued`, `grounding`, `solving`, `stopping`, and
`interrupted` states. Completed wave summaries distinguish:

- `certified`: workers that proved optimality for their candidate domain;
- `sat`: workers that found an uncertified solution;
- `unsat`: workers that proved their candidate domain unsatisfiable;
- `unknown`: workers that ended without a logical result;
- `cancelled`: workers stopped because another result made further work
  unnecessary.

Certification on an incomplete candidate domain does not establish optimality
for another domain or stop candidates exploring different compositions.

### Yield and Refreshes

`minimum-domain-yield` sets the minimum retained-node gain for an expansion. If
the yield is too low, scBOLT can retry another candidate composition at the
same size. `maximum-domain-refreshes` limits those retries.

Set `minimum-domain-yield: 0` to disable yield-triggered refreshes. Set
`maximum-domain-refreshes: 0` to disable all constant-size refreshes. These
settings affect search scheduling, not solver certification.

### Memory Budget

`memory` is a soft portfolio budget. scBOLT adapts the number of active workers
to observed memory use and may interrupt less advanced candidates when the
budget is reached, while retaining at least one solver. A single solver can
still exceed the budget before it can be stopped, so `memory` is not an
operating-system hard limit.

### Reproducibility

Candidate construction and solver profiles are deterministic for a fixed
`seed`, clause bound, wave, and `jobs` value. Patience and timeout boundaries
remain sensitive to hardware performance and process scheduling. Certified
results retain their solver guarantee, whereas time-limited incumbents may
differ across machines.

Domain continuation is available for `soft`, `relaxed`, `seed`, and `lock`. It
is enabled by default for `relaxed`, `seed`, and `lock`, and disabled by default
for `soft`. Lock uses expansion only when it receives a witness computed under
the complete specification.

## Subset-Minimal Enumeration

When available, the final gene-selection witness guides acquisition of the
first subset-minimal network without changing the admissible solution set.

During `bn-submin`, completed networks are checkpointed. If memory pressure
requires a restart, scBOLT preserves complete networks and continues with a
smaller active portfolio when necessary. If the run is interrupted, the next
interactive invocation offers:

```text
1) restart
2) resume
3) exit
```

Resume is the default, and non-interactive invocations resume automatically.
Incompatible checkpoints are not mixed with the current solution space. Use
`--reset-target=bn-submin` to request a fresh enumeration explicitly.

## Configuration Reference

`<stage>` denotes `soft`, `relaxed`, `seed`, or `lock`, except where stated
otherwise.

### Problem Definition

| Parameter | Meaning |
| --- | --- |
| `prior-knowledge` | Regulatory resource or custom influence graph defining the complete structural domain. |
| `max-clauses` | Maximum number of conjunctive terms joined by OR in each Boolean update function. |
| `seed` | Shared seed for reproducible ordering and portfolio construction. |

Resource-version parameters such as `geneinfo-version`, `omnipath-version`,
`hcop-version`, `dorothea-api`, `dorothea-compatibility`, and
`dorothea-levels` also affect a built-in regulatory domain.

### Staged Constraint Enforcement

| Parameter | Meaning |
| --- | --- |
| `bounded-nonreach` | Optional shared non-reachability certificate bound. |
| `strong-constants-scope` | Place `max-consts` at `soft`, `relaxed`, or `full`; `none` disables it. |
| `minimize-self-loops-constants` | Also minimize one-node feedbacks during strong-constant optimization. |
| `timeout-soft` | Total runtime limit for soft node selection. |
| `timeout-consts` | Total runtime limit for strong-constant optimization. |
| `timeout-relaxed` | Total runtime limit after intermediate constraints are introduced. |
| `timeout-seed` | Total runtime limit for complete-constraint seed optimization. |
| `timeout-lock` | Total runtime limit for lock optimization; `0` retains the seed solution directly. |

Each `timeout-<stage>` covers the complete stage and is not reset between
clause bounds or domain waves.

### Clause Continuation

| Parameter | Meaning |
| --- | --- |
| `clause-continuation-<stage>` | Enable successive clause-bound expansion for the stage. |
| `clause-bound-patience` | Maximum stagnation time at an intermediate clause bound. |

An empty or zero clause-bound patience disables early advancement based on
stagnation.

### Domain Continuation

| Parameter | Meaning |
| --- | --- |
| `domain-continuation-<stage>` | Enable adaptive witness acquisition and domain expansion for the stage. |
| `domain-wave-patience` | Wave stagnation time for `soft`, `relaxed`, and `seed`; default `5m`. |
| `domain-wave-patience-lock` | Wave stagnation time for `lock`; default `10m`. |
| `minimum-domain-yield` | Minimum retained-node gain per node added; `0` disables yield-triggered refreshes. |
| `maximum-domain-refreshes` | Maximum constant-size retries; `0` disables them. |
| `memory` | Soft memory budget used to adapt the active portfolio. |
| `jobs` | Maximum number of concurrent portfolio workers. |

### Clingo Optimization

| Parameter | Meaning |
| --- | --- |
| `clingo-config-<stage>` | Named Clingo preset or custom configuration file; default `auto`. |
| `clingo-mode-<stage>` | `opt`, `optN`, or `ignore`; `ignore` disables optimization objectives. |
| `clingo-strategy-<stage>` | Clingo optimization strategy, such as `bb,inc`, `bb,lin`, or `usc,*`. |
| `clingo-threads` | Threads used by a stage-level solve when domain continuation is disabled. |

With domain continuation and no explicit strategy, `soft`, `relaxed`, and
`seed` use `bb,inc`. Lock defaults to `opt` with `bb,lin`. Without domain
continuation, the default optimization strategy is `bb,lin`.

### Final Boolean Network Inference

| Parameter | Meaning |
| --- | --- |
| `minimize-self-loops-inference` | Use one-node feedback count as a tie-breaker for `bn-min`. |
| `inference-limit` | Maximum generated networks; `null` or `0` requests all available solutions. |
| `configuration-formats` | Export formats for compatible state configurations. |
| `graph-formats` | Graph formats exported for inferred networks. |

`bn-min` first minimizes the number of signed regulatory interactions. It does
not maximize constants. `bn-submin` enumerates networks whose signed influence
graphs have no compatible proper subset. `bn-diverse` samples compatible
networks using diversity-oriented heuristics without claiming either form of
minimality.

## Time Budgets and Partial Results

The three time controls have different scopes:

1. `domain-wave-patience` or `domain-wave-patience-lock` bounds objective
   stagnation within one portfolio wave;
2. `clause-bound-patience` bounds objective stagnation at one intermediate
   clause bound;
3. `timeout-<stage>` bounds the complete stage and is never reset.

Whenever a witness exists, scBOLT can retain the best node set and structural
witness after a timeout or user interruption. Such a result is explicitly
partial and uncertified. If no witness was found, timeout remains `UNKNOWN` and
cannot produce a partial solution.
