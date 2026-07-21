#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tmpdir="$(mktemp -d)"

trap 'rm -rf "${tmpdir}"' EXIT

run_helper() {
    local outfile="$1"
    shift

    make -s -C "${repo_root}" -f - "$@" > "${outfile}" <<'MAKE'
diagnostic_mode = true
include mk/default_params.mk
include mk/modules.mk

.PHONY: all
all:
	@printf '%s\n' \
		'soft=$(call clause_continuation,CLAUSE_CONTINUATION_SOFT)' \
		'soft_patience=$(PATIENCE_CLAUSE_BOUND_SOFT)' \
		'soft_mode=$(CLINGO_OPT_MODE_SOFT)' \
		'soft_strategy=$(CLINGO_OPT_STRATEGY_SOFT)' \
		'relaxed=$(call clause_continuation,CLAUSE_CONTINUATION_RELAXED)' \
		'relaxed_patience=$(PATIENCE_CLAUSE_BOUND_RELAXED)' \
		'relaxed_mode=$(CLINGO_OPT_MODE_RELAXED)' \
		'relaxed_strategy=$(CLINGO_OPT_STRATEGY_RELAXED)' \
		'seed=$(call clause_continuation,CLAUSE_CONTINUATION_SEED)' \
		'seed_patience=$(PATIENCE_CLAUSE_BOUND_SEED)' \
		'seed_mode=$(CLINGO_OPT_MODE_SEED)' \
		'seed_strategy=$(CLINGO_OPT_STRATEGY_SEED)' \
		'lock=$(call clause_continuation,CLAUSE_CONTINUATION_LOCK)'
	@printf '%s\n' \
		'lock_patience=$(PATIENCE_CLAUSE_BOUND_LOCK)' \
		'lock_mode=$(CLINGO_OPT_MODE_LOCK)' \
		'lock_strategy=$(CLINGO_OPT_STRATEGY_LOCK)' \
		'domain_soft=$(call domain_continuation,DOMAIN_CONTINUATION_SOFT)' \
		'domain_relaxed=$(call domain_continuation,DOMAIN_CONTINUATION_RELAXED)' \
		'domain_seed=$(call domain_continuation,DOMAIN_CONTINUATION_SEED)' \
		'domain_lock=$(call domain_continuation,DOMAIN_CONTINUATION_LOCK)'
MAKE
}

defaults="$(${repo_root}/bin/scbolt config --default --raw)"
grep -qx 'CLAUSE_CONTINUATION_SOFT=false' <<< "${defaults}"
grep -qx 'CLAUSE_CONTINUATION_RELAXED=true' <<< "${defaults}"
grep -qx 'CLAUSE_CONTINUATION_SEED=true' <<< "${defaults}"
grep -qx 'CLAUSE_CONTINUATION_LOCK=true' <<< "${defaults}"
grep -qx 'PATIENCE_CLAUSE_BOUND_SOFT=30m' <<< "${defaults}"
grep -qx 'PATIENCE_CLAUSE_BOUND_RELAXED=30m' <<< "${defaults}"
grep -qx 'PATIENCE_CLAUSE_BOUND_SEED=30m' <<< "${defaults}"
grep -qx 'PATIENCE_CLAUSE_BOUND_LOCK=30m' <<< "${defaults}"
grep -qx 'DOMAIN_CONTINUATION_SOFT=false' <<< "${defaults}"
grep -qx 'DOMAIN_CONTINUATION_RELAXED=false' <<< "${defaults}"
grep -qx 'DOMAIN_CONTINUATION_SEED=true' <<< "${defaults}"
grep -qx 'DOMAIN_CONTINUATION_LOCK=true' <<< "${defaults}"
grep -qx 'PATIENCE_DOMAIN_WAVE_SEED=5m' <<< "${defaults}"
grep -qx 'PATIENCE_DOMAIN_WAVE_LOCK=5m' <<< "${defaults}"
grep -qx 'MIN_DOMAIN_YIELD=0.10' <<< "${defaults}"
grep -qx 'JOBS_CLINGO_SEED=1' <<< "${defaults}"

