# Solver Strategies

**Status:** this document is a design draft. It describes the intended solver
behavior before implementation and is not yet the source of truth for the
current scBOLT code. Parameter names, defaults, and transition policies may be
adjusted after experimental validation.

## Scope

Before Boolean network enumeration, scBOLT reduces a prior regulatory domain
to a set of components compatible with the user-defined dynamical constraints.
This gene-selection procedure is expressed as a sequence of BoNesis
optimization problems solved with Clingo.

Let:

- `G` be the complete regulatory domain;
- `D` be the candidate subdomain used by one solver instance, with `D` a
  subgraph of `G`;
- `C` be the active set of dynamical constraints;
- `q` be the maximum number of clauses allowed in each Boolean update
  function;
- `W` be a structural witness containing a satisfiable set of nodes, clauses,
  and constants.

Node selection first prioritizes user-defined important nodes and then
maximizes the total number of satisfiable nodes. Mandatory nodes must occur in
every admissible solution. Important and mandatory nodes are included in every
candidate domain considered by domain continuation.

Three complementary strategies control the complexity of this optimization:

1. progressive constraint relaxation;
2. clause continuation;
3. domain continuation.

The strategies act on different axes. Constraint relaxation changes `C`,
clause continuation changes `q`, and domain continuation changes `D` to first
acquire a witness `W` and then lift it progressively to the complete domain.

## Solver Outcomes

Every bounded solver attempt must preserve the distinction between `SAT`,
`UNSAT`, and `UNKNOWN`.

### `SAT`

`SAT` means that Clingo found at least one witness for the exact combination of
constraints, clause bound, and domain being tested.

For an optimization problem, `SAT` does not imply that the witness is globally
optimal. A witness interrupted by a patience limit, a total timeout, or the
user is a partial solution unless Clingo has certified optimality.

### `UNSAT`

`UNSAT` means that Clingo completed the search and proved that no witness exists
for the exact problem:

```text
(constraints=C, max clauses=q, domain=D)
```

This is a solver result, not a failure to obtain a result. Its scope must not be
extended beyond the problem that was actually proved unsatisfiable:

- `UNSAT` on a subdomain does not imply `UNSAT` on the complete domain because
  additional nodes and interactions may restore satisfiability;
- `UNSAT` at clause bound `q` does not imply `UNSAT` at a larger clause bound
  because additional clauses increase the expressiveness of Boolean functions;
- `UNSAT` under the complete hard constraint set does not describe a relaxed
  problem from which some constraints were removed.

### `UNKNOWN`

`UNKNOWN` means that no witness and no proof of unsatisfiability were obtained
within the allocated search budget. Typical causes include:

- domain-continuation patience expiration;
- clause-continuation patience expiration before any witness;
- the stage-wide timeout;
- user interruption;
- an explicit solver interruption.

`UNKNOWN` must never be reported or interpreted as `UNSAT`. It indicates a
computational bottleneck rather than a logical conclusion.

## Progressive Constraint Relaxation

Formal synthesis requires all active constraints to be satisfied
simultaneously. Large regulatory domains combined with expensive dynamical
properties can therefore produce difficult optimization problems. scBOLT
introduces constraint classes progressively so that early stages can remove
incompatible or dynamically uninformative components before the complete
constraint set is solved.

The constraint hierarchy is:

1. **Soft constraints:** configuration equality and inequality, reachability,
   and attractor-related properties that do not require the intermediate or
   hard predicates below.
2. **Intermediate constraints:** non-reachability and final non-reachability
   properties.
3. **Hard constraints:** universal properties such as constraints over all
   fixed points or the reachability of all relevant attractors.

The corresponding selection modules are:

| Module | Active constraint level | Purpose |
| --- | --- | --- |
| `max-nodes-soft` | soft | Maximize satisfiable nodes under the least expensive constraint set. |
| `max-consts-soft` | soft | Identify strong constants and retain components contributing dynamical variability. |
| `max-nodes-relaxed` | soft + intermediate | Re-optimize the reduced domain after introducing non-reachability constraints. |
| `max-nodes-seed` | complete | Search for a bounded-time seed solution under all constraints. |
| `max-nodes-lock` | complete | Resume from the seed witness while forcing previously retained seed nodes to remain selected. |

