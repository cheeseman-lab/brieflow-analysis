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
    # Configure Phenotype Parameters

    This notebook should be used as a test for ensuring correct phenotype image loading and processing before running phenotype module.
    Cells marked with <font color='red'>SET PARAMETERS</font> contain crucial variables that need to be set according to your specific experimental setup and data organization.
    Please review and modify these variables as needed before proceeding with the analysis.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Fixed parameters for phenotype processing

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
    import numpy as np
    from lib.shared.image_io import read_image
    import matplotlib.pyplot as plt
    from microfilm.microplot import Microimage

    from lib.shared.configuration_utils import (
        CONFIG_FILE_HEADER,
        create_micropanel,
        random_cmap,
        image_segmentation_annotations,
        convert_tuples_to_lists,
    )
    from lib.shared.file_utils import get_filename, get_hcs_nested_path, split_well
    from lib.shared.illumination_correction import apply_ic_field
    from lib.phenotype.align_channels import align_phenotype_channels, visualize_phenotype_alignment
    from lib.shared.align import apply_custom_offsets
    from lib.phenotype.identify_cytoplasm_cellpose import (
        identify_cytoplasm_cellpose,
    )
    from lib.phenotype.custom_features import (
        load_custom_features,
        register_custom_features,
    )

    return (
        CONFIG_FILE_HEADER,
        Microimage,
        Path,
        align_phenotype_channels,
        apply_custom_offsets,
        apply_ic_field,
        convert_tuples_to_lists,
        create_micropanel,
        get_filename,
        get_hcs_nested_path,
        identify_cytoplasm_cellpose,
        image_segmentation_annotations,
        load_custom_features,
        np,
        plt,
        random_cmap,
        read_image,
        register_custom_features,
        visualize_phenotype_alignment,
        yaml,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Parameters for testing phenotype processing

    - `TEST_PLATE`, `TEST_WELL`, `TEST_TILE`: Plate/well/tile combination used for configuring parameters in this notebook.

    ### Channels
    - `CHANNEL_NAMES`: A list of names for each channel in your phenotyping image. These names will be used in the output data frame to label the features extracted from each channel.
    - `CHANNEL_CMAPS`: A list of color maps to use when showing channel microimages. These need to be a Matplotlib or microfilm colormap. We recommend using: `["pure_red", "pure_green", "pure_blue", "pure_cyan", "pure_magenta", "pure_yellow"]`.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    TEST_PLATE = None
    TEST_WELL = None
    TEST_TILE = None
    CHANNEL_NAMES = None              # e.g., ["DAPI", "COXIV", "CENPA", "WGA"]
    CHANNEL_CMAPS = None              # e.g., ["pure_blue", "pure_green", "pure_red", "pure_magenta"]
    # === END OPERATOR PARAMETERS ===

    WILDCARDS = dict(well=TEST_WELL, tile=TEST_TILE)
    return (
        CHANNEL_CMAPS,
        CHANNEL_NAMES,
        TEST_PLATE,
        TEST_TILE,
        TEST_WELL,
        WILDCARDS,
    )


@app.cell
def _(
    CHANNEL_CMAPS,
    CHANNEL_NAMES,
    CONFIG_FILE_PATH,
    Microimage,
    Path,
    TEST_PLATE,
    TEST_TILE,
    TEST_WELL,
    apply_ic_field,
    create_micropanel,
    get_filename,
    get_hcs_nested_path,
    plt,
    read_image,
    yaml,
):
    # Load config file
    with open(CONFIG_FILE_PATH, 'r') as _config_file:
        config = yaml.safe_load(_config_file)
    print('Loading test image...')
    # Load test image data
    ROOT_FP = Path(config['all']['root_fp'])
    PREPROCESS_FP = ROOT_FP / 'preprocess'
    IMAGE_FORMAT = config['all'].get('image_format', 'tiff')
    # HCS-nested zarr layout: preprocess/phenotype/<plate>/<row>/<col>/...
    # IC field: preprocess/ic_fields/phenotype/<plate>/<row>/<col>/ic_field.zarr/zarr.json
    _row, _col = split_well(TEST_WELL)
    if IMAGE_FORMAT == 'zarr':
        phenotype_test_image_path = str(PREPROCESS_FP / 'phenotype' / get_hcs_nested_path({'plate': TEST_PLATE, 'row': _row, 'col': _col, 'tile': TEST_TILE}, 'image'))
    else:
        phenotype_test_image_path = str(PREPROCESS_FP / 'phenotype' / get_filename({'plate': TEST_PLATE, 'well': TEST_WELL, 'tile': TEST_TILE}, 'image', 'tiff'))
    phenotype_test_image = read_image(phenotype_test_image_path)
    print('Applying illumination correction...')
    if IMAGE_FORMAT == 'zarr':
        ic_field_path = str(PREPROCESS_FP / 'ic_fields' / 'phenotype' / str(TEST_PLATE) / _row / _col / 'ic_field.zarr' / 'zarr.json')
    else:
        ic_field_path = str(PREPROCESS_FP / 'ic_fields' / 'phenotype' / get_filename({'plate': TEST_PLATE, 'well': TEST_WELL}, 'ic_field', 'tiff'))
    ic_field = read_image(ic_field_path)
    corrected_image = apply_ic_field(phenotype_test_image, correction=ic_field)
    print('Example corrected image:')
    corrected_microimages = [Microimage(corrected_image[i], channel_names=CHANNEL_NAMES[i], cmaps=CHANNEL_CMAPS[i]) for i in range(corrected_image.shape[0])]
    corrected_panel = create_micropanel(corrected_microimages, add_channel_label=True)
    # Read the illumination correction file
    # Apply illumination correction
    # Create and display micropanel of corrected images
    plt.show()
    return config, corrected_image


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Aligning (optional)

    - `ALIGN`: Whether to conduct alignment. This is suggested **unless** each image is captured with each channel consecutively.
    - `TARGET`: Name of the channel that other channels will be aligned to.
    - `SOURCE`: Name of the channel to align with the target.
    - `RIDERS`: Additional channel indices that should follow the same alignment as the source channel.
    - `REMOVE_CHANNEL`: Specifies whether to remove channels after alignment. In the case of duplicate channels that are used to align the image, should be set to `"source"`.
    - `UPSAMPLE_FACTOR`: Subpixel alignment precision factor (default: 2). Higher values provide more precise alignment but increase processing time.
    - `WINDOW`: Size of the region used for alignment calculation (default: 2). Higher values use a smaller centered region of the image.

    ### Custom Alignment (optional)

    - `CUSTOM_CHANNEL_OFFSETS`: Dict mapping channel names to their (y, x) pixel offsets. Can be used independently or in combination with standard alignment for fine-tuning channel registration. Example: `{"DAPI": (5, 10), "AF750": (3, -2)}` shifts DAPI by 5 pixels up and 10 left, AF750 by 3 up and 2 right. Channel names must match those in `CHANNEL_NAMES`. Offset directions: +y = up, -y = down, +x = left, -x = right.
    """)
    return


@app.cell
def _(CHANNEL_NAMES):
    # === OPERATOR PARAMETERS ===
    ALIGN = None
    TARGET = None
    SOURCE = None
    RIDERS = None
    REMOVE_CHANNEL = None
    UPSAMPLE_FACTOR = 2               # library default; raise for finer alignment
    WINDOW = 2                        # library default
    CUSTOM_CHANNEL_OFFSETS = None     # e.g., {"DAPI": (5, 10), "AF750": (3, -2)}
    # === END OPERATOR PARAMETERS ===

    # Derive alignment indexes
    if ALIGN:
        TARGET_INDEX = CHANNEL_NAMES.index(TARGET)
        SOURCE_INDEX = CHANNEL_NAMES.index(SOURCE)
        RIDER_INDEXES = [CHANNEL_NAMES.index(r) for r in RIDERS]

    # Derive custom alignment indexes from channel names
    if CUSTOM_CHANNEL_OFFSETS:
        CUSTOM_CHANNEL_OFFSETS_INDEXED = {
            CHANNEL_NAMES.index(name): offset 
            for name, offset in CUSTOM_CHANNEL_OFFSETS.items()
        }
    return (
        ALIGN,
        CUSTOM_CHANNEL_OFFSETS,
        CUSTOM_CHANNEL_OFFSETS_INDEXED,
        REMOVE_CHANNEL,
        RIDERS,
        RIDER_INDEXES,
        SOURCE,
        SOURCE_INDEX,
        TARGET,
        TARGET_INDEX,
        UPSAMPLE_FACTOR,
        WINDOW,
    )


@app.cell
def _(
    ALIGN,
    CHANNEL_CMAPS,
    CHANNEL_NAMES,
    CUSTOM_CHANNEL_OFFSETS,
    CUSTOM_CHANNEL_OFFSETS_INDEXED,
    REMOVE_CHANNEL,
    RIDERS,
    RIDER_INDEXES,
    SOURCE,
    SOURCE_INDEX,
    TARGET,
    TARGET_INDEX,
    UPSAMPLE_FACTOR,
    WINDOW,
    align_phenotype_channels,
    apply_custom_offsets,
    corrected_image,
):
    # Start with the corrected image
    aligned_image = corrected_image.copy()

    # Apply custom offsets 
    if CUSTOM_CHANNEL_OFFSETS:
        print(f"Custom offsets: {CUSTOM_CHANNEL_OFFSETS_INDEXED}")
        aligned_image = apply_custom_offsets(
            aligned_image,
            offsets_dict=CUSTOM_CHANNEL_OFFSETS_INDEXED
        )

    # Apply automatic alignment
    if ALIGN:
        aligned_image = align_phenotype_channels(
            aligned_image,
            target=TARGET_INDEX,
            source=SOURCE_INDEX,
            riders=RIDER_INDEXES,
            remove_channel=REMOVE_CHANNEL,
            upsample_factor=UPSAMPLE_FACTOR,
            window=WINDOW,
            verbose=True,
        )
        # Automatically remove channels based on REMOVE_CHANNEL
        if REMOVE_CHANNEL == "source":
            remove_index = CHANNEL_NAMES.index(SOURCE)
            CHANNEL_NAMES.pop(remove_index)
            CHANNEL_CMAPS.pop(remove_index)
        elif REMOVE_CHANNEL == "target":
            remove_index = CHANNEL_NAMES.index(TARGET)
            CHANNEL_NAMES.pop(remove_index)
            CHANNEL_CMAPS.pop(remove_index)
        elif REMOVE_CHANNEL == "riders":
            # Remove riders in reverse order to maintain correct indices
            for rider in reversed(RIDERS):
                remove_index = CHANNEL_NAMES.index(rider)
                CHANNEL_NAMES.pop(remove_index)
                CHANNEL_CMAPS.pop(remove_index)
    return (aligned_image,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Visualize Alignment Quality (Optional)

    Visualize channel alignment across 16 locations in the image. The first channel (DAPI) is shown in grayscale with the remaining 3 channels as an RGB overlay. You may want to consider removing channels for a first pass if you want to visualize alignment between different rounds.

    - `VIZ_CHANNELS`: List of exactly 4 channel names to visualize (1st=grayscale base, 2nd-4th=RGB overlay)
    """)
    return


