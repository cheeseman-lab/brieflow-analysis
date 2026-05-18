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
    from lib.shared.io import read_image
    import matplotlib.pyplot as plt
    from microfilm.microplot import Microimage

    from lib.shared.configuration_utils import (
        CONFIG_FILE_HEADER,
        create_micropanel,
        random_cmap,
        image_segmentation_annotations,
        convert_tuples_to_lists,
    )
    from lib.shared.file_utils import get_filename, get_hcs_nested_path
    from lib.shared.illumination_correction import apply_ic_field
    from lib.phenotype.align_channels import align_phenotype_channels, visualize_phenotype_alignment
    from lib.shared.align import apply_custom_offsets
    from lib.phenotype.identify_cytoplasm_cellpose import (
        identify_cytoplasm_cellpose,
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
        np,
        plt,
        random_cmap,
        read_image,
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
    if IMAGE_FORMAT == 'zarr':
        phenotype_test_image_path = str(PREPROCESS_FP / 'images' / 'phenotype' / get_hcs_nested_path({'plate': TEST_PLATE, 'row': TEST_WELL[0], 'col': TEST_WELL[1:], 'tile': TEST_TILE}, 'image'))
    else:
        phenotype_test_image_path = str(PREPROCESS_FP / 'images' / 'phenotype' / get_filename({'plate': TEST_PLATE, 'well': TEST_WELL, 'tile': TEST_TILE}, 'image', 'tiff'))
    phenotype_test_image = read_image(phenotype_test_image_path)
    print('Applying illumination correction...')
    if IMAGE_FORMAT == 'zarr':
        ic_field_path = str(PREPROCESS_FP / 'ic_fields' / 'phenotype' / get_hcs_nested_path({'plate': TEST_PLATE, 'row': TEST_WELL[0], 'col': TEST_WELL[1:], 'tile': '0'}, 'ic_field'))
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
    # === END OPERATOR PARAMETERS ===

    DAPI_INDEX = CHANNEL_NAMES.index("DAPI")
    CYTO_INDEX = CHANNEL_NAMES.index(CYTO_CHANNEL)

    if SEGMENTATION_METHOD == "cellpose":
        # Parameters for CellPose method
        CELLPOSE_MODEL = "cyto3"
        NUCLEI_FLOW_THRESHOLD = 0.4
        NUCLEI_CELLPROB_THRESHOLD = 0.0
        CELL_FLOW_THRESHOLD = 1
        CELL_CELLPROB_THRESHOLD = 0
        HELPER_INDEX = None  # Optional: channel index to help with CPSAM segmentation

        # Only estimate diameters for non-CPSAM models
        if CELLPOSE_MODEL != "cpsam":
            from lib.shared.segment_cellpose import estimate_diameters
            print("Estimating optimal cell and nuclei diameters...")
            NUCLEI_DIAMETER, CELL_DIAMETER = estimate_diameters(
                aligned_image,
                dapi_index=DAPI_INDEX,
                cyto_index=CYTO_INDEX,
                cellpose_model=CELLPOSE_MODEL,
            )
        else:
            print("CPSAM model selected. Initial diameters set to None.")
            print("Note: Diameters will be estimated automatically from segmentation results in the next cell.")
            NUCLEI_DIAMETER = None  # Will be estimated from segmentation
            CELL_DIAMETER = None    # Will be estimated from segmentation

    elif SEGMENTATION_METHOD == "stardist":
        # Parameters for StarDist method
        STARDIST_MODEL = "2D_versatile_fluo"
        NUCLEI_PROB_THRESHOLD = 0.479071
        NUCLEI_NMS_THRESHOLD = 0.3
        CELL_PROB_THRESHOLD = 0.479071
        CELL_NMS_THRESHOLD = 0.3
    return (
        CELLPOSE_MODEL,
        CELL_CELLPROB_THRESHOLD,
        CELL_DIAMETER,
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
    CELL_DIAMETER,
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
    NUCLEI_DIAMETER,
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
        result = segment_cellpose(aligned_image, dapi_index=DAPI_INDEX, cyto_index=CYTO_INDEX, nuclei_diameter=NUCLEI_DIAMETER, cell_diameter=CELL_DIAMETER, cellpose_kwargs=dict(nuclei_flow_threshold=NUCLEI_FLOW_THRESHOLD, nuclei_cellprob_threshold=NUCLEI_CELLPROB_THRESHOLD, cell_flow_threshold=CELL_FLOW_THRESHOLD, cell_cellprob_threshold=CELL_CELLPROB_THRESHOLD), cellpose_model=CELLPOSE_MODEL, helper_index=HELPER_INDEX, gpu=GPU, reconcile=RECONCILE, cells=SEGMENT_CELLS)
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
    if SEGMENTATION_METHOD == 'cellpose' and CELLPOSE_MODEL == 'cpsam':
        from skimage.measure import regionprops
        nuclei_props = regionprops(nuclei)
        nuclei_diameters = [prop.equivalent_diameter for prop in nuclei_props]
    # Handle unpacking based on SEGMENT_CELLS
        estimated_nuclei_diameter = np.mean(nuclei_diameters)
        print(f'Nuclei - Average diameter: {estimated_nuclei_diameter:.2f} pixels')
        if SEGMENT_CELLS:
            cells_props = regionprops(cells)
            cells_diameters = [prop.equivalent_diameter for prop in cells_props]  # No cell segmentation
            estimated_cell_diameter = np.mean(cells_diameters)
    # Create and display micropanel of nuclei segmentation
            print(f'Cells - Average diameter: {estimated_cell_diameter:.2f} pixels')
            CELL_DIAMETER_1 = estimated_cell_diameter
            print(f'\nUpdated CELL_DIAMETER to {CELL_DIAMETER_1:.2f} pixels')
        NUCLEI_DIAMETER_1 = estimated_nuclei_diameter
    # Create and display micropanel of segmented cells (only if segmenting cells)
        print(f'Updated NUCLEI_DIAMETER to {NUCLEI_DIAMETER_1:.2f} pixels')  # Create and display micropanel of annotated phenotype data  # Create and display micropanel of cytoplasms  # Calculate nuclei diameters  # Calculate cell diameters  # Update the diameter variables for config
    return CELL_DIAMETER_1, NUCLEI_DIAMETER_1, cells, cytoplasms, nuclei


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
def _(
    CHANNEL_NAMES,
    CP_METHOD,
    FOCI_CHANNEL,
    SEGMENT_CELLS,
    WILDCARDS,
    aligned_image,
    cells,
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
    ## Add phenotype process parameters to config file
    """)
    return


@app.cell
def _(
    ALIGN,
    CELLPOSE_MODEL,
    CELL_CELLPROB_THRESHOLD,
    CELL_DIAMETER_1,
    CELL_FLOW_THRESHOLD,
    CELL_NMS_THRESHOLD,
    CELL_PROB_THRESHOLD,
    CHANNEL_NAMES,
    CONFIG_FILE_HEADER,
    CONFIG_FILE_PATH,
    CP_METHOD,
    CUSTOM_CHANNEL_OFFSETS,
    CUSTOM_CHANNEL_OFFSETS_INDEXED,
    CYTO_INDEX,
    DAPI_INDEX,
    FOCI_CHANNEL_INDEX,
    GPU,
    HELPER_INDEX,
    NUCLEI_CELLPROB_THRESHOLD,
    NUCLEI_DIAMETER_1,
    NUCLEI_FLOW_THRESHOLD,
    NUCLEI_NMS_THRESHOLD,
    NUCLEI_PROB_THRESHOLD,
    RECONCILE,
    REMOVE_CHANNEL,
    RIDER_INDEXES,
    SEGMENTATION_METHOD,
    SEGMENT_CELLS,
    SOURCE_INDEX,
    STARDIST_MODEL,
    TARGET_INDEX,
    UPSAMPLE_FACTOR,
    WINDOW,
    config,
    convert_tuples_to_lists,
    yaml,
):
    config['phenotype'] = {'foci_channel_index': FOCI_CHANNEL_INDEX, 'channel_names': CHANNEL_NAMES, 'align': ALIGN, 'dapi_index': DAPI_INDEX, 'cyto_index': CYTO_INDEX, 'segmentation_method': SEGMENTATION_METHOD, 'reconcile': RECONCILE, 'gpu': GPU, 'segment_cells': SEGMENT_CELLS, 'cp_method': CP_METHOD}
    if SEGMENTATION_METHOD == 'cellpose':
        config['phenotype'].update({'nuclei_diameter': NUCLEI_DIAMETER_1, 'cell_diameter': CELL_DIAMETER_1, 'nuclei_flow_threshold': NUCLEI_FLOW_THRESHOLD, 'nuclei_cellprob_threshold': NUCLEI_CELLPROB_THRESHOLD, 'cell_flow_threshold': CELL_FLOW_THRESHOLD, 'cell_cellprob_threshold': CELL_CELLPROB_THRESHOLD, 'cellpose_model': CELLPOSE_MODEL})
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
    if CUSTOM_CHANNEL_OFFSETS:
        config['phenotype']['custom_channel_offsets'] = CUSTOM_CHANNEL_OFFSETS_INDEXED
    safe_config = convert_tuples_to_lists(config)
    with open(CONFIG_FILE_PATH, 'w') as _config_file:
        _config_file.write(CONFIG_FILE_HEADER)
        yaml.dump(safe_config, _config_file, default_flow_style=False, sort_keys=False)
    return


if __name__ == "__main__":
    app.run()