run_helper "${tmpdir}/defaults.out"
grep -qx 'soft=' "${tmpdir}/defaults.out"
grep -qx 'soft_patience=30m' "${tmpdir}/defaults.out"
grep -qx 'soft_mode=optN' "${tmpdir}/defaults.out"
grep -qx 'soft_strategy=usc' "${tmpdir}/defaults.out"
grep -qx 'relaxed=--clause-continuation' "${tmpdir}/defaults.out"
grep -qx 'relaxed_patience=30m' "${tmpdir}/defaults.out"
grep -qx 'relaxed_mode=opt' "${tmpdir}/defaults.out"
grep -qx 'relaxed_strategy=bb,lin' "${tmpdir}/defaults.out"
grep -qx 'seed=--clause-continuation' "${tmpdir}/defaults.out"
grep -qx 'seed_patience=30m' "${tmpdir}/defaults.out"
grep -qx 'seed_mode=opt' "${tmpdir}/defaults.out"
grep -qx 'seed_strategy=bb,lin' "${tmpdir}/defaults.out"
grep -qx 'lock=--clause-continuation' "${tmpdir}/defaults.out"
grep -qx 'lock_patience=30m' "${tmpdir}/defaults.out"
grep -qx 'lock_mode=opt' "${tmpdir}/defaults.out"
grep -qx 'lock_strategy=bb,lin' "${tmpdir}/defaults.out"
grep -qx 'domain_soft=' "${tmpdir}/defaults.out"
grep -qx 'domain_relaxed=' "${tmpdir}/defaults.out"
grep -qx 'domain_seed=--domain-continuation' "${tmpdir}/defaults.out"
grep -qx 'domain_lock=--domain-continuation' "${tmpdir}/defaults.out"

run_helper "${tmpdir}/disabled.out" \
    CLAUSE_CONTINUATION_SOFT=false \
    CLAUSE_CONTINUATION_RELAXED=false \
    CLAUSE_CONTINUATION_SEED=false \
    CLAUSE_CONTINUATION_LOCK=false \
    DOMAIN_CONTINUATION_SEED=false \
    DOMAIN_CONTINUATION_LOCK=false
test "$(grep -c -- '--clause-continuation' "${tmpdir}/disabled.out" || true)" -eq 0
grep -qx 'soft_mode=optN' "${tmpdir}/disabled.out"
grep -qx 'soft_strategy=usc' "${tmpdir}/disabled.out"
grep -qx 'relaxed_mode=optN' "${tmpdir}/disabled.out"
grep -qx 'relaxed_strategy=usc' "${tmpdir}/disabled.out"
grep -qx 'seed_mode=opt' "${tmpdir}/disabled.out"
grep -qx 'seed_strategy=bb,inc' "${tmpdir}/disabled.out"
grep -qx 'lock_mode=opt' "${tmpdir}/disabled.out"
grep -qx 'lock_strategy=usc' "${tmpdir}/disabled.out"

run_helper "${tmpdir}/soft-enabled.out" CLAUSE_CONTINUATION_SOFT=true
grep -qx 'soft=--clause-continuation' "${tmpdir}/soft-enabled.out"
grep -qx 'soft_mode=opt' "${tmpdir}/soft-enabled.out"
grep -qx 'soft_strategy=bb,lin' "${tmpdir}/soft-enabled.out"

run_helper "${tmpdir}/overridden.out" \
    CLAUSE_CONTINUATION_RELAXED=true \
    CLINGO_OPT_MODE_RELAXED=optN \
    CLINGO_OPT_STRATEGY_RELAXED=usc
grep -qx 'relaxed_mode=optN' "${tmpdir}/overridden.out"
grep -qx 'relaxed_strategy=usc' "${tmpdir}/overridden.out"

for stage in SOFT RELAXED SEED LOCK; do
    grep -Fq \
        "\$(call clause_continuation,CLAUSE_CONTINUATION_${stage})" \
        "${repo_root}/Makefile"
    grep -Fq -- \
        "--clause-continuation-parameter CLAUSE_CONTINUATION_${stage}" \
        "${repo_root}/Makefile"
    grep -Fq -- \
        "--clause-bound-patience \"\$(PATIENCE_CLAUSE_BOUND_${stage})\"" \
        "${repo_root}/Makefile"
done

for stage in SOFT RELAXED SEED LOCK; do
    grep -Fq \
        "\$(call domain_continuation,DOMAIN_CONTINUATION_${stage})" \
        "${repo_root}/Makefile"
    grep -Fq -- \
        "--domain-wave-patience \"\$(PATIENCE_DOMAIN_WAVE_${stage})\"" \
        "${repo_root}/Makefile"
    grep -Fq -- \
        "--domain-continuation-jobs \$(JOBS)" \
        "${repo_root}/Makefile"
    grep -Fq -- \
        "--domain-continuation-seed \$(SEED)" \
        "${repo_root}/Makefile"
    grep -Fq -- \
        "--min-domain-yield \$(MIN_DOMAIN_YIELD)" \
        "${repo_root}/Makefile"
done

for stage in SOFT CONSTS RELAXED SEED LOCK; do
    grep -Fq -- \
        "--jobs \$(JOBS_CLINGO_${stage})" \
        "${repo_root}/Makefile"
done

grep -Fq -- \
    '$(if $(filter true,$(DOMAIN_CONTINUATION_LOCK)),--domain-continuation-expansion-only)' \
    "${repo_root}/Makefile"