@app.cell
def _(CHANNEL_NAMES, aligned_image, plt, visualize_phenotype_alignment):
    # Set channels to visualize (first=grayscale, remaining 3=RGB overlay)
    VIZ_CHANNELS = None

    if VIZ_CHANNELS is not None:
        print("Visualizing alignment across 16 locations...")
        fig = visualize_phenotype_alignment(
            aligned_image,
            channel_names=CHANNEL_NAMES,
            viz_channels=VIZ_CHANNELS,
            crop_size=300
        )
        plt.show()
    else:
        print("Skipping visualization (VIZ_CHANNELS not set)")
    return


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

    #### Common Parameters
    - `GPU`: Set to True to use GPU acceleration (if available).
    - `RECONCILE`: Method for reconciling nuclei and cell masks (typically "contained_in_cells", which allows more than one nucleus per cell and is useful for cells that are dividing).
    - `SEGMENT_CELLS`: Whether to segment cells, or only segment nuclei. If your analysis only requires nuclear features, set to False for faster processing.

    #### Select Segmentation Method
    - `SEGMENTATION_METHOD`: Choose from "cellpose" or "stardist" for cell segmentation.

    #### Cellpose Parameters (if using "cellpose")
    - `CELLPOSE_MODEL`: CellPose model to use. Options: "cyto3" (default), "cyto2", "cyto", "nuclei", or "cpsam" (requires Cellpose 4.x).
      - Note: When `SEGMENT_CELLS=False`, you can still use "cyto3" instead of "nuclei" if the nuclei model produces poor results.
    - `CELL_FLOW_THRESHOLD` & `NUCLEI_FLOW_THRESHOLD`: Flow threshold for Cellpose segmentation. Default is 0.4.
    - `CELL_CELLPROB_THRESHOLD` & `NUCLEI_CELLPROB_THRESHOLD`: Cell probability threshold for Cellpose. Default is 0.
    - `HELPER_INDEX`: (Optional) Index of additional channel to help with CPSAM segmentation. Only used with `cellpose_model="cpsam"`. Default is None.
    - Note: For Cellpose 3.x models (cyto3, cyto2), nuclei and cell diameters will be estimated automatically. For CPSAM (Cellpose 4.x), diameters can be left as None and will be estimated from initial segmentation results.

    #### StarDist Parameters (if using "stardist")
    - `STARDIST_MODEL`: StarDist model type. Default is "2D_versatile_fluo".
    - `CELL_PROB_THRESHOLD` & `NUCLEI_PROB_THRESHOLD`: Probability threshold for segmentation. Default is 0.479071.
    - `CELL_NMS_THRESHOLD` & `NUCLEI_NMS_THRESHOLD`: Non-maximum suppression threshold. Default is 0.3.
    """)
    return


@app.cell
def _(CHANNEL_NAMES, aligned_image):
    # === OPERATOR PARAMETERS ===
    CYTO_CHANNEL = None
    GPU = False
    RECONCILE = "contained_in_cells"
    SEGMENT_CELLS = True
    SEGMENTATION_METHOD = "cellpose"   # "cellpose" | "stardist"
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
    # === END OPERATOR PARAMETERS ===

    DAPI_INDEX = CHANNEL_NAMES.index("DAPI")
    CYTO_INDEX = CHANNEL_NAMES.index(CYTO_CHANNEL)

    # Estimate diameters (derivation; non-CPSAM cellpose only)
    if SEGMENTATION_METHOD == "cellpose" and CELLPOSE_MODEL != "cpsam":
        from lib.shared.segment_cellpose import estimate_diameters
        print("Estimating optimal cell and nuclei diameters...")
        NUCLEI_DIAMETER_INPUT, CELL_DIAMETER_INPUT = estimate_diameters(
            aligned_image,
            dapi_index=DAPI_INDEX,
            cyto_index=CYTO_INDEX,
            cellpose_model=CELLPOSE_MODEL,
        )
    else:
        # CPSAM cellpose / stardist: diameter inputs not pre-estimated.
        # CPSAM derives downstream from regionprops; stardist doesn't use these.
        print("Diameter inputs set to None (derived downstream for CPSAM, unused for stardist).")
        NUCLEI_DIAMETER_INPUT = None
        CELL_DIAMETER_INPUT = None
    return (
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
        NUCLEI_CELLPROB_THRESHOLD,
        NUCLEI_DIAMETER,
        NUCLEI_FLOW_THRESHOLD,
        NUCLEI_NMS_THRESHOLD,
        NUCLEI_PROB_THRESHOLD,
        RECONCILE,
        SEGMENTATION_METHOD,
        SEGMENT_CELLS,
        STARDIST_MODEL,
    )


@app.cell
def _(
    CELLPOSE_MODEL,
    CELL_CELLPROB_THRESHOLD,
    CELL_DIAMETER_INPUT,
    CELL_FLOW_THRESHOLD,
    CELL_NMS_THRESHOLD,
    CELL_PROB_THRESHOLD,
    CHANNEL_CMAPS,
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
    RECONCILE,
    SEGMENTATION_METHOD,
    SEGMENT_CELLS,
    STARDIST_MODEL,
    aligned_image,
    create_micropanel,
    identify_cytoplasm_cellpose,
    image_segmentation_annotations,
    np,
    plt,
    random_cmap,
):
    print(f'Segmenting image with {SEGMENTATION_METHOD}...')
    if SEGMENTATION_METHOD == 'cellpose':
        from lib.shared.segment_cellpose import segment_cellpose
        result = segment_cellpose(aligned_image, dapi_index=DAPI_INDEX, cyto_index=CYTO_INDEX, nuclei_diameter=NUCLEI_DIAMETER_INPUT, cell_diameter=CELL_DIAMETER_INPUT, cellpose_kwargs=dict(nuclei_flow_threshold=NUCLEI_FLOW_THRESHOLD, nuclei_cellprob_threshold=NUCLEI_CELLPROB_THRESHOLD, cell_flow_threshold=CELL_FLOW_THRESHOLD, cell_cellprob_threshold=CELL_CELLPROB_THRESHOLD), cellpose_model=CELLPOSE_MODEL, helper_index=HELPER_INDEX, gpu=GPU, reconcile=RECONCILE, cells=SEGMENT_CELLS)
    elif SEGMENTATION_METHOD == 'stardist':
        from lib.shared.segment_stardist import segment_stardist
        result = segment_stardist(aligned_image, dapi_index=DAPI_INDEX, cyto_index=CYTO_INDEX, model_type=STARDIST_MODEL, stardist_kwargs=dict(nuclei_prob_threshold=NUCLEI_PROB_THRESHOLD, nuclei_nms_threshold=NUCLEI_NMS_THRESHOLD, cell_prob_threshold=CELL_PROB_THRESHOLD, cell_nms_threshold=CELL_NMS_THRESHOLD), gpu=GPU, reconcile=RECONCILE, cells=SEGMENT_CELLS)
    if SEGMENT_CELLS:
        nuclei, cells = result
    else:
        nuclei = result
        cells = None
    print('Example microplots for DAPI channel and nuclei segmentation:')
    nuclei_cmap = random_cmap(num_colors=len(np.unique(nuclei)))
    nuclei_seg_microimages = [Microimage(aligned_image[DAPI_INDEX], channel_names='DAPI', cmaps=CHANNEL_CMAPS[DAPI_INDEX]), Microimage(nuclei, cmaps=nuclei_cmap, channel_names='Nuclei')]
    nuclei_seg_panel = create_micropanel(nuclei_seg_microimages, add_channel_label=True)
    plt.show()
    if SEGMENT_CELLS:
        print('Example microplots for merged channels and cells segmentation:')
        cells_cmap = random_cmap(num_colors=len(np.unique(cells)))
        cells_seg_microimages = [Microimage(aligned_image, channel_names='Merged', cmaps=CHANNEL_CMAPS), Microimage(cells, cmaps=cells_cmap, channel_names='Cells')]
        cells_seg_panel = create_micropanel(cells_seg_microimages, add_channel_label=True)
        plt.show()
        print('Example microplot for phenotype data annotated with segmentation:')
        annotated_data = image_segmentation_annotations(aligned_image, nuclei, cells)
        annotated_microimage = [Microimage(annotated_data, channel_names='Merged', cmaps=CHANNEL_CMAPS + ['pure_cyan'])]
        annotated_panel = create_micropanel(annotated_microimage, num_cols=1, figscaling=10, add_channel_label=False)
        plt.show()
        print('Example microplots for cytoplasms relative to nuclei:')
        cytoplasms = identify_cytoplasm_cellpose(nuclei, cells)
        cytoplasms_cmap = random_cmap(num_colors=len(np.unique(cytoplasms)))
        cytoplasms_microimages = [Microimage(nuclei, cmaps=nuclei_cmap, channel_names='Nuclei'), Microimage(cytoplasms, cmaps=cytoplasms_cmap, channel_names='Cytoplasms')]
        cytoplasms_panel = create_micropanel(cytoplasms_microimages, add_channel_label=True)
        plt.show()
    else:
        print('Skipping cell/cytoplasm visualization (SEGMENT_CELLS=False)')
        cytoplasms = None
    # Final diameters that go to config.yml. For CPSAM, derive from segmented
    # objects (regionprops); for non-CPSAM cellpose, pass through the pre-seg
    # estimate; for stardist, None (unused by that method).
    if SEGMENTATION_METHOD == 'cellpose' and CELLPOSE_MODEL == 'cpsam':
        from skimage.measure import regionprops
        nuclei_props = regionprops(nuclei)
        nuclei_diameters = [prop.equivalent_diameter for prop in nuclei_props]
        NUCLEI_DIAMETER = float(np.mean(nuclei_diameters))
        print(f'CPSAM derived NUCLEI_DIAMETER from segmentation: {NUCLEI_DIAMETER:.2f} px')
        if SEGMENT_CELLS:
            cells_props = regionprops(cells)
            cells_diameters = [prop.equivalent_diameter for prop in cells_props]
            CELL_DIAMETER = float(np.mean(cells_diameters))
            print(f'CPSAM derived CELL_DIAMETER from segmentation: {CELL_DIAMETER:.2f} px')
        else:
            CELL_DIAMETER = None
    else:
        # Non-CPSAM cellpose / stardist: pass through input
        NUCLEI_DIAMETER = NUCLEI_DIAMETER_INPUT
        CELL_DIAMETER = CELL_DIAMETER_INPUT
    return CELL_DIAMETER, NUCLEI_DIAMETER, cells, cytoplasms, nuclei


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

    ### Feature extraction

    - `CP_METHOD`: Methodology for phenotype feature extraction.
        - `cp_emulator`: Use emulated code from original _Feldman et. al. 2019_ to extract CellProfiler-like features.
        - `cp_measure`: Use Pythonic version of [CellProfiler](https://github.com/afermg/cp_measure) directly from Imaging Platform. Still in development, may run slowly in Jupyter notebook for testing purposes.
    - `FOCI_CHANNEL`: Name of the channel(s) used for foci detection (e.g., "GH2AX", "DAPI"). Can be a single channel name (string) or a list of channel names. The channel index(es) will be automatically derived from this name.
    - `CUSTOM_FEATURES`: List of extra per-cell feature functions to extract alongside the built-in ones, for measurements `cp_emulator` does not provide. Each takes a regionprops-like region, whose `region.intensity_image` is `(height, width, channel)` in `CHANNEL_NAMES` order, and returns a single number. Entries are either a bare function, measured on the nucleus, or a `(function, compartment)` pair, where compartment is `"nucleus"`, `"cell"`, or `"cytoplasm"` — measuring a nuclear feature on the cell mask returns plausible but wrong numbers, so declare the compartment the measurement is defined on. Only the function source travels to the workflow, so each function must define or import every name it uses. Each becomes a `{compartment}_custom_{name}_{hash}` column, where the hash pins the definition that produced it. Declaring `"cytoplasm"` requires `SEGMENT_CELLS = True` and cytoplasm segmentation. Requires `CP_METHOD = "cp_emulator"`.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    CP_METHOD = "cp_emulator"          # "cp_emulator" | "cp_measure"
    FOCI_CHANNEL = None
    # === END OPERATOR PARAMETERS ===
    return CP_METHOD, FOCI_CHANNEL


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    # Define each feature with def, then list it in CUSTOM_FEATURES, either bare to
    # measure it on the nucleus or as a (function, compartment) pair, e.g.
    #
    # def puncta_count(region):
    #     import skimage.measure
    #     import skimage.morphology
    #
    #     channel = region.intensity_image[..., 1]
    #     tophat = skimage.morphology.white_tophat(channel, skimage.morphology.disk(3))
    #     return int(skimage.measure.label(tophat > 50).max())
    #
    # CUSTOM_FEATURES = [puncta_count, (spread_index, "cell")]

    CUSTOM_FEATURES = []
    # === END OPERATOR PARAMETERS ===
    return (CUSTOM_FEATURES,)


@app.cell
def _(CUSTOM_FEATURES, load_custom_features, register_custom_features):
    # Round trip through the source text the workflow will receive, so a definition
    # that cannot survive the config hop fails here rather than on a compute node
    CUSTOM_FEATURE_DEFINITIONS = register_custom_features(CUSTOM_FEATURES)
    custom_features = load_custom_features(CUSTOM_FEATURE_DEFINITIONS)

    print(f"{len(CUSTOM_FEATURE_DEFINITIONS)} custom features registered:")
    for _definition in CUSTOM_FEATURE_DEFINITIONS:
        print(f"  {_definition['column']}")
    return CUSTOM_FEATURE_DEFINITIONS, custom_features


@app.cell
def _(
    CHANNEL_NAMES,
    CP_METHOD,
    FOCI_CHANNEL,
    SEGMENT_CELLS,
    WILDCARDS,
    aligned_image,
    cells,
    custom_features,
    cytoplasms,
    nuclei,
):
    print("Extracting phenotype features:")

    # Compute foci channel index from channel name(s)
    if FOCI_CHANNEL:
        if isinstance(FOCI_CHANNEL, str):
            FOCI_CHANNEL_INDEX = CHANNEL_NAMES.index(FOCI_CHANNEL)
        else:
            FOCI_CHANNEL_INDEX = [CHANNEL_NAMES.index(ch) for ch in FOCI_CHANNEL]
    else:
        FOCI_CHANNEL_INDEX = None

    if CP_METHOD == "cp_measure":
        from lib.phenotype.extract_phenotype_cp_measure import extract_phenotype_cp_measure
        # Extract features using cp_measure
        # Pass cells=None when SEGMENT_CELLS=False to skip cell/cytoplasm feature extraction
        phenotype_cp = extract_phenotype_cp_measure(
            aligned_image,
            nuclei=nuclei,
            cells=cells if SEGMENT_CELLS else None,
            cytoplasms=cytoplasms,
            channel_names=CHANNEL_NAMES,
        )
    elif CP_METHOD == "cp_emulator":
        from lib.phenotype.extract_phenotype_cp_emulator import (
            extract_phenotype_cp_emulator,
        )
        # Extract features using CellProfiler emulator
        # Pass cells=None when SEGMENT_CELLS=False to skip cell/cytoplasm feature extraction
        phenotype_cp = extract_phenotype_cp_emulator(
            aligned_image,
            nuclei=nuclei,
            cells=cells if SEGMENT_CELLS else None,
            wildcards=WILDCARDS,
            cytoplasms=cytoplasms,
            foci_channel=FOCI_CHANNEL_INDEX,
            channel_names=CHANNEL_NAMES,
            custom_features=custom_features,
        )
    else:
        raise ValueError(f"Unknown CP_METHOD: {CP_METHOD}. Choose 'cp_measure' or 'cp_emulator'.")

    phenotype_cp
    return FOCI_CHANNEL_INDEX, phenotype_cp


@app.cell
def _(CHANNEL_NAMES, phenotype_cp):
    # Remove channel names from feature names
    def remove_channel_name(feature, channels):
        for channel in channels:
            feature = feature.replace(f"_{channel}", "")
        return feature


    # Remove label, well, tile and isolate remaining feature names
    filtered_features = [
        feature
        for feature in phenotype_cp.columns.tolist()
        if feature not in ["label", "well", "tile"]
    ]

    # Apply the function to remove channel names
    feature_types = [
        remove_channel_name(feature, CHANNEL_NAMES) for feature in filtered_features
    ]

    # Get unique feature types
    unique_feature_types = sorted(set(feature_types))

    print("Unique feature types:")
    unique_feature_types
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Secondary object detection (optional)

    Segment and phenotype additional objects contained within cells (e.g. an intracellular pathogen, organelles, foci). Leave `SECOND_OBJ_DETECTION = False` to skip.

    - `SECOND_OBJ_DETECTION`: Whether to detect secondary objects.
    - `SECOND_OBJ_CHANNEL`: Name of the channel carrying the secondary objects.
    - `SECOND_OBJ_METHOD`: `"threshold"` (classical), `"cellpose"`, or `"stardist"`.

    **Size filtering and cell association (all methods)**
    - `SECOND_OBJ_MIN_SIZE` / `SECOND_OBJ_MAX_SIZE`: Valid object size, as Feret diameter or pixel area depending on `SIZE_FILTER_METHOD` (`"feret"` or `"area"`).
    - `MAX_OBJECTS_PER_CELL`: Maximum objects kept per cell.
    - `OVERLAP_THRESHOLD`: Minimum overlap ratio to associate an object with a cell.
    - `MAX_TOTAL_OBJECTS`: Failsafe; a tile with more detected objects returns empty results.

    **Cellpose** (`SECOND_OBJ_METHOD = "cellpose"`): `SECOND_OBJ_CELLPOSE_MODEL`, `SECOND_OBJ_DIAMETER` (`None` estimates from the test image), `SECOND_OBJ_FLOW_THRESHOLD`, `SECOND_OBJ_CELLPROB_THRESHOLD`.

    **StarDist** (`SECOND_OBJ_METHOD = "stardist"`): `SECOND_OBJ_STARDIST_MODEL`, `SECOND_OBJ_PROB_THRESHOLD`, `SECOND_OBJ_NMS_THRESHOLD`.

    **Threshold** (`SECOND_OBJ_METHOD = "threshold"`)
    - `THRESHOLD_SMOOTHING_SCALE`: Gaussian sigma before thresholding.
    - `THRESHOLD_METHOD`: `"otsu_two_peak"`, `"otsu_three_peak_mid_bg"`, `"otsu_three_peak_mid_fg"`, or `"min_cross_entropy"`.
    - `USE_MORPHOLOGICAL_OPENING` / `OPENING_DISK_RADIUS`: Opening to separate weakly connected objects.
    - `FILL_HOLES`: `"threshold"`, `"declump"`, `"both"`, or `"none"`.
    - `DECLUMP_METHOD`: `"none"`, `"shape"`, `"intensity"`, or `"shape_intensity"`; `DECLUMP_MODE`: `"watershed"`, `"propagate"`, or `"none"`.
    - `SUPPRESS_LOCAL_MAXIMA`: Minimum spacing between seeds in pixels (decrease if objects merge, increase if they over-split).
    - `MAXIMA_REDUCTION_FACTOR`: H-minima suppression of weak seeds (0-1), `None` to disable.
    - `USE_SHAPE_REFINEMENT` / `PROPORTION_THRESHOLD`: Reject watershed splits whose boundary is long relative to the perimeter.
    """)
    return


