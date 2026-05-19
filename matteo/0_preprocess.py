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
    # Configure Preprocessing Params

    This notebook should be used to set up preprocessing params.
    Cells marked with <font color='red'>SET PARAMETERS</font> contain crucial variables that need to be set according to your specific experimental setup and data organization.
    Please review and modify these variables as needed before proceeding with the analysis.

    **Dual-mode**: when run interactively (`marimo edit`), edit the SET PARAMETERS cells directly. When run via the brieflow-ops wizard, the wizard reads `analysis/.brieflow/interview.json` and rewrites the literal values between the `=== OPERATOR PARAMETERS ===` markers in each parameter cell. Either way, the notebook itself is the readable record of what was set.
    """)
    return


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
    import pandas as pd
    from microfilm.microplot import Microimage
    import matplotlib.pyplot as plt

    from lib.shared.configuration_utils import (
        CONFIG_FILE_HEADER,
        create_samples_df,
        create_micropanel,
        convert_tuples_to_lists,
    )
    from lib.preprocess.preprocess import extract_metadata, convert_to_array
    from lib.preprocess.file_utils import get_sample_fps, get_tile_count_from_well

    return (
        CONFIG_FILE_HEADER,
        Microimage,
        Path,
        convert_to_array,
        convert_tuples_to_lists,
        create_micropanel,
        create_samples_df,
        extract_metadata,
        get_sample_fps,
        get_tile_count_from_well,
        pd,
        plt,
        yaml,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Fixed parameters for preprocessing

    - `CONFIG_FILE_PATH`: Path to a Brieflow config file used during processing.
    - `ROOT_FP`: Path to root of Brieflow output directory.
    - `IMAGE_FORMAT`: Output image format for Brieflow (`"zarr"` or `"tiff"`).
      - Use `"zarr"` for OME-Zarr outputs (writes `*.zarr/` directories + `zarr.json` metadata).
      - Use `"tiff"` for legacy TIFF-based outputs.

    *Note: Paths can be absolute or relative to where workflows are run from.*
    """)
    return


