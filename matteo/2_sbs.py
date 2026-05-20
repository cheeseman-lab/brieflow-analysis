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
    # Configure SBS Parameters

    This notebook should be used as a test for ensuring correct SBS image loading and processing before running the SBS module.
    Cells marked with <font color='red'>SET PARAMETERS</font> contain crucial variables that need to be set according to your specific experimental setup and data organization.
    Please review and modify these variables as needed before proceeding with the analysis.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Fixed parameters for SBS processing

    - `CONFIG_FILE_PATH`: Path to a Brieflow config file used during processing. Absolute or relative to where workflows are run from.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    CONFIG_FILE_PATH = "config/config.yml"
    # === END OPERATOR PARAMETERS ===
    return (CONFIG_FILE_PATH,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Imports
    """)
    return


@app.cell
def _():
    from pathlib import Path

    import yaml
    from lib.shared.image_io import read_image
    import pandas as pd
    from snakemake.io import expand
    from microfilm.microplot import Microimage
    import matplotlib.pyplot as plt
    import numpy as np
    import seaborn as sns

    from lib.shared.configuration_utils import (
        CONFIG_FILE_HEADER,
        create_micropanel,
        random_cmap,
        image_segmentation_annotations,
        convert_tuples_to_lists,
    )
    from lib.shared.file_utils import get_filename, get_hcs_nested_path
    from lib.sbs.align_cycles import align_cycles, visualize_sbs_alignment
    from lib.shared.log_filter import log_filter
    from lib.sbs.compute_standard_deviation import compute_standard_deviation
    from lib.sbs.max_filter import max_filter
    from lib.sbs.find_peaks import (
        find_peaks,
        find_peaks_spotiflow,
        plot_channels_with_peaks,
    )
    from lib.shared.illumination_correction import apply_ic_field, combine_ic_images
    from lib.shared.segment_cellpose import prepare_cellpose
    from lib.cluster.scrape_benchmarks import get_uniprot_data
    from lib.sbs.standardize_barcode_design import (
        standardize_barcode_design,
        get_barcode_list,
        get_gene_mapping,
    )
    from lib.sbs.extract_bases import extract_bases
    from lib.sbs.call_reads import call_reads, plot_normalization_comparison
    from lib.sbs.call_cells import call_cells
    from lib.shared.extract_phenotype_minimal import extract_phenotype_minimal
    from lib.sbs.eval_mapping import (
        plot_mapping_vs_threshold,
        plot_cell_mapping_heatmap,
        plot_cell_metric_histogram,
        plot_gene_symbol_histogram,
        plot_barcode_prefix_matching,
    )

    return (
        CONFIG_FILE_HEADER,
        Microimage,
        Path,
        align_cycles,
        apply_ic_field,
        call_cells,
        call_reads,
        combine_ic_images,
        compute_standard_deviation,
        convert_tuples_to_lists,
        create_micropanel,
        expand,
        extract_bases,
        extract_phenotype_minimal,
        find_peaks,
        find_peaks_spotiflow,
        get_barcode_list,
        get_filename,
        get_gene_mapping,
        get_hcs_nested_path,
        get_uniprot_data,
        image_segmentation_annotations,
        log_filter,
        max_filter,
        np,
        pd,
        plot_barcode_prefix_matching,
        plot_cell_mapping_heatmap,
        plot_cell_metric_histogram,
        plot_channels_with_peaks,
        plot_gene_symbol_histogram,
        plot_mapping_vs_threshold,
        plot_normalization_comparison,
        plt,
        prepare_cellpose,
        random_cmap,
        read_image,
        sns,
        standardize_barcode_design,
        visualize_sbs_alignment,
        yaml,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Parameters for testing SBS processing

    - `TEST_PLATE`, `TEST_WELL`, `TEST_TILE`: Plate/well/tile combination used for configuring parameters in this notebook.

    ### Channels

    - `CHANNEL_NAMES`: A list of ordered names for each channel in your SBS image.
    - `CHANNEL_CMAPS`: A list of color maps to use when showing channel microimages. These need to be a Matplotlib or microfilm colormap. We recommend using: `["pure_red", "pure_green", "pure_blue", "pure_cyan", "pure_magenta", "pure_yellow"]`.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    TEST_PLATE = None
    TEST_WELL = None
    TEST_TILE = None
    CHANNEL_NAMES = None  # e.g., ["DAPI", "G", "T", "A", "C"]
    CHANNEL_CMAPS = None
    # === END OPERATOR PARAMETERS ===

    # Derive wildcard dictionary for testing
    WILDCARDS = dict(well=TEST_WELL, tile=TEST_TILE)
    # Remove DAPI channel to get bases
    BASES = [channel for channel in CHANNEL_NAMES if channel in ["G", "T", "A", "C"]]
    EXTRA_CHANNELS = [
        channel for channel in CHANNEL_NAMES if channel not in ["G", "T", "A", "C"]
    ]
    return (
        BASES,
        CHANNEL_CMAPS,
        CHANNEL_NAMES,
        EXTRA_CHANNELS,
        TEST_PLATE,
        TEST_TILE,
        TEST_WELL,
        WILDCARDS,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

      ### Alignment
      - `ALIGNMENT_METHOD`: Optional. Method for aligning SBS images between cycles. If not specified, the method will be automatically selected based on available channels, but can be overridden by the user:
          - `DAPI`: the DAPI channel is used for alignment between cycles. Automatically selected if **DAPI is present in each** round of SBS imaging.
          - `sbs_mean`: the mean intensity of base channels is used for alignment between cycles. Automatically selected if **DAPI is not present in each** round of SBS imaging.
      - `UPSAMPLE_FACTOR`: Factor used for subpixel alignment. Defaults to `2`
          - Higher values provide more precise alignment but increase processing time.
          - Set to `1` to disable subpixel alignment for faster processing.
      - `WINDOW`: A centered subset of data is used for alignment if greater than one. Defaults to `2`
          - Higher values use more of the image for alignment registration.
          - Set to `1` to use the full image.
      - `SKIP_CYCLES`: Optional. List of cycle indices to skip during alignment. Defaults to `None`
          - Use this to exclude problematic cycles that would interfere with alignment
          - Example: `[1]` to skip the first cycle, `[1, 6]` to skip cycles 1 and 6
          - Skipped cycles are completely removed from processing and will not appear in final results
      - `MANUAL_BACKGROUND_CYCLE`: Optional. Specific cycle to use as the source for segmentation background channels. Defaults to `None`
          - Use this when you have segmentation channels (e.g., DAPI, Vimentin) in a specific cycle that you want propagated to all cycles
          - If not specified, automatically selects the cycle with the most extra (non-GTAC) channels
          - Example: `3` to use cycle 3 as the source for background channels
          - Note: This refers to the original cycle number before any cycles are skipped
          - **Only works with simple channel configurations** (see note below)
      - `MANUAL_CHANNEL_MAPPING`: Optional. Explicit specification of which channels are present in each cycle. Defaults to `None`
          - Required when channel structure varies across cycles in non-standard ways
          - Provide a list of channel name lists, one per cycle, matching the order channels appear in each cycle's image data
          - The function will map channels by name to create the final output matching `CHANNEL_NAMES`

      **Note on Channel Configuration:**

      SBS images are commonly generated in two ways:
      1. **Same channels across all cycles** - All cycles have identical channel structure (e.g., all have DAPI, Vimentin, G, T, A, C)
      2. **Base channels + one background cycle** - Most cycles have only base channels (G, T, A, C), and one cycle has additional channels for segmentation (e.g., DAPI, Vimentin) at the beginning or end of the channel array

      If your imaging setup deviates from these approaches (e.g., some cycles missing channels that are in the middle of your target channel order), you must use `MANUAL_CHANNEL_MAPPING` to explicitly specify which channels are
      present in each cycle.

      **Example:** If `CHANNEL_NAMES = ["DAPI", "Vimentin", "G", "T", "A", "C"]` but only cycle 3 has Vimentin:

      ```python
      MANUAL_CHANNEL_MAPPING = [
          ["DAPI", "G", "T", "A", "C"],              # Cycle 1: no Vimentin
          ["DAPI", "G", "T", "A", "C"],              # Cycle 2: no Vimentin
          ["DAPI", "Vimentin", "G", "T", "A", "C"],  # Cycle 3: has Vimentin
          ["DAPI", "G", "T", "A", "C"],              # Cycle 4: no Vimentin
          # ... repeat for all cycles
      ]
      MANUAL_BACKGROUND_CYCLE = 3  # Source for Vimentin propagation
      ```

      The function will copy Vimentin from cycle 3 to all other cycles, creating output with shape (n_cycles, 6, height, width) where all cycles have the full `CHANNEL_NAMES` channel order.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    ALIGNMENT_METHOD = None
    UPSAMPLE_FACTOR = 2  # library default
    WINDOW = 2  # library default
    SKIP_CYCLES = None
    MANUAL_BACKGROUND_CYCLE = None
    MANUAL_CHANNEL_MAPPING = None
    # === END OPERATOR PARAMETERS ===
    return (
        ALIGNMENT_METHOD,
        MANUAL_BACKGROUND_CYCLE,
        MANUAL_CHANNEL_MAPPING,
        SKIP_CYCLES,
        UPSAMPLE_FACTOR,
        WINDOW,
    )


@app.cell
def _(
    ALIGNMENT_METHOD,
    CHANNEL_CMAPS,
    CHANNEL_NAMES,
    CONFIG_FILE_PATH,
    MANUAL_BACKGROUND_CYCLE,
    MANUAL_CHANNEL_MAPPING,
    Microimage,
    Path,
    SKIP_CYCLES,
    TEST_PLATE,
    TEST_TILE,
    TEST_WELL,
    UPSAMPLE_FACTOR,
    WINDOW,
    align_cycles,
    create_micropanel,
    expand,
    get_filename,
    get_hcs_nested_path,
    pd,
    plt,
    read_image,
    yaml,
):
    # Load config file
    with open(CONFIG_FILE_PATH, "r") as _config_file:
        config = yaml.safe_load(_config_file)
    SBS_SAMPLES_FP = Path(config["preprocess"]["sbs_samples_fp"])
    # Get paths to the sample files dfs
    sbs_samples = pd.read_csv(SBS_SAMPLES_FP, sep="\t")
    # Load the sample TSV files
    SBS_CYCLES = sorted(list(sbs_samples["cycle"].unique()))
    SKIP_CYCLES_INDICES = (
        [SBS_CYCLES.index(c) for c in SKIP_CYCLES] if SKIP_CYCLES is not None else None
    )
    # Define cycles for testing if not None
    MANUAL_BACKGROUND_CYCLE_INDEX = (
        SBS_CYCLES.index(MANUAL_BACKGROUND_CYCLE)
        if MANUAL_BACKGROUND_CYCLE is not None
        else None
    )
    print("Loading test images...")
    ROOT_FP = Path(config["all"]["root_fp"])
    # Load test image data
    PREPROCESS_FP = ROOT_FP / "preprocess"
    IMAGE_FORMAT = config["all"].get("image_format", "tiff")
    if IMAGE_FORMAT == "zarr":
        sbs_test_image_paths = expand(
            PREPROCESS_FP
            / "sbs"
            / get_hcs_nested_path(
                {
                    "plate": TEST_PLATE,
                    "row": TEST_WELL[0],
                    "col": TEST_WELL[1:],
                    "tile": TEST_TILE,
                    "cycle": "{cycle}",
                },
                "image",
            ),
            cycle=SBS_CYCLES,
        )
    else:
        sbs_test_image_paths = expand(
            PREPROCESS_FP
            / "sbs"
            / get_filename(
                {
                    "plate": TEST_PLATE,
                    "well": TEST_WELL,
                    "tile": TEST_TILE,
                    "cycle": "{cycle}",
                },
                "image",
                "tiff",
            ),
            cycle=SBS_CYCLES,
        )
    sbs_test_images = [read_image(file_path) for file_path in sbs_test_image_paths]
    print("Aligning test images...")
    aligned = align_cycles(
        sbs_test_images,
        channel_order=CHANNEL_NAMES,
        method=ALIGNMENT_METHOD,
        upsample_factor=UPSAMPLE_FACTOR,
        window=WINDOW,
        skip_cycles=SKIP_CYCLES_INDICES,
        manual_background_cycle=MANUAL_BACKGROUND_CYCLE_INDEX,
        manual_channel_mapping=MANUAL_CHANNEL_MAPPING,
    )
    print("Example aligned image for first cycle:")
    _aligned_microimages_c0 = [
        Microimage(
            aligned[0, i, :, :], channel_names=CHANNEL_NAMES[i], cmaps=CHANNEL_CMAPS[i]
        )
        for i in range(aligned.shape[1])
    ]
    _aligned_panel_c0 = create_micropanel(
        _aligned_microimages_c0, add_channel_label=True
    )
    # Align cycles
    # Create and display micropanel of aligned images
    # NOTE: You can also loop through all your cycles to display micropanels to be sure of alignment by uncommenting the following lines:
    # for cycle_idx in range(aligned.shape[0]):  # Adjust this range if you have a different number of cycles
    #     print(f"Example aligned image for cycle {cycle_idx + 1}:")
    #     aligned_microimages = [
    #         Microimage(
    #             aligned[cycle_idx, i, :, :], channel_names=CHANNEL_NAMES[i], cmaps=CHANNEL_CMAPS[i]
    #         )
    #         for i in range(aligned.shape[1])
    #     ]
    #     aligned_panel = create_micropanel(aligned_microimages, add_channel_label=True)
    #     plt.show()
    plt.show()
    return (
        MANUAL_BACKGROUND_CYCLE_INDEX,
        PREPROCESS_FP,
        SBS_CYCLES,
        SKIP_CYCLES_INDICES,
        aligned,
        config,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Visualize Alignment (Optional)

    #### Within-Cycle
    Verify that all channels are properly structured for a given cycle.
    - `VIZ_CYCLE`: Cycle index to display (0-indexed). Shows all channels as a micropanel.

    #### Between-Cycle
    Verify base channels are properly aligned across cycles. Shows 3 locations (corner, center, random) with DAPI reference (grayscale) and base channels from different cycles (RGB overlay). Color fringing indicates misalignment.
    - `DAPI_REFERENCE_CYCLE`: Cycle index for DAPI anatomical reference (shown as grayscale)
    - `VIZ_CHANNELS`: List of 3 `(cycle_idx, channel_name)` tuples for RGB overlay (e.g., `[(0, "G"), (5, "T"), (10, "A")]`)
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    VIZ_CYCLE = 0
    DAPI_REFERENCE_CYCLE = 0
    VIZ_CHANNELS = None  # e.g., [(0, "G"), (5, "T"), (10, "A")]
    # === END OPERATOR PARAMETERS ===
    return DAPI_REFERENCE_CYCLE, VIZ_CHANNELS, VIZ_CYCLE


@app.cell
def _(
    CHANNEL_CMAPS,
    CHANNEL_NAMES,
    Microimage,
    VIZ_CYCLE,
    aligned,
    create_micropanel,
    plt,
):
    if VIZ_CYCLE is not None:
        print(f"Aligned image for cycle {VIZ_CYCLE + 1}:")
        aligned_microimages = [
            Microimage(
                aligned[VIZ_CYCLE, i, :, :],
                channel_names=CHANNEL_NAMES[i],
                cmaps=CHANNEL_CMAPS[i],
            )
            for i in range(aligned.shape[1])
        ]
        aligned_panel = create_micropanel(aligned_microimages, add_channel_label=True)
        plt.show()
    return


@app.cell
def _(
    CHANNEL_NAMES,
    DAPI_REFERENCE_CYCLE,
    VIZ_CHANNELS,
    aligned,
    plt,
    visualize_sbs_alignment,
):
    if VIZ_CHANNELS is not None:
        print("Visualizing alignment...")
        alignment_fig = visualize_sbs_alignment(
            aligned, CHANNEL_NAMES, DAPI_REFERENCE_CYCLE, VIZ_CHANNELS, crop_size=300
        )
        plt.show()
    else:
        print("Skipping visualization (VIZ_CHANNELS not set)")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Spot detection

    - `MAX_FILTER_WIDTH`: Width parameter used for determining the neighborhood size for finding local maxima. No default value, but `3` is suggested
    - `SPOT_DETECTION_METHOD`: Methodology for calling spots:
        - `STANDARD`: Standard method for calling spots, involving Laplacian of Gaussian correction, and computation of spots across cycles. Spots are identified based on signal intensity and consistency across cycles.
            - `PEAK_WIDTH`: Width parameter used for peak detection, sets neighborhood size for finding local maxima of base channels standard deviation. Defaults to `5`
        - `SPOTIFLOW`: Deep learning based methodology for calling spots. Spots are called independently on all 4 bases of a selected cycle, and then coalesced to ensure minimum distance between spots. If this method is selected, the following parameters are required:
            - `SPOTIFLOW_CYCLE_INDEX`: Cycle to use for spot detection
            - `SPOTIFLOW_MODEL`: Model to use for spot detection (e.g., "general", "hybiss")
            - `SPOTIFLOW_THRESHOLD`: Probability threshold for confidence in spot detection
            - `SPOTIFLOW_MIN_DISTANCE`: Minimum distance (in pixels) required between detected spots

    **Note on Spotiflow:** Spotiflow returns binary spot locations (present/absent) rather than continuous intensity values. As a result, `THRESHOLD_READS` should be set to `0` when using Spotiflow, and the "Mapping rate vs. peak threshold" QC plot will not provide meaningful threshold optimization (all spots have the same binary value).
    """)
    return