@app.cell
def _(CHANNEL_NAMES, GPU, aligned_image):
    # === OPERATOR PARAMETERS (SECONDARY OBJECTS — optional) ===
    SECOND_OBJ_DETECTION = False
    SECOND_OBJ_CHANNEL = None
    SECOND_OBJ_METHOD = "threshold"    # "threshold" | "cellpose" | "stardist"

    # Size filtering and cell association (all methods)
    SECOND_OBJ_MIN_SIZE = 10
    SECOND_OBJ_MAX_SIZE = 200
    SIZE_FILTER_METHOD = "feret"
    MAX_OBJECTS_PER_CELL = 120
    OVERLAP_THRESHOLD = 0.1
    MAX_TOTAL_OBJECTS = 1000

    # Cellpose parameters (SECOND_OBJ_METHOD == "cellpose")
    SECOND_OBJ_CELLPOSE_MODEL = "cyto3"
    SECOND_OBJ_DIAMETER_INPUT = None   # None = estimate from the test image
    SECOND_OBJ_FLOW_THRESHOLD = 0.4
    SECOND_OBJ_CELLPROB_THRESHOLD = 0.0

    # StarDist parameters (SECOND_OBJ_METHOD == "stardist")
    SECOND_OBJ_STARDIST_MODEL = "2D_versatile_fluo"
    SECOND_OBJ_PROB_THRESHOLD = 0.5
    SECOND_OBJ_NMS_THRESHOLD = 0.4

    # Threshold parameters (SECOND_OBJ_METHOD == "threshold")
    THRESHOLD_SMOOTHING_SCALE = 1.3488
    THRESHOLD_METHOD = "otsu_two_peak"
    USE_MORPHOLOGICAL_OPENING = True
    OPENING_DISK_RADIUS = 1
    FILL_HOLES = "both"
    DECLUMP_METHOD = "shape"
    DECLUMP_MODE = "watershed"
    SUPPRESS_LOCAL_MAXIMA = 20
    MAXIMA_REDUCTION_FACTOR = None
    USE_SHAPE_REFINEMENT = False
    PROPORTION_THRESHOLD = 0.4
    RETURN_INTERMEDIATE_OUTPUTS = False  # show the threshold mask in the preview below
    # === END OPERATOR PARAMETERS ===

    SECOND_OBJ_CHANNEL_INDEX = (
        CHANNEL_NAMES.index(SECOND_OBJ_CHANNEL) if SECOND_OBJ_DETECTION else None
    )
    SECOND_OBJ_DIAMETER = SECOND_OBJ_DIAMETER_INPUT
    if (
        SECOND_OBJ_DETECTION
        and SECOND_OBJ_METHOD == "cellpose"
        and SECOND_OBJ_DIAMETER is None
    ):
        from lib.phenotype.segment_secondary_object import estimate_second_obj_diameter

        # cpsam (Cellpose 4) has no automatic diameter estimate
        _estimation_method = "manual" if SECOND_OBJ_CELLPOSE_MODEL == "cpsam" else "cellpose"
        print(f"Estimating secondary object diameter in {SECOND_OBJ_CHANNEL}...")
        SECOND_OBJ_DIAMETER = estimate_second_obj_diameter(
            aligned_image,
            SECOND_OBJ_CHANNEL_INDEX,
            method=_estimation_method,
            model_type=SECOND_OBJ_CELLPOSE_MODEL,
            gpu=GPU,
        )
        print(f"Estimated diameter: {SECOND_OBJ_DIAMETER}")
    return (
        DECLUMP_METHOD,
        DECLUMP_MODE,
        FILL_HOLES,
        MAXIMA_REDUCTION_FACTOR,
        MAX_OBJECTS_PER_CELL,
        MAX_TOTAL_OBJECTS,
        OPENING_DISK_RADIUS,
        OVERLAP_THRESHOLD,
        PROPORTION_THRESHOLD,
        RETURN_INTERMEDIATE_OUTPUTS,
        SECOND_OBJ_CELLPOSE_MODEL,
        SECOND_OBJ_CELLPROB_THRESHOLD,
        SECOND_OBJ_CHANNEL,
        SECOND_OBJ_CHANNEL_INDEX,
        SECOND_OBJ_DETECTION,
        SECOND_OBJ_DIAMETER,
        SECOND_OBJ_FLOW_THRESHOLD,
        SECOND_OBJ_MAX_SIZE,
        SECOND_OBJ_METHOD,
        SECOND_OBJ_MIN_SIZE,
        SECOND_OBJ_NMS_THRESHOLD,
        SECOND_OBJ_PROB_THRESHOLD,
        SECOND_OBJ_STARDIST_MODEL,
        SIZE_FILTER_METHOD,
        SUPPRESS_LOCAL_MAXIMA,
        THRESHOLD_METHOD,
        THRESHOLD_SMOOTHING_SCALE,
        USE_MORPHOLOGICAL_OPENING,
        USE_SHAPE_REFINEMENT,
    )