@app.cell
def _(Path):
    # === OPERATOR PARAMETERS ===
    CONFIG_FILE_PATH = "config/config.yml"
    ROOT_FP = "brieflow_output/"
    IMAGE_FORMAT = "zarr"              # "zarr" | "tiff"
    # === END OPERATOR PARAMETERS ===

    Path(CONFIG_FILE_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(ROOT_FP).mkdir(parents=True, exist_ok=True)
    return CONFIG_FILE_PATH, IMAGE_FORMAT, ROOT_FP


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Paths to dataframes with sample information
    - `SBS_SAMPLES_DF_FP`/`PHENOTYPE_SAMPLES_DF_FP`: Path to dataframe where SBS/phenotype samples location and metadata will be stored.
    - `SBS_COMBO_DF_FP`/`PHENOTYPE_COMBO_DF_FP`: Path to dataframe where SBS/phenotype sample metadata combinations will be stored.
    - `SBS_IMAGES_DIR_FP`/`PHENOTYPE_IMAGES_DIR_FP`: Path to directories with SBS/phenotype sample ND2 files. Set to `None` to ignore SBS/phenotype testing in this notebook.

    ### Pattern configurations for metadata extraction

    #### SBS Configuration
    - `SBS_PATH_PATTERN`: Regex pattern to match directory structure of SBS files
    - `SBS_PATH_METADATA`: List of metadata to extract from file path
        - Should include at least `"plate", "well", "tile", "cycle"` to extract SBS processing information
        - Optionally include `"z"` if your TIFF files are split by z-plane (e.g., `image_Z-0.tif`, `image_Z-1.tif`)
    - `SBS_METADATA_ORDER_TYPE`: Metadata order will be used to organize the file paths dataframe. Metadata types will be used to convert parsed information.
    - `SBS_N_Z_PLANES`: Number of z-planes per channel. Set to `None` for standard inputs, or an integer (e.g., `2`, `3`) if input files are split by z-plane. When specified, all z-planes for each channel will be stacked and max-projected to create a single 3D image (CYX).

    #### Phenotype Configuration
    - `PHENOTYPE_PATH_PATTERN`: Regex pattern to match directory structure of phenotype files
    - `PHENOTYPE_PATH_METADATA`: List of metadata to extract from file path
        - Should include at least `"plate", "well", "tile"` to extract phenotype processing information
        - Optionally include `"z"` if your TIFF files are split by z-plane (e.g., `image_Z-0.tif`, `image_Z-1.tif`)
    - `PHENOTYPE_METADATA_ORDER_TYPE`: Metadata order will be used to organize the file paths dataframe. Metadata types will be used to convert parsed information.
    - `PHENOTYPE_N_Z_PLANES`: Number of z-planes per channel. Set to `None` for standard inputs, or an integer (e.g., `2`, `3`) if input files are split by z-plane. When specified, all z-planes for each channel will be stacked and max-projected to create a single 3D image (CYX).

    ### Data Format and Organization

    - `SBS_DATA_FORMAT`/`PHENOTYPE_DATA_FORMAT`:
      - `"nd2"`: Nikon ND2 files (most common)
      - `"tiff"`: TIFF files (requires external metadata)

    - `SBS_DATA_ORGANIZATION`/`PHENOTYPE_DATA_ORGANIZATION`:
      - `"tile"`: Each file contains ONE field of view (FOV/position)
        - Use when: Files like `plate1_well_A01_tile_001.nd2`, or `plate1_well_A01_tile_001.tiff`
      - `"well"`: Each file contains MULTIPLE fields of view
        - Use when: Files like `plate1_well_A01.nd2` with multiple positions inside

    ### Z-Dimension Handling (Optional)

    **When to use**: If your microscopy data is exported with separate TIFF files per z-plane (e.g., `image_Z-0.tif`, `image_Z-1.tif`, `image_Z-2.tif`), set the `*_N_Z_PLANES` parameter to the number of z-planes per channel.

    **How it works**:
    1. Include `"z"` in your `*_PATH_METADATA` list and capture it in your regex pattern
    2. Set `*_N_Z_PLANES` to the number of z-planes per channel (e.g., `2`, `3`, `5`)
    3. During preprocessing, files will be grouped by channel, and for each channel:
       - All z-planes are stacked along the Z axis (creating CZYX format)
       - Max-projected along Z to create final CYX output
    4. The output will be a standard 3D image (CYX) for downstream processing

    **Example for z-split TIFFs with 2 z-planes per channel**:
    ```python
    SBS_PATH_PATTERN = r"plate_(\d+)/c(\d+)/.*_Wells-([A-Z]\d+)_Points-(\d+)_Z-(\d+)\.tif"
    SBS_PATH_METADATA = ["plate", "cycle", "well", "tile", "z"]
    SBS_METADATA_ORDER_TYPE = {"plate": int, "well": str, "tile": int, "cycle": int, "z": int}
    SBS_N_Z_PLANES = 2  # 2 z-planes per channel
    SBS_CHANNEL_ORDER = ["DAPI", "GFP", "mCherry", "Cy5"]  # Must specify channel order for z-split files
    ```

    *Notes:*
    - Paths can be absolute or relative to where workflows are run from
    - Each pattern should have the same number of capture groups as pieces of metadata listed
    - Metadata lists should be ordered to match the capture groups in their corresponding regex pattern
    - Numeric values (like cycle numbers) will automatically be converted to integers
    - For Brieflow to run effectively, each sample file path should have an associated plate/well. For single plate/well screens, manually add a plate/well to the file path dataframe.
    - Z-dimension is **optional** - most datasets won't have it. Only include `"z"` in metadata if your files actually contain z-plane identifiers.
    - **IMPORTANT**: When using z-split files, you MUST specify `*_CHANNEL_ORDER` so files can be correctly grouped by channel before z-stacking.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    # Paths to sample dataframes (output of this notebook)
    SBS_SAMPLES_DF_FP = "config/sbs_samples.tsv"
    PHENOTYPE_SAMPLES_DF_FP = "config/phenotype_samples.tsv"
    SBS_COMBO_DF_FP = "config/sbs_combo.tsv"
    PHENOTYPE_COMBO_DF_FP = "config/phenotype_combo.tsv"

    # Paths to image directories — REQUIRED. e.g.: "/archive/.../input_sbs/"
    SBS_IMAGES_DIR_FP = None
    PHENOTYPE_IMAGES_DIR_FP = None

    # SBS pattern configurations — REQUIRED
    SBS_PATH_PATTERN = None              # e.g. r"plate_(\d+)/c(\d+)/.*Well([A-Z]\d+)..."
    SBS_PATH_METADATA = None             # e.g. ["plate", "cycle", "well", "channel"]
    SBS_METADATA_ORDER_TYPE = None       # e.g. {"plate": int, "well": str, "cycle": int, "channel": str}

    # Phenotype pattern configurations — REQUIRED
    PHENOTYPE_PATH_PATTERN = None
    PHENOTYPE_PATH_METADATA = None
    PHENOTYPE_METADATA_ORDER_TYPE = None

    # Data format and organization
    SBS_DATA_FORMAT = None                # "nd2" | "tiff"
    SBS_DATA_ORGANIZATION = None          # "tile" | "well"
    PHENOTYPE_DATA_FORMAT = None
    PHENOTYPE_DATA_ORGANIZATION = None

    # Z-dimension handling (None = 2D / standard input)
    SBS_N_Z_PLANES = None
    PHENOTYPE_N_Z_PLANES = None
    # === END OPERATOR PARAMETERS ===
    return (
        PHENOTYPE_COMBO_DF_FP,
        PHENOTYPE_DATA_FORMAT,
        PHENOTYPE_DATA_ORGANIZATION,
        PHENOTYPE_IMAGES_DIR_FP,
        PHENOTYPE_METADATA_ORDER_TYPE,
        PHENOTYPE_N_Z_PLANES,
        PHENOTYPE_PATH_METADATA,
        PHENOTYPE_PATH_PATTERN,
        PHENOTYPE_SAMPLES_DF_FP,
        SBS_COMBO_DF_FP,
        SBS_DATA_FORMAT,
        SBS_DATA_ORGANIZATION,
        SBS_IMAGES_DIR_FP,
        SBS_METADATA_ORDER_TYPE,
        SBS_N_Z_PLANES,
        SBS_PATH_METADATA,
        SBS_PATH_PATTERN,
        SBS_SAMPLES_DF_FP,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    You must supply a working regex to the `SBS_PATH_PATTERN` and `PHENOTYPE_PATH_PATTERN` variables. If you don't have experience with regex, you can use the following LLM prompt to generate the patterns.

    *Enter into a basic LLM chatbot*:

    Given ND2 filenames from your experiment, generate regex patterns to extract metadata. Return only the regex patterns with no explanation.

    Example sbs filenames: **[ENTER YOUR EXAMPLE SBS FILES HERE WITH ANY UPSTREAM FOLDER STRUCTURE THAT IS RELEVANT TO THE METADATA]**

    Example phenotype filenames: **[ENTER YOUR EXAMPLE PHENOTYPE FILES HERE WITH ANY UPSTREAM FOLDER STRUCTURE THAT IS RELEVANT TO THE METADATA]**

    Required regex patterns (return these exact variable assignments):
    ```python
    SBS_PATH_PATTERN = r"..."      # To match file path structure
    PHENOTYPE_PATH_PATTERN = r"..." # To match file path structure
    ```

    The patterns should extract:
    1. SBS pattern:
         - Plate number (after "plate_")
         - Well ID (e.g., "A1", "B2")
         - Tile number (after "Points-")
         - Cycle number (after "/c")
         - **Optional**: Z-plane number if files are z-split (e.g., "Z-0", "Z-1")
    2. PHENOTYPE pattern:
         - Plate number (after "plate_")
         - Well ID (e.g., "A1", "B2")
         - Tile number (after "Points-")
         - **Optional**: Z-plane number if files are z-split (e.g., "Z-0", "Z-1")

    Also provide the corresponding metadata lists and variable types:
    ```python
    SBS_PATH_METADATA = ["plate", "cycle", "well", "tile"]
    PHENOTYPE_PATH_METADATA = ["plate", "well", "tile"]
    SBS_METADATA_ORDER_TYPE = {"plate": int, "well": str, "tile": int, "cycle": int}
    PHENOTYPE_METADATA_ORDER_TYPE = {"plate": int, "well": str, "tile": int}

    # If z-dimension is present in filenames, add "z" to metadata:
    # SBS_PATH_METADATA = ["plate", "cycle", "well", "tile", "z"]
    # SBS_METADATA_ORDER_TYPE = {"plate": int, "well": str, "tile": int, "cycle": int, "z": int}
    # SBS_HAS_Z_DIMENSION = True
    ```

    Example patterns for reference:
    ```python
    # Standard patterns (no z-dimension)
    SBS_PATH_PATTERN = r"plate_(\d+)/c(\d+)/.*_Wells-([A-Z]\d+)_Points-(\d+)__.*"
    PHENOTYPE_PATH_PATTERN = r"P(\d+)_Pheno_20x_Wells-([A-Z]\d+)_Points-(\d+)__.*"

    SBS_PATH_METADATA = ["plate", "cycle", "well", "tile"]
    PHENOTYPE_PATH_METADATA = ["plate", "well", "tile"]

    SBS_METADATA_ORDER_TYPE = {"plate": int, "well": str, "tile": int, "cycle": int}
    PHENOTYPE_METADATA_ORDER_TYPE = {"plate": int, "well": str, "tile": int}

    # Example with z-dimension (z-split TIFFs)
    # SBS_PATH_PATTERN = r"plate_(\d+)/c(\d+)/.*_Wells-([A-Z]\d+)_Points-(\d+)_Z-(\d+)\.tif"
    # SBS_PATH_METADATA = ["plate", "cycle", "well", "tile", "z"]
    # SBS_METADATA_ORDER_TYPE = {"plate": int, "well": str, "tile": int, "cycle": int, "z": int}
    # SBS_HAS_Z_DIMENSION = True
    ```
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Create Sample DFs
    """)
    return


@app.cell
def _(
    PHENOTYPE_COMBO_DF_FP,
    PHENOTYPE_DATA_ORGANIZATION,
    PHENOTYPE_IMAGES_DIR_FP,
    PHENOTYPE_METADATA_ORDER_TYPE,
    PHENOTYPE_PATH_METADATA,
    PHENOTYPE_PATH_PATTERN,
    PHENOTYPE_SAMPLES_DF_FP,
    SBS_COMBO_DF_FP,
    SBS_DATA_ORGANIZATION,
    SBS_IMAGES_DIR_FP,
    SBS_METADATA_ORDER_TYPE,
    SBS_PATH_METADATA,
    SBS_PATH_PATTERN,
    SBS_SAMPLES_DF_FP,
    create_samples_df,
    mo,
    get_tile_count_from_well,
    pd,
):
    # Create SBS samples DataFrame
    sbs_samples = create_samples_df(
        SBS_IMAGES_DIR_FP, SBS_PATH_PATTERN, SBS_PATH_METADATA, SBS_METADATA_ORDER_TYPE
    )
    sbs_samples.to_csv(SBS_SAMPLES_DF_FP, sep="\t", index=False)
    print("SBS samples:")
    mo.ui.table(sbs_samples)

    # Create SBS wildcard combos based on data organization
    if SBS_DATA_ORGANIZATION == "tile":
        sbs_wildcard_combos = sbs_samples[SBS_PATH_METADATA].drop_duplicates().astype(str)
        sbs_wildcard_combos.to_csv(SBS_COMBO_DF_FP, sep="\t", index=False)
        print("SBS wildcard combos (tile organization):")
        mo.ui.table(sbs_wildcard_combos)
    elif SBS_DATA_ORGANIZATION == "well" and len(sbs_samples) > 0:
        print("SBS: Detecting tile count for well organization...")
        # Get tile count from a sample well
        SBS_TILES = get_tile_count_from_well(
            sbs_samples,
            plate=sbs_samples["plate"].iloc[0],
            well=sbs_samples["well"].iloc[0],
            cycle=sbs_samples["cycle"].iloc[0] if "cycle" in sbs_samples.columns else None,
            verbose=True
        )
        print(f"Detected {SBS_TILES} tiles per well for SBS")

        # Generate combos with detected tile count
        base_combos = sbs_samples[SBS_PATH_METADATA].drop_duplicates().astype(str)
        tiles = [str(i) for i in range(SBS_TILES)]
        sbs_wildcard_combos = pd.DataFrame([
            {**row.to_dict(), "tile": tile}
            for _, row in base_combos.iterrows()
            for tile in tiles
        ])
        sbs_wildcard_combos.to_csv(SBS_COMBO_DF_FP, sep="\t", index=False)
        print("SBS wildcard combos (well organization):")
        mo.ui.table(sbs_wildcard_combos)

    # Create phenotype samples DataFrame (always)
    phenotype_samples = create_samples_df(
        PHENOTYPE_IMAGES_DIR_FP,
        PHENOTYPE_PATH_PATTERN,
        PHENOTYPE_PATH_METADATA,
        PHENOTYPE_METADATA_ORDER_TYPE,
    )
    phenotype_samples.to_csv(PHENOTYPE_SAMPLES_DF_FP, sep="\t", index=False)
    print("Phenotype samples:")
    mo.ui.table(phenotype_samples)

    # Create phenotype wildcard combos based on data organization
    if PHENOTYPE_DATA_ORGANIZATION == "tile":
        phenotype_wildcard_combos = phenotype_samples[PHENOTYPE_PATH_METADATA].drop_duplicates().astype(str)
        phenotype_wildcard_combos.to_csv(PHENOTYPE_COMBO_DF_FP, sep="\t", index=False)
        print("Phenotype wildcard combos (tile organization):")
        mo.ui.table(phenotype_wildcard_combos)
    elif PHENOTYPE_DATA_ORGANIZATION == "well" and len(phenotype_samples) > 0:
        print("Phenotype: Detecting tile count for well organization...")
        # Get tile count from a sample well
        PHENOTYPE_TILES = get_tile_count_from_well(
            phenotype_samples,
            plate=phenotype_samples["plate"].iloc[0],
            well=phenotype_samples["well"].iloc[0],
            verbose=True
        )
        print(f"Detected {PHENOTYPE_TILES} tiles per well for phenotype")

        # Generate combos with detected tile count
        base_combos = phenotype_samples[PHENOTYPE_PATH_METADATA].drop_duplicates().astype(str)
        tiles = [str(i) for i in range(PHENOTYPE_TILES)]
        phenotype_wildcard_combos = pd.DataFrame([
            {**row.to_dict(), "tile": tile}
            for _, row in base_combos.iterrows()
            for tile in tiles
        ])
        phenotype_wildcard_combos.to_csv(PHENOTYPE_COMBO_DF_FP, sep="\t", index=False)
        print("Phenotype wildcard combos (well organization):")
        mo.ui.table(phenotype_wildcard_combos)
    return phenotype_samples, sbs_samples


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Metadata Source Configuration

    - `SBS_METADATA_*`/`PHENOTYPE_METADATA_*`: Configuration for external metadata files containing positional and imaging metadata.
     - **For TIFF files**: Usually required (e.g., `coordinates.csv`, `metadata.tsv`)
     - **For ND2 files**: Usually set directories to `None` (metadata extracted from ND2 headers)

    **Metadata File Organization:**
    - `*_METADATA_IMAGES_DIR_FP`: Base directory containing metadata files
    - `*_METADATA_PATH_PATTERN`: Regex pattern to find metadata files
    - `*_METADATA_PATH_METADATA`: Metadata to extract from file paths
    - `*_METADATA_SAMPLES_DF_FP`: Where to save the metadata file inventory
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    # External metadata files (TIFF-only; leave as None for ND2 data).
    SBS_METADATA_IMAGES_DIR_FP = None
    SBS_METADATA_PATH_PATTERN = None
    SBS_METADATA_PATH_METADATA = None
    SBS_METADATA_ORDER_TYPE_1 = None
    SBS_METADATA_SAMPLES_DF_FP = None
    PHENOTYPE_METADATA_IMAGES_DIR_FP = None
    PHENOTYPE_METADATA_PATH_PATTERN = None
    PHENOTYPE_METADATA_PATH_METADATA = None
    PHENOTYPE_METADATA_ORDER_TYPE_1 = None
    PHENOTYPE_METADATA_SAMPLES_DF_FP = None
    # === END OPERATOR PARAMETERS ===
    return (
        PHENOTYPE_METADATA_IMAGES_DIR_FP,
        PHENOTYPE_METADATA_ORDER_TYPE_1,
        PHENOTYPE_METADATA_PATH_METADATA,
        PHENOTYPE_METADATA_PATH_PATTERN,
        PHENOTYPE_METADATA_SAMPLES_DF_FP,
        SBS_METADATA_IMAGES_DIR_FP,
        SBS_METADATA_ORDER_TYPE_1,
        SBS_METADATA_PATH_METADATA,
        SBS_METADATA_PATH_PATTERN,
        SBS_METADATA_SAMPLES_DF_FP,
    )


@app.cell
def _(
    PHENOTYPE_METADATA_IMAGES_DIR_FP,
    PHENOTYPE_METADATA_ORDER_TYPE_1,
    PHENOTYPE_METADATA_PATH_METADATA,
    PHENOTYPE_METADATA_PATH_PATTERN,
    PHENOTYPE_METADATA_SAMPLES_DF_FP,
    SBS_METADATA_IMAGES_DIR_FP,
    SBS_METADATA_ORDER_TYPE_1,
    SBS_METADATA_PATH_METADATA,
    SBS_METADATA_PATH_PATTERN,
    SBS_METADATA_SAMPLES_DF_FP,
    create_samples_df,
    mo,
    pd,
):
    # Generate SBS metadata samples table
    if SBS_METADATA_IMAGES_DIR_FP is not None:
        print('Generating SBS metadata file inventory...')
        sbs_metadata_samples = create_samples_df(SBS_METADATA_IMAGES_DIR_FP, SBS_METADATA_PATH_PATTERN, SBS_METADATA_PATH_METADATA, SBS_METADATA_ORDER_TYPE_1)
        sbs_metadata_samples.to_csv(SBS_METADATA_SAMPLES_DF_FP, sep='\t', index=False)
        print('SBS metadata files found:')
        mo.ui.table(sbs_metadata_samples)
    else:
        print('SBS: No external metadata files - will extract from image files')
        sbs_metadata_samples = pd.DataFrame()
    if PHENOTYPE_METADATA_IMAGES_DIR_FP is not None:
        print('\nGenerating phenotype metadata file inventory...')
        phenotype_metadata_samples = create_samples_df(PHENOTYPE_METADATA_IMAGES_DIR_FP, PHENOTYPE_METADATA_PATH_PATTERN, PHENOTYPE_METADATA_PATH_METADATA, PHENOTYPE_METADATA_ORDER_TYPE_1)
        phenotype_metadata_samples.to_csv(PHENOTYPE_METADATA_SAMPLES_DF_FP, sep='\t', index=False)
        print('Phenotype metadata files found:')
        mo.ui.table(phenotype_metadata_samples)
    # Generate phenotype metadata samples table
    else:
        print('Phenotype: No external metadata files - will extract from ND2 files')
        phenotype_metadata_samples = pd.DataFrame()
    return phenotype_metadata_samples, sbs_metadata_samples


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Test Metadata Extraction
    """)
    return


@app.cell
def _(
    PHENOTYPE_DATA_FORMAT,
    PHENOTYPE_DATA_ORGANIZATION,
    SBS_DATA_FORMAT,
    SBS_DATA_ORGANIZATION,
    mo,
    extract_metadata,
    get_sample_fps,
    phenotype_metadata_samples,
    phenotype_samples,
    sbs_metadata_samples,
    sbs_samples,
):
    if len(sbs_samples) > 0:
        print("Testing SBS metadata extraction...")

        # Get metadata file for this specific sample
        if len(sbs_metadata_samples) > 0:
            # Find matching metadata file
            test_metadata_file = get_sample_fps(
                sbs_metadata_samples,
                plate=sbs_samples["plate"].iloc[0],
                cycle=sbs_samples["cycle"].iloc[0] if "cycle" in sbs_samples.columns else None
            )
            print(f"Using metadata file: {test_metadata_file}")
        else:
            test_metadata_file = None  
            print("No metadata files - extracting from image files")

        # Extract metadata using unified function
        test_sbs_metadata = extract_metadata(
            sbs_samples["sample_fp"].iloc[0],
            plate=sbs_samples["plate"].iloc[0],
            well=sbs_samples["well"].iloc[0],
            tile=sbs_samples["tile"].iloc[0] if "tile" in sbs_samples.columns else 0,
            cycle=sbs_samples.get("cycle", [None]).iloc[0],
            data_format=SBS_DATA_FORMAT,
            data_organization=SBS_DATA_ORGANIZATION,
            metadata_file_path=test_metadata_file,
            verbose=True
        )
        print("SBS test metadata:")
        mo.ui.table(test_sbs_metadata)

    # Test phenotype metadata extraction  
    if len(phenotype_samples) > 0:
        print("\nTesting phenotype metadata extraction...")

        # Get metadata file for this specific sample (if any)
        if len(phenotype_metadata_samples) > 0:
            # Find matching metadata file
            test_metadata_file = get_sample_fps(
                phenotype_metadata_samples,
                plate=phenotype_samples["plate"].iloc[0],
                round_order=phenotype_samples["round"].iloc[0] if "round" in phenotype_samples.columns else None
            )
            print(f"Using metadata file: {test_metadata_file}")
        else:
            test_metadata_file = None 
            print("No metadata files - extracting from ND2 files")

        # Extract metadata using unified function
        test_phenotype_metadata = extract_metadata(
            phenotype_samples["sample_fp"].iloc[0],
            plate=phenotype_samples["plate"].iloc[0],
            well=phenotype_samples["well"].iloc[0],
            tile=phenotype_samples["tile"].iloc[0] if "tile" in phenotype_samples.columns else 0,
            round=phenotype_samples["round"].iloc[0] if "round" in phenotype_samples.columns else None,
            data_format=PHENOTYPE_DATA_FORMAT,
            data_organization=PHENOTYPE_DATA_ORGANIZATION,
            metadata_file_path=test_metadata_file,
            verbose=True
        )
        print("Phenotype test metadata:")
        mo.ui.table(test_phenotype_metadata)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Image conversion

    - `SBS_CHANNEL_ORDER`/`PHENOTYPE_CHANNEL_ORDER`: Manually set channel order _if ND2 images are acquired as single channels, or there are multiple files for each tile (e.g. multiple rounds of phenotype images). Should be `None` if multichannel image files are acquired. The extracted channel names must match the values that will be displayed in the samples DataFrame channel column (e.g., `["DAPI", "GFP", "CY3", "CY5", "AF750"]`).
    - `PHENOTYPE_ROUND_ORDER`: List of round numbers specifying the order in which to process phenotype image rounds. Should be `None` if there is only one round of phenotyping. For multiple rounds, specify the round numbers in the desired order (e.g., `[1, 2, 3]`). The round numbers must match the values in the samples DataFrame round column.

    **Note** For single-channel files, each file must contain a channel identifier that your regex can extract. For multichannel files, set the channel patterns to `None`. Metadata extraction is only performed on the first channel dimension for each tile. Please ensure the Dapi channel is displayed first!

    - `SBS_CHANNEL_ORDER_FLIP`/`PHENOTYPE_CHANNEL_ORDER_FLIP`: Whether or not to flip channel order when converting ND2->tiff. Should be `False` if channels are in a standard order (with Dapi first), or `True` if channels are reversed. This will only occur for multichannel ND2 files, for each individual ND2 file. Setting the channel order for single channel files is done by setting `SBS_CHANNEL_ORDER`/`PHENOTYPE_CHANNEL_ORDER` previously.

    **Note** Channel order can be checked with the test conversions below. Please ensure the Dapi channel is displayed first!
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    SBS_CHANNEL_ORDER = None             # e.g., ["DAPI", "CY3", "A594", "CY5", "CY7"]
    PHENOTYPE_CHANNEL_ORDER = None       # e.g., ["DAPI", "GFP", "A594", "A750"]
    PHENOTYPE_ROUND_ORDER = None         # e.g., [1] for single-round, [1, 2, 3] for multi-round
    SBS_CHANNEL_ORDER_FLIP = False
    PHENOTYPE_CHANNEL_ORDER_FLIP = False
    # === END OPERATOR PARAMETERS ===
    return (
        PHENOTYPE_CHANNEL_ORDER,
        PHENOTYPE_CHANNEL_ORDER_FLIP,
        PHENOTYPE_ROUND_ORDER,
        SBS_CHANNEL_ORDER,
        SBS_CHANNEL_ORDER_FLIP,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Test Image Conversion
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Test SBS conversion
    """)
    return


@app.cell
def _(
    Microimage,
    SBS_CHANNEL_ORDER,
    SBS_CHANNEL_ORDER_FLIP,
    SBS_DATA_FORMAT,
    SBS_DATA_ORGANIZATION,
    SBS_N_Z_PLANES,
    convert_to_array,
    create_micropanel,
    get_sample_fps,
    plt,
    sbs_samples,
):
    if len(sbs_samples) > 0:
        print("Testing SBS image conversion...")

        # Get sample files based on data organization
        if SBS_DATA_ORGANIZATION == "tile":
            sbs_sample_files = get_sample_fps(
                sbs_samples,
                plate=sbs_samples["plate"].iloc[0],
                well=sbs_samples["well"].iloc[0],
                tile=sbs_samples["tile"].iloc[0] if "tile" in sbs_samples.columns else 0,
                cycle=sbs_samples["cycle"].iloc[0] if "cycle" in sbs_samples.columns else None,
                channel_order=SBS_CHANNEL_ORDER,
            )
        else:  # well organization
            sbs_sample_files = get_sample_fps(
                sbs_samples,
                plate=sbs_samples["plate"].iloc[0],
                well=sbs_samples["well"].iloc[0],
                cycle=sbs_samples["cycle"].iloc[0] if "cycle" in sbs_samples.columns else None,
                channel_order=SBS_CHANNEL_ORDER,
            )

        # Convert using unified function
        sbs_image = convert_to_array(
            sbs_sample_files,
            data_format=SBS_DATA_FORMAT,
            data_organization=SBS_DATA_ORGANIZATION,
            position=0 if SBS_DATA_ORGANIZATION == "well" else None,
            channel_order_flip=SBS_CHANNEL_ORDER_FLIP,
            n_z_planes=SBS_N_Z_PLANES,
            verbose=True
        )

        print(f"SBS converted image shape: {sbs_image.shape}")

        # Display images
        sbs_microimages = [Microimage(image) for image in sbs_image]
        sbs_panel = create_micropanel(sbs_microimages, add_channel_label=False)
        plt.title("SBS Test Conversion")
        plt.show()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Test phenotype conversion
    """)
    return


@app.cell
def _(
    Microimage,
    PHENOTYPE_CHANNEL_ORDER,
    PHENOTYPE_CHANNEL_ORDER_FLIP,
    PHENOTYPE_DATA_FORMAT,
    PHENOTYPE_DATA_ORGANIZATION,
    PHENOTYPE_N_Z_PLANES,
    PHENOTYPE_ROUND_ORDER,
    convert_to_array,
    create_micropanel,
    get_sample_fps,
    phenotype_samples,
    plt,
):
    if len(phenotype_samples) > 0:
        print("Testing phenotype image conversion...")

        # Get sample files based on data organization
        if PHENOTYPE_DATA_ORGANIZATION == "tile":
            phenotype_sample_files = get_sample_fps(
                phenotype_samples,
                plate=phenotype_samples["plate"].iloc[0],
                well=phenotype_samples["well"].iloc[0],
                tile=phenotype_samples["tile"].iloc[0] if "tile" in phenotype_samples.columns else 0,
                round_order=PHENOTYPE_ROUND_ORDER,
                channel_order=PHENOTYPE_CHANNEL_ORDER,
            )
        else:  # well organization
            phenotype_sample_files = get_sample_fps(
                phenotype_samples,
                plate=phenotype_samples["plate"].iloc[0],
                well=phenotype_samples["well"].iloc[0],
                round_order=PHENOTYPE_ROUND_ORDER,
                channel_order=PHENOTYPE_CHANNEL_ORDER,
            )

        # Convert using unified function
        phenotype_image = convert_to_array(
            phenotype_sample_files,
            data_format=PHENOTYPE_DATA_FORMAT,
            data_organization=PHENOTYPE_DATA_ORGANIZATION,
            position=0 if PHENOTYPE_DATA_ORGANIZATION == "well" else None,
            channel_order_flip=PHENOTYPE_CHANNEL_ORDER_FLIP,
            n_z_planes=PHENOTYPE_N_Z_PLANES,
            verbose=True
        )

        print(f"Phenotype converted image shape: {phenotype_image.shape}")

        # Display images
        phenotype_microimages = [Microimage(image) for image in phenotype_image]
        phenotype_panel = create_micropanel(phenotype_microimages, add_channel_label=False)
        plt.title("Phenotype Test Conversion")
        plt.show()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Calculate illumination correction field

    - `SAMPLE_FRACTION`: Controls what percentage of images to use when calculating the illumination correction field (0.0-1.0). Using a smaller fraction (e.g., 0.2 = 20%) speeds up processing by randomly sampling only a subset of your images. Default is 1.0 (use all images). For reliable results, ensure your sample contains enough images to accurately represent illumination variation.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    SAMPLE_FRACTION = 1.0
    # === END OPERATOR PARAMETERS ===
    return (SAMPLE_FRACTION,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Parameters for writing OME-Zarr **root** metadata for both SBS and PHENOTYPE (the 2 code cells proceeding this markdown cell)

    These parameters control what gets written into the *plate root* `zarr.json` for the SBS/Phenotype output.

    ### Channels

    - `<SBS or PHENOTYPE>_CHANNELS_METADATA`: A list of dictionaries, one per channel, written into the plate root `zarr.json`.
      - **Must be the same length and order as `CHANNEL_NAMES`.**
      - **Indices should start at 0 and match the position in `CHANNEL_NAMES`.**

    ### Fields per channel entry

    Each channel dictionary should include:

    - `name`: The channel name (should match `CHANNEL_NAMES[i]`)
    - `index`: The channel index (0-based, should equal `i`)
    - `channel_type`: A string describing the channel type
    - `description`: A short human-readable description
    - `biological_annotation`: Optional dictionary (include only if you want biological annotations)

    ### Example channel entry (with biological annotation)

    ```json
    {
      "name": "GFP",
      "index": 2,
      "channel_type": "fluorescent",
      "description": "Max projected chaperones visualized via HSPA1B",
      "biological_annotation": {
        "organelle": "chaperones",
        "marker": "HSPA1B",
        "marker_type": "endogenous_tag",
        "full_label": "chaperones, HSPA1B"
      }
    }
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    SBS_CHANNELS_METADATA = None        # list[dict]; see markdown above
    # === END OPERATOR PARAMETERS ===
    return (SBS_CHANNELS_METADATA,)


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    PHENOTYPE_CHANNELS_METADATA = None  # list[dict]; see markdown above
    # === END OPERATOR PARAMETERS ===
    return (PHENOTYPE_CHANNELS_METADATA,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Create config file with params
    """)
    return


@app.cell
def _(
    CONFIG_FILE_HEADER,
    CONFIG_FILE_PATH,
    IMAGE_FORMAT,
    PHENOTYPE_CHANNEL_ORDER,
    PHENOTYPE_CHANNEL_ORDER_FLIP,
    PHENOTYPE_CHANNELS_METADATA,
    PHENOTYPE_COMBO_DF_FP,
    PHENOTYPE_DATA_FORMAT,
    PHENOTYPE_DATA_ORGANIZATION,
    PHENOTYPE_METADATA_SAMPLES_DF_FP,
    PHENOTYPE_N_Z_PLANES,
    PHENOTYPE_ROUND_ORDER,
    PHENOTYPE_SAMPLES_DF_FP,
    ROOT_FP,
    SAMPLE_FRACTION,
    SBS_CHANNEL_ORDER,
    SBS_CHANNEL_ORDER_FLIP,
    SBS_CHANNELS_METADATA,
    SBS_COMBO_DF_FP,
    SBS_DATA_FORMAT,
    SBS_DATA_ORGANIZATION,
    SBS_METADATA_SAMPLES_DF_FP,
    SBS_N_Z_PLANES,
    SBS_SAMPLES_DF_FP,
    convert_tuples_to_lists,
    yaml,
):
    # Create empty config variable
    config = {}

    # Add all section
    config["all"] = {
        "root_fp": ROOT_FP,
        "image_format": IMAGE_FORMAT,
    }

    # Add preprocess section
    config["preprocess"] = {
        # File paths
        "sbs_samples_fp": SBS_SAMPLES_DF_FP,
        "sbs_combo_fp": SBS_COMBO_DF_FP,
        "phenotype_samples_fp": PHENOTYPE_SAMPLES_DF_FP,
        "phenotype_combo_fp": PHENOTYPE_COMBO_DF_FP,

        # SBS configuration
        "sbs_data_format": SBS_DATA_FORMAT,
        "sbs_data_organization": SBS_DATA_ORGANIZATION,
        "sbs_channel_order": SBS_CHANNEL_ORDER,
        "sbs_channel_order_flip": SBS_CHANNEL_ORDER_FLIP,
        "sbs_n_z_planes": SBS_N_Z_PLANES,
        "sbs_metadata_samples_df_fp": SBS_METADATA_SAMPLES_DF_FP,

        # Phenotype configuration
        "phenotype_data_format": PHENOTYPE_DATA_FORMAT,
        "phenotype_data_organization": PHENOTYPE_DATA_ORGANIZATION,
        "phenotype_channel_order": PHENOTYPE_CHANNEL_ORDER,
        "phenotype_channel_order_flip": PHENOTYPE_CHANNEL_ORDER_FLIP,
        "phenotype_round_order": PHENOTYPE_ROUND_ORDER,
        "phenotype_n_z_planes": PHENOTYPE_N_Z_PLANES,
        "phenotype_metadata_samples_df_fp": PHENOTYPE_METADATA_SAMPLES_DF_FP,

        # Processing parameters
        "sample_fraction": SAMPLE_FRACTION,

        # OME-Zarr channels_metadata (written to plate-root zarr.json)
        "sbs_channels_metadata": SBS_CHANNELS_METADATA,
        "phenotype_channels_metadata": PHENOTYPE_CHANNELS_METADATA,
    }

    # Convert tuples to lists before dumping
    safe_config = convert_tuples_to_lists(config)

    # Write the updated configuration back with markdown-style comments
    with open(CONFIG_FILE_PATH, "w") as config_file:
        # Write the introductory markdown-style comments
        config_file.write(CONFIG_FILE_HEADER)

        # Dump the updated YAML structure, keeping markdown comments for sections
        yaml.dump(safe_config, config_file, default_flow_style=False, sort_keys=False)
    return


if __name__ == "__main__":
    app.run()