@app.cell
def _(CHANNEL_NAMES, EXTRA_CHANNELS):
    # === OPERATOR PARAMETERS ===
    MAX_FILTER_WIDTH = 3  # library default
    SPOT_DETECTION_METHOD = "standard"  # "standard" | "spotiflow"
    if SPOT_DETECTION_METHOD == "standard":
        PEAK_WIDTH = 5

    elif SPOT_DETECTION_METHOD == "spotiflow":
        SPOTIFLOW_CYCLE_INDEX = 0
        SPOTIFLOW_MODEL = "general"
        SPOTIFLOW_THRESHOLD = 0.3
        SPOTIFLOW_MIN_DISTANCE = 1
    # === END OPERATOR PARAMETERS ===

    # Derive extra channel indices
    EXTRA_CHANNEL_INDICES = [CHANNEL_NAMES.index(channel) for channel in EXTRA_CHANNELS]
    return (
        EXTRA_CHANNEL_INDICES,
        MAX_FILTER_WIDTH,
        PEAK_WIDTH,
        SPOTIFLOW_CYCLE_INDEX,
        SPOTIFLOW_MIN_DISTANCE,
        SPOTIFLOW_MODEL,
        SPOTIFLOW_THRESHOLD,
        SPOT_DETECTION_METHOD,
    )


