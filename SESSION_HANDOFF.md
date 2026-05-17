# Session handoff — Stage 2 (Baker E2E) starting point

**You are a fresh Claude Code session picking up an autonomous-plugin sprint.**
The previous session closed Stage 1 (gens + wizard + CSV taxonomy + plugin
chain refactor). Your job: drive the marimo notebooks via the wizard, one at
a time, to confirm each works end-to-end against the plugin — then we can
do an interleaved full-pipeline run (Stage 2).

## TL;DR your task

1. Drive `brieflow_wizard.py` to build a fresh `analysis/.brieflow/screen_manifest.yaml` for the baker screen
2. Run each marimo gen (`0_preprocess.py`, `2_sbs.py`, `3_phenotype.py`, `5_merge.py`, `8_aggregate.py`, `10_cluster.py`) — verify each emits valid verbose-JSON GenResult
3. Each gen that needs upstream pipeline output (phenotype `estimate_diameters`, merge alignment cross-correlation, etc.) reads from `analysis/brieflow_output/` (preserved from a prior full baker run — 2.4 TB on disk)
4. Report which gens work as-is and which need fixes
5. **Do not** look at `/lab/ops_analysis_ssd/test_matteo/baker_first_run_archive/` — that's the previous-run reference for diff-validation, not a hint about expected values

## What the previous session built

Stage 1 ✅ complete:

- **6 marimo gens** at `analysis/{0_preprocess,2_sbs,3_phenotype,5_merge,8_aggregate,10_cluster}.py` — dual-mode (interactive `marimo edit` + headless `python file.py --manifest X --output-dir Y --verbose-json`). Hand-converted from the canonical `.ipynb` files. Each is a thin wrapper around brieflow's lib functions; no reimplementation.
- **CSV parameter taxonomy** at `/lab/barcheese01/mdiberna/brieflow-ops/plugins/brieflow-ops/data/config_parameter_buckets.csv` — 239 rows, 5 buckets (auto/tuned/user/override/auto_probe), 7 cols including `written_to_config` (yes/no/conditional). The source of truth for what to ask the operator vs. derive vs. flag for review. Stage 1c reclassifications already applied based on 17 production-config variance analysis.
- **Wizard library** at `/lab/barcheese01/mdiberna/brieflow-ops/plugins/brieflow-ops/scripts/brieflow_wizard.py` — load CSV → ordered user-bucket prompts, gate conditional rows, validate answers, assemble + persist manifest.
- **Wizard skill** at `/lab/barcheese01/mdiberna/brieflow-ops/plugins/brieflow-ops/skills/brieflow-ops/references/wizard_workflow.md` — the agent-facing protocol for driving the wizard.
- **Plugin chain** at `/lab/barcheese01/mdiberna/brieflow-ops/plugins/brieflow-ops/scripts/brieflow_run_screen.py` — subprocesses each gen directly in dependency order; merges per-step JSON into final `config.yml`; handles review-required loops.

## What's on disk and what isn't

Inside `analysis/`:

