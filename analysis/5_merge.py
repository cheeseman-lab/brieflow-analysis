import marimo

__generated_with = "0.23.6"
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

    from lib.shared.file_utils import get_filename, get_hcs_nested_path
    from lib.shared.configuration_utils import CONFIG_FILE_HEADER, convert_tuples_to_lists
    from lib.merge.merge_utils import (
        plot_combined_tile_grid,
        plot_merge_example,
        preview_mask_transformations,
        align_metadata,
        find_closest_tiles,
        fast_merge_example,
    )
    from lib.merge.hash import hash_cell_locations, initial_alignment
    from lib.merge.eval_alignment import plot_alignment_quality

    return (
        CONFIG_FILE_HEADER,
        Path,
        align_metadata,
        convert_tuples_to_lists,
        fast_merge_example,
        find_closest_tiles,
        get_filename,
        hash_cell_locations,
        initial_alignment,
        pd,
        plot_alignment_quality,
        plot_combined_tile_grid,
        preview_mask_transformations,
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
    _row, _col = TEST_WELL[0], TEST_WELL[1:]
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
    return ph_test_metadata, sbs_test_metadata


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


@app.cell
def _(find_closest_tiles, ph_aligned, sbs_aligned):
    # === OPERATOR PARAMETERS ===
    INITIAL_SITES_APPROACH = None      # "auto" | "manual"
    INITIAL_SBS_TILES = None           # auto: list of SBS tile indices distributed across the well
    INITIAL_SITES = None               # manual: list of [phenotype_tile, sbs_tile] pairs
    # === END OPERATOR PARAMETERS ===
    if INITIAL_SITES_APPROACH == 'auto':
    # Option 2: Manual - specify explicit [phenotype_tile, sbs_tile] pairs
    # Only used if INITIAL_SITES_APPROACH = "manual"
        candidate_pairs = []  # Set to list of pairs if using manual approach
        print('Discovering phenotype tiles for each SBS tile...')
    # Auto-discover matches from SBS tiles (for visualization and validation)
        for _sbs_tile in INITIAL_SBS_TILES:
            closest = find_closest_tiles(sbs_aligned, ph_aligned, _sbs_tile, verbose=True)
            best_match = int(closest.iloc[0]['tile'])
            candidate_pairs.append([best_match, _sbs_tile])
        print('\n' + '=' * 50)
        print('Discovered candidate pairs:')
        print('=' * 50)
        print(f'candidate_pairs = {candidate_pairs}')
    else:
        if INITIAL_SITES is None:
            raise ValueError('INITIAL_SITES must be set when using manual approach')
        candidate_pairs = INITIAL_SITES
        print(f'Using {len(candidate_pairs)} manually specified initial sites')
    return (
        INITIAL_SBS_TILES,
        INITIAL_SITES,
        INITIAL_SITES_APPROACH,
        candidate_pairs,
    )


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
    candidate_pairs,
    get_filename,
    hash_cell_locations,
    initial_alignment,
    pd,
):
    _row2, _col2 = TEST_WELL[0], TEST_WELL[1:]
    _phenotype_info_fp = ROOT_FP / 'phenotype' / 'parquets' / str(TEST_PLATE) / _row2 / _col2 / 'phenotype_info.parquet'
    phenotype_info_1 = pd.read_parquet(_phenotype_info_fp)
    phenotype_info_hash = hash_cell_locations(phenotype_info_1)
    _sbs_info_fp = ROOT_FP / 'sbs' / 'parquets' / str(TEST_PLATE) / _row2 / _col2 / 'sbs_info.parquet'
    sbs_info_1 = pd.read_parquet(_sbs_info_fp)
    sbs_info_hash = hash_cell_locations(sbs_info_1).rename(columns={'tile': 'site'})
    initial_alignment_df = initial_alignment(phenotype_info_hash, sbs_info_hash, initial_sites=candidate_pairs)
    initial_alignment_df
    return initial_alignment_df, phenotype_info_1, sbs_info_1