@app.cell
def _(
    BASES,
    CHANNEL_CMAPS,
    EXTRA_CHANNEL_INDICES,
    MAX_FILTER_WIDTH,
    Microimage,
    PEAK_WIDTH,
    SPOTIFLOW_CYCLE_INDEX,
    SPOTIFLOW_MIN_DISTANCE,
    SPOTIFLOW_MODEL,
    SPOTIFLOW_THRESHOLD,
    SPOT_DETECTION_METHOD,
    aligned,
    compute_standard_deviation,
    create_micropanel,
    find_peaks,
    find_peaks_spotiflow,
    log_filter,
    max_filter,
    plot_channels_with_peaks,
    plt,
):
    print("Detecting candidate reads...")

    print("Applying Laplacian-of-Gaussian (LoG) filter...")
    loged = log_filter(aligned, skip_index=EXTRA_CHANNEL_INDICES)

    print("Applying max filter...")
    maxed = max_filter(
        loged, width=MAX_FILTER_WIDTH, remove_index=EXTRA_CHANNEL_INDICES
    )

    if SPOT_DETECTION_METHOD == "standard":
        print("Computing standard deviation over cycles...")
        standard_deviation = compute_standard_deviation(
            loged, remove_index=EXTRA_CHANNEL_INDICES
        )

        print("Finding peaks using standard method...")
        peaks = find_peaks(standard_deviation, width=PEAK_WIDTH)

    elif SPOT_DETECTION_METHOD == "spotiflow":
        print(f"Finding peaks using Spotiflow (model: {SPOTIFLOW_MODEL})...")
        peaks, _ = find_peaks_spotiflow(
            aligned_images=aligned,
            cycle_idx=SPOTIFLOW_CYCLE_INDEX,
            model=SPOTIFLOW_MODEL,
            prob_thresh=SPOTIFLOW_THRESHOLD,
            min_distance=SPOTIFLOW_MIN_DISTANCE,
            remove_index=EXTRA_CHANNEL_INDICES,
            verbose=True,
        )

    # Create and display micropanel of max filtered datas
    print("Example max filtered image for first cycle:")
    maxed_microimages = [
        Microimage(
            maxed[1, i, :, :], channel_names=BASES[i], cmaps=CHANNEL_CMAPS[i + 1]
        )
        for i in range(maxed.shape[1])
    ]
    maxed_panel = create_micropanel(maxed_microimages, add_channel_label=True)
    plt.show()

    # Plot spots on base channels
    fig, axes = plot_channels_with_peaks(
        maxed,
        peaks,
        BASES,
        cycle_number=0,
        threshold_peaks=200 if SPOT_DETECTION_METHOD == "standard" else None,
        peak_colors=["orange"],
        peak_labels=["Detected Peaks"],
    )
    plt.show()
    return maxed, peaks


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Illumination Correction and Segmentation

    These parameters specify which cycle and channels to use for cell segmentation. All three are required.

    - `DAPI_CYCLE`: Cycle number containing DAPI. This cycle must also contain any cellular stain you want to use for segmentation (e.g., Vimentin, GFP, Phalloidin).
    - `CYTO_CYCLE`: Cycle number for the cytoplasmic channel. Set equal to `DAPI_CYCLE` when using a cellular stain.
    - `CYTO_CHANNEL`: Name of the channel used for cell boundary detection.

    **Common Configurations:**

    1. **Using a cellular stain** (recommended): Set `DAPI_CYCLE = CYTO_CYCLE` to the cycle containing both DAPI and your stain.
       - Example: `DAPI_CYCLE = 1`, `CYTO_CYCLE = 1`, `CYTO_CHANNEL = "Vimentin"`

    2. **No cellular stain available**: Set `CYTO_CYCLE` to any cycle and use a base channel (G, T, A, or C) for cytoplasm detection.
       - Example: `DAPI_CYCLE = 1`, `CYTO_CYCLE = 5`, `CYTO_CHANNEL = "G"`

    **Note:** If you don't need cell segmentation (nuclei-only), use configuration 1 and set `SEGMENT_CELLS = False` in the Segmentation section below.
    """)
    return


@app.cell
def _(BASES, CHANNEL_NAMES, SBS_CYCLES, SKIP_CYCLES):
    # === OPERATOR PARAMETERS ===
    DAPI_CYCLE = None
    CYTO_CYCLE = None
    CYTO_CHANNEL = None
    # === END OPERATOR PARAMETERS ===

    # Derive DAPI and CYTO indexes
    DAPI_INDEX = CHANNEL_NAMES.index("DAPI")
    CYTO_INDEX = CHANNEL_NAMES.index(CYTO_CHANNEL)
    DAPI_CYCLE_INDEX = SBS_CYCLES.index(DAPI_CYCLE) - len(
        [skip for skip in (SKIP_CYCLES or []) if skip < SBS_CYCLES.index(DAPI_CYCLE)]
    )
    CYTO_CYCLE_INDEX = SBS_CYCLES.index(CYTO_CYCLE) - len(
        [skip for skip in (SKIP_CYCLES or []) if skip < SBS_CYCLES.index(CYTO_CYCLE)]
    )

    # Validate DAPI and CYTO cycles and channels
    if DAPI_CYCLE != CYTO_CYCLE and CYTO_CHANNEL not in BASES:
        raise ValueError(
            f"When DAPI_CYCLE ({DAPI_CYCLE}) != CYTO_CYCLE ({CYTO_CYCLE}), "
            f"CYTO_CHANNEL should be a base channel {BASES}, but got '{CYTO_CHANNEL}'. "
            f"If using a cellular stain, set DAPI_CYCLE = CYTO_CYCLE."
        )
    return (
        CYTO_CYCLE,
        CYTO_CYCLE_INDEX,
        CYTO_INDEX,
        DAPI_CYCLE,
        DAPI_CYCLE_INDEX,
        DAPI_INDEX,
    )


@app.cell
def _(
    CYTO_CYCLE,
    CYTO_CYCLE_INDEX,
    CYTO_INDEX,
    DAPI_CYCLE,
    DAPI_CYCLE_INDEX,
    DAPI_INDEX,
    EXTRA_CHANNEL_INDICES,
    Microimage,
    PREPROCESS_FP,
    TEST_PLATE,
    TEST_WELL,
    aligned,
    apply_ic_field,
    combine_ic_images,
    create_micropanel,
    get_filename,
    plt,
    prepare_cellpose,
    read_image,
):
    # Logic based on whether DAPI and CYTO come from same or different cycles
    if DAPI_CYCLE != CYTO_CYCLE:
        # Different cycles - need to combine image data AND IC fields from both cycles
        print(f"DAPI cycle ({DAPI_CYCLE}) != CYTO cycle ({CYTO_CYCLE})")
        print("Combining image data and IC fields from both cycles...")

        # Combine image data from both cycles (DAPI channels from DAPI cycle, base channels from CYTO cycle)
        aligned_image_data_segmentation_cycle = combine_ic_images(
            [aligned[DAPI_CYCLE_INDEX], aligned[CYTO_CYCLE_INDEX]],
            [EXTRA_CHANNEL_INDICES, None],
        )

        # Load and combine IC fields (HCS-nested zarr layout: <plate>/<row>/<col>/<cycle>/ic_field.zarr)
        _row, _col = TEST_WELL[0], TEST_WELL[1:]
        ic_field_dapi = read_image(
            PREPROCESS_FP
            / "ic_fields"
            / "sbs"
            / str(TEST_PLATE)
            / _row
            / _col
            / str(DAPI_CYCLE)
            / "ic_field.zarr"
            / "zarr.json"
        )
        ic_field_cyto = read_image(
            PREPROCESS_FP
            / "ic_fields"
            / "sbs"
            / str(TEST_PLATE)
            / _row
            / _col
            / str(CYTO_CYCLE)
            / "ic_field.zarr"
            / "zarr.json"
        )
        ic_field = combine_ic_images(
            [ic_field_dapi, ic_field_cyto], [EXTRA_CHANNEL_INDICES, None]
        )
    else:
        # Same cycle - use single cycle for both image data and IC field
        aligned_image_data_segmentation_cycle = aligned[CYTO_CYCLE_INDEX]
        _row, _col = TEST_WELL[0], TEST_WELL[1:]
        ic_field = read_image(
            PREPROCESS_FP
            / "ic_fields"
            / "sbs"
            / str(TEST_PLATE)
            / _row
            / _col
            / str(DAPI_CYCLE)
            / "ic_field.zarr"
            / "zarr.json"
        )

    print("Applying illumination correction to segmentation cycle image...")
    # Apply illumination correction field
    corrected_image = apply_ic_field(
        aligned_image_data_segmentation_cycle, correction=ic_field
    )

    # Prepare corrected image for CellPose segmentation
    # NOTE: this process is done during the `segment_cellpose`` method below as well
    # Use the prepared_cellpose image to test CellPose (see below)
    print("Preparing IC segmentation image for CellPose...")
    cellpose_rgb = prepare_cellpose(
        corrected_image,
        DAPI_INDEX,
        CYTO_INDEX,
    )

    # show max filtered data for one round
    print("Pre-segmentation images:")
    pre_seg_microimages = [
        Microimage(cellpose_rgb[2], channel_names="Dapi"),
        Microimage(cellpose_rgb[1], channel_names="Cyto"),
    ]
    pre_seg_panel = create_micropanel(pre_seg_microimages, add_channel_label=True)
    plt.show()
    return cellpose_rgb, corrected_image


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Segmentation

    **IMPORTANT: GPU Recommendation for CPSAM**
    If testing the CPSAM model (`cellpose_model="cpsam"`), we strongly recommend:
    - Using a GPU-enabled machine (`GPU=True`)
    - Allocating sufficient time (segmentation can take 30+ minutes per tile)
    - Consider running this notebook in a GPU-enabled environment or testing on a smaller region

    #### Select Segmentation Method
    - `SEGMENTATION_METHOD`: Choose from "cellpose", "stardist", or "watershed" for cell segmentation.

    #### Common Parameters
    - `GPU`: Set to True to use GPU acceleration (if available).
    - `RECONCILE`: Method for reconciling nuclei and cell masks (typically "contained_in_cells", which allows more than one nucleus per cell and is useful for cells that are dividing).
    - `SEGMENT_CELLS`: Whether to segment cells, or only segment nuclei. If spots are contained in nuclei, there is no need to segment cell bodies. This may speed up analysis.

    #### Cellpose Parameters (if using "cellpose")
    - `CELLPOSE_MODEL`: CellPose model to use. Options: "cyto3" (default), "cyto2", "cyto", "nuclei", or "cpsam" (requires Cellpose 4.x).
      - When `SEGMENT_CELLS = True`: The "nuclei" model is always used for nuclei segmentation, and `CELLPOSE_MODEL` is used for cell segmentation.
      - When `SEGMENT_CELLS = False`: `CELLPOSE_MODEL` is used directly for nuclei segmentation. The default "cyto3" works well, but you can set to "nuclei" if preferred.
      - For CPSAM: The "cpsam" model is used for both nuclei and cells regardless of `SEGMENT_CELLS`.
    - `CELL_FLOW_THRESHOLD` & `NUCLEI_FLOW_THRESHOLD`: Flow threshold for Cellpose segmentation. Default is 0.4.
    - `CELL_CELLPROB_THRESHOLD` & `NUCLEI_CELLPROB_THRESHOLD`: Cell probability threshold for Cellpose. Default is 0.
    - `HELPER_INDEX`: (Optional) Index of additional channel to help with CPSAM segmentation. Only used with `cellpose_model="cpsam"`. Default is None.
    - Note: For Cellpose 3.x models (cyto3, cyto2), nuclei and cell diameters will be estimated automatically. For CPSAM (Cellpose 4.x), diameters can be left as None and will be estimated from initial segmentation results.

    #### StarDist Parameters (if using "stardist")
    - `STARDIST_MODEL`: StarDist model type. Default is "2D_versatile_fluo".
    - `CELL_PROB_THRESHOLD` & `NUCLEI_PROB_THRESHOLD`: Probability threshold for segmentation. Default is 0.479071.
    - `CELL_NMS_THRESHOLD` & `NUCLEI_NMS_THRESHOLD`: Non-maximum suppression threshold. Default is 0.3.

    #### Watershed Parameters (if using "watershed")
    - `THRESHOLD_DAPI`: Threshold for nuclei segmentation.
    - `THRESHOLD_CELL`: Threshold for cell boundary segmentation.
    - `NUCLEUS_AREA`: Range for filtering nuclei by area as a tuple (min, max).
    """)
    return