seed_help="$(
    "${repo_root}/bin/scbolt" max-nodes-seed help \
        --params="${repo_root}/tests/fixtures/params.mk"
)"
grep -Fq 'PATIENCE_CLAUSE_BOUND_SEED' <<< "${seed_help}"
grep -Fq 'PATIENCE_DOMAIN_WAVE_SEED' <<< "${seed_help}"
grep -Fq 'DOMAIN_CONTINUATION_SEED' <<< "${seed_help}"
grep -Fq 'MIN_DOMAIN_YIELD' <<< "${seed_help}"
grep -Fq 'Low-yield expansions are refreshed at constant size' <<< "${seed_help}"
grep -Fq 'JOBS' <<< "${seed_help}"
grep -Fq 'Maximum time without a Clingo objective improvement' <<< "${seed_help}"
grep -Fq \
    'Maximum time without an improvement of the best portfolio objective' \
    <<< "${seed_help}"

lock_help="$(
    "${repo_root}/bin/scbolt" max-nodes-lock help \
        --params="${repo_root}/tests/fixtures/params.mk"
)"
grep -Fq 'PATIENCE_DOMAIN_WAVE_LOCK' <<< "${lock_help}"
grep -Fq 'DOMAIN_CONTINUATION_LOCK' <<< "${lock_help}"
grep -Fq 'MIN_DOMAIN_YIELD' <<< "${lock_help}"
grep -Fq \
    'Expand the retained SEED witness through candidate subdomains' \
    <<< "${lock_help}"
grep -Fq \
    'LOCK skips first-witness acquisition' \
    <<< "${lock_help}"
grep -Fq \
    '0.0 if is_target else args.clause_bound_patience' \
    "${repo_root}/scripts/infer/selection.py"
grep -Fq \
    '"{desc}: {n_fmt}it ({elapsed}{postfix})"' \
    "${repo_root}/scripts/infer/selection.py"
grep -Fq \
    'f"{stage_name} [{stage_index}/{len(bounds)}, "' \
    "${repo_root}/scripts/infer/selection.py"
grep -Fq \
    'f"max clauses={max_clause}]"' \
    "${repo_root}/scripts/infer/selection.py"
! grep -Fq 'q={max_clause}' \
    "${repo_root}/scripts/infer/selection.py"
! grep -Fq 'candidate_patience' \
    "${repo_root}/scripts/infer/selection.py"
! grep -Fq 'stop_on_first_witness' \
    "${repo_root}/scripts/infer/selection.py"
! grep -Fq 'f"selected=' \
    "${repo_root}/scripts/infer/selection.py"
grep -Fq \
    "f\"domain continuation [{', '.join(context)}]: \"" \
    "${repo_root}/scripts/infer/selection.py"
grep -Fq \
    "f\"{result} ({', '.join(outcomes)})\"" \
    "${repo_root}/scripts/infer/selection.py"
grep -Fq 'MAX_DOMAIN_REFRESH_WAVES = 5' \
    "${repo_root}/scripts/infer/_domain_continuation.py"
grep -Fq 'class InheritedObjectiveProgress(ptqdm):' \
    "${repo_root}/scripts/infer/selection.py"
grep -Fq 'retained["objective"],' \
    "${repo_root}/scripts/infer/selection.py"
grep -Fq \
    '"no objective improvement within the clause-bound patience "' \
    "${repo_root}/scripts/infer/selection.py"
grep -Fq \
    'f"[max clauses={max_clause}, "' \
    "${repo_root}/scripts/infer/selection.py"
grep -Fq 'f"{solution_summary}"' \
    "${repo_root}/scripts/infer/selection.py"
! grep -Fq 'models=' \
    "${repo_root}/scripts/infer/selection.py"
grep -Fq 'kwargs["leave"] = False' \
    "${repo_root}/scripts/infer/utils.py"
! grep -Fq 'leave_progress' \
    "${repo_root}/scripts/infer/utils.py"
! grep -Fq 'leave=is_target' \
    "${repo_root}/scripts/infer/selection.py"

! grep -Fq -- \
    "--initial-witness \$(dir \$(max_consts_soft))witness.lp" \
    "${repo_root}/Makefile"
! grep -Fq -- \
    "--initial-witness \$(dir \$(max_nodes_relaxed))witness.lp" \
    "${repo_root}/Makefile"
grep -Fq -- \
    "--initial-witness \$(lastword \$^)" \
    "${repo_root}/Makefile"
grep -Fq -- \
    "--initial-witness \$(max_nodes_lock_witness)" \
    "${repo_root}/Makefile"
grep -Fq 'canonicalize_structural_witness(witness)' \
    "${repo_root}/scripts/infer/infer.py"
grep -Fq \
    'args.domain_continuation_expansion_only and not initial_witness' \
    "${repo_root}/scripts/infer/selection.py"
grep -Fq \
    'expansion-only domain continuation requires an initial' \
    "${repo_root}/scripts/infer/selection.py"
grep -Fq -- \
    "\$(max_nodes_lock) \$(max_nodes_lock_witness) &: \$(bonesis_model)" \
    "${repo_root}/Makefile"