The procedure is a domain-reduction heuristic. Selecting one admissible optimum
at an intermediate stage is not formally equivalent to solving all constraints
simultaneously because tied intermediate solutions may retain different node
sets. The staged procedure nevertheless avoids exposing the most expensive
constraints to the complete initial domain.

Strong-constant optimization is restricted to the early soft stage. Components
identified as strong constants can be removed before harder constraints are
introduced, reducing the domain without treating uniform Boolean assignments as
dynamic regulatory signals.

The optional `forbidden_nodes` specification excludes components before the
`SOFT` stage. These components are removed from both the macrostate table and
the initial regulatory domain. Because every later selection stage operates on
the domain retained by its predecessor, the exclusion is applied only once and
forbidden components cannot be reintroduced downstream.

The `seed` and `lock` stages have distinct roles. `max-nodes-seed` is allowed to
return a partial bounded-time solution. `max-nodes-lock` receives its structural
witness and makes the selected seed nodes mandatory, preventing later solving
from replacing already admissible components while trying to improve coverage.

## Clause Continuation

The number of clauses allowed in each Boolean update function strongly affects
the size of the ASP search space. Clause continuation replaces one direct solve
at `MAX_CLAUSE` with a sequence of increasingly expressive problems:

```text
q=1 -> q=2 -> ... -> q=MAX_CLAUSE
```

Each satisfiable stage writes a structural witness. The witness is passed to the
next clause bound as a soft Clingo heuristic, not as a hard restriction. The
next stage may therefore improve or replace the previous structure.

When `LOCK` reuses a seed witness requiring more than one clause, clause
continuation starts at the smallest compatible bound instead of returning to
`q=1`.

Intermediate clause bounds use a patience limit measuring time since the most
recent objective improvement. Every improved solution resets this patience.
The target bound `MAX_CLAUSE` disables clause patience: it terminates only after
certified optimality, the stage-wide timeout, or user interruption.

The transition policy at an intermediate clause bound is:

- `SAT`: preserve the best witness and continue with the next bound;
- `UNSAT`: continue immediately because a larger clause bound may restore
  satisfiability;
- `UNKNOWN`: preserve any witness already found, then continue when the
  clause-continuation patience expires;
- theoretical maximum reached: stop the selection stage because no larger
  clause bound can improve node coverage.

A Clingo optimum certified at an intermediate bound is optimal only for that
bound. Unless it reaches the theoretical maximum objective, clause continuation
still advances because a more expressive update function may retain additional
nodes.

When clause continuation is enabled and optimization settings are not
explicitly overridden, scBOLT uses an anytime-oriented Clingo mode and
branch-and-bound strategy suitable for producing intermediate witnesses.
Explicit `CLINGO_OPT_MODE_<STAGE>` and
`CLINGO_OPT_STRATEGY_<STAGE>` values always take precedence over these derived
defaults.

Clause continuation is available for `SOFT`, `RELAXED`, `SEED`, and `LOCK` node
selection stages. It does not apply to the `CONSTS` stage.

## Domain Continuation

Domain continuation addresses a different bottleneck: a complete regulatory
domain may be too large for Clingo to find or improve a witness directly, even
when a satisfiable subdomain would provide an effective warm start.

Domain continuation has two phases:

1. **First-witness portfolio:** while no witness is available, scBOLT launches
   single-job Clingo instances over different candidate subdomains.
2. **Witness-guided expansion:** after selecting a witness, scBOLT evaluates
   parallel waves of larger candidate domains and reuses the best structural
   witness as a warm start until the complete domain is reached.

```text
no witness -> acquisition portfolio -> witness on D0
           -> expansion wave -> selected D1
           -> expansion wave -> selected D2 -> ... -> G
```

Every candidate contains all important and mandatory nodes. The remaining
nodes follow deterministic, seed-dependent priority orders so that both the
acquisition portfolio and expansion waves explore domain compositions
reproducibly.

Each portfolio branch defines nested candidate domains:

```text
required nodes <= D1 <= D2 <= ... <= G
```

Nested domains make an `UNSAT` result informative within one branch: if `D1` is
proved unsatisfiable, its smaller prefixes need not be reconsidered. Different
branches use different node orders and can therefore test alternative
compositions at similar sizes.

