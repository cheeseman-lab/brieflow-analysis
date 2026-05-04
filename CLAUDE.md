# CLAUDE.md

Instructions for Claude Code when working in this repository.

## Project

**brieflow-analysis** (Test/Dev) — Parameter-free template repo for the Brieflow OPS pipeline. This is the development and testing environment; production screens live in `/lab/ops_analysis_ssd/cheeseman/*-analysis/`.

## Two-Tier System

This repo is the **development tier**. Changes flow:
1. Develop and test here (safe — no real screen data)
2. PR to main
3. Pull tested changes into production screen repos

For porting changes FROM production screens back here, use the `brieflow-dev` skill. The key challenge: production notebooks have parameters baked in, this repo's notebooks are parameter-free templates.

## Current Focus

**Branch**: `zarr3-transition` — Active Zarr3 data format migration.

## Development

```bash
eval "$(conda shell.bash hook)" && conda activate brieflow
```

## Code Structure

```
brieflow-analysis/
├── analysis/                    # Run scripts and config notebooks
│   ├── *.ipynb                  # Parameter configuration notebooks (TEMPLATE — no params)
│   ├── *.sh                     # SLURM run scripts
│   ├── config/                  # Pipeline configuration
│   └── slurm/                   # SLURM resource config + output
├── brieflow/                    # Git submodule — core pipeline code
│   ├── workflow/
│   │   ├── lib/                 # Library functions (edit first)
│   │   ├── scripts/             # Scripts calling lib
│   │   ├── rules/               # Snakemake rules (*.smk)
│   │   └── targets/             # Output definitions
│   └── pyproject.toml
└── notebooks/                   # Analysis notebooks
```

## Git Workflow

**CRITICAL**: Create branches in BOTH repos with the same name:
```bash
git checkout -b feature-name
cd brieflow/ && git checkout -b feature-name
```

Never push directly to `main`. Always PR.

Edit order in submodule: `lib/` → `scripts/` → `rules/` → `targets/`

## Code Style (submodule)

```bash
cd brieflow/ && ruff format workflow/ && ruff check workflow/
```

## Testing

```bash
cd brieflow/tests/small_test_analysis/
# Run relevant pipeline modules before PRing
```

## Resources

- Docs: https://brieflow.readthedocs.io/
- Issues: https://github.com/cheeseman-lab/brieflow/issues