@app.cell(hide_code=True)
def _(mo):
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
def _(DET_RANGE, initial_alignment_df):
    # Validate that enough pairs pass the thresholds
    d0, d1 = DET_RANGE
    valid_pairs_df = initial_alignment_df.query(
        "@d0 <= determinant <= @d1 & score > @SCORE"
    )

    print(f"\n{'='*50}")
    print(f"VALIDATION RESULTS")
    print(f"{'='*50}")
    print(f"Total candidate pairs: {len(initial_alignment_df)}")
    print(f"Pairs passing thresholds: {len(valid_pairs_df)}")
    print(f"Minimum required: 5")
    print(f"{'='*50}")

    if len(valid_pairs_df) < 5:
        print(f"\nWARNING: Only {len(valid_pairs_df)} pairs pass thresholds!")
        print("The pipeline requires at least 5 valid pairs.")
        print("Consider:")
        print("  - Adjusting DET_RANGE or SCORE thresholds")
        print("  - Adding more SBS tiles to INITIAL_SBS_TILES")
        print("  - Using manual INITIAL_SITES with known good pairs")
    else:
        print(f"\nValidation passed! {len(valid_pairs_df)} pairs will be used.")
    
    # Show which pairs passed
    print(f"\nValid pairs (tile, site):")
    for _, row in valid_pairs_df.iterrows():
        print(f"  [{int(row['tile'])}, {int(row['site'])}] - score: {row['score']:.3f}, det: {row['determinant']:.6f}")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Visualize cell matches based on initial alignment

    - `THRESHOLD`: Determines the maximum euclidean distance between a phenotype point and its matched SBS point for them to be considered a valid match
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    THRESHOLD = None                   # e.g., 2
    # === END OPERATOR PARAMETERS ===
    return (THRESHOLD,)


@app.cell
def _(
    THRESHOLD,
    candidate_pairs,
    fast_merge_example,
    initial_alignment_df,
    phenotype_info_1,
    sbs_info_1,
):
    for _ph_tile, sbs_site in candidate_pairs:
        success = fast_merge_example(_ph_tile, sbs_site, initial_alignment_df, phenotype_info_1, sbs_info_1, THRESHOLD)
        if not success:
            print(f'  Try a different tile-site combination or proceed to stitch approach.')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS (OPTIONAL): STITCH APPROACH</font>

    ### Parameters for image stitching

    If no successful initial sites can be configured or results show poor performance, try the stitch-based merge approach.

    `STITCH`: Whether to merge using stitch approach. This approach stitches the images into wells before performing alignment, merge, and deduplication.

    `MASK_TYPE`: Type of object to align.
    - `"nuclei"` uses segmented nuclei masks.
    - `"cells"` uses segmented cell masks.

    ### Parameters for image orientation
    Each microscope handles individual tile coordinates differently for stitching. Adjust the following parameters until you obtain images that look right.

    `FLIPUD`: Flip images upside-down (vertical flip). Defaults `False`.

    `FLIPLR`: Flip images left-to-right (horizontal flip). Defaults `False`.

    `ROT90`: Number of 90° rotations to apply to the image. For example, ROT90_K = 1 rotates the image 90° clockwise, ROT90_K = 2 rotates 180°, and so on.

    `NUM_TILES_PHENO` & `NUM_TILES_SBS`: For testing purposes, number of tiles to display. Higher numbers may increase processing time but allow a larger view of the well.

    **Eval Options:**
    - `STITCHED_IMAGE`: Determines whether a stitched image will be produced for qc. **Note:** Setting this to True will significantly increase processing time but it is recommended on the first run.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS (STITCH APPROACH — optional) ===
    STITCH = False
    MASK_TYPE = "nuclei"
    FLIPUD = False
    FLIPLR = False
    ROT90 = 0
    STITCHED_IMAGE = False
    # === END OPERATOR PARAMETERS ===
    return FLIPLR, FLIPUD, MASK_TYPE, ROT90, STITCH, STITCHED_IMAGE