Before the first witness is found, domain size is adapted according to the
solver outcome rather than following a fixed increasing schedule:

| Outcome | Domain-continuation action |
| --- | --- |
| `SAT` | Stop competing portfolio workers, retain the successful branch, and begin witness-guided expansion. |
| `UNSAT` | Increase the domain because the tested subdomain lacks a satisfiable structure. |
| `UNKNOWN` | Reduce or change the domain because the current search encountered a computational bottleneck. |

Within one branch, the largest domain proved `UNSAT` forms a logical lower
bound on useful domain size. The smallest domain returning `UNKNOWN` forms a
heuristic upper bound on tractable search size. A subsequent candidate can be
chosen between these bounds. The `UNKNOWN` bound is computational rather than
logical because solver runtime is not guaranteed to vary monotonically with
domain size.

Portfolio workers seek a first satisfiable witness and therefore use one
Clingo job each. They do not run the complete optimization assigned to the
stage. If several workers report `SAT` during the same coordination round,
scBOLT selects a witness deterministically by objective value and then by
portfolio index.

After a witness is selected:

1. all remaining first-witness portfolio workers are terminated;
2. the successful candidate domain becomes the current domain;
3. scBOLT constructs a wave of larger candidate domains of the same size;
4. every candidate contains the complete current domain but differs in the
   additional nodes selected by its deterministic branch;
5. the current witness is injected into every candidate as a soft heuristic;
6. the candidates are evaluated in parallel, using one Clingo job each;
7. scBOLT selects the best successful candidate deterministically by stage
   objective and then by candidate index;
8. the selected candidate and its best witness become the current domain and
   witness for the next wave;
9. expansion waves continue while another strict subdomain can be tested;
10. when the next expansion would be the complete domain, the portfolio stops
    and one final Clingo instance resumes optimization using
    `JOBS_CLINGO_<STAGE>`.

For example, a witness retaining 230 nodes in a 250-node domain can warm-start
several alternative 380-node domains. Every 380-node candidate contains the
same initial 250 nodes, while their 130 additional nodes differ. The selected
380-node domain and its best witness then form the common base of the next
expansion wave. Across waves, selected domains are therefore nested; within one
wave, sibling candidates are not nested relative to each other. This gradual
and diversified expansion avoids both reintroducing the original
complete-domain bottleneck immediately and committing permanently to the node
order that produced the first witness.

The two job controls are not nested:

```make
JOBS_DOMAIN_CONTINUATION_SEED = 8
JOBS_CLINGO_SEED = 4
```

This configuration means that every acquisition or expansion wave evaluates
up to eight candidate domains simultaneously, each with one Clingo job. Once
the complete domain is reached, the candidate portfolio stops and one final
optimization instance uses four jobs. The maximum concurrent job count is
therefore the maximum of the two values, not their product.

### Special Cases

The combined domain and clause transition policy is:

- **Complete domain `UNSAT`:** the current clause bound is genuinely
  insufficient. Advance immediately from `q` to `q+1`, then restart domain
  continuation at the new clause bound.
- **Complete domain `UNKNOWN` without a witness:** the complete-domain search
  is a computational bottleneck. Continue searching smaller or compositionally
  different domains at the same clause bound.
- **Expansion wave without a successful candidate:** retain the last successful
  witness and domain, then reduce the expansion step or generate a new wave
  with different additional nodes. Individual `UNKNOWN` candidates do not
  block successful siblings.
- **Minimal domain `UNKNOWN`:** try another deterministic branch or Clingo
  configuration. If all minimal-domain alternatives remain unknown, the
  clause-continuation patience eventually advances to the next clause bound.
  At `MAX_CLAUSE`, only the stage timeout or user interruption can end the
  unresolved search.
- **Witness found:** stop the competing first-witness workers and begin
  parallel witness-guided expansion waves toward the complete domain.
- **Complete domain `UNSAT` at `MAX_CLAUSE`:** no solution exists for the
  complete problem represented by the current constraint set and regulatory
  domain.

If no witness is found at `q=1`, domain continuation can therefore be restarted
at `q=2`. If a witness is found, domain continuation can continue at the same
clause bound by expanding its domain progressively. It is therefore neither
restricted permanently to the first clause bound nor limited to first-witness
acquisition.

