# Brieflow Zarr3 — Undergrad Handoff Guide

**Cheeseman Lab | Whitehead Institute for Biomedical Research**

---

## Your Starting Point

### Branch Setup

Matteo has been working on the `zarr3-transition` branch in the brieflow submodule. You'll branch off of it:

```bash
cd /lab/ops_analysis_ssd/test_ege/brieflow-analysis/brieflow/
git fetch origin
git checkout zarr3-transition
git pull
git checkout -b metadata-enrichment    # your branch
```

### Repository Structure

Brieflow uses two repos:

1. **brieflow-analysis** (outer) — config, notebooks, run scripts, outputs
2. **brieflow/** (submodule) — the pipeline code

```
brieflow/workflow/
├── lib/        # 1. Library functions (edit first)
├── scripts/    # 2. Scripts that call lib functions
├── rules/      # 3. Snakemake rules
└── targets/    # 4. Output path definitions
```

Edit in order: **lib -> scripts -> rules -> targets**

### Test Data

The small test dataset lives at `brieflow/tests/small_test_analysis/`. Run the pipeline on it:

```bash
cd brieflow/tests/small_test_analysis/
eval "$(conda shell.bash hook)" && conda activate brieflow_SCREEN_NAME
bash run_brieflow_omezarr.sh      # zarr mode (your focus)
bash run_brieflow.sh              # tiff mode (for comparison)
```

Zarr mode produces **294/294 steps** (3 extra HCS finalize rules). TIFF mode produces **291/291 steps**. Both should exit with code 0.

---

## Pipeline Output Structure

### Zarr mode (HCS direct-write)

The pipeline writes zarr stores **directly** into HCS-compliant plate zarr directories. There is no separate `hcs/` or `images/` subdirectory — the plate zarr IS the output. A lightweight finalize step writes metadata-only `zarr.json` at plate/row/well levels.

#### SBS Module (`brieflow_output_zarr/sbs/`)

```
sbs/
├── 1.zarr/                                      # plate store (plate=1)
│   ├── zarr.json                                # HCS plate metadata (OME v0.5)
│   └── A/                                       # row
│       ├── zarr.json                            # row group metadata
│       ├── 1/                                   # col  (well = A1)
│       │   ├── zarr.json                        # well metadata (lists fields)
│       │   ├── 0/                               # tile (field of view)
│       │   │   ├── aligned.zarr/                #   multiscale image (levels 0..4)
│       │   │   ├── illumination_corrected.zarr/
│       │   │   ├── log_filtered.zarr/
│       │   │   ├── max_filtered.zarr/
│       │   │   ├── peaks.zarr/
│       │   │   ├── standard_deviation.zarr/
│       │   │   └── labels/
│       │   │       ├── zarr.json                # labels group metadata
│       │   │       ├── cells.zarr/
│       │   │       └── nuclei.zarr/
│       │   ├── 2/  ...                          # more tiles
│       │   └── 32/ ...
│       └── 2/                                   # col  (well = A2)
│           └── (same structure)
├── parquets/1/A/{1,2}/                          # plate/row/col/
│   ├── cells.parquet
│   ├── reads.parquet
│   └── sbs_info.parquet
├── tsvs/1/A/{1,2}/{0,2,32}/segmentation_stats.tsv
└── eval/{mapping,segmentation}/1/*.{png,tsv}
```

#### Phenotype Module (`brieflow_output_zarr/phenotype/`)

```
phenotype/
├── 1.zarr/                                      # plate store
│   └── A/{1,2}/                                 # row/col (wells)
│       └── {2,5,141}/                           # tiles
│           ├── aligned.zarr/
│           ├── illumination_corrected.zarr/
│           └── labels/
│               ├── cells.zarr/
│               ├── nuclei.zarr/
│               └── identified_cytoplasms.zarr/  # phenotype-only
├── parquets/1/A/{1,2}/{phenotype_cp,phenotype_cp_min,phenotype_info}.parquet
├── tsvs/1/A/{1,2}/{2,5,141}/segmentation_stats.tsv
└── eval/{features,segmentation}/1/*.*
```

#### Preprocess Module (`brieflow_output_zarr/preprocess/`)

```
preprocess/
├── sbs/1.zarr/A/{1,2}/{0,2,32}/{1..11}/image.zarr/   # per-cycle images
├── phenotype/1.zarr/A/{1,2}/{2,5,141}/image.zarr/     # single acquisition
├── ic_fields/{sbs,phenotype}/1/A/{1,2}/...             # IC field zarrs
└── metadata/{sbs,phenotype}/1/A/{1,2}/combined_metadata.parquet
```

### TIFF mode (flat naming, for comparison)

```
sbs/
├── images/P-1_W-A1_T-0__{nuclei,cells}.tiff     # P-{plate}_W-{well}_T-{tile}__{type}
├── parquets/P-1_W-A1__{cells,reads,sbs_info}.parquet
├── tsvs/P-1_W-A1_T-0__segmentation_stats.tsv
└── eval/{mapping,segmentation}/P-1__*.{png,tsv}
```

**Key difference:** Zarr replaces the flat `P-{plate}_W-{well}_T-{tile}__` naming with the HCS hierarchy `{plate}.zarr/{row}/{col}/{tile}/`.

---

## Your Goal: Metadata Enrichment

The pipeline writes valid OME-Zarr v3 stores, but the metadata is minimal (generic channel names, no physical units, no contrast limits). Your job is to enrich the zarr metadata so that tools like napari render the data correctly out of the box.

### Starter Notebook

Matteo has set up a notebook at:

```
brieflow/tests/small_test_analysis/notebooks/metadata_enrichment.ipynb
```

This notebook opens real zarr test outputs and demonstrates the current metadata structure. Use it as your workspace — prototype each change here before touching pipeline code.

### What to Add

Work through these items in the notebook. For each one, use `zarr.open()` to inspect the current `zarr.json`, add the metadata, and verify it renders correctly in napari.

| Metadata | What it does | Where in zarr.json |
|----------|-------------|-------------------|
| **Axis units** | `"micrometer"` on spatial axes | `ome.multiscales[0].axes[].unit` |
| **Pixel sizes** | Physical scale factors from config | `ome.multiscales[0].datasets[].coordinateTransformations[].scale` |
| **Channel names** | DAPI, GFP, etc. instead of c0, c1 | `omero.channels[].label` |
| **Contrast limits** | 1st/99th percentile intensity windows | `omero.channels[].window` |
| **Label dtype** | int32 for segmentation masks | Array-level `data_type` |
| **Segmentation metadata** | Method name, label identity | `image-label` attributes |

Use the [BioHub reference spec](zarr3_biohub_spec.md) as the primary target, but also consult the [OME-NGFF v0.5 spec](https://ngff.openmicroscopy.org/latest/) directly — there may be additional useful fields beyond what BioHub writes.

### iohub for Metadata Automation

[iohub](https://github.com/czbiohub-sf/iohub) is CZ Biohub's I/O library for OME-Zarr. It can read/write OME-Zarr with rich metadata handling and may be useful for:

- Automatically deriving metadata from pipeline data (channel names from config, pixel sizes from hardware metadata parquets)
- Writing compliant HCS metadata more efficiently than manual `zarr.json` editing
- Validating output against the OME-NGFF spec

Evaluate whether iohub can replace or complement our current manual metadata writing approach. It may be optimal to have metadata set automatically based on data flowing through the pipeline (e.g., pixel sizes from acquisition metadata, channel names from config, contrast limits computed from the data itself).

### Metadata Propagation

The key question you need to figure out: **when the pipeline reads a zarr and writes a new zarr, does the metadata carry forward?**

- Test this: write metadata to a store, read it with `read_image()`, write to a new store with `save_image()`. Is the metadata still there?
- Some metadata may propagate automatically. Some will need explicit forwarding at each pipeline step.
- Once you understand what propagates, integrate into the pipeline:
  - `workflow/lib/shared/io.py` — `save_image()` accepts metadata kwargs
  - `workflow/lib/shared/omezarr_writer.py` — writes the richer metadata
  - `workflow/scripts/` — scripts forward metadata from snakemake params
  - `workflow/rules/` — rules pass config values as params
  - Config YAML — add `pixel_size_um`, channel name lists, etc.

### Napari Validation

Set up napari **locally** (your laptop, not the cluster) to validate everything visually:

```bash
conda create -n napari-viz -c conda-forge python=3.11 napari napari-ome-zarr -y
conda activate napari-viz
# Copy test output locally or mount cluster via sshfs
napari --plugin napari-ome-zarr path/to/sbs/1.zarr
```

With direct-write, the plate zarr is the output directory itself (no `hcs/` subdirectory):

```bash
# Whole plate:
napari --plugin napari-ome-zarr output/sbs/1.zarr

# Single tile:
python tests/viewer/load_omezarr_in_napari.py output/sbs/1.zarr/A/1/0/aligned.zarr

# Field with labels:
python tests/viewer/load_omezarr_in_napari.py output/sbs/1.zarr/A/1/0
```

Check at each pipeline step (not just final outputs):
- Channel names visible (not `c0`, `c1`)
- Scale bar shows correct physical coordinates
- Contrast limits render sensibly
- Segmentation labels overlay on images
- Plate zarr navigable as plate -> well -> tile

If napari renders it correctly, other OME-NGFF consumers will too.

---

## Open Questions: Tabular Data Format

How to best store tables (single-cell measurements, reads, etc.) alongside OME-NGFF images is an **unsettled question** in the community.

**Background:** The main OME-NGFF tables spec proposal ([ome/ngff#64](https://github.com/ome/ngff/pull/64)) was closed without merging in September 2023. Key tensions included AnnData being too Python-centric for a universal imaging spec, scope disputes about what belongs in the spec, and governance questions. The community acknowledged the need for a governance framework before revisiting.

**Current approach:** We write parquets in a nested directory structure (`parquets/{plate}/{row}/{col}/`). This works but lacks a formal link between image data and tabular measurements.

**Formats to be aware of:**

| Format | Pros | Cons |
|--------|------|------|
| **Parquet** (current) | Simple, language-agnostic, fast columnar reads | No standard for linking to zarr images |
| **AnnData (`.h5ad`)** | scverse ecosystem (scanpy, squidpy); single-cell standard | Python-centric; HDF5 doesn't nest in zarr |
| **AnnData-Zarr** | Could live inside the zarr store hierarchy | Spec not finalized |
| **SpatialData** | Unified image + table + spatial workflows | Heavy dependency; still maturing |

This does not need to be solved now — keep using parquets and focus on image metadata enrichment. But be aware that the tabular format may evolve, and design your work so it's not tightly coupled to parquet.

---

## Contacts and Collaboration

| Person | Role |
|--------|------|
| **Matteo** (mdiberna@wi.mit.edu) | Zarr3 transition lead, primary point of contact |
| **Mikala** (CZI) | Point of contact for OME-Zarr / iohub questions |

### BioHub Slack Channel

There is a Slack channel with CZ BioHub collaborators where OME-Zarr implementation decisions, iohub updates, and spec discussions happen. This is a valuable resource for:

- OME-Zarr best practices and spec interpretation
- iohub usage and feature requests
- Feedback on our HCS layout and metadata approach
- Guidance on the tables/AnnData question

**Action item:** Ege needs to be added to this channel. Ask Matteo to facilitate the invite.

---

## Key Files

| File | Purpose |
|------|---------|
| `zarr3_final_plan.md` | Full plan with output structure, roadmap, and open questions |
| `zarr3_biohub_spec.md` | BioHub reference spec we're aligning to |
| `workflow/lib/shared/io.py` | `read_image()` / `save_image()` — the main I/O dispatchers |
| `workflow/lib/shared/omezarr_writer.py` | Zarr writing logic (pyramids, OME metadata) |
| `workflow/lib/shared/file_utils.py` | `get_nested_path()` / `get_hcs_nested_path()` for nested directory paths |
| `workflow/lib/shared/hcs.py` | `discover_plate_structure()` + `write_hcs_metadata()` (metadata-only fusion) |

## References

- [OME-NGFF v0.5 Spec](https://ngff.openmicroscopy.org/latest/)
- [HCS Plate Layout](https://ngff.openmicroscopy.org/latest/#hcs-layout)
- [ome-zarr-py Docs](https://ome-zarr.readthedocs.io/)
- [napari-ome-zarr](https://github.com/ome/napari-ome-zarr)
- [iohub — CZ Biohub OME-Zarr I/O](https://github.com/czbiohub-sf/iohub)
- [ome/ngff#64 — Tables spec discussion](https://github.com/ome/ngff/pull/64)
- [Brieflow Docs](https://brieflow.readthedocs.io/)