@app.cell
def _(CYTO_INDEX, DAPI_INDEX, corrected_image):
    # === OPERATOR PARAMETERS ===
    SEGMENTATION_METHOD = "cellpose"  # "cellpose" | "stardist"
    GPU = False
    RECONCILE = "contained_in_cells"
    SEGMENT_CELLS = True
    if SEGMENTATION_METHOD == "cellpose":
        # Parameters for CellPose method
        CELLPOSE_MODEL = "cyto3"
        NUCLEI_FLOW_THRESHOLD = 0.4
        NUCLEI_CELLPROB_THRESHOLD = 0.0
        CELL_FLOW_THRESHOLD = 1
        CELL_CELLPROB_THRESHOLD = 0
        HELPER_INDEX = None  # Optional: channel index to help with CPSAM segmentation
    elif SEGMENTATION_METHOD == "stardist":
        # Parameters for StarDist method
        STARDIST_MODEL = "2D_versatile_fluo"
        NUCLEI_PROB_THRESHOLD = 0.479071
        NUCLEI_NMS_THRESHOLD = 0.3
        CELL_PROB_THRESHOLD = 0.479071
        CELL_NMS_THRESHOLD = 0.3
    elif SEGMENTATION_METHOD == "watershed":
        # Parameters for Watershed method
        THRESHOLD_DAPI = 4260
        THRESHOLD_CELL = 1300
        NUCLEUS_AREA = (45, 450)
    # === END OPERATOR PARAMETERS ===

    # Estimate diameters (derivation; non-CPSAM cellpose only)
    if SEGMENTATION_METHOD == "cellpose" and CELLPOSE_MODEL != "cpsam":
        from lib.shared.segment_cellpose import estimate_diameters

        print("Estimating optimal cell and nuclei diameters...")
        NUCLEI_DIAMETER_INPUT, CELL_DIAMETER_INPUT = estimate_diameters(
            corrected_image,
            dapi_index=DAPI_INDEX,
            cyto_index=CYTO_INDEX,
            cellpose_model=CELLPOSE_MODEL,
        )
    else:
        # CPSAM cellpose / stardist / watershed: diameter inputs not pre-estimated.
        # CPSAM derives final diameters downstream from regionprops; stardist/watershed don't use these.
        print(
            "Diameter inputs set to None (derived downstream for CPSAM, unused for stardist/watershed)."
        )
        NUCLEI_DIAMETER_INPUT = None
        CELL_DIAMETER_INPUT = None
    return (
        CELLPOSE_MODEL,
        CELL_CELLPROB_THRESHOLD,
        CELL_DIAMETER_INPUT,
        CELL_FLOW_THRESHOLD,
        CELL_NMS_THRESHOLD,
        CELL_PROB_THRESHOLD,
        GPU,
        HELPER_INDEX,
        NUCLEI_CELLPROB_THRESHOLD,
        NUCLEI_DIAMETER_INPUT,
        NUCLEI_FLOW_THRESHOLD,
        NUCLEI_NMS_THRESHOLD,
        NUCLEI_PROB_THRESHOLD,
        NUCLEUS_AREA,
        RECONCILE,
        SEGMENTATION_METHOD,
        SEGMENT_CELLS,
        STARDIST_MODEL,
        THRESHOLD_CELL,
        THRESHOLD_DAPI,
    )


