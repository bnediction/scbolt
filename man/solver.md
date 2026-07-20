# Solver Strategies

**Status:** domain continuation is implemented experimentally. This document
describes its current contract and rationale, but transition policies may still
be adjusted after validation on larger case studies.

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

Within one acquisition wave, all candidates have the same size and contain the
required nodes:

```text
required nodes <= Di <= G
```

Different candidates use different deterministic node orders and therefore
test alternative compositions at that size. An `UNSAT` result applies only to
the exact candidate that was solved. When every candidate in a wave is
`UNSAT`, scBOLT increases the target size and generates another deterministic
wave; this is a scheduling decision, not a proof that every domain of the
smaller size is unsatisfiable.

Before the first witness is found, domain size is adapted according to the
solver outcome rather than following a fixed increasing schedule:

| Outcome | Domain-continuation action |
| --- | --- |
| `SAT` | Make the first successful candidate the wave leader, continue the portfolio while its best objective improves, then retain the best candidate for witness-guided expansion. |
| `UNSAT` | Increase the domain because the tested subdomain lacks a satisfiable structure. |
| `UNKNOWN` | Reduce or change the domain because the current search encountered a computational bottleneck. |

The largest size at which a complete tested wave is `UNSAT` forms a scheduling
lower bound. The smallest size returning `UNKNOWN` forms a heuristic upper
bound on tractable search size. A subsequent wave is chosen between these
bounds. Neither size is a logical statement about untested domain
compositions, and solver runtime is not guaranteed to vary monotonically with
domain size.

The first acquisition wave starts halfway between the required-node domain and
the complete domain. A wave containing only `UNSAT` candidates moves the next
target halfway toward the complete domain. A wave containing `UNKNOWN`
candidates moves the target halfway toward the remaining smaller interval.
When no interior size remains, scBOLT changes deterministic candidate
compositions at the same boundary until clause patience or the stage timeout
decides the transition.

Portfolio workers use one Clingo job each. Finding the first satisfiable
witness does not terminate the acquisition wave. The first witness becomes the
wave leader, and the remaining workers continue searching for a better
objective until the shared wave patience expires or every worker finishes.

Every acquisition and expansion wave owns one shared patience clock. The clock
starts when all candidate instances are launched. The first valid witness in
the new candidate domains becomes the leader and resets the clock. A later
witness resets it only when its lexicographic objective
`(important nodes, total nodes)` is strictly better than the current leader's
objective. A worker improving its own solution without overtaking the leader
does not reset the clock, and an objective equal to the leader does not reset
it either. This prevents staggered but equivalent results from extending a
wave without improving its retained solution.

When the shared patience expires, all unresolved workers are interrupted.
Candidates that already produced a witness remain `SAT`; interrupted
candidates without a witness become `UNKNOWN`. scBOLT then selects the best
successful candidate deterministically by objective value and candidate index.
The patience clock is newly initialized for every wave.

After a witness is selected:

1. the best successful candidate domain becomes the current domain;
2. scBOLT constructs a wave of larger candidate domains of the same size;
3. every candidate contains the complete current domain but differs in the
   additional nodes selected by its deterministic ordering;
4. the current witness is injected into every candidate as a soft heuristic;
5. the candidates are evaluated in parallel, using one Clingo job each and the
   same leader-based wave patience as during acquisition;
6. scBOLT selects the best successful candidate deterministically by stage
   objective and then by candidate index;
7. the selected candidate and its best witness become the current domain and
   witness for the next wave;
8. expansion waves continue while another strict subdomain can be tested;
9. when the next expansion would be the complete domain, the portfolio stops
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

Expansion sizes also use midpoints. After retaining a domain `D`, the next
target lies halfway between `D` and `G`. If a complete expansion wave produces
no successful candidate, scBOLT halves the expansion step and generates new
candidate compositions while preserving `D` and its witness.

The two job controls are not nested:

```make
JOBS = 8
JOBS_CLINGO_SEED = 1
```

`JOBS` controls the number of candidate domains evaluated simultaneously in
every acquisition or expansion wave, with one Clingo job per candidate. Once
the complete domain is reached, the candidate portfolio stops and one final
optimization instance uses `JOBS_CLINGO_<STAGE>`. The maximum concurrent job
count is therefore the maximum of the two values, not their product.

Each candidate owns an independent BoNesis problem and Clingo control. The
patience clock and leader objective belong to the coordinating wave, not to an
individual candidate. Portable Python worker threads coordinate these controls
on Linux and macOS; the Clingo solves themselves execute outside the Python
GIL. Only the coordinator writes outputs and renders progress. An interactive
terminal displays one reusable progress line per active candidate, whereas log
files retain only completed wave summaries and solver outcomes.