@app.cell
def _(
    CHANNEL_CMAPS,
    CHANNEL_NAMES,
    DECLUMP_METHOD,
    DECLUMP_MODE,
    FILL_HOLES,
    GPU,
    MAXIMA_REDUCTION_FACTOR,
    MAX_OBJECTS_PER_CELL,
    MAX_TOTAL_OBJECTS,
    OPENING_DISK_RADIUS,
    OVERLAP_THRESHOLD,
    PROPORTION_THRESHOLD,
    RETURN_INTERMEDIATE_OUTPUTS,
    SECOND_OBJ_CELLPOSE_MODEL,
    SECOND_OBJ_CELLPROB_THRESHOLD,
    SECOND_OBJ_CHANNEL,
    SECOND_OBJ_CHANNEL_INDEX,
    SECOND_OBJ_DETECTION,
    SECOND_OBJ_DIAMETER,
    SECOND_OBJ_FLOW_THRESHOLD,
    SECOND_OBJ_MAX_SIZE,
    SECOND_OBJ_METHOD,
    SECOND_OBJ_MIN_SIZE,
    SECOND_OBJ_NMS_THRESHOLD,
    SECOND_OBJ_PROB_THRESHOLD,
    SECOND_OBJ_STARDIST_MODEL,
    SIZE_FILTER_METHOD,
    SUPPRESS_LOCAL_MAXIMA,
    THRESHOLD_METHOD,
    THRESHOLD_SMOOTHING_SCALE,
    USE_MORPHOLOGICAL_OPENING,
    USE_SHAPE_REFINEMENT,
    aligned_image,
    cells,
    cytoplasms,
    nuclei,
    plt,
):
    # Segment secondary objects on the test image
    second_obj_masks = None
    cell_second_obj_table = None
    if SECOND_OBJ_DETECTION:
        from skimage import measure
        from lib.phenotype.segment_secondary_object import (
            segment_second_objs,
            segment_second_objs_ml,
            create_second_obj_boundary_visualization,
            create_second_obj_standard_visualization,
        )

        print(f"Segmenting secondary objects in {SECOND_OBJ_CHANNEL} with the {SECOND_OBJ_METHOD} method...")

        # Nuclei centroids for cell-nucleus distance features
        _nuclei_centroids = {
            region.label: region.centroid for region in measure.regionprops(nuclei)
        }
        _common = dict(
            image=aligned_image,
            second_obj_channel_index=SECOND_OBJ_CHANNEL_INDEX,
            cell_masks=cells,
            cytoplasm_masks=cytoplasms,
            second_obj_min_size=SECOND_OBJ_MIN_SIZE,
            second_obj_max_size=SECOND_OBJ_MAX_SIZE,
            size_filter_method=SIZE_FILTER_METHOD,
            max_objects_per_cell=MAX_OBJECTS_PER_CELL,
            overlap_threshold=OVERLAP_THRESHOLD,
            nuclei_centroids=_nuclei_centroids,
            max_total_objects=MAX_TOTAL_OBJECTS,
        )
        _threshold_output = None

        if SECOND_OBJ_METHOD == "cellpose":
            second_obj_masks, cell_second_obj_table, _updated_cytoplasms = segment_second_objs_ml(
                **_common,
                second_obj_method="cellpose",
                gpu=GPU,
                second_obj_cellpose_model=SECOND_OBJ_CELLPOSE_MODEL,
                second_obj_diameter=SECOND_OBJ_DIAMETER,
                second_obj_flow_threshold=SECOND_OBJ_FLOW_THRESHOLD,
                second_obj_cellprob_threshold=SECOND_OBJ_CELLPROB_THRESHOLD,
            )
        elif SECOND_OBJ_METHOD == "stardist":
            second_obj_masks, cell_second_obj_table, _updated_cytoplasms = segment_second_objs_ml(
                **_common,
                second_obj_method="stardist",
                gpu=GPU,
                second_obj_stardist_model=SECOND_OBJ_STARDIST_MODEL,
                second_obj_prob_threshold=SECOND_OBJ_PROB_THRESHOLD,
                second_obj_nms_threshold=SECOND_OBJ_NMS_THRESHOLD,
            )
        elif SECOND_OBJ_METHOD == "threshold":
            _result = segment_second_objs(
                **_common,
                threshold_smoothing_scale=THRESHOLD_SMOOTHING_SCALE,
                threshold_method=THRESHOLD_METHOD,
                use_morphological_opening=USE_MORPHOLOGICAL_OPENING,
                opening_disk_radius=OPENING_DISK_RADIUS,
                fill_holes=FILL_HOLES,
                declump_method=DECLUMP_METHOD,
                declump_mode=DECLUMP_MODE,
                suppress_local_maxima=SUPPRESS_LOCAL_MAXIMA,
                maxima_reduction_factor=MAXIMA_REDUCTION_FACTOR,
                use_shape_refinement=USE_SHAPE_REFINEMENT,
                proportion_threshold=PROPORTION_THRESHOLD,
                return_threshold_output=RETURN_INTERMEDIATE_OUTPUTS,
            )
            second_obj_masks, cell_second_obj_table, _updated_cytoplasms, *_opt = _result
            _threshold_output = _opt[0] if _opt else None
        else:
            raise ValueError(f"Unknown SECOND_OBJ_METHOD: {SECOND_OBJ_METHOD}")

        _summary = cell_second_obj_table["cell_summary"]
        print(f"Found secondary objects in {_summary['has_second_obj'].sum()} of {len(_summary)} cells")
        print(f"Mean objects per cell with objects: {_summary.loc[_summary['has_second_obj'], 'num_second_objs'].mean():.2f}")
        print(f"Mean secondary object area ratio: {_summary['second_obj_area_ratio'].mean():.4f}")

        print("Example microplots:")
        create_second_obj_standard_visualization(
            aligned_image,
            SECOND_OBJ_CHANNEL_INDEX,
            SECOND_OBJ_CHANNEL,
            second_obj_masks,
            threshold_output=_threshold_output,
        )
        plt.show()

        print("Cell and secondary object boundaries:")
        create_second_obj_boundary_visualization(
            aligned_image,
            SECOND_OBJ_CHANNEL_INDEX,
            cell_masks=cells,
            second_obj_masks=second_obj_masks,
            channel_names=CHANNEL_NAMES,
            channel_cmaps=CHANNEL_CMAPS,
        )
        plt.show()
    else:
        print("SECOND_OBJ_DETECTION is False, skipping secondary object segmentation")
    return cell_second_obj_table, second_obj_masks