@app.cell
def _(
    CELLPOSE_MODEL,
    CELL_CELLPROB_THRESHOLD,
    CELL_DIAMETER_INPUT,
    CELL_FLOW_THRESHOLD,
    CELL_NMS_THRESHOLD,
    CELL_PROB_THRESHOLD,
    CYTO_INDEX,
    DAPI_INDEX,
    GPU,
    HELPER_INDEX,
    Microimage,
    NUCLEI_CELLPROB_THRESHOLD,
    NUCLEI_DIAMETER_INPUT,
    NUCLEI_FLOW_THRESHOLD,
    NUCLEI_NMS_THRESHOLD,
    NUCLEI_PROB_THRESHOLD,
    NUCLEUS_AREA,
    RECONCILE,
    SEGMENTATION_METHOD,
    SEGMENT_CELLS,
    STARDIST_MODEL,
    THRESHOLD_CELL,
    THRESHOLD_DAPI,
    cellpose_rgb,
    corrected_image,
    create_micropanel,
    image_segmentation_annotations,
    np,
    plt,
    random_cmap,
):
    print(f"Segmenting image with {SEGMENTATION_METHOD}...")
    if SEGMENTATION_METHOD == "cellpose":
        from lib.shared.segment_cellpose import segment_cellpose

        result = segment_cellpose(
            corrected_image,
            dapi_index=DAPI_INDEX,
            cyto_index=CYTO_INDEX,
            nuclei_diameter=NUCLEI_DIAMETER_INPUT,
            cell_diameter=CELL_DIAMETER_INPUT,
            cellpose_kwargs=dict(
                nuclei_flow_threshold=NUCLEI_FLOW_THRESHOLD,
                nuclei_cellprob_threshold=NUCLEI_CELLPROB_THRESHOLD,
                cell_flow_threshold=CELL_FLOW_THRESHOLD,
                cell_cellprob_threshold=CELL_CELLPROB_THRESHOLD,
            ),
            cellpose_model=CELLPOSE_MODEL,
            helper_index=HELPER_INDEX,
            gpu=GPU,
            reconcile=RECONCILE,
            cells=SEGMENT_CELLS,
        )
    elif SEGMENTATION_METHOD == "stardist":
        from lib.shared.segment_stardist import segment_stardist

        result = segment_stardist(
            corrected_image,
            dapi_index=DAPI_INDEX,
            cyto_index=CYTO_INDEX,
            model_type=STARDIST_MODEL,
            stardist_kwargs=dict(
                nuclei_prob_threshold=NUCLEI_PROB_THRESHOLD,
                nuclei_nms_threshold=NUCLEI_NMS_THRESHOLD,
                cell_prob_threshold=CELL_PROB_THRESHOLD,
                cell_nms_threshold=CELL_NMS_THRESHOLD,
            ),
            gpu=GPU,
            reconcile=RECONCILE,
            cells=SEGMENT_CELLS,
        )
    elif SEGMENTATION_METHOD == "watershed":
        from lib.shared.segment_watershed import segment_watershed

        result = segment_watershed(
            corrected_image,
            nuclei_threshold=THRESHOLD_DAPI,
            nuclei_area_min=NUCLEUS_AREA[0],
            nuclei_area_max=NUCLEUS_AREA[1],
            cell_threshold=THRESHOLD_CELL,
            cells=SEGMENT_CELLS,
        )
    if SEGMENT_CELLS:
        nuclei, cells = result
    else:
        nuclei = result
        cells = nuclei
    print("Example microplots for DAPI channel and nuclei segmentation:")
    nuclei_cmap = random_cmap(num_colors=len(np.unique(nuclei)))
    nuclei_seg_microimages = [
        Microimage(cellpose_rgb[2], channel_names="Dapi"),
        Microimage(nuclei, cmaps=nuclei_cmap, channel_names="Nuclei"),
    ]
    nuclei_seg_panel = create_micropanel(nuclei_seg_microimages, add_channel_label=True)
    plt.show()
    print(
        f"Example microplots for merged channels and {('cells' if SEGMENT_CELLS else 'nuclei')} segmentation:"
    )
    cells_cmap = random_cmap(
        num_colors=len(np.unique(cells if SEGMENT_CELLS else nuclei))
    )
    cells_seg_microimages = [
        Microimage(cellpose_rgb, channel_names="Merged"),
        Microimage(
            cells if SEGMENT_CELLS else nuclei,
            cmaps=cells_cmap,
            channel_names="Cells" if SEGMENT_CELLS else "Nuclei",
        ),
    ]
    cells_seg_panel = create_micropanel(cells_seg_microimages, add_channel_label=True)
    plt.show()
    print("Example microplot for sequencing data annotated with segmentation:")
    annotated_data = image_segmentation_annotations(
        cellpose_rgb[1:], nuclei, cells if SEGMENT_CELLS else nuclei
    )
    annotated_microimage = [
        Microimage(
            annotated_data,
            channel_names="Merged",
            cmaps=["pure_blue", "pure_red", "pure_green"],
        )
    ]
    annotated_panel = create_micropanel(
        annotated_microimage, num_cols=1, figscaling=10, add_channel_label=False
    )
    plt.show()
    # Final diameters that go to config.yml. For CPSAM, derive from segmented
    # objects (regionprops); for non-CPSAM cellpose, pass through the pre-seg
    # estimate; for stardist/watershed, None (unused by those methods).
    if SEGMENTATION_METHOD == "cellpose" and CELLPOSE_MODEL == "cpsam":
        from skimage.measure import regionprops

        nuclei_props = regionprops(nuclei)
        nuclei_diameters = [prop.equivalent_diameter for prop in nuclei_props]
        NUCLEI_DIAMETER = float(np.mean(nuclei_diameters))
        cells_props = regionprops(cells)
        cells_diameters = [prop.equivalent_diameter for prop in cells_props]
        CELL_DIAMETER = float(np.mean(cells_diameters))
        print(
            f"CPSAM derived diameters from segmentation: NUCLEI_DIAMETER={NUCLEI_DIAMETER:.2f} px, CELL_DIAMETER={CELL_DIAMETER:.2f} px"
        )
    else:
        # Non-CPSAM cellpose / stardist / watershed: pass through the input
        # (None for stardist/watershed; the estimate_diameters output for non-CPSAM cellpose).
        NUCLEI_DIAMETER = NUCLEI_DIAMETER_INPUT
        CELL_DIAMETER = CELL_DIAMETER_INPUT
    return CELL_DIAMETER, NUCLEI_DIAMETER, cells, nuclei


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Note: You may want to adjust these parameters and run segmentation tests if you feel you are capturing too little or too much area for the masks. For cellpose, the nuclei and cell diameters will be automatically estimated, but can be manually adjusted if needed. You manually can set `NUCLEI_DIAMETER` and `CELL_DIAMETER` and rerun the above blocks as many times as needed.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Barcode design table standardization

    Raw barcode design tables from different sources often have inconsistent formatting, column names, and gene annotations that need to be cleaned and validated before analysis. This standardization step transforms your raw design file into a consistent format with validated gene symbols, standardized column names, and proper barcode prefixes for read mapping.

    **Barcode Type Selection:**
    - `BARCODE_TYPE`: Choose "simple" (single-barcode protocol) or "multi" (multi-barcode with MAP/RECOMB regions)
    - **Default**: "simple" for standard protocols
    - See Cell 32 for detailed explanation of barcode types and when to use each mode

    **Essential Parameters:**
    - `DF_DESIGN_FP`: File path to your raw guide RNA design file (TSV format)
    - `DF_BARCODE_LIBRARY_FP`: File path where the cleaned, standardized barcode library will be saved
    - `UNIPROT_DATA_FP`: File path for temporary UniProt annotation data (automatically generated and deleted)
    - `GENE_SYMBOL_COL`: Column name containing gene symbols (e.g., "gene_symbol", "target_gene"). Set to `None` if unavailable
    - `GENE_ID_COL`: Column name containing gene IDs (e.g., "gene_id", "ensembl_id"). Set to `None` if not needed

    **Simple Mode Parameters:**
    - `BARCODE_COL`: Column containing full barcode sequences (e.g., "sgRNA", "guide_sequence")
    - `PREFIX_LENGTH`: Total barcode length BEFORE skipping cycles
      - Final length = PREFIX_LENGTH - number of skipped cycles
      - Example: 13 bases → skip [2,3,4] → 10 final bases
    - `SKIP_CYCLES_MAP`: 1-based cycle positions to skip (e.g., `[2, 3, 4]`)
      - **IMPORTANT**: Must match `SKIP_CYCLES` from Cell 8 (imaging alignment)
      - Set to `None` if no cycles were skipped

    **Multi Mode Parameters:**
    - `PREFIX_MAP`: Column with MAP region barcode sequences (e.g., "iBAR2")
    - `PREFIX_RECOMB`: Column with RECOMB region barcode sequences (optional)
    - `MAP_PREFIX_LENGTH`: Total bases BEFORE skipping for MAP region
      - Final length = MAP_PREFIX_LENGTH - len(SKIP_CYCLES_MAP)
    - `RECOMB_PREFIX_LENGTH`: Total bases BEFORE skipping for RECOMB region
      - Final length = RECOMB_PREFIX_LENGTH - len(SKIP_CYCLES_RECOMB)
    - `SKIP_CYCLES_MAP`: 1-based positions to skip in MAP region (optional)
    - `SKIP_CYCLES_RECOMB`: 1-based positions to skip in RECOMB region (optional)
    - `SEQUENCING_ORDER`: Order of barcode regions during sequencing. Options are:
        - `"map_recomb"`: MAP region sequenced first, then RECOMB region
        - `"recomb_map"`: RECOMB region sequenced first, then MAP region

    **Non-Targeting Control Parameters:**
    - `NONTARGETING_FORMAT`: Format string for standardized non-targeting names (default: "nontargeting_{prefix}")
      - Use `{prefix}` for barcode prefix, `{original}` for original name
    - `NONTARGETING_PATTERNS`: List of patterns to identify non-targeting controls (default: ["nontargeting", "sg_nt", "non-targeting"])

    **Note:** For complex scenarios (custom prefix generation), you can use custom prefix functions (`prefix_map_func`, `prefix_recomb_func`). See function documentation for details.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    BARCODE_TYPE = "simple"  # "simple" | "multi"
    DF_DESIGN_FP = None
    DF_BARCODE_LIBRARY_FP = "config/barcode_library.tsv"
    UNIPROT_DATA_FP = "config/uniprot_data.tsv"
    GENE_SYMBOL_COL = None
    GENE_ID_COL = None
    NONTARGETING_FORMAT = "nontargeting_{prefix}"
    NONTARGETING_PATTERNS = ["nontargeting", "sg_nt", "non-targeting"]
    # Simple-mode params (used when BARCODE_TYPE == "simple")
    BARCODE_COL = None  # Column with full barcode sequences
    # PREFIX_LENGTH = FULL barcode length in your design library; final length = PREFIX_LENGTH - len(SKIP_CYCLES_MAP)
    PREFIX_LENGTH = None  # e.g., 12 for 12-base barcodes
    # SKIP_CYCLES_MAP should match SKIP_CYCLES from the alignment cell (1-based positions).
    SKIP_CYCLES_MAP = None  # e.g., [1, 6], or None if no cycles skipped
    # Multi-mode params (used when BARCODE_TYPE == "multi"; leave None for simple mode)
    PREFIX_MAP = None  # Column with MAP region barcode sequences (e.g., "iBAR2")
    PREFIX_RECOMB = None  # Column with RECOMB region barcode sequences (optional)
    MAP_PREFIX_LENGTH = None  # e.g., 6 for cycles 0-5
    RECOMB_PREFIX_LENGTH = None  # e.g., 6 for cycles 6-11
    SKIP_CYCLES_RECOMB = None  # 1-based positions to skip in RECOMB region
    SEQUENCING_ORDER = None  # "map_recomb" | "recomb_map"
    # === END OPERATOR PARAMETERS ===

    # Mode-specific barcode parameters
    if BARCODE_TYPE == "simple":
        pass  # values already supplied via OPERATOR PARAMETERS above

    elif BARCODE_TYPE == "multi":
        # Multi-mode: zero out simple-mode params (operator sets multi-mode params in markers above)
        BARCODE_COL = None
        PREFIX_LENGTH = None
    return (
        BARCODE_COL,
        BARCODE_TYPE,
        DF_BARCODE_LIBRARY_FP,
        DF_DESIGN_FP,
        GENE_ID_COL,
        GENE_SYMBOL_COL,
        MAP_PREFIX_LENGTH,
        NONTARGETING_FORMAT,
        NONTARGETING_PATTERNS,
        PREFIX_LENGTH,
        PREFIX_MAP,
        PREFIX_RECOMB,
        RECOMB_PREFIX_LENGTH,
        SEQUENCING_ORDER,
        SKIP_CYCLES_MAP,
        SKIP_CYCLES_RECOMB,
        UNIPROT_DATA_FP,
    )