Domain continuation supports the `SOFT`, `RELAXED`, and `SEED` node-selection
stages. It does not apply to the `CONSTS` stage. It is intentionally unavailable
for `LOCK`, which receives the seed witness, forces its selected nodes to remain
mandatory, and starts directly on the complete retained domain. If no seed
witness exists, the lock stage cannot provide a meaningful fallback.

Domain and clause continuation are independent. With clause continuation
disabled, domain continuation operates directly at `MAX_CLAUSE`. With domain
continuation disabled, each enabled clause bound is solved on the complete
domain. When both are enabled, witness acquisition and expansion operate within
each clause bound as needed.

## Combined Control Flow

For one node-selection stage without an initial witness, the intended control
flow is:

```text
for q in 1..MAX_CLAUSE:
    while no witness exists:
        evaluate candidate domains in parallel

        SAT:
            retain one deterministic witness
            stop competing portfolio workers
            retain the successful domain

        UNSAT on a subdomain:
            enlarge that branch

        UNKNOWN on a subdomain:
            reduce or diversify that branch

        UNSAT on the complete domain:
            continue with q+1

    while the next expansion remains a proper subdomain of the complete domain:
        construct a wave of equally sized candidate supersets
        inject the current witness into every candidate
        evaluate candidates in parallel with one Clingo job each

        one or more successful candidates:
            select the best candidate deterministically
            retain its domain and best witness

        no successful candidate:
            preserve the previous witness
            reduce the expansion step or diversify added nodes

    optimize the complete domain at q using the best witness and
    JOBS_CLINGO_<STAGE>

    if the theoretical maximum objective is reached:
        stop

    if q < MAX_CLAUSE:
        continue with q+1
```

Constraint relaxation surrounds this control flow: each selection module uses
its own active constraint set and passes a reduced domain or structural witness
to the next module.

## Make Parameter Reference

`<STAGE>` denotes `SOFT`, `RELAXED`, `SEED`, or `LOCK`, except where a smaller
set is stated explicitly. The explicit parameter names below form the intended
interface of this design draft.

### Problem Definition

| Parameter | Meaning |
| --- | --- |
| `PRIOR_KNOWLEDGE` | Regulatory resource or custom influence graph defining the complete structural domain. |
| `MAX_CLAUSE` | Target maximum number of clauses allowed in each Boolean update function. |
| `CANONICAL_FILTER` | Whether gene-selection stages enforce canonical Boolean function representations. |
| `SEED` | Seed used to construct deterministic domain portfolios and resolve reproducible ordering choices. |

Resource-version parameters such as `GENEINFO_VERSION`, `OMNIPATH_VERSION`,
`HCOP_VERSION`, `DOROTHEA_API`, `DOROTHEA_COMPATIBILITY`, and
`DOROTHEA_LEVELS` also affect the complete domain when a built-in prior is
used. They define the problem itself rather than the solver strategy.

### Constraint Relaxation

| Parameter | Meaning |
| --- | --- |
| `MIN_SELF_LOOP_CONSTS` | Whether `max-consts-soft` additionally minimizes one-node feedbacks while optimizing strong constants. |
| `TIMEOUT_SOFT` | Total solver-runtime limit for the soft node-selection stage. |
| `TIMEOUT_CONSTS` | Total solver-runtime limit for strong-constant optimization. |
| `TIMEOUT_RELAXED` | Total solver-runtime limit after intermediate constraints are introduced. |
| `TIMEOUT_SEED` | Required bounded runtime for complete-constraint seed optimization. |
| `TIMEOUT_LOCK` | Total runtime for lock optimization; `0` skips solving and retains the seed solution directly. |

Each `TIMEOUT_*` value covers all solver attempts inside its stage. Its clock
starts when optimization begins and is not reset when the clause bound, domain,
branch, or Clingo instance changes.

### Clause Continuation

| Parameter | Meaning |
| --- | --- |
| `CLAUSE_CONTINUATION_<STAGE>` | Enable progressive clause bounds for the selected node-selection stage. |
| `PATIENCE_CLAUSE_CONTINUATION_<STAGE>` | Maximum time without an objective improvement at an intermediate clause bound. Disabled at `MAX_CLAUSE`. |

Clause continuation supports `SOFT`, `RELAXED`, `SEED`, and `LOCK`. An empty or
zero patience disables early advancement based on missing improvements.