@app.cell
def _(
    CHANNEL_NAMES,
    FOCI_CHANNEL_INDEX,
    SECOND_OBJ_DETECTION,
    WILDCARDS,
    aligned_image,
    cell_second_obj_table,
    second_obj_masks,
):
    # Extract secondary object features on the test image
    if SECOND_OBJ_DETECTION:
        from lib.phenotype.extract_phenotype_second_objs import extract_phenotype_second_objs

        second_obj_phenotype = extract_phenotype_second_objs(
            aligned_image,
            second_objs=second_obj_masks,
            second_obj_cell_mapping_df=cell_second_obj_table["second_obj_cell_mapping"],
            wildcards=WILDCARDS,
            foci_channel=FOCI_CHANNEL_INDEX,
            channel_names=CHANNEL_NAMES,
        )
        print(f"Mean secondary object diameter: {second_obj_phenotype['second_obj_diameter'].mean():.2f}")
        print(f"Mean secondary object area: {second_obj_phenotype['second_obj_area'].mean():.2f}")

        _feature_cols = [
            col for col in second_obj_phenotype.columns
            if col not in ["label", "well", "tile", "cell_label"]
        ]
        print(f"Number of secondary object features: {len(_feature_cols)}")

        def _strip_channels(feature):
            for channel in CHANNEL_NAMES:
                feature = feature.replace(f"_{channel}", "")
            return feature

        print("Unique secondary object feature types:")
        sorted(set(_strip_channels(feature) for feature in _feature_cols))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Add phenotype process parameters to config file
    """)
    return


@app.cell
def _(
    ALIGN,
    CELLPOSE_MODEL,
    CELL_CELLPROB_THRESHOLD,
    CELL_DIAMETER,
    CELL_FLOW_THRESHOLD,
    CELL_NMS_THRESHOLD,
    CELL_PROB_THRESHOLD,
    CHANNEL_NAMES,
    CONFIG_FILE_HEADER,
    CONFIG_FILE_PATH,
    CP_METHOD,
    CUSTOM_CHANNEL_OFFSETS,
    CUSTOM_CHANNEL_OFFSETS_INDEXED,
    CUSTOM_FEATURE_DEFINITIONS,
    CYTO_INDEX,
    DAPI_INDEX,
    DECLUMP_METHOD,
    DECLUMP_MODE,
    FILL_HOLES,
    FOCI_CHANNEL_INDEX,
    GPU,
    HELPER_INDEX,
    MAXIMA_REDUCTION_FACTOR,
    MAX_OBJECTS_PER_CELL,
    MAX_TOTAL_OBJECTS,
    NUCLEI_CELLPROB_THRESHOLD,
    NUCLEI_DIAMETER,
    NUCLEI_FLOW_THRESHOLD,
    NUCLEI_NMS_THRESHOLD,
    NUCLEI_PROB_THRESHOLD,
    OPENING_DISK_RADIUS,
    OVERLAP_THRESHOLD,
    PROPORTION_THRESHOLD,
    RECONCILE,
    REMOVE_CHANNEL,
    RIDER_INDEXES,
    SECOND_OBJ_CELLPOSE_MODEL,
    SECOND_OBJ_CELLPROB_THRESHOLD,
    SECOND_OBJ_CHANNEL_INDEX,
    SECOND_OBJ_DETECTION,
    SECOND_OBJ_DIAMETER,
    SECOND_OBJ_FLOW_THRESHOLD,
    SECOND_OBJ_MAX_SIZE,
    SECOND_OBJ_METHOD,
    SECOND_OBJ_MIN_SIZE,
    SECOND_OBJ_NMS_THRESHOLD,
    SECOND_OBJ_PROB_THRESHOLD,
    SECOND_OBJ_STARDIST_MODEL,
    SEGMENTATION_METHOD,
    SEGMENT_CELLS,
    SIZE_FILTER_METHOD,
    SOURCE_INDEX,
    STARDIST_MODEL,
    SUPPRESS_LOCAL_MAXIMA,
    TARGET_INDEX,
    THRESHOLD_METHOD,
    THRESHOLD_SMOOTHING_SCALE,
    UPSAMPLE_FACTOR,
    USE_MORPHOLOGICAL_OPENING,
    USE_SHAPE_REFINEMENT,
    WINDOW,
    config,
    convert_tuples_to_lists,
    yaml,
):
    config['phenotype'] = {'foci_channel_index': FOCI_CHANNEL_INDEX, 'channel_names': CHANNEL_NAMES, 'align': ALIGN, 'dapi_index': DAPI_INDEX, 'cyto_index': CYTO_INDEX, 'segmentation_method': SEGMENTATION_METHOD, 'reconcile': RECONCILE, 'gpu': GPU, 'segment_cells': SEGMENT_CELLS, 'cp_method': CP_METHOD}
    if SEGMENTATION_METHOD == 'cellpose':
        config['phenotype'].update({'nuclei_diameter': NUCLEI_DIAMETER, 'cell_diameter': CELL_DIAMETER, 'nuclei_flow_threshold': NUCLEI_FLOW_THRESHOLD, 'nuclei_cellprob_threshold': NUCLEI_CELLPROB_THRESHOLD, 'cell_flow_threshold': CELL_FLOW_THRESHOLD, 'cell_cellprob_threshold': CELL_CELLPROB_THRESHOLD, 'cellpose_model': CELLPOSE_MODEL})
        if HELPER_INDEX is not None:
            config['phenotype']['helper_index'] = HELPER_INDEX
    elif SEGMENTATION_METHOD == 'stardist':
        config['phenotype'].update({'stardist_model': STARDIST_MODEL, 'nuclei_prob_threshold': NUCLEI_PROB_THRESHOLD, 'nuclei_nms_threshold': NUCLEI_NMS_THRESHOLD, 'cell_prob_threshold': CELL_PROB_THRESHOLD, 'cell_nms_threshold': CELL_NMS_THRESHOLD})
    if ALIGN:
        config['phenotype']['target'] = TARGET_INDEX
        config['phenotype']['source'] = SOURCE_INDEX
        config['phenotype']['riders'] = RIDER_INDEXES
        config['phenotype']['remove_channel'] = REMOVE_CHANNEL
        config['phenotype']['upsample_factor'] = UPSAMPLE_FACTOR
        config['phenotype']['window'] = WINDOW
    if SECOND_OBJ_DETECTION:
        config['phenotype'].update({'second_obj_detection': SECOND_OBJ_DETECTION, 'second_obj_channel_index': SECOND_OBJ_CHANNEL_INDEX, 'second_obj_method': SECOND_OBJ_METHOD, 'use_ml_segmentation': SECOND_OBJ_METHOD in ['cellpose', 'stardist'], 'second_obj_min_size': SECOND_OBJ_MIN_SIZE, 'second_obj_max_size': SECOND_OBJ_MAX_SIZE, 'size_filter_method': SIZE_FILTER_METHOD, 'max_objects_per_cell': MAX_OBJECTS_PER_CELL, 'overlap_threshold': OVERLAP_THRESHOLD, 'max_total_objects': MAX_TOTAL_OBJECTS})
        if SECOND_OBJ_METHOD == 'cellpose':
            config['phenotype'].update({'second_obj_cellpose_model': SECOND_OBJ_CELLPOSE_MODEL, 'second_obj_diameter': SECOND_OBJ_DIAMETER, 'second_obj_flow_threshold': SECOND_OBJ_FLOW_THRESHOLD, 'second_obj_cellprob_threshold': SECOND_OBJ_CELLPROB_THRESHOLD})
        elif SECOND_OBJ_METHOD == 'stardist':
            config['phenotype'].update({'second_obj_stardist_model': SECOND_OBJ_STARDIST_MODEL, 'second_obj_prob_threshold': SECOND_OBJ_PROB_THRESHOLD, 'second_obj_nms_threshold': SECOND_OBJ_NMS_THRESHOLD})
        elif SECOND_OBJ_METHOD == 'threshold':
            config['phenotype'].update({'threshold_smoothing_scale': THRESHOLD_SMOOTHING_SCALE, 'threshold_method': THRESHOLD_METHOD, 'use_morphological_opening': USE_MORPHOLOGICAL_OPENING, 'opening_disk_radius': OPENING_DISK_RADIUS, 'fill_holes': FILL_HOLES, 'declump_method': DECLUMP_METHOD, 'declump_mode': DECLUMP_MODE, 'suppress_local_maxima': SUPPRESS_LOCAL_MAXIMA, 'maxima_reduction_factor': MAXIMA_REDUCTION_FACTOR, 'use_shape_refinement': USE_SHAPE_REFINEMENT, 'proportion_threshold': PROPORTION_THRESHOLD})
    else:
        config['phenotype']['second_obj_detection'] = False
    if CUSTOM_CHANNEL_OFFSETS:
        config['phenotype']['custom_channel_offsets'] = CUSTOM_CHANNEL_OFFSETS_INDEXED
    if CUSTOM_FEATURE_DEFINITIONS:
        config['phenotype']['custom_features'] = CUSTOM_FEATURE_DEFINITIONS
    safe_config = convert_tuples_to_lists(config)
    with open(CONFIG_FILE_PATH, 'w') as _config_file:
        _config_file.write(CONFIG_FILE_HEADER)
        yaml.dump(safe_config, _config_file, default_flow_style=False, sort_keys=False)
    return


@app.cell
def _(
    NUCLEI_DIAMETER,
    CELL_DIAMETER,
    SEGMENTATION_METHOD,
    CELLPOSE_MODEL,
):
    # === TUNED EXPORT ===
    # Writes derivation-cell outputs the wizard's confirm_tuned_loop reads
    # post-run (R3). Schema: {param: {derived, src}}.
    import json as _je
    from pathlib import Path as _Pe
    _t = {}
    if SEGMENTATION_METHOD == 'cellpose':
        _src = "regionprops on segmented objects" if CELLPOSE_MODEL == 'cpsam' else f"estimate_diameters ({CELLPOSE_MODEL})"
        _t["NUCLEI_DIAMETER"] = {"derived": float(NUCLEI_DIAMETER), "src": _src}
        if CELL_DIAMETER is not None:
            _t["CELL_DIAMETER"] = {"derived": float(CELL_DIAMETER), "src": _src}
    _out = _Pe(".brieflow") / "tuned_phenotype.json"
    _out.parent.mkdir(exist_ok=True)
    _out.write_text(_je.dumps(_t, indent=2, default=str))
    # === END TUNED EXPORT ===
    return


if __name__ == "__main__":
    app.run()
