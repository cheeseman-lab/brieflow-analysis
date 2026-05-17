# analysis/ marimo notebooks — dual-mode config generation

Hand-converted marimo notebooks that produce brieflow `config.yml` sections.
Each notebook runs **two ways from the same file**:

1. **Interactive** (`marimo edit N_<phase>.py`) — operator opens the notebook,
   reactive cell UI, plots render inline. Use for new screens, debugging, or
   visual confirmation of tuned params.
2. **Headless** (`python N_<phase>.py --manifest X --output-dir Y --verbose-json`)
   — plugin invokes as subprocess. Emits a single JSON object on stdout
   matching `_gen_common.GenResult`. No marimo UI overhead.

Mode is detected via `mo.running_in_notebook()` inside the file. The output
contract is identical to what the brieflow-auto plugin's orchestrator and
email-ping review flow consume.

Source-of-truth for every notebook's logic: the sibling `.ipynb` files in
`analysis/*.configure_*.ipynb`. These marimo files are line-for-line manual
conversions (auto-conversion produced botched ports — see git history). The
`.ipynb` files remain for now and will be retired once the marimo path is
proven across multiple screens.

## Files

| File | Source `.ipynb` | Tuned params (review_required) |
|---|---|---|
| `0_preprocess.py` | 0.configure_preprocess_params.ipynb | 0 (deterministic geometry) |
| `2_sbs.py` | 2.configure_sbs_params.ipynb | 9 (cell/nuclei diameter, threshold_peaks, call_reads_method, q_min, max_filter_width, peak_width, upsample_factor, window) |
| `3_phenotype.py` | 3.configure_phenotype_params.ipynb | 5 (cell/nuclei diameter, source, target, align) |
| `5_merge.py` | 5.configure_merge_params.ipynb | 4 (det_range, initial_sites, score, threshold) |
| `7_classify.py` | 7.configure_classify_params.ipynb (v1 skip — manifest.classifier.enabled=false default) | — |
| `8_aggregate.py` | 8.configure_aggregate_params.ipynb | 2 (channel_combos, variance_or_ncomp) |
| `10_cluster.py` | 10.configure_cluster_params.ipynb | 2 (min_cell_cutoffs, leiden_resolutions) |
| `_gen_common.py` | — | Shared `GenResult` dataclass + `emit()` / `load_manifest()` helpers |
| `screen_manifest_baker.yaml` | — | Baker reference manifest (reverse-engineered from `config/config.yml`) |

Chaining the gens in dependency order, capturing JSON, merging into a final
`config.yml`, and pausing on `review_required` is the **plugin**'s job (lives
at `/lab/barcheese01/mdiberna/brieflow-ops/plugins/brieflow-ops/scripts/brieflow_run_screen.py`).
The gens here are self-contained building blocks; they don't ship a runner.

## Verbose-JSON contract

Each gen emits exactly one JSON object on stdout (when headless):

```json
{
  "status": "success" | "needs_review" | "failed",
  "outputs": {"<config-section>": {...}},
  "metrics": {"n_tiles": ..., "..."},
  "visualizations": [{"path": "/path/to/viz.png", "caption": "..."}],
  "review_required": bool,
  "review_prompt": "..."
}
```

Exit code is always 0 (failure semantics in `status` field; non-zero exit means
the script crashed unexpectedly).

## Architecture: gen as thin wrapper, not reimplementation

Each gen is **a thin plumber** over brieflow's canonical functions. For example,
`0_preprocess.py` does no file scanning of its own — it calls
`lib.shared.configuration_utils.create_samples_df` and
`lib.preprocess.file_utils.get_tile_count_from_well`, which are the same
functions the `.ipynb` calls. Auto-derivation (tile counts, cellpose diameter,
cross-correlation alignment) lives in brieflow's library and is invoked
identically from both the `.ipynb` (operator-interactive) and the marimo
gen file (manifest-driven). No drift between paths.

## Writing rules (marimo cell hygiene)

Marimo enforces **no cross-cell variable redefinition**. Common gotchas:

- Import once at the top in an `imports` cell, return everything; downstream
  cells consume via function-argument fan-out.
- Local helpers / loop variables that don't escape the cell: prefix with `_`
  (e.g. `_p`, `_msg`, `_row`). Marimo ignores `_`-prefixed names for cross-cell
  uniqueness.
- The cell's `return (foo,)` defines what variable name downstream cells see.
  If you want cell `Y(foo)` to receive `foo` from cell `X`, X must literally
  `return (foo,)` — naming a local `bar` and returning `(bar,)` won't work.

## Output paths

Each gen always writes to `--output-dir` (a CLI flag). Manifest's `*_fp` fields
are **advisory hints recorded in the config section**, not write targets — this
keeps autonomous-generated outputs cleanly separable from operator-curated
config under `config/`.

## Validation: baker side-by-side

Rather than maintain dedicated test files, validation lives as a tracked
side-by-side directory:

- `config/config.yml`, `config/sbs_combo.tsv`, etc. = baker's hand-tuned
  ground truth (what the production pipeline actually ran with).
- `config/marimo/config.yml`, `config/marimo/sbs_combo.tsv`, etc. =
  marimo-generated equivalents from `screen_manifest_baker.yaml`.

Diff the two to see exactly where the autonomous path diverges from hand-tuned:

```bash
diff analysis/config/config.yml analysis/config/marimo/config.yml
```

`config/marimo/` is regenerated by the plugin when it runs the gens against a
manifest — for ad-hoc baker re-validation, the plugin (or any subprocess
chaining the 6 N_<phase>.py files in dependency order) reproduces it.

Currently:
- All TSVs (sbs_samples, sbs_combo, phenotype_samples, phenotype_combo,
  merge_combo, aggregate_combo, cluster_combo) are **byte-identical**.
- `cell_data_metadata_cols.tsv` differs (52 vs 41 entries) because brieflow's
  `DEFAULT_METADATA_COLS` moved since baker was tuned.
- `config.yml` is leaner (marimo omits: header comment, `all.image_format: zarr`,
  rich `sbs/phenotype_channels_metadata` blocks). These belong in the manifest
  / wizard layer, not in the preprocess gen — see Stage 1b in the plugin
  roadmap.

This diff-driven validation **is** the gen test suite. No separate smoke
test files needed.

## Manifest

`screen_manifest_baker.yaml` is the baker reference manifest, reverse-engineered
from baker's hand-tuned `config/config.yml`. Stage 1b (wizard expansion) will
produce equivalent manifests for new screens via interactive Q&A.

## Long-term migration

These files eventually move to the brieflow submodule so every analysis dir
consumes them without sprint-specific copies. For now, brieflow-speed carries
the canonical version while the patterns settle. Orchestration touchpoints
(plugin's `brieflow_run_screen.py`, `orchestrate.py`) are stable across that
move.