@app.cell
def _(
    BARCODE_COL,
    BARCODE_TYPE,
    DF_BARCODE_LIBRARY_FP,
    DF_DESIGN_FP,
    GENE_ID_COL,
    GENE_SYMBOL_COL,
    MAP_PREFIX_LENGTH,
    NONTARGETING_FORMAT,
    NONTARGETING_PATTERNS,
    PREFIX_LENGTH,
    PREFIX_MAP,
    PREFIX_RECOMB,
    Path,
    RECOMB_PREFIX_LENGTH,
    SEQUENCING_ORDER,
    SKIP_CYCLES_MAP,
    SKIP_CYCLES_RECOMB,
    UNIPROT_DATA_FP,
    mo,
    get_barcode_list,
    get_uniprot_data,
    pd,
    standardize_barcode_design,
):
    # Get uniprot data and save it temporarily
    uniprot_data = get_uniprot_data()
    uniprot_data.to_csv(UNIPROT_DATA_FP, sep="\t", index=False)
    uniprot_data = pd.read_csv(UNIPROT_DATA_FP, sep="\t")

    # Read design table
    print("Loading and standardizing barcode design table...")
    df_design = pd.read_csv(DF_DESIGN_FP, sep="\t")

    # Call standardize_barcode_design with mode-specific parameters
    if BARCODE_TYPE == "simple":
        # Simple mode: use barcode_col and prefix_length (legacy parameter names)
        df_barcode_library = standardize_barcode_design(
            df_design,
            prefix_map=BARCODE_COL,  # In simple mode, this is the barcode column
            gene_symbol_col=GENE_SYMBOL_COL,
            gene_id_col=GENE_ID_COL,
            map_prefix_length=PREFIX_LENGTH,  # In simple mode, this is the prefix length
            skip_cycles_map=SKIP_CYCLES_MAP,  # Pass skip_cycles for simple mode
            uniprot_data_path=UNIPROT_DATA_FP,
            nontargeting_format=NONTARGETING_FORMAT,
            nontargeting_patterns=NONTARGETING_PATTERNS,
        )

    elif BARCODE_TYPE == "multi":
        # Multi mode: use prefix_map, prefix_recomb, and region-specific lengths
        df_barcode_library = standardize_barcode_design(
            df_design,
            prefix_map=PREFIX_MAP,
            prefix_recomb=PREFIX_RECOMB,
            gene_symbol_col=GENE_SYMBOL_COL,
            gene_id_col=GENE_ID_COL,
            map_prefix_length=MAP_PREFIX_LENGTH,
            recomb_prefix_length=RECOMB_PREFIX_LENGTH,
            skip_cycles_map=SKIP_CYCLES_MAP,
            skip_cycles_recomb=SKIP_CYCLES_RECOMB,
            uniprot_data_path=UNIPROT_DATA_FP,
            nontargeting_format=NONTARGETING_FORMAT,
            nontargeting_patterns=NONTARGETING_PATTERNS,
        )

    # Delete uniprot data file
    Path(UNIPROT_DATA_FP).unlink(missing_ok=True)

    # Save standardized design table
    df_barcode_library.to_csv(DF_BARCODE_LIBRARY_FP, sep="\t", index=False)
    print(f"Standardized barcode design saved to: {DF_BARCODE_LIBRARY_FP}")
    mo.ui.table(df_barcode_library)

    # Extract barcodes (prefixes) for mapping - conditional based on barcode type
    if BARCODE_TYPE == "multi":
        barcodes = get_barcode_list(
            df_barcode_library, sequencing_order=SEQUENCING_ORDER
        )
    else:
        barcodes = get_barcode_list(df_barcode_library)

    print(f"Extracted {len(barcodes)} barcode prefixes for read mapping")
    return barcodes, df_barcode_library


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Extract base intensity, call reads, assign to cells
    - `THRESHOLD_READS`: Initial threshold for detecting sequencing reads, set to ~50 for preliminary analysis. This parameter will be optimized based on the mapping rate vs. peak threshold plot generated below. A higher threshold increases confidence in read calls but reduces the total number of detected reads.
    - `CALL_READS_METHOD`: Method to use for correcting base intensity across channels. The below `plot_normalization_comparison` function will help you assess what method to use. Options are:
        - `MEDIAN`: Uses median-based correction, performed independently for each tile. This is the default method.
        - `PERCENTILE`: Uses percentile-based correction, performed independently for each tile.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    THRESHOLD_READS = 50  # library default; raise to be stricter
    CALL_READS_METHOD = "median"  # "median" | "max"
    # === END OPERATOR PARAMETERS ===
    return CALL_READS_METHOD, THRESHOLD_READS


@app.cell
def _(
    BASES,
    CALL_READS_METHOD,
    SEGMENT_CELLS,
    THRESHOLD_READS,
    WILDCARDS,
    call_reads,
    cells,
    extract_bases,
    maxed,
    nuclei,
    peaks,
):
    # Run extract_bases and call_reads with the default threshold
    df_bases = extract_bases(
        peaks,
        maxed,
        cells if SEGMENT_CELLS else nuclei,
        THRESHOLD_READS,
        wildcards=WILDCARDS,
        bases=BASES,
    )
    df_reads = call_reads(df_bases, peaks_data=peaks, method=CALL_READS_METHOD)
    return (df_reads,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Determine Optimal Read Threshold

    **These plots show READ-LEVEL metrics** (not final cell-level mapping):
    - **Blue line**: Fraction of reads matching expected barcodes
    - **Orange solid**: Total reads with valid barcodes
    - **Orange dotted**: Unique cells with ≥1 valid barcode (not necessarily singlets)

    Use these to set `THRESHOLD_READS` to maximize clean reads. Final cell-level QC comes later.
    """)
    return


@app.cell
def _(barcodes, df_reads, plot_mapping_vs_threshold, plt):
    print("Mapping rate vs. peak threshold for determining optimal peak cutoff:")
    plot_mapping_vs_threshold(df_reads, barcodes, "peak")
    plt.show()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    **How to read these plots:**
    - **Left**: All reads (including background noise)
    - **Right**: Cell-associated reads only (cell > 0)

    **Goal**: Find threshold where mapping rate plateaus (~70-80%) while retaining enough reads/cells for analysis.

    **Note**: High read mapping ≠ high cell mapping. Many reads might cluster in few cells, or cells might have mixed barcodes. See cell-level QC below for final mapping quality.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Read Prioritization Method: Peak vs. Count

    The `SORT_CALLS` parameter determines how barcodes are prioritized when assigning reads to cells. This choice depends on your sequencing protocol:

    **Count Prioritization (`SORT_CALLS = "count"`):**
    - Prioritizes barcodes based on the **number of spots** detected per cell
    - **Recommended for mRNA barcode protocols** (e.g., IVT-based perturbations)
    - Why: mRNA barcodes produce multiple spots per cell, so more spots = more confident call
    - Best for protocols where barcode signal is distributed throughout the cell

    **Peak Prioritization (`SORT_CALLS = "peak"`):**
    - Prioritizes barcodes based on the **peak intensity** of spots
    - **Recommended for DNA barcode protocols** (e.g., Zombie, T7 amplification)
    - Why: DNA barcodes typically produce a singular, bright spot per cell
    - Best for protocols with focused, high-intensity signal

    **Default**: `"count"` is the default and works well for most applications.

    ### Read Mapping Parameters

    **Common to both barcode modes:**
    - `Q_MIN`: Minimum quality score for base reads (default: 0)
    - `ERROR_CORRECT`: Enable read error correction (default: False)
    - `SORT_CALLS`: Method for prioritizing barcodes - 'count' for mRNA protocols, 'peak' for DNA protocols
    - `MAX_DISTANCE`: Maximum edit distance for barcode matching (optional)

    **Simple mode specific:**
    - `BARCODE_COL`: Column in barcode library with full sequences (defined upstream in the barcode design cell)
    - `PREFIX_COL`: standardize_barcode_design output column for prefixes (default `"prefix"`)
    - `N_BARCODES`: Number of ranked barcodes to store per cell (default 2)

    **Multi mode specific:**
    - `MAP_START`, `MAP_END`: Cycle positions defining MAP region for first barcode
    - `RECOMB_START`, `RECOMB_END`: Cycle positions defining RECOMB region
    - `PREFIX_MAP`, `PREFIX_RECOMB`: standardize_barcode_design output column names (defaults `"prefix_map"`, `"prefix_recomb"`)

    **Recombination Quality Filtering (Multi-mode only):**
    - `RECOMB_FILTER_COL`: Quality column in the reads data to use for filtering recombination calls. Set to `"Q_recomb"` to filter based on the minimum quality score across recombination cycles (computed by `prep_multi_reads`). Set to `None` to disable quality filtering.
    - `RECOMB_Q_THRESH`: Quality score threshold for accepting recombination barcode calls. Reads with `RECOMB_FILTER_COL` below this threshold will have their recombination status set to undetermined. Default is 0.1.

    **Note**: The output will include `no_recomb_0` and `no_recomb_1` columns indicating whether each cell's barcodes show recombination (True = no recombination detected, barcodes match library expectations).

    The Q_min plot below helps determine optimal sequence quality cutoff:
    """)
    return


