# Multiround MN-body example

This example requires a Brieflow revision containing the companion MN extension, including peak-relative 53BP1 refinement. The example alone does not update the nested `brieflow` checkout. Check that the selected core revision contains `workflow/rules/mn_bodies.smk` and `docs/source/mn_bodies.md` before using these instructions. The companion pull-request description records the core dependency; after it is merged, use an upstream core commit that includes it.

The overlay in `config/mn_bodies.example.yml` is a five-round, seven-marker pilot example. Calibrate object sizes, intensities, registration checks and artifact thresholds to your instrument. Keep DAPI from each round and match the actual converted CYX channel order. The supplied 30% boundary threshold is a reviewed pilot choice, not a universal setting.

Use `segment_cells: false`, `align: false`, `cellpose_model: cpsam` and a verified Cellpose 4 runtime. Disable other secondary-object extensions. Preserve the screen's existing preprocess, SBS and merge settings.

`phenotype.mn_bodies.enabled: true` activates the extension. `segment_cells: false` requests nuclei only. `align: false` skips the ordinary phenotype channel-alignment step because the MN workflow registers each imaging round to primary DAPI itself. It does not turn off MN round registration. `cellpose_model: cpsam` selects the parent-nucleus model; it does not install Cellpose or configure a Python environment. The pilot used Cellpose 4.0.6, and the core package's dependency policy must support this before a fresh environment can run the example.

The converted stack must contain the 15 channels listed in the example, in that order, or the mapping must be edited to match the actual data. Retain each round's DAPI. Combine the overlay with a complete screen configuration and metadata, and initially restrict that screen to a few representative fields. The file is not a standalone runnable dataset.

From `analysis/`, first inspect a dry-run:

```sh
snakemake --snakefile ../brieflow/workflow/Snakefile \
  --configfile config/config.yml config/mn_bodies.example.yml \
  --cores 4 --dry-run all_phenotype
```

Then remove `--dry-run` for the small validation batch. A dry-run checks workflow construction and inputs; it does not validate image quality or run segmentation. Check DAPI registration, original/refined focus masks, per-object boundary audit, reporter association and marker baselines before a full screen. Full method details are in Brieflow's `docs/source/mn_bodies.md`.

Object-level features remain separate from one-row-per-parent phenotype summaries. After SBS, assign genotypes to objects through `(plate, well, tile, parent_nucleus_id)`. Resolve tile overlap separately. Old reports do not update automatically when masks change.

No image data or site-specific filesystem paths are included. This configuration alone cannot run without the screen's ordinary metadata/configuration and images.