| Present | Purpose |
|---|---|
| `0_preprocess.py` ... `10_cluster.py` (6 gens) + `_gen_common.py` | The marimo gen layer |
| `0.configure_*.ipynb` ... `12.analyze.ipynb` (7 notebooks) | Canonical source-of-truth notebooks (gens hand-converted from these) |
| `MARIMO.md` | Docs for the marimo gen design |
| `screen.yaml` | Screen metadata (identifies this as baker — 9 SBS cycles × 1 plate × 6 wells, channels DAPI/CENPA/COXIV/WGA) |
| `flow.sh` | Pipeline launcher (calls snakemake via plugin's resolver) |
| `slurm/` (config.yaml + mem_recommendations.json) | Slurm profile + canonical per-rule memory caps from prior baker run |
| `cluster_optimization/` (harness.py + results/baker_*.csv) | Memory/scaling bootstrap data from prior baker run |
| `brieflow_output/` (2.4 TB) | **Intermediate outputs from a prior full baker run** — kept so each gen can be tested against real upstream pipeline output |
| `status.sh` | Operator status check |

NOT present (intentional):

| Absent | Why | Where it went |
|---|---|---|
| `analysis/config/` | Operator-supplied values would bias the new session | Zipped to `/lab/ops_analysis_ssd/test_matteo/baker_first_run_archive/config_baker_first_run_2026-05-16.zip` for reference-only; DO NOT OPEN |
| `analysis/.brieflow/screen_manifest.yaml` | You need to build a fresh one | Wizard creates it |
| `analysis/brieflow_output_tile/`, `_well/` | Tile/well-tier benchmark artifacts, unrelated to baker E2E | Deleted |
| `analysis/.snakemake/`, `.brieflow*/` | Runtime caches; regenerated per run | Deleted |

## The interleaved-flow design (what Stage 2 ultimately tests)

In the autonomous-plugin design, the plugin alternates gen ↔ pipeline phase
so each notebook reads real upstream output for auto-derivation:

```
0_preprocess.py     → flow.sh preprocess      → produces aligned tiffs, ic_fields, metadata parquets
2_sbs.py + 3_phenotype.py → flow.sh sbs phenotype → produces sbs_info, phenotype_info parquets, cells masks
5_merge.py          → flow.sh merge           → produces merge_final parquets
8_aggregate.py      → flow.sh aggregate       → produces aggregated cell data
10_cluster.py       → flow.sh cluster         → produces clustering output
```

For Stage 2's first cut, **the pipeline outputs ALREADY EXIST** at
`analysis/brieflow_output/` from a prior baker run. So each gen can be run
in isolation against existing upstream output — no need to actually trigger
flow.sh until you've validated each gen works.

**Your job is the second part of that** — get to a state where each gen
runs cleanly given a manifest + existing pipeline output. The full
interleaved run (gen → flow.sh → gen → flow.sh) comes after.

## Suggested workflow

### Step 1: Drive the wizard to build a manifest

Read `skills/brieflow-ops/references/wizard_workflow.md` (in the plugin) for
the agent-facing protocol. The skill tells you how to:
- Load `data/config_parameter_buckets.csv` via `brieflow_wizard.py`
- Walk sections in order (library → paths → channels → ... → cluster)
- Auto-probe data dirs when given paths (sample filenames → propose regex; extract channel names; etc.)
- Ask the operator for biological labels + channel-role mappings
- Skip conditional rows (multi-mode barcode, stardist, etc.) based on earlier answers
- Save to `analysis/.brieflow/screen_manifest.yaml`

For baker: source data is at `/archive/cheeseman/ops_data/baker/input_sbs/`
and `/archive/cheeseman/ops_data/baker/input_ph/`. `screen.yaml` has the
high-level structural info. **Ask the operator everything you can't infer.**

### Step 2: Run each gen one at a time

```bash
eval "$(conda shell.bash hook)" && conda activate brieflow_speed
cd analysis
mkdir -p .cache/handoff_test  # output dir
python 0_preprocess.py --manifest .brieflow/screen_manifest.yaml \
    --output-dir .cache/handoff_test --verbose-json
```

Check the GenResult JSON: status, review_required, outputs, metrics. Verify
the TSVs got written. If the gen fails, that's a bug to fix.

Then `2_sbs.py`, then `3_phenotype.py`, etc. The first few (preprocess, sbs)
mostly auto-derive from manifest + file scan. Later ones (phenotype, merge)
will need to read from `analysis/brieflow_output/` — make sure the manifest's
paths point at those existing outputs.

### Step 3: Report back

Tell the operator:
- Which gens work as-is
- Which had issues (and what fixes)
- Whether the wizard's question flow felt right or needs adjustment
- Anything in the CSV taxonomy that needs updating based on what you saw

### Step 4 (later, after operator approves): full interleaved run

Once each gen is validated, trigger `brieflow-run-screen baker` (or the
equivalent invocation) for the actual end-to-end test. This will overwrite
`analysis/brieflow_output/` with a new run — at that point we can delete
the preserved 2.4 TB.

## Pointers

- Plugin repo: `/lab/barcheese01/mdiberna/brieflow-ops/`
- This repo: `/lab/ops_analysis_ssd/test_matteo/brieflow-speed/`
- Source data: `/archive/cheeseman/ops_data/baker/input_{sbs,ph}/`
- Prior-run reference (DO NOT OPEN — for diff-validation only): `/lab/ops_analysis_ssd/test_matteo/baker_first_run_archive/`
- Conda env: `brieflow_speed` (activate with `eval "$(conda shell.bash hook)" && conda activate brieflow_speed`)
- Read `CLAUDE.md` at this repo's root for the standing project rules
- Read `analysis/MARIMO.md` for the gen-layer design
- Read the plugin's `skills/brieflow-ops/SKILL.md` + `references/wizard_workflow.md`

## After you finish this

Delete this `SESSION_HANDOFF.md` as part of your closing commit. It's only
useful at the moment of handoff.