### Domain Continuation

| Parameter | Meaning |
| --- | --- |
| `DOMAIN_CONTINUATION_<STAGE>` | Enable adaptive first-witness search and progressive witness-guided domain expansion. |
| `PATIENCE_DOMAIN_CONTINUATION_<STAGE>` | Maximum search time assigned to one candidate-domain attempt before its result becomes `UNKNOWN`. |
| `JOBS_DOMAIN_CONTINUATION_<STAGE>` | Maximum number of candidate domains evaluated simultaneously in any acquisition or expansion wave. Every candidate uses one Clingo job. |

Domain continuation supports only `SOFT`, `RELAXED`, and `SEED`. No
`DOMAIN_CONTINUATION_LOCK`, `PATIENCE_DOMAIN_CONTINUATION_LOCK`, or
`JOBS_DOMAIN_CONTINUATION_LOCK` parameter is defined.

### Clingo Optimization

| Parameter | Meaning |
| --- | --- |
| `CLINGO_CONFIG_<STAGE>` | Named Clingo configuration or custom configuration file used by the stage. |
| `CLINGO_OPT_MODE_<STAGE>` | Optimization handling mode: `opt` for anytime optimization, `optN` for optimum enumeration and certification, or `ignore` for satisfiability only. |
| `CLINGO_OPT_STRATEGY_<STAGE>` | Clingo optimization algorithm, such as branch-and-bound (`bb,*`) or unsatisfiable-core optimization (`usc,*`). |
| `JOBS_CLINGO_<STAGE>` | Number of Clingo jobs used by the final optimization instance on the complete domain. |

`JOBS_CLINGO_CONSTS` is the corresponding control for
`max-consts-soft`. Domain-continuation workers always use one Clingo job and do
not multiply `JOBS_CLINGO_<STAGE>` by
`JOBS_DOMAIN_CONTINUATION_<STAGE>`.

### Illustrative Seed Configuration

The following configuration illustrates the separation between the two
continuation strategies and their parallelism controls. The values are examples
for design discussion, not finalized defaults.

```make
DOMAIN_CONTINUATION_SEED = true
CLAUSE_CONTINUATION_SEED = true

PATIENCE_DOMAIN_CONTINUATION_SEED = 5m
PATIENCE_CLAUSE_CONTINUATION_SEED = 30m
TIMEOUT_SEED = 24h

JOBS_DOMAIN_CONTINUATION_SEED = 8
JOBS_CLINGO_SEED = 4

CLINGO_CONFIG_SEED =
CLINGO_OPT_MODE_SEED = opt
CLINGO_OPT_STRATEGY_SEED = bb,lin
```

At a clause bound without a witness, this configuration evaluates up to eight
candidate domains in parallel with one Clingo job each. One candidate becomes
`UNKNOWN` after five minutes without a witness or an `UNSAT` proof. Once a
witness exists, each expansion wave evaluates up to eight larger candidate
domains, again with one Clingo job each. The selected candidate becomes the
common base of the following wave. On the complete domain, one final instance
uses four Clingo jobs. Thirty minutes without an objective improvement advances
an intermediate clause bound, while the 24-hour timeout is shared by the
complete seed stage.

## Time Budgets and Partial Results

Three time controls have distinct meanings:

1. `PATIENCE_DOMAIN_CONTINUATION_<STAGE>` bounds one candidate-domain attempt,
   either during first-witness acquisition or witness-guided expansion.
   Expiration produces `UNKNOWN` for that attempt. Any witness retained from a
   previous successful domain remains available as a partial solution.
2. `PATIENCE_CLAUSE_CONTINUATION_<STAGE>` bounds the time without objective
   improvement across all attempts at one intermediate clause bound. Every
   improvement resets this clause-level patience.
3. `TIMEOUT_<STAGE>` bounds the complete solver execution of the stage and is
   never reset.

Whenever a witness exists, scBOLT writes the best retained node set and its
structural witness as intermediate outputs. A timeout or user interruption may
therefore preserve a partial solution. Metadata must record whether the result
is partial or globally optimal, its node coverage, the effective elapsed time,
and the solver parameters that produced it.

When no witness has ever been found, neither patience expiration nor timeout
may fabricate a partial solution. The correct result remains `UNKNOWN`.
