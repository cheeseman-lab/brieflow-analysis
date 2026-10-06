import marimo

__generated_with = "0.25.0"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Configure Merge Module Params

    This notebook should be used as a test for ensuring correct merge parameters before merge processing.
    Cells marked with <font color='red'>SET PARAMETERS</font> contain crucial variables that need to be set according to your specific experimental setup and data organization.
    Please review and modify these variables as needed before proceeding with the analysis.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Fixed parameters for merge processing

    - `CONFIG_FILE_PATH`: Path to a Brieflow config file used during processing. Absolute or relative to where workflows are run from.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    CONFIG_FILE_PATH = "config/config.yml"
    # === END OPERATOR PARAMETERS ===
    return (CONFIG_FILE_PATH,)


@app.cell
def _():
    import warnings
    from pathlib import Path
    import yaml
    import pandas as pd

    from lib.shared.file_utils import get_filename, get_hcs_nested_path, split_well
    from lib.shared.configuration_utils import CONFIG_FILE_HEADER, convert_tuples_to_lists
    from lib.merge.merge_utils import (
        plot_combined_tile_grid,
        plot_merge_example,
        align_metadata,
        find_closest_tiles,
        filter_low_score_seeds,
        fast_merge_example,
        load_merge_dapi_pair,
        plot_merge_alignment_overlay,
    )
    from lib.merge.positions_overlay import (
        image_path_templates,
        overlay_candidates,
        overlay_image_paths,
        plot_phenotype_in_sbs,
        plot_tile_overlaps,
        positions_merge_well,
    )
    from lib.merge.hash import hash_cell_locations, initial_alignment
    from lib.merge.eval_alignment import plot_alignment_quality

    return (
        CONFIG_FILE_HEADER,
        Path,
        align_metadata,
        convert_tuples_to_lists,
        fast_merge_example,
        filter_low_score_seeds,
        find_closest_tiles,
        get_filename,
        hash_cell_locations,
        image_path_templates,
        initial_alignment,
        load_merge_dapi_pair,
        overlay_candidates,
        overlay_image_paths,
        pd,
        plot_alignment_quality,
        plot_combined_tile_grid,
        plot_merge_alignment_overlay,
        plot_phenotype_in_sbs,
        plot_tile_overlaps,
        positions_merge_well,
        warnings,
        yaml,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Determine merge plate-well combos
    - `MERGE_COMBO_DF_FP`: Plate used for testing configuration
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    MERGE_COMBO_DF_FP = "config/merge_combo.tsv"
    # === END OPERATOR PARAMETERS ===
    return (MERGE_COMBO_DF_FP,)


@app.cell
def _(CONFIG_FILE_PATH, MERGE_COMBO_DF_FP, Path, pd, warnings, yaml):
    # load config file and determine root path
    with open(CONFIG_FILE_PATH, 'r') as _config_file:
        config = yaml.safe_load(_config_file)
    SBS_COMBO_FP = Path(config['preprocess']['sbs_combo_fp'])
    sbs_wildcard_combos = pd.read_csv(SBS_COMBO_FP, sep='\t')
    PHENOTYPE_COMBO_FP = Path(config['preprocess']['phenotype_combo_fp'])
    phenotype_wildcard_combos = pd.read_csv(PHENOTYPE_COMBO_FP, sep='\t')
    sbs_combos = set(zip(sbs_wildcard_combos['plate'], sbs_wildcard_combos['well']))
    phenotype_combos = set(zip(phenotype_wildcard_combos['plate'], phenotype_wildcard_combos['well']))
    # Generate plate-well combinations for merge
    if sbs_combos == phenotype_combos:
        merge_wildcard_combos = pd.DataFrame(list(sbs_combos), columns=['plate', 'well'])
    else:
        warnings.warn('SBS and PHENOTYPE do not have matching plate-well combinations. Merging requires identical sets.')
    # Check if SBS and PHENOTYPE have the same plate-well combinations
        merge_wildcard_combos = pd.DataFrame(columns=['plate', 'well'])
    merge_wildcard_combos.to_csv(MERGE_COMBO_DF_FP, sep='\t', index=False)
    merge_wildcard_combos
    return (config,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Parameters for testing merge module
    - `TEST_PLATE`: Plate used for testing configuration
    - `TEST_WELL`: Well identifier used for testing configuration

    ### Parameters for metadata extraction
    - `SBS_METADATA_CYCLE`: Cycle number for extracting SBS data positions from the combined metadata file
    - `SBS_METADATA_CHANNEL`: Optional channel filter for SBS metadata. Use this to filter the combined metadata file to a specific channel when multiple channels were acquired. If not specified, metadata will be automatically deduplicated by plate, well, and tile.
    - `PH_METADATA_CHANNEL`: Optional channel filter for phenotype metadata. Use this to filter the combined metadata file to a specific channel when multiple channels were acquired. If not specified, metadata will be automatically deduplicated by plate, well, and tile.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    TEST_PLATE = None
    TEST_WELL = None
    SBS_METADATA_CYCLE = 1             # library default; cycle to extract for sbs metadata
    SBS_METADATA_CHANNEL = None
    PH_METADATA_CHANNEL = None
    # === END OPERATOR PARAMETERS ===
    return (
        PH_METADATA_CHANNEL,
        SBS_METADATA_CHANNEL,
        SBS_METADATA_CYCLE,
        TEST_PLATE,
        TEST_WELL,
    )


@app.cell
def _(Path, TEST_PLATE, TEST_WELL, config):
    # Extract image dimensions from a sample tile
    from lib.shared.image_io import read_image

    ROOT_FP = Path(config["all"]["root_fp"])
    IMAGE_FORMAT = config["all"].get("image_format", "tiff")

    if IMAGE_FORMAT == "zarr":
        # Find a sample phenotype zarr image
        ph_image_dir = ROOT_FP / "phenotype"
        ph_zarr_stores = list(ph_image_dir.glob("aligned_*.zarr"))
        if ph_zarr_stores:
            # Find first tile zarr.json
            ph_tiles = list(ph_zarr_stores[0].rglob("*/zarr.json"))
            ph_tiles = [p for p in ph_tiles if "labels" not in str(p) and p.parent.parent.parent.parent == ph_zarr_stores[0]]
            if ph_tiles:
                sample_ph = read_image(ph_tiles[0])
                PHENOTYPE_DIMENSIONS = sample_ph.shape[-2:]
                print(f"Phenotype image dimensions: {PHENOTYPE_DIMENSIONS} (from zarr)")
            else:
                print("No phenotype tiles found, using default (2960, 2960)")
                PHENOTYPE_DIMENSIONS = (2960, 2960)
        else:
            print("No phenotype zarr stores found, using default (2960, 2960)")
            PHENOTYPE_DIMENSIONS = (2960, 2960)

        # Find a sample SBS zarr image (nuclei label store)
        sbs_image_dir = ROOT_FP / "sbs"
        sbs_zarr_stores = list(sbs_image_dir.glob("aligned_*.zarr"))
        if sbs_zarr_stores:
            sbs_tiles = list(sbs_zarr_stores[0].rglob("*/zarr.json"))
            sbs_tiles = [p for p in sbs_tiles if "labels" not in str(p) and p.parent.parent.parent.parent == sbs_zarr_stores[0]]
            if sbs_tiles:
                sample_sbs = read_image(sbs_tiles[0])
                SBS_DIMENSIONS = sample_sbs.shape[-2:]
                print(f"SBS image dimensions: {SBS_DIMENSIONS} (from zarr)")
            else:
                print("No SBS tiles found, using default (1480, 1480)")
                SBS_DIMENSIONS = (1480, 1480)
        else:
            print("No SBS zarr stores found, using default (1480, 1480)")
            SBS_DIMENSIONS = (1480, 1480)
    else:
        from tifffile import imread

        # Find a sample phenotype image (aligned.tiff)
        ph_image_dir = ROOT_FP / "phenotype" / "images"
        ph_images = list(ph_image_dir.glob(f"P-{TEST_PLATE}_W-{TEST_WELL}*__aligned.tiff"))
        if ph_images:
            sample_ph = imread(ph_images[0])
            PHENOTYPE_DIMENSIONS = sample_ph.shape[-2:]
            print(f"Phenotype image dimensions: {PHENOTYPE_DIMENSIONS} (from {ph_images[0].name})")
        else:
            print("No phenotype images found, using default (2960, 2960)")
            PHENOTYPE_DIMENSIONS = (2960, 2960)

        # Find a sample SBS image (nuclei.tiff as aligned.tiff is usually a temp file)
        sbs_image_dir = ROOT_FP / "sbs" / "images"
        sbs_images = list(sbs_image_dir.glob(f"P-{TEST_PLATE}_W-{TEST_WELL}*__nuclei.tiff"))
        if sbs_images:
            sample_sbs = imread(sbs_images[0])
            SBS_DIMENSIONS = sample_sbs.shape[-2:]
            print(f"SBS image dimensions: {SBS_DIMENSIONS} (from {sbs_images[0].name})")
        else:
            print("No SBS images found, using default (1480, 1480)")
            SBS_DIMENSIONS = (1480, 1480)
    return PHENOTYPE_DIMENSIONS, ROOT_FP, SBS_DIMENSIONS


@app.cell
def _(
    PHENOTYPE_DIMENSIONS,
    PH_METADATA_CHANNEL,
    ROOT_FP,
    SBS_DIMENSIONS,
    SBS_METADATA_CHANNEL,
    SBS_METADATA_CYCLE,
    TEST_PLATE,
    TEST_WELL,
    get_filename,
    pd,
    plot_combined_tile_grid,
):
    # load phenotype and SBS metadata dfs (HCS-nested zarr layout: metadata + info parquets at
    # preprocess/metadata/{phenotype,sbs}/<plate>/<row>/<col>/combined_metadata.parquet and
    # {phenotype,sbs}/parquets/<plate>/<row>/<col>/{phenotype_info,sbs_info}.parquet)
    _row, _col = split_well(TEST_WELL)
    ph_test_metadata_fp = ROOT_FP / 'preprocess' / 'metadata' / 'phenotype' / str(TEST_PLATE) / _row / _col / 'combined_metadata.parquet'
    ph_test_metadata = pd.read_parquet(ph_test_metadata_fp)
    if PH_METADATA_CHANNEL is not None:
        ph_test_metadata = ph_test_metadata[ph_test_metadata['channel'] == PH_METADATA_CHANNEL]
    else:
        ph_test_metadata = ph_test_metadata.drop_duplicates(subset=['plate', 'well', 'tile'])
    sbs_test_metadata_fp = ROOT_FP / 'preprocess' / 'metadata' / 'sbs' / str(TEST_PLATE) / _row / _col / 'combined_metadata.parquet'
    sbs_test_metadata = pd.read_parquet(sbs_test_metadata_fp)
    sbs_test_metadata = sbs_test_metadata[sbs_test_metadata['cycle'] == SBS_METADATA_CYCLE]
    if SBS_METADATA_CHANNEL is not None:
        sbs_test_metadata = sbs_test_metadata[sbs_test_metadata['channel'] == SBS_METADATA_CHANNEL]
    else:
        sbs_test_metadata = sbs_test_metadata.drop_duplicates(subset=['plate', 'well', 'tile'])
    _phenotype_info_fp = ROOT_FP / 'phenotype' / 'parquets' / str(TEST_PLATE) / _row / _col / 'phenotype_info.parquet'
    phenotype_info = pd.read_parquet(_phenotype_info_fp)
    _sbs_info_fp = ROOT_FP / 'sbs' / 'parquets' / str(TEST_PLATE) / _row / _col / 'sbs_info.parquet'
    sbs_info = pd.read_parquet(_sbs_info_fp)
    _combined_tile_grid = plot_combined_tile_grid(ph_test_metadata, sbs_test_metadata, ph_image_dims=PHENOTYPE_DIMENSIONS, sbs_image_dims=SBS_DIMENSIONS)
    # Apply SBS filtering - always filter by cycle, optionally by channel, otherwise deduplicate
    # Derive phenotype alignment hash
    # Derive SBS alignment hash
    # create plot with combined tile view
    _combined_tile_grid.show()  # Only deduplicate if no channel filter was applied (cycle filter was already applied)
    return ph_test_metadata, phenotype_info, sbs_info, sbs_test_metadata


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Parameters for metadata alignment
    Each microscope handles global coordinates differently. If datasets were acquired in two different microscopes the metadata of the wells needs to be aligned.

    `METADATA_ALIGN`: Whether to perform metadata alignment. Defaults `False`.

    `ALIGNMENT_FLIP_X`: Flip images left-to-right (horizontal flip). Defaults `False`.

    `ALIGNMENT_FLIP_Y`: Flip images up-down (vertical flip). Defaults `False`.

    `ALIGNMENT_ROTATE_90`: Whether to rotate 90 degrees counterclockwise. Defaults `False`.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    METADATA_ALIGN = False
    ALIGNMENT_FLIP_X = False
    ALIGNMENT_FLIP_Y = False
    ALIGNMENT_ROTATE_90 = False
    # === END OPERATOR PARAMETERS ===
    return (
        ALIGNMENT_FLIP_X,
        ALIGNMENT_FLIP_Y,
        ALIGNMENT_ROTATE_90,
        METADATA_ALIGN,
    )


@app.cell
def _(
    ALIGNMENT_FLIP_X,
    ALIGNMENT_FLIP_Y,
    ALIGNMENT_ROTATE_90,
    METADATA_ALIGN,
    PHENOTYPE_DIMENSIONS,
    SBS_DIMENSIONS,
    align_metadata,
    ph_test_metadata,
    plot_combined_tile_grid,
    sbs_test_metadata,
):
    # Apply flip and rotate transformation
    if METADATA_ALIGN:
        sbs_aligned, ph_aligned, transform_info = align_metadata(sbs_test_metadata, ph_test_metadata, flip_x=ALIGNMENT_FLIP_X, flip_y=ALIGNMENT_FLIP_Y, rotate_90=ALIGNMENT_ROTATE_90)
        _combined_tile_grid = plot_combined_tile_grid(ph_aligned, sbs_aligned, ph_image_dims=PHENOTYPE_DIMENSIONS, sbs_image_dims=SBS_DIMENSIONS)
        _combined_tile_grid.show()  # Flip x coordinates (horizontal flip)
    else:  # Flip y coordinates (vertical flip)
        sbs_aligned = sbs_test_metadata  # Rotation
        ph_aligned = ph_test_metadata  # Check the result with your combined tile grid
    return ph_aligned, sbs_aligned


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Merge approach

    - `MERGE_APPROACH`: `"fast"` (default) aligns tile pairs by hashing triangles of nuclei and needs initial sites; `"positions"` matches cells from tile stage positions and centroids fitted over the whole well and needs no initial sites. Choose `"positions"` at high phenotype magnification or when tiles hold too few cells for `"fast"`. Only the section of the chosen approach runs below.
    - `THRESHOLD`: Maximum distance, in SBS pixels, between a phenotype cell and an SBS cell for them to match (both approaches), e.g. `2`.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    MERGE_APPROACH = "fast"            # "fast" | "positions"
    THRESHOLD = None                   # e.g., 2
    # === END OPERATOR PARAMETERS ===
    if MERGE_APPROACH not in ("fast", "positions"):
        raise ValueError(f'MERGE_APPROACH must be "fast" or "positions", got {MERGE_APPROACH!r}')
    return MERGE_APPROACH, THRESHOLD


@app.cell
def _():
    def drop_none(**kwargs):
        """Keep only the keyword args that were actually set (drop None)."""
        return {k: v for k, v in kwargs.items() if v is not None}

    return (drop_none,)


@app.cell(hide_code=True)
def _(MERGE_APPROACH, mo):
    mo.stop(MERGE_APPROACH != "fast")
    mo.md(r"""
    ## Fast approach

    Tile-site pairs are aligned by hashing triangles of nuclei, starting from a few initial pairs, and checked below before the config is written.
    """)
    return


@app.cell(hide_code=True)
def _(MERGE_APPROACH, mo):
    mo.stop(MERGE_APPROACH != "fast")
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Initial Sites Configuration

    - `INITIAL_SITES_APPROACH`: Method for configuring initial tile-site pairs for alignment.
      - `"auto"`: Specify SBS tiles and automatically discover matching phenotype tiles based on stage coordinates. Simpler configuration with automatic validation.
      - `"manual"`: Specify explicit `[phenotype_tile, sbs_tile]` pairs for precise control.

    - `INITIAL_SBS_TILES`: (Used when `INITIAL_SITES_APPROACH = "auto"`) List of SBS tile IDs distributed across the well. The pipeline will automatically find the closest matching phenotype tile for each.
      - Example: `INITIAL_SBS_TILES = [1, 23, 44, 85, 119, 174, 200, 254, 277, 316, 330]`

    - `INITIAL_SITES`: (Used when `INITIAL_SITES_APPROACH = "manual"`) List of explicit `[phenotype_tile, sbs_tile]` pairs.
      - Example: `INITIAL_SITES = [[1, 1], [76, 23], [174, 44], ...]`

    **Validation:** Both approaches should contain at least 5 pairs to pass `DET_RANGE` and `SCORE` thresholds before the pipeline can proceed.
    """)
    return


@app.cell(hide_code=True)
def _(MERGE_APPROACH, mo):
    mo.stop(MERGE_APPROACH != "fast")
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS (OPTIONAL): ADVANCED FAST-MERGE LEVERS</font>

    Optional levers to improve a difficult merge (e.g. a large rotation / scale offset between the two scopes). All default to `None` (pipeline built-in behavior). Set them here; the alignment and match-preview cells below use them, so you can evaluate a setting before committing the config. Only levers set to a non-`None` value are written to `config.yml`.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS: ADVANCED FAST-MERGE LEVERS ===
    LOCAL_REFINEMENT = None       # None | "polynomial" | "thin_plate_spline"; within-tile warp
    WARP_DEGREE = None            # polynomial warp degree (e.g. 3)
    WARP_ITERATIONS = None        # refine-and-rematch passes (e.g. 2)
    WARP_SMOOTHING = None         # thin-plate-spline regularization (e.g. 10)
    SEED_OPTIMIZE = None          # try top-SEED_TOPK nearest tiles per seed, keep best (e.g. True)
    SEED_TOPK = None              # nearest tiles to evaluate when SEED_OPTIMIZE (e.g. 3)
    THRESHOLD_TRIANGLE = None     # triangle hash-match distance (e.g. 0.3)
    # === END OPERATOR PARAMETERS ===
    return (
        LOCAL_REFINEMENT,
        SEED_OPTIMIZE,
        SEED_TOPK,
        THRESHOLD_TRIANGLE,
        WARP_DEGREE,
        WARP_ITERATIONS,
        WARP_SMOOTHING,
    )


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    INITIAL_SITES_APPROACH = None      # "auto" | "manual"
    INITIAL_SBS_TILES = None           # auto: list of SBS tile indices distributed across the well
    INITIAL_SITES = None               # manual: list of [phenotype_tile, sbs_tile] pairs
    # === END OPERATOR PARAMETERS ===
    return INITIAL_SBS_TILES, INITIAL_SITES, INITIAL_SITES_APPROACH


@app.cell
def _(
    INITIAL_SBS_TILES,
    INITIAL_SITES,
    INITIAL_SITES_APPROACH,
    MERGE_APPROACH,
    SEED_OPTIMIZE,
    SEED_TOPK,
    find_closest_tiles,
    mo,
    ph_aligned,
    sbs_aligned,
):
    mo.stop(MERGE_APPROACH != "fast")
    if INITIAL_SITES_APPROACH == 'auto':
    # Option 2: Manual - specify explicit [phenotype_tile, sbs_tile] pairs
    # Only used if INITIAL_SITES_APPROACH = "manual"
        candidate_pairs = []  # Set to list of pairs if using manual approach
        print('Discovering phenotype tiles for each SBS tile...')
    # Auto-discover matches from SBS tiles (for visualization and validation)
        for _sbs_tile in INITIAL_SBS_TILES:
            closest = find_closest_tiles(sbs_aligned, ph_aligned, _sbs_tile, verbose=True)
            if SEED_OPTIMIZE:
                for _ph_tile in closest.head(SEED_TOPK or 3)['tile'].astype(int):
                    candidate_pairs.append([int(_ph_tile), _sbs_tile])
            else:
                candidate_pairs.append([int(closest.iloc[0]['tile']), _sbs_tile])
        print('\n' + '=' * 50)
        print('Discovered candidate pairs:')
        print('=' * 50)
        print(f'candidate_pairs = {candidate_pairs}')
    else:
        if INITIAL_SITES is None:
            raise ValueError('INITIAL_SITES must be set when using manual approach')
        candidate_pairs = INITIAL_SITES
        print(f'Using {len(candidate_pairs)} manually specified initial sites')
    return (candidate_pairs,)


@app.cell
def _(candidate_pairs):
    # Display the candidate pairs for review
    print(f'Candidate pairs to validate: {len(candidate_pairs)}')
    for _ph_tile, _sbs_tile in candidate_pairs:
        print(f'  PH tile {_ph_tile} <-> SBS tile {_sbs_tile}')
    return


@app.cell
def _(
    ROOT_FP,
    TEST_PLATE,
    TEST_WELL,
    THRESHOLD_TRIANGLE,
    candidate_pairs,
    drop_none,
    get_filename,
    hash_cell_locations,
    initial_alignment,
    mo,
    pd,
):
    mo.stop(not candidate_pairs, mo.md("No initial tile-site pairs to test: set `INITIAL_SITES` or `INITIAL_SBS_TILES`."))
    _row2, _col2 = split_well(TEST_WELL)
    _phenotype_info_fp = ROOT_FP / 'phenotype' / 'parquets' / str(TEST_PLATE) / _row2 / _col2 / 'phenotype_info.parquet'
    phenotype_info_1 = pd.read_parquet(_phenotype_info_fp)
    phenotype_info_hash = hash_cell_locations(phenotype_info_1)
    _sbs_info_fp = ROOT_FP / 'sbs' / 'parquets' / str(TEST_PLATE) / _row2 / _col2 / 'sbs_info.parquet'
    sbs_info_1 = pd.read_parquet(_sbs_info_fp)
    sbs_info_hash = hash_cell_locations(sbs_info_1).rename(columns={'tile': 'site'})
    evaluate_kwargs = drop_none(threshold_triangle=THRESHOLD_TRIANGLE)
    initial_alignment_df = initial_alignment(phenotype_info_hash, sbs_info_hash, initial_sites=candidate_pairs, evaluate_kwargs=evaluate_kwargs)
    initial_alignment_df
    return initial_alignment_df, phenotype_info_1, sbs_info_1


@app.cell(hide_code=True)
def _(MERGE_APPROACH, mo):
    mo.stop(MERGE_APPROACH != "fast")
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Visualize gating strategy based on initial alignment

    - `DET_RANGE`: Enforces valid magnification ratios between phenotype and genotype images.
      - The determinant range accounts for differences in:
        - Objective magnifications (e.g., 20X vs 10X)
        - Camera binning settings (e.g., 2x2 vs unbinned)
      - Calculation formula:
        - If magnification ratio = M and binning ratio = B
        - Total difference factor = M × B
        - `DET_RANGE` = [0.9/(M×B)², 1.1/(M×B)²] (numerators are whatever range around 1 that you would like to accept)
      - Example:
        - With 2× magnification difference and 2× binning difference
        - Total difference factor = 2 × 2 = 4
        - `DET_RANGE` = [0.9/16, 1.1/16] = [0.056, 0.069]
      - Adjust range as needed for matching precision
    - `SCORE`: This parameter is the score of the transformation, typically 0.1
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    DET_RANGE = None                   # e.g., [0.06, 0.065]
    # === END OPERATOR PARAMETERS ===

    SCORE = 0.1                        # library default (auto bucket)
    return DET_RANGE, SCORE


@app.cell
def _(DET_RANGE, SCORE, initial_alignment_df, plot_alignment_quality):
    plot_alignment_quality(
        initial_alignment_df, det_range=DET_RANGE, score=SCORE, xlim=(0, 0.1), ylim=(0, 1)
    )
    return


@app.cell
def _(DET_RANGE, SCORE, SEED_OPTIMIZE, filter_low_score_seeds, initial_alignment_df):
    # Validate that enough pairs pass the thresholds
    d0, d1 = DET_RANGE
    valid_pairs_df = initial_alignment_df.query(
        "@d0 <= determinant <= @d1 & score > @SCORE"
    )

    # Collapse top-K seed candidates to the best-scoring phenotype tile per SBS site.
    # Mirrors the pipeline (fast_alignment.py) so this preview shows the 1:1 mapping the run will use.
    if SEED_OPTIMIZE:
        _n_before = len(valid_pairs_df)
        valid_pairs_df = valid_pairs_df.sort_values(
            "score", ascending=False
        ).drop_duplicates(subset="site", keep="first")
        print(f"seed_optimize: kept best-scoring tile per site ({_n_before} -> {len(valid_pairs_df)})")

    # Drop seeds whose score is a low outlier relative to the cohort (keeps >= 5)
    _n_before = len(valid_pairs_df)
    valid_pairs_df = filter_low_score_seeds(valid_pairs_df)
    if len(valid_pairs_df) < _n_before:
        print(f"filtered {_n_before - len(valid_pairs_df)} low-score outlier seed(s) ({_n_before} -> {len(valid_pairs_df)})")

    valid_pairs_df = valid_pairs_df.sort_values("site")
    final_pairs = valid_pairs_df[["tile", "site"]].astype(int).values.tolist()

    print(f"\n{'='*50}")
    print(f"VALIDATION RESULTS")
    print(f"{'='*50}")
    print(f"Total candidate pairs: {len(initial_alignment_df)}")
    print(f"Valid pairs (1 phenotype tile per SBS site): {len(final_pairs)}")
    print(f"Minimum required: 5")
    print(f"{'='*50}")

    if len(final_pairs) < 5:
        print(f"\nWARNING: Only {len(final_pairs)} pairs pass thresholds!")
        print("The pipeline requires at least 5 valid pairs.")
        print("Consider:")
        print("  - Adjusting DET_RANGE or SCORE thresholds")
        print("  - Adding more SBS tiles to INITIAL_SBS_TILES")
        print("  - Using manual INITIAL_SITES with known good pairs")
    else:
        print(f"\nValidation passed! {len(final_pairs)} pairs will be used.")

    # Show which pairs passed (one phenotype tile per SBS site)
    print(f"\nValid pairs (tile, site):")
    for _, row in valid_pairs_df.iterrows():
        print(f"  [{int(row['tile'])}, {int(row['site'])}] - score: {row['score']:.3f}, det: {row['determinant']:.6f}")
    return (final_pairs,)


@app.cell(hide_code=True)
def _(MERGE_APPROACH, mo):
    mo.stop(MERGE_APPROACH != "fast")
    mo.md(r"""
    ### Visualize cell matches based on initial alignment

    Cells of each validated tile-site pair matched within `THRESHOLD` (set with the merge approach above).
    """)
    return


@app.cell
def _(
    LOCAL_REFINEMENT,
    THRESHOLD,
    WARP_DEGREE,
    WARP_ITERATIONS,
    WARP_SMOOTHING,
    drop_none,
    fast_merge_example,
    final_pairs,
    initial_alignment_df,
    phenotype_info_1,
    sbs_info_1,
):
    warp_kwargs = drop_none(degree=WARP_DEGREE, iterations=WARP_ITERATIONS, smoothing=WARP_SMOOTHING) or None
    for _ph_tile, sbs_site in final_pairs:
        success = fast_merge_example(_ph_tile, sbs_site, initial_alignment_df, phenotype_info_1, sbs_info_1, THRESHOLD, local_refinement=LOCAL_REFINEMENT, warp_kwargs=warp_kwargs)
        if not success:
            print(f'  Try a different tile-site combination or MERGE_APPROACH = "positions".')
    return


@app.cell(hide_code=True)
def _(MERGE_APPROACH, mo):
    mo.stop(MERGE_APPROACH != "fast")
    mo.md(r"""
    ### Check the merge alignment on the images

    For each selected tile-site pair (by default the first one above), the whole SBS site is shown with the phenotype tile outlined (SBS DAPI outside the tile is magenta: SBS only), next to a zoom on the tile. Inside the tile: SBS DAPI (magenta) and phenotype DAPI mapped onto it (green), brightness-matched for display. Aligned nuclei look white or grey; a wrong alignment leaves magenta and green fringes; a nucleus found in one image only stays fully magenta or green. The title gives the remaining shift in SBS pixels. Pick more pairs with the selector below.
    """)
    return


@app.cell
def _(final_pairs, mo):
    _labels = {f"PH tile {t} → SBS site {s}": i for i, (t, s) in enumerate(final_pairs)}
    merge_overlay_pairs = mo.ui.multiselect(
        options=_labels, value=list(_labels)[:1], label="Tile-site pairs to draw"
    )
    merge_overlay_pairs
    return (merge_overlay_pairs,)


@app.cell
def _(
    ROOT_FP,
    TEST_PLATE,
    TEST_WELL,
    config,
    final_pairs,
    initial_alignment_df,
    load_merge_dapi_pair,
    merge_overlay_pairs,
    plot_merge_alignment_overlay,
):
    for _ph_tile, _sbs_site in [final_pairs[i] for i in merge_overlay_pairs.value]:
        _sbs_dapi, _ph_dapi = load_merge_dapi_pair(
            ROOT_FP,
            TEST_PLATE,
            TEST_WELL,
            _ph_tile,
            _sbs_site,
            config["all"].get("image_format", "tiff"),
            config.get("phenotype", {}).get("channel_names") or [],
            config.get("sbs", {}).get("channel_names") or [],
        )
        if _sbs_dapi is None or _ph_dapi is None:
            print(f"No images found for PH tile {_ph_tile} and SBS site {_sbs_site}; skipping overlay")
            continue
        plot_merge_alignment_overlay(_sbs_dapi, _ph_dapi, initial_alignment_df, _ph_tile, _sbs_site)
    return


@app.cell(hide_code=True)
def _(MERGE_APPROACH, mo):
    mo.stop(MERGE_APPROACH != "positions")
    mo.md(r"""
    ## Positions approach

    The positions approach places every cell from its tile's stage position and its centroid, fits each microscope's camera scale, rotation and lens distortion plus one phenotype-to-SBS offset from all cells of the well, corrects each tile's stage position, and matches cells one-to-one within `THRESHOLD`. No initial sites are needed.

    ### <font color='red'>SET PARAMETERS</font>: tile orientation
    Each microscope relates tile images to stage coordinates differently. The fit scores all eight orientations on the tile overlaps and names the best one when the configured one looks wrong; set these to match.

    `FLIPUD`: Tile rows run against stage y (vertical flip). Defaults `False`.

    `FLIPLR`: Tile columns run against stage x (horizontal flip). Defaults `False`.

    `ROT90`: Number of 90° counterclockwise rotations (as `numpy.rot90`), applied after the flips. Defaults `0`.

    The preview below runs the positions merge on `TEST_WELL` and prints its fit: match rate, fit residual, tile-overlap agreement of every orientation and any warning. The check by eye follows it.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS (POSITIONS APPROACH) ===
    FLIPUD = False
    FLIPLR = False
    ROT90 = 0
    # === END OPERATOR PARAMETERS ===
    return FLIPLR, FLIPUD, ROT90


@app.cell
def _(
    ALIGNMENT_FLIP_X,
    ALIGNMENT_FLIP_Y,
    ALIGNMENT_ROTATE_90,
    FLIPLR,
    FLIPUD,
    METADATA_ALIGN,
    PHENOTYPE_DIMENSIONS,
    PHENOTYPE_PIXEL_SIZE_1,
    MERGE_APPROACH,
    ROOT_FP,
    ROT90,
    SBS_DIMENSIONS,
    SBS_PIXEL_SIZE_1,
    TEST_PLATE,
    TEST_WELL,
    THRESHOLD,
    config,
    image_path_templates,
    mo,
    ph_test_metadata,
    phenotype_info,
    positions_merge_well,
    sbs_info,
    sbs_test_metadata,
):
    mo.stop(MERGE_APPROACH != "positions")
    _merged, positions_qc, positions_placement, _, _ = positions_merge_well(
        phenotype_info, sbs_info, ph_test_metadata, sbs_test_metadata, TEST_PLATE, TEST_WELL,
        PHENOTYPE_DIMENSIONS, SBS_DIMENSIONS, threshold=THRESHOLD, flipud=FLIPUD, fliplr=FLIPLR, rot90=ROT90,
        phenotype_pixel_size=PHENOTYPE_PIXEL_SIZE_1, sbs_pixel_size=SBS_PIXEL_SIZE_1,
        alignment={'metadata_align': METADATA_ALIGN, 'flip_x': ALIGNMENT_FLIP_X, 'flip_y': ALIGNMENT_FLIP_Y, 'rotate_90': ALIGNMENT_ROTATE_90},
    )
    print(positions_qc.T.to_string(header=False))
    mo.stop(positions_placement is None, mo.md("Too few cells in the test well for a positions merge."))
    return positions_placement, positions_qc


@app.cell(hide_code=True)
def _(MERGE_APPROACH, mo):
    mo.stop(MERGE_APPROACH != "positions")
    mo.md(r"""
    ### Check the positions placement on the images

    **Tile overlaps:** where two neighbouring tiles of one modality overlap, tile A is magenta and tile B green, each placed with the fitted model. **Phenotype in SBS:** phenotype DAPI mapped into an SBS tile (green) over SBS DAPI (magenta). Aligned nuclei look white or grey; a placement error shows every nucleus twice, magenta and green. Titles give the remaining shift. The pairs are spread over the well, and the tile overlaps include the sparsest tiles. Each selector draws 2 pairs per kind by default; pick more, or `all` for every candidate.
    """)
    return


@app.cell
def _(mo, overlay_candidates, phenotype_info, positions_placement, sbs_info):
    positions_candidates = overlay_candidates(
        positions_placement,
        {'phenotype': phenotype_info['tile'].value_counts(), 'sbs': sbs_info['tile'].value_counts()},
    )
    _overlap_labels = {f'{_m} tiles {_a} | {_b}': _i for _i, (_m, _a, _b) in enumerate(positions_candidates['tile_overlaps'])}
    _in_sbs_labels = {f'PH tile {_p} in SBS tile {_s}': _i for _i, (_p, _s) in enumerate(positions_candidates['phenotype_in_sbs'])}
    _default_overlaps = [
        _label for _m in ('phenotype', 'sbs')
        for _label in [_l for _l in _overlap_labels if _l.startswith(_m)][:2]
    ]
    positions_overlap_pairs = mo.ui.multiselect(
        options={'all': -1, **_overlap_labels}, value=_default_overlaps, label='Tile overlaps to draw'
    )
    positions_in_sbs_pairs = mo.ui.multiselect(
        options={'all': -1, **_in_sbs_labels}, value=list(_in_sbs_labels)[:2], label='Phenotype-in-SBS tiles to draw'
    )
    mo.hstack([positions_overlap_pairs, positions_in_sbs_pairs])
    return positions_candidates, positions_in_sbs_pairs, positions_overlap_pairs


@app.cell
def _(
    ROOT_FP,
    TEST_PLATE,
    TEST_WELL,
    config,
    image_path_templates,
    mo,
    overlay_image_paths,
    plot_phenotype_in_sbs,
    plot_tile_overlaps,
    positions_candidates,
    positions_in_sbs_pairs,
    positions_overlap_pairs,
    positions_placement,
):
    def _chosen(selector, candidates):
        return list(candidates) if -1 in selector.value else [candidates[_i] for _i in selector.value]

    _overlaps = _chosen(positions_overlap_pairs, positions_candidates['tile_overlaps'])
    _in_sbs = _chosen(positions_in_sbs_pairs, positions_candidates['phenotype_in_sbs'])
    _tiles = {
        'phenotype': {t for _m, _a, _b in _overlaps if _m == 'phenotype' for t in (_a, _b)} | {_p for _p, _s in _in_sbs},
        'sbs': {t for _m, _a, _b in _overlaps if _m == 'sbs' for t in (_a, _b)} | {_s for _p, _s in _in_sbs},
    }
    _labels, _images = overlay_image_paths(
        image_path_templates(ROOT_FP, config['all'].get('image_format', 'tiff')), _tiles, TEST_PLATE, TEST_WELL
    )
    _dapi = {_m: config.get(_m, {}).get('dapi_index') or 0 for _m in ('phenotype', 'sbs')}
    _overlap_records, _overlap_fig = plot_tile_overlaps(positions_placement, _overlaps, _labels, _images, _dapi)
    _in_sbs_records, _in_sbs_fig = plot_phenotype_in_sbs(positions_placement, _in_sbs, _labels, _images, _dapi)
    mo.vstack([mo.as_html(_f) for _f in (_overlap_fig, _in_sbs_fig) if _f is not None] + [_overlap_records, _in_sbs_records])
    return


@app.cell(hide_code=True)
def _(MERGE_APPROACH, mo):
    mo.stop(MERGE_APPROACH != "positions")
    mo.md(r"""
    ### Set pixel size (optional)
    The positions approach converts stage coordinates (in micrometers) to pixel coordinates. The cell below prints the pixel sizes found in the image metadata; if one is missing, set it in the cell after.

    `SBS_PIXEL_SIZE_1`: Pixel size (in μm/pixel) of SBS images.
    `PHENOTYPE_PIXEL_SIZE_1`: Pixel size (in μm/pixel) of phenotyping images.
    """)
    return


@app.cell
def _(MERGE_APPROACH, ph_test_metadata, sbs_test_metadata):
    if MERGE_APPROACH == "positions":
        # For SBS
        if 'pixel_size_x' in sbs_test_metadata.columns:
            SBS_PIXEL_SIZE = sbs_test_metadata['pixel_size_x'].iloc[0]
            print(f"SBS pixel size found in metadata: {SBS_PIXEL_SIZE:.6f} μm/pixel")
        else:
            print("No pixel_size_x found in SBS metadata.")
            # Check what columns are available
            print(f"SBS columns: {list(sbs_test_metadata.columns)}")

        # For Phenotype  
        if 'pixel_size_x' in ph_test_metadata.columns:
            PHENOTYPE_PIXEL_SIZE = ph_test_metadata['pixel_size_x'].iloc[0]
            print(f"Phenotype pixel size found in metadata: {PHENOTYPE_PIXEL_SIZE:.6f} μm/pixel")
        else:
            print("No pixel_size_x found in phenotype metadata.")
            # Check what columns are available
            print(f"\nPhenotype columns: {list(ph_test_metadata.columns)}")
    return


@app.cell
def _():
    SBS_PIXEL_SIZE_1 = None
    PHENOTYPE_PIXEL_SIZE_1 = None
    return PHENOTYPE_PIXEL_SIZE_1, SBS_PIXEL_SIZE_1


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    `SBS_DEDUP_PRIOR` & `PHENO_DEDUP_PRIOR`: Control how duplicate cell mappings are resolved through two sequential steps:

    - Step 1: For each phenotype cell with multiple SBS matches, keeps the best SBS match
    - Step 2: For each remaining SBS cell with multiple phenotype matches, keeps the best phenotype match

    Each parameter is a `{"key": value}` dictionary where:

    - **Keys**: Column names to sort by (e.g., distance, mapped_single_gene, fov_distance_0).
    - **Values**: Sort direction (True = ascending, False = descending).
    - **Order matters:** First column has highest priority, subsequent columns break ties.

    **Example strategies:**
    - `SBS_DEDUP_PRIOR = {"distance": True, "mapped_single_gene": False}`: Prioritize spatial accuracy first, then gene mapping quality.
    - `SBS_DEDUP_PRIOR = {"mapped_single_gene": False, "distance": True}`: Prioritize single-gene assignments first, then spatial proximity.
    - `PHENO_DEDUP_PRIOR = {"distance": True, "fov_distance_0": True}`: Prefer close phenotype matches near field-of-view center.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    SBS_DEDUP_PRIOR = None             # SBS-side deduplication prior
    PHENO_DEDUP_PRIOR = None           # phenotype-side deduplication prior
    # === END OPERATOR PARAMETERS ===
    return PHENO_DEDUP_PRIOR, SBS_DEDUP_PRIOR


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Add merge parameters to config file
    """)
    return


@app.cell
def _(
    ALIGNMENT_FLIP_X,
    ALIGNMENT_FLIP_Y,
    ALIGNMENT_ROTATE_90,
    CONFIG_FILE_HEADER,
    CONFIG_FILE_PATH,
    DET_RANGE,
    FLIPLR,
    FLIPUD,
    INITIAL_SBS_TILES,
    INITIAL_SITES,
    INITIAL_SITES_APPROACH,
    LOCAL_REFINEMENT,
    MERGE_COMBO_DF_FP,
    METADATA_ALIGN,
    PHENOTYPE_DIMENSIONS,
    PHENOTYPE_PIXEL_SIZE_1,
    PHENO_DEDUP_PRIOR,
    PH_METADATA_CHANNEL,
    MERGE_APPROACH,
    ROT90,
    SBS_DEDUP_PRIOR,
    SBS_DIMENSIONS,
    SBS_METADATA_CHANNEL,
    SBS_METADATA_CYCLE,
    SBS_PIXEL_SIZE_1,
    SCORE,
    SEED_OPTIMIZE,
    SEED_TOPK,
    THRESHOLD,
    THRESHOLD_TRIANGLE,
    WARP_DEGREE,
    WARP_ITERATIONS,
    WARP_SMOOTHING,
    config,
    convert_tuples_to_lists,
    drop_none,
    yaml,
):
    config['merge'] = {'approach': MERGE_APPROACH, 'merge_combo_fp': MERGE_COMBO_DF_FP, 'phenotype_dimensions': PHENOTYPE_DIMENSIONS, 'sbs_dimensions': SBS_DIMENSIONS, 'sbs_metadata_cycle': SBS_METADATA_CYCLE, 'score': SCORE, 'threshold': THRESHOLD, 'sbs_metadata_channel': SBS_METADATA_CHANNEL, 'ph_metadata_channel': PH_METADATA_CHANNEL, 'metadata_align': METADATA_ALIGN, 'alignment_flip_x': ALIGNMENT_FLIP_X, 'alignment_flip_y': ALIGNMENT_FLIP_Y, 'alignment_rotate_90': ALIGNMENT_ROTATE_90, 'sbs_dedup_prior': SBS_DEDUP_PRIOR, 'pheno_dedup_prior': PHENO_DEDUP_PRIOR}
    if MERGE_APPROACH == "positions":
        config['merge'].update({'flipud': FLIPUD, 'fliplr': FLIPLR, 'rot90': ROT90, 'sbs_pixel_size': SBS_PIXEL_SIZE_1, 'phenotype_pixel_size': PHENOTYPE_PIXEL_SIZE_1})
    elif INITIAL_SITES_APPROACH == 'auto':
        config['merge'].update({'initial_sbs_tiles': INITIAL_SBS_TILES, 'det_range': DET_RANGE})
        print(f'Config will use initial_sbs_tiles: {INITIAL_SBS_TILES}')
    else:
        config['merge'].update({'initial_sites': INITIAL_SITES, 'det_range': DET_RANGE})
        print(f'Config will use initial_sites: {len(INITIAL_SITES)} pairs')
    config['merge'].update(drop_none(seed_optimize=SEED_OPTIMIZE, seed_topk=SEED_TOPK, local_refinement=LOCAL_REFINEMENT, warp_smoothing=WARP_SMOOTHING, warp_degree=WARP_DEGREE, warp_iterations=WARP_ITERATIONS, threshold_triangle=THRESHOLD_TRIANGLE))
    safe_config = convert_tuples_to_lists(config)
    with open(CONFIG_FILE_PATH, 'w') as _config_file:
        _config_file.write(CONFIG_FILE_HEADER)
        yaml.dump(safe_config, _config_file, default_flow_style=False, sort_keys=False)
    print(f'Image dimensions: phenotype={PHENOTYPE_DIMENSIONS}, sbs={SBS_DIMENSIONS}')
    print(f'Config saved to: {CONFIG_FILE_PATH}')
    return


@app.cell
def _():
    # === TUNED EXPORT ===
    # No notebook-derived tuned values for merge (det_range + threshold are
    # operator-set upfront, not notebook-derived). Empty export for symmetry.
    import json as _je
    from pathlib import Path as _Pe
    _t = {}
    _out = _Pe(".brieflow") / "tuned_merge.json"
    _out.parent.mkdir(exist_ok=True)
    _out.write_text(_je.dumps(_t, indent=2, default=str))
    # === END TUNED EXPORT ===
    return


if __name__ == "__main__":
    app.run()