Expansion progress starts from the objective of the inherited witness for
every candidate. Although each Clingo control must reconstruct a model on its
larger domain, scBOLT does not display a regression below the solution already
retained by the continuation algorithm. Candidate progress therefore reports
the best inherited or locally improved objective, rather than restarting
visually from zero.

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
- **Minimal domain `UNKNOWN`:** try another deterministic candidate
  composition when alternatives exist. If the minimal domain is fixed by the
  required nodes, repeat attempts remain bounded by clause patience. At
  `MAX_CLAUSE`, only the stage timeout or user interruption can end the
  unresolved search.
- **Witness found:** make the first witness the wave leader, continue until the
  shared wave patience expires without a strict portfolio improvement, then
  use the selected leader for expansion toward the complete domain.
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

It is enabled by default for `SEED` and disabled by default for `SOFT` and
`RELAXED` while the strategy remains under experimental validation.

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

        first SAT:
            set the wave leader
            reset shared wave patience

        strictly better (important nodes, total nodes):
            replace the wave leader
            reset shared wave patience

        equal or locally improved but globally inferior objective:
            do not reset shared wave patience

        shared wave patience expires:
            interrupt unresolved workers
            retain the best successful domain and witness

        UNSAT across the candidate wave:
            increase the target size and generate another wave

        UNKNOWN in the candidate wave:
            reduce the target size or diversify candidate composition

        UNSAT on the complete domain:
            continue with q+1

    while the next expansion remains a proper subdomain of the complete domain:
        construct a wave of equally sized candidate supersets
        inject the current witness into every candidate
        evaluate candidates in parallel with one Clingo job each

        first SAT or strict portfolio improvement:
            update the wave leader
            reset shared wave patience

        one or more successful candidates:
            after wave completion, select the best candidate deterministically
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
set is stated explicitly. The explicit parameter names below form the current
solver interface.

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
| `PATIENCE_DOMAIN_CONTINUATION_<STAGE>` | Maximum time without a strict improvement of the best portfolio objective within one acquisition or expansion wave. |

Domain continuation supports only `SOFT`, `RELAXED`, and `SEED`. No
`DOMAIN_CONTINUATION_LOCK` or `PATIENCE_DOMAIN_CONTINUATION_LOCK` parameter is
defined. The global `JOBS` parameter controls the number of candidate domains
evaluated simultaneously, and every candidate uses one Clingo job.

### Clingo Optimization

| Parameter | Meaning |
| --- | --- |
| `CLINGO_CONFIG_<STAGE>` | Named Clingo configuration or custom configuration file used by the stage. |
| `CLINGO_OPT_MODE_<STAGE>` | Optimization handling mode: `opt` for anytime optimization, `optN` for optimum enumeration and certification, or `ignore` to disable optimization objectives and accept a satisfiable model. |
| `CLINGO_OPT_STRATEGY_<STAGE>` | Clingo optimization algorithm, such as branch-and-bound (`bb,*`) or unsatisfiable-core optimization (`usc,*`). |
| `JOBS_CLINGO_<STAGE>` | Number of Clingo jobs used by the final optimization instance on the complete domain. |

`JOBS_CLINGO_CONSTS` is the corresponding control for
`max-consts-soft`. Domain-continuation workers always use one Clingo job and do
not multiply `JOBS_CLINGO_<STAGE>` by `JOBS`.

### Illustrative Seed Configuration

The following configuration shows the default seed strategy.

```make
DOMAIN_CONTINUATION_SEED = true
CLAUSE_CONTINUATION_SEED = true

PATIENCE_DOMAIN_CONTINUATION_SEED = 5m
PATIENCE_CLAUSE_CONTINUATION_SEED = 30m
TIMEOUT_SEED = 24h

JOBS = 8
JOBS_CLINGO_SEED = 1

CLINGO_CONFIG_SEED =
CLINGO_OPT_MODE_SEED = opt
CLINGO_OPT_STRATEGY_SEED = bb,lin
```

At a clause bound without a witness, this configuration evaluates up to eight
candidate domains in parallel with one Clingo job each. The first witness
becomes the wave leader, and each strict improvement of the best portfolio
objective restarts the shared five-minute patience. Once that patience expires,
unresolved candidates become `UNKNOWN` and the best successful candidate
becomes the common base of the following expansion wave. Expansion waves apply
the same rule to larger candidate domains. On the complete domain, one final
instance uses one Clingo job. Thirty minutes without an objective improvement
advances an intermediate clause bound, while the 24-hour timeout is shared by
the complete seed stage.

## Time Budgets and Partial Results

Three time controls have distinct meanings:

1. `PATIENCE_DOMAIN_CONTINUATION_<STAGE>` bounds stagnation of the best
   portfolio objective within one acquisition or expansion wave. Its clock is
   reset by the first wave witness and every strict leader improvement, but not
   by equal or globally inferior results. Expiration interrupts all unresolved
   workers; workers without a witness become `UNKNOWN`, while successful
   candidates remain eligible for deterministic selection.
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