@app.cell
def _(barcodes, df_reads, plot_mapping_vs_threshold, plt):
    print("Mapping rate vs. Q_min for determining optimal sequence quality cutoff:")
    plot_mapping_vs_threshold(df_reads, barcodes, "Q_min")
    plt.show()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    #### Left Plot (All Reads):
    - Shows how Q_min threshold affects all detected reads
    - Blue line: Mapping rate (fraction of reads matching expected barcodes)
    - Solid red line: Total number of mapped spots (reads with valid barcodes)
    - Dotted red line: Number of unique cells with at least one mapped read

    #### Right Plot (Cell-Associated Reads Only):
    - Shows the same metrics but only for reads associated with cells

    #### Interpreting Q_min Results:
    With our optimized peak threshold, these plots confirm that adjusting Q_min provides little benefit:
    - The mapping rate (blue line) is already very high at Q_min = 0
    - Increasing Q_min only marginally improves mapping rate
    - However, this comes at a significant cost:
      - Total mapped spots and mapped cells decreases substantially
    - The small gain in mapping rate doesn't justify the large loss of data
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    Q_MIN = 0  # library default
    ERROR_CORRECT = False
    SORT_CALLS = "count"  # "count" | "peak"
    MAX_DISTANCE = None  # max edit distance for barcode matching
    # Multi-mode cycle positions (only used when BARCODE_TYPE == "multi")
    MAP_START = None  # e.g., 0
    MAP_END = None  # e.g., 5
    RECOMB_START = None  # e.g., 6
    RECOMB_END = None  # e.g., 11
    BARCODE_INFO_COLS = None  # optional additional barcode info cols
    # === END OPERATOR PARAMETERS ===

    # Library defaults (auto bucket) — output col names renamed to *_OUT to avoid
    # colliding with the Cell 8 operator-set PREFIX_MAP/PREFIX_RECOMB (which are
    # input column names in the design table).
    N_BARCODES = 2  # number of ranked barcodes to store per cell
    PREFIX_COL = "prefix"  # simple mode: standardize_barcode_design output col
    PREFIX_MAP_OUT = "prefix_map"  # multi mode: MAP region output col
    PREFIX_RECOMB_OUT = "prefix_recomb"  # multi mode: RECOMB region output col
    RECOMB_FILTER_COL = "Q_recomb"  # multi mode: quality col for recomb filtering
    RECOMB_Q_THRESH = 0.1  # multi mode: quality threshold for recomb calls
    return (
        BARCODE_INFO_COLS,
        ERROR_CORRECT,
        MAP_END,
        MAP_START,
        MAX_DISTANCE,
        N_BARCODES,
        PREFIX_COL,
        PREFIX_MAP_OUT,
        PREFIX_RECOMB_OUT,
        Q_MIN,
        RECOMB_END,
        RECOMB_FILTER_COL,
        RECOMB_Q_THRESH,
        RECOMB_START,
        SORT_CALLS,
    )


@app.cell
def _(BARCODE_TYPE, ERROR_CORRECT, MAX_DISTANCE, PREFIX_COL, df_barcode_library):
    if ERROR_CORRECT:
        import math

        d = MAX_DISTANCE if MAX_DISTANCE is not None else 1
        prefix_col_to_use = PREFIX_COL if BARCODE_TYPE == "simple" else "prefix_map"
        prefix_length = len(df_barcode_library[prefix_col_to_use].dropna().iloc[0])
        recommended_d = prefix_length - math.ceil(math.log(len(df_barcode_library), 4))

        if recommended_d <= 0:
            print(
                "WARNING: Error correction not recommended — library too complex relative to cycles sequenced."
            )
        elif d > recommended_d:
            print(
                f"WARNING: MAX_DISTANCE={d} may be too aggressive. Recommended max edit distance: {recommended_d}."
            )
        else:
            print(
                f"Error correction parameters look appropriate (recommended max edit distance: {recommended_d})."
            )
    return