@app.cell
def _(
    FLIPLR,
    FLIPUD,
    MASK_TYPE,
    ROOT_FP,
    ROT90,
    STITCH,
    ph_test_metadata,
    preview_mask_transformations,
):
    # === OPERATOR PARAMETERS ===
    NUM_TILES_PHENO = None  # int (e.g., 10) to preview that many phenotype tiles; only used when STITCH=True
    # === END OPERATOR PARAMETERS ===

    if STITCH:
        print("Testing phenotype data:")
        ph_params = preview_mask_transformations(
            ph_test_metadata,
            ROOT_FP,
            "phenotype",
            mask_type=MASK_TYPE,
            num_tiles=NUM_TILES_PHENO,
            flipud=FLIPUD,
            fliplr=FLIPLR,
            rot90=ROT90
        )
    return


@app.cell
def _(
    FLIPLR,
    FLIPUD,
    MASK_TYPE,
    ROOT_FP,
    ROT90,
    STITCH,
    preview_mask_transformations,
    sbs_test_metadata,
):
    # === OPERATOR PARAMETERS ===
    NUM_TILES_SBS = None  # int (e.g., 10) to preview that many SBS tiles; only used when STITCH=True
    # === END OPERATOR PARAMETERS ===

    if STITCH:
        print("\nTesting SBS data with same transformation:")
        sbs_params = preview_mask_transformations(
            sbs_test_metadata,
            ROOT_FP, 
            "sbs",
            mask_type=MASK_TYPE,
            num_tiles=NUM_TILES_SBS,
            flipud=FLIPUD,
            fliplr=FLIPLR,
            rot90=ROT90
        )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Set pixel size (optional)
    Coordinate-based stitching converts stage coordinates (in micrometers) to pixel coordinates. If pixel size is not available in your image metadata you will have to set it manually below.

    `SBS_PIXEL_SIZE`: Pixel size (in μm/pixel) of SBS images.
    `PHENOTYPE_PIXEL_SIZE`: Pixel size (in μm/pixel) of phenotyping images.
    """)
    return


@app.cell
def _(STITCH, ph_test_metadata, sbs_test_metadata):
    if STITCH:
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
    ## <font color='red'>SET PARAMETERS (OPTIONAL): ADVANCED FAST-MERGE LEVERS</font>

    Tune the fast-merge alignment + warp. **All default to `None` (pipeline built-in values) — leave them unless a merge is underperforming.** Only levers set to a non-`None` value are written to `config.yml`. Only levers with measured impact are surfaced.

    **Two-microscope / rotated acquisitions — validated high-impact fix (Vaishnavi well A1: median 0.91px -> 0.08px, coverage 59% -> 92%). Strongly recommended for two-scope screens:**

    - `SEED_OPTIMIZE`: evaluate the top-`SEED_TOPK` nearest phenotype tiles per SBS seed and keep the best (vs the stage-nearest tile, often not the true overlap). Rec. `True`.
    - `SEED_TOPK`: nearest tiles to evaluate. Rec. `3`.
    - `LOCAL_REFINEMENT`: within-tile warp model, `"polynomial"` | `"thin_plate_spline"`. **TPS is the biggest quality lever on two-scope data (0.08px)**; polynomial is the robust generalizer. Rec. `"thin_plate_spline"` (two-scope), else `"polynomial"`.
    - `WARP_SMOOTHING`: TPS regularization. Rec. `10`.

    **Cross-optics generalized winner (all four datasets, 0.05% tax):**

    - `WARP_DEGREE`: polynomial warp degree. Rec. `3` (pipeline default `2`).
    - `WARP_ITERATIONS`: refine-and-rematch passes. Rec. `2`.
    - `THRESHOLD_TRIANGLE`: max triangle-hash match distance. Rec. `0.3`.
    - `RANSAC_RANDOM_STATE`: pin RANSAC for reproducibility (determinism, not quality). Rec. `0`.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS: ADVANCED FAST-MERGE LEVERS ===
    # All None => pipeline default. TPS + find-optimal-site recommended for two-scope screens.
    SEED_OPTIMIZE = None          # keep best of top-K nearest PH tiles per SBS seed; rec. True (two-scope)
    SEED_TOPK = None              # nearest tiles to evaluate when SEED_OPTIMIZE; rec. 3
    LOCAL_REFINEMENT = None       # None | "polynomial" | "thin_plate_spline"; rec. "thin_plate_spline" (two-scope)
    WARP_SMOOTHING = None         # thin-plate-spline regularization; rec. 10
    WARP_DEGREE = None            # polynomial warp degree; rec. 3
    WARP_ITERATIONS = None        # refine-and-rematch passes; rec. 2
    THRESHOLD_TRIANGLE = None     # triangle hash-match distance; rec. 0.3
    RANSAC_RANDOM_STATE = None    # pin RANSAC for reproducibility; rec. 0
    # === END OPERATOR PARAMETERS ===
    return (
        LOCAL_REFINEMENT,
        RANSAC_RANDOM_STATE,
        SEED_OPTIMIZE,
        SEED_TOPK,
        THRESHOLD_TRIANGLE,
        WARP_DEGREE,
        WARP_ITERATIONS,
        WARP_SMOOTHING,
    )


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
    RANSAC_RANDOM_STATE,
    ROT90,
    SBS_DEDUP_PRIOR,
    SBS_DIMENSIONS,
    SBS_METADATA_CHANNEL,
    SBS_METADATA_CYCLE,
    SBS_PIXEL_SIZE_1,
    SCORE,
    SEED_OPTIMIZE,
    SEED_TOPK,
    STITCH,
    STITCHED_IMAGE,
    THRESHOLD,
    THRESHOLD_TRIANGLE,
    WARP_DEGREE,
    WARP_ITERATIONS,
    WARP_SMOOTHING,
    config,
    convert_tuples_to_lists,
    yaml,
):
    config['merge'] = {'approach': 'stitch' if STITCH else 'fast', 'merge_combo_fp': MERGE_COMBO_DF_FP, 'phenotype_dimensions': PHENOTYPE_DIMENSIONS, 'sbs_dimensions': SBS_DIMENSIONS, 'sbs_metadata_cycle': SBS_METADATA_CYCLE, 'score': SCORE, 'threshold': THRESHOLD, 'sbs_metadata_channel': SBS_METADATA_CHANNEL, 'ph_metadata_channel': PH_METADATA_CHANNEL, 'metadata_align': METADATA_ALIGN, 'alignment_flip_x': ALIGNMENT_FLIP_X, 'alignment_flip_y': ALIGNMENT_FLIP_Y, 'alignment_rotate_90': ALIGNMENT_ROTATE_90, 'sbs_dedup_prior': SBS_DEDUP_PRIOR, 'pheno_dedup_prior': PHENO_DEDUP_PRIOR}
    if STITCH:
        config['merge'].update({'stitched_image': STITCHED_IMAGE, 'flipud': FLIPUD, 'fliplr': FLIPLR, 'rot90': ROT90, 'sbs_pixel_size': SBS_PIXEL_SIZE_1, 'phenotype_pixel_size': PHENOTYPE_PIXEL_SIZE_1})
    elif INITIAL_SITES_APPROACH == 'auto':
        config['merge'].update({'initial_sbs_tiles': INITIAL_SBS_TILES, 'det_range': DET_RANGE})
        print(f'Config will use initial_sbs_tiles: {INITIAL_SBS_TILES}')
    else:
        config['merge'].update({'initial_sites': INITIAL_SITES, 'det_range': DET_RANGE})
        print(f'Config will use initial_sites: {len(INITIAL_SITES)} pairs')
    # Advanced fast-merge levers - only written when set (absent keys => pipeline defaults)
    advanced_merge_levers = {'seed_optimize': SEED_OPTIMIZE, 'seed_topk': SEED_TOPK, 'local_refinement': LOCAL_REFINEMENT, 'warp_smoothing': WARP_SMOOTHING, 'warp_degree': WARP_DEGREE, 'warp_iterations': WARP_ITERATIONS, 'threshold_triangle': THRESHOLD_TRIANGLE, 'ransac_random_state': RANSAC_RANDOM_STATE}
    config['merge'].update({_k: _v for _k, _v in advanced_merge_levers.items() if _v is not None})
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