@app.cell
def _(
    BARCODE_COL,
    BARCODE_INFO_COLS,
    BARCODE_TYPE,
    ERROR_CORRECT,
    MAP_END,
    MAP_START,
    MAX_DISTANCE,
    N_BARCODES,
    PREFIX_COL,
    PREFIX_MAP,
    PREFIX_RECOMB,
    Q_MIN,
    RECOMB_END,
    RECOMB_FILTER_COL,
    RECOMB_Q_THRESH,
    RECOMB_START,
    SORT_CALLS,
    WILDCARDS,
    barcodes,
    call_cells,
    df_barcode_library,
    df_reads,
    mo,
    extract_phenotype_minimal,
    nuclei,
    plot_cell_mapping_heatmap,
    plot_cell_metric_histogram,
    plot_gene_symbol_histogram,
    plt,
):
    print("Calling cells with barcode mapping...")
    if BARCODE_TYPE == "simple":
        df_cells = call_cells(
            df_reads,
            df_barcode_library=df_barcode_library,
            q_min=Q_MIN,
            barcode_col=BARCODE_COL,
            prefix_col=PREFIX_COL,
            error_correct=ERROR_CORRECT,
            sort_calls=SORT_CALLS,
            max_distance=MAX_DISTANCE,
            n_barcodes=N_BARCODES,
        )
    elif BARCODE_TYPE == "multi":
        from lib.sbs.call_cells import prep_multi_reads

        print("Preparing multi-barcode reads...")
        df_reads_prepped = prep_multi_reads(
            df_reads,
            map_start=MAP_START,
            map_end=MAP_END,
            recomb_start=RECOMB_START,
            recomb_end=RECOMB_END,
            prefix_map=PREFIX_MAP,
            prefix_recomb=PREFIX_RECOMB,
        )
        print("Calling cells with multi-barcode detection...")
        df_cells = call_cells(
            reads_data=df_reads_prepped,
            df_barcode_library=df_barcode_library,
            q_min=Q_MIN,
            map_start=MAP_START,
            map_end=MAP_END,
            prefix_map=PREFIX_MAP,
            recomb_start=RECOMB_START,
            recomb_end=RECOMB_END,
            prefix_recomb=PREFIX_RECOMB,
            recomb_filter_col=RECOMB_FILTER_COL,
            recomb_q_thresh=RECOMB_Q_THRESH,
            error_correct=ERROR_CORRECT,
            sort_calls=SORT_CALLS,
            max_distance=MAX_DISTANCE,
            n_barcodes=N_BARCODES,
            barcode_info_cols=BARCODE_INFO_COLS,
        )
    print(f"Called {len(df_cells)} cells using {BARCODE_TYPE} mode")
    mo.ui.table(df_cells)
    if BARCODE_TYPE == "multi":
        total_mapped_cells = len(df_cells)
        if "no_recomb_0" in df_cells.columns:
            cells_no_recomb = df_cells["no_recomb_0"].sum()
            no_recomb_percent = (
                cells_no_recomb / total_mapped_cells * 100
                if total_mapped_cells > 0
                else 0
            )
            print(
                f"\nRecombination Statistics:"
            )  # Multi mode: prep reads first, then call cells
            print(f"  Total mapped cells: {total_mapped_cells}")
            print(
                f"  Cells with no recombination detected: {cells_no_recomb} ({no_recomb_percent:.1f}%)"
            )
    print("Minimal phenotype features:")
    df_sbs_info = extract_phenotype_minimal(
        phenotype_data=nuclei, nuclei_data=nuclei, wildcards=WILDCARDS
    )
    mo.ui.table(df_sbs_info)
    print("Summary of the fraction of cells mapping to one barcode:")
    one_barcode_mapping = plot_cell_mapping_heatmap(
        df_cells,
        df_sbs_info,
        barcodes,
        mapping_to="one",
        mapping_strategy="gene symbols",
        return_plot=False,
        return_summary=True,
    )
    mo.ui.table(one_barcode_mapping)
    print("Summary of the fraction of cells mapping to any barcode:")
    any_barcode_mapping = plot_cell_mapping_heatmap(
        df_cells,
        df_sbs_info,
        barcodes,
        mapping_to="any",
        mapping_strategy="gene symbols",
        return_plot=False,
        return_summary=True,
    )
    mo.ui.table(any_barcode_mapping)
    print("Histogram of the number of reads per cell:")
    outliers = plot_cell_metric_histogram(df_cells, sort_by=SORT_CALLS)
    plt.show()
    print("Histogram of the number of counts of each unique gene symbols:")
    outliers = plot_gene_symbol_histogram(df_cells)
    # Show recombination statistics for multi-mode
    plt.show()  # Count cells where no_recomb_0 = True (no recombination detected)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Add sbs process parameters to config file
    """)
    return


@app.cell
def _(
    ALIGNMENT_METHOD,
    BARCODE_COL,
    BARCODE_INFO_COLS,
    BARCODE_TYPE,
    BASES,
    CALL_READS_METHOD,
    CELLPOSE_MODEL,
    CELL_CELLPROB_THRESHOLD,
    CELL_DIAMETER,
    CELL_FLOW_THRESHOLD,
    CELL_NMS_THRESHOLD,
    CELL_PROB_THRESHOLD,
    CHANNEL_NAMES,
    CONFIG_FILE_HEADER,
    CONFIG_FILE_PATH,
    CYTO_CYCLE,
    CYTO_CYCLE_INDEX,
    CYTO_INDEX,
    DAPI_CYCLE,
    DAPI_CYCLE_INDEX,
    DAPI_INDEX,
    DF_BARCODE_LIBRARY_FP,
    ERROR_CORRECT,
    EXTRA_CHANNEL_INDICES,
    GPU,
    HELPER_INDEX,
    MANUAL_BACKGROUND_CYCLE_INDEX,
    MANUAL_CHANNEL_MAPPING,
    MAP_END,
    MAP_START,
    MAX_DISTANCE,
    MAX_FILTER_WIDTH,
    N_BARCODES,
    NUCLEI_CELLPROB_THRESHOLD,
    NUCLEI_DIAMETER,
    NUCLEI_FLOW_THRESHOLD,
    NUCLEI_NMS_THRESHOLD,
    NUCLEI_PROB_THRESHOLD,
    NUCLEUS_AREA,
    PEAK_WIDTH,
    PREFIX_COL,
    PREFIX_MAP,
    PREFIX_RECOMB,
    Q_MIN,
    RECOMB_END,
    RECOMB_FILTER_COL,
    RECOMB_Q_THRESH,
    RECOMB_START,
    RECONCILE,
    SEGMENTATION_METHOD,
    SEGMENT_CELLS,
    SKIP_CYCLES_INDICES,
    SORT_CALLS,
    SPOTIFLOW_CYCLE_INDEX,
    SPOTIFLOW_MIN_DISTANCE,
    SPOTIFLOW_MODEL,
    SPOTIFLOW_THRESHOLD,
    SPOT_DETECTION_METHOD,
    STARDIST_MODEL,
    THRESHOLD_CELL,
    THRESHOLD_DAPI,
    THRESHOLD_READS,
    UPSAMPLE_FACTOR,
    WINDOW,
    config,
    convert_tuples_to_lists,
    yaml,
):
    config["sbs"] = {
        "alignment_method": ALIGNMENT_METHOD,
        "channel_names": CHANNEL_NAMES,
        "upsample_factor": UPSAMPLE_FACTOR,
        "window": WINDOW,
        "skip_cycles_indices": SKIP_CYCLES_INDICES,
        "manual_background_cycle_index": MANUAL_BACKGROUND_CYCLE_INDEX,
        "manual_channel_mapping": MANUAL_CHANNEL_MAPPING,
        "extra_channel_indices": EXTRA_CHANNEL_INDICES,
        "max_filter_width": MAX_FILTER_WIDTH,
        "spot_detection_method": SPOT_DETECTION_METHOD,
        "dapi_cycle": DAPI_CYCLE,
        "dapi_cycle_index": DAPI_CYCLE_INDEX,
        "cyto_cycle": CYTO_CYCLE,
        "cyto_cycle_index": CYTO_CYCLE_INDEX,
        "dapi_index": DAPI_INDEX,
        "cyto_index": CYTO_INDEX,
        "segmentation_method": SEGMENTATION_METHOD,
        "gpu": GPU,
        "reconcile": RECONCILE,
        "segment_cells": SEGMENT_CELLS,
        "df_barcode_library_fp": DF_BARCODE_LIBRARY_FP,
        "threshold_peaks": THRESHOLD_READS,
        "call_reads_method": CALL_READS_METHOD,
        "bases": BASES,
        "q_min": Q_MIN,
        "error_correct": ERROR_CORRECT,
        "sort_calls": SORT_CALLS,
        "n_barcodes": N_BARCODES,
        "barcode_type": BARCODE_TYPE,
    }
    if MAX_DISTANCE is not None:
        config["sbs"]["max_distance"] = MAX_DISTANCE
    if BARCODE_TYPE == "simple":
        config["sbs"].update({"barcode_col": BARCODE_COL, "prefix_col": PREFIX_COL})
    elif BARCODE_TYPE == "multi":
        config["sbs"].update(
            {
                "map_start": MAP_START,
                "map_end": MAP_END,
                "prefix_map": PREFIX_MAP,
                "recomb_start": RECOMB_START,
                "recomb_end": RECOMB_END,
                "prefix_recomb": PREFIX_RECOMB,
            }
        )
        if RECOMB_FILTER_COL is not None:
            config["sbs"]["recomb_filter_col"] = RECOMB_FILTER_COL
        if RECOMB_Q_THRESH is not None:
            config["sbs"]["recomb_q_thresh"] = RECOMB_Q_THRESH
        if BARCODE_INFO_COLS is not None:
            config["sbs"]["barcode_info_cols"] = BARCODE_INFO_COLS
    if SPOT_DETECTION_METHOD == "standard":
        config["sbs"].update({"peak_width": PEAK_WIDTH})
    elif SPOT_DETECTION_METHOD == "spotiflow":
        config["sbs"].update(
            {
                "spotiflow_cycle_index": SPOTIFLOW_CYCLE_INDEX,
                "spotiflow_model": SPOTIFLOW_MODEL,
                "spotiflow_threshold": SPOTIFLOW_THRESHOLD,
                "spotiflow_min_distance": SPOTIFLOW_MIN_DISTANCE,
                "spotiflow_remove_index": EXTRA_CHANNEL_INDICES,
            }
        )
    if SEGMENTATION_METHOD == "cellpose":
        config["sbs"].update(
            {
                "nuclei_diameter": NUCLEI_DIAMETER,
                "cell_diameter": CELL_DIAMETER,
                "nuclei_flow_threshold": NUCLEI_FLOW_THRESHOLD,
                "nuclei_cellprob_threshold": NUCLEI_CELLPROB_THRESHOLD,
                "cell_flow_threshold": CELL_FLOW_THRESHOLD,
                "cell_cellprob_threshold": CELL_CELLPROB_THRESHOLD,
                "cellpose_model": CELLPOSE_MODEL,
            }
        )
        if HELPER_INDEX is not None:
            config["sbs"]["helper_index"] = HELPER_INDEX
    elif SEGMENTATION_METHOD == "stardist":
        config["sbs"].update(
            {
                "stardist_model": STARDIST_MODEL,
                "nuclei_prob_threshold": NUCLEI_PROB_THRESHOLD,
                "nuclei_nms_threshold": NUCLEI_NMS_THRESHOLD,
                "cell_prob_threshold": CELL_PROB_THRESHOLD,
                "cell_nms_threshold": CELL_NMS_THRESHOLD,
            }
        )
    elif SEGMENTATION_METHOD == "watershed":
        config["sbs"].update(
            {
                "threshold_dapi": THRESHOLD_DAPI,
                "nucleus_area_min": NUCLEUS_AREA[0],
                "nucleus_area_max": NUCLEUS_AREA[1],
                "threshold_cell": THRESHOLD_CELL,
            }
        )
    safe_config = convert_tuples_to_lists(config)
    with open(CONFIG_FILE_PATH, "w") as _config_file:
        _config_file.write(CONFIG_FILE_HEADER)
        yaml.dump(safe_config, _config_file, default_flow_style=False, sort_keys=False)
    return


@app.cell
def _(
    NUCLEI_DIAMETER,
    CELL_DIAMETER,
    THRESHOLD_READS,
    PEAK_WIDTH,
    SEGMENTATION_METHOD,
    CELLPOSE_MODEL,
):
    # === TUNED EXPORT ===
    # Writes derivation-cell outputs the wizard's confirm_tuned_loop reads
    # post-run (R3). Schema: {param: {derived, src}}.
    import json as _je
    from pathlib import Path as _Pe

    _t = {}
    if SEGMENTATION_METHOD == "cellpose" and NUCLEI_DIAMETER is not None:
        _src = (
            "regionprops on segmented objects"
            if CELLPOSE_MODEL == "cpsam"
            else f"estimate_diameters ({CELLPOSE_MODEL})"
        )
        _t["NUCLEI_DIAMETER"] = {"derived": float(NUCLEI_DIAMETER), "src": _src}
        _t["CELL_DIAMETER"] = {"derived": float(CELL_DIAMETER), "src": _src}
    _t["THRESHOLD_READS"] = {
        "derived": THRESHOLD_READS,
        "src": "operator-set (reactive — change THRESHOLD_READS to refine; downstream df_bases / mapping rate update automatically)",
    }
    _t["PEAK_WIDTH"] = {"derived": PEAK_WIDTH, "src": "operator-set (reactive)"}
    _out = _Pe(".brieflow") / "tuned_sbs.json"
    _out.parent.mkdir(exist_ok=True)
    _out.write_text(_je.dumps(_t, indent=2, default=str))
    # === END TUNED EXPORT ===
    return


if __name__ == "__main__":
    app.run()
