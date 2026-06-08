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
    # Configure Aggregate Module Params

    This notebook should be used as a test for ensuring correct aggregate parameters before aggregate processing.
    Cells marked with <font color='red'>SET PARAMETERS</font> contain crucial variables that need to be set according to your specific experimental setup and data organization.
    Please review and modify these variables as needed before proceeding with the analysis.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Fixed parameters for aggregate module

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
    from pathlib import Path
    from itertools import product
    import random

    import yaml
    import pandas as pd
    import matplotlib.pyplot as plt

    from lib.shared.file_utils import get_filename, load_parquet_subset
    from lib.aggregate.cell_data_utils import split_cell_data, channel_combo_subset
    from lib.aggregate.cell_classification import CellClassifier
    from lib.aggregate.montage_utils import create_cell_montage, add_filenames
    from lib.aggregate.filter import (
        query_filter,
        perturbation_filter,
        missing_values_filter,
        intensity_filter,
    )
    from lib.aggregate.align import (
        prepare_alignment_data,
        pca_variance_plot,
        embed_by_pca,
        tvn_on_controls,
    )
    from lib.aggregate.aggregate import aggregate
    from lib.aggregate.eval_aggregate import (
        nas_summary,
        summarize_cell_data,
        plot_feature_distributions,
    )
    from lib.shared.configuration_utils import CONFIG_FILE_HEADER, convert_tuples_to_lists

    random.seed(42)
    return (
        CONFIG_FILE_HEADER,
        CellClassifier,
        Path,
        add_filenames,
        aggregate,
        channel_combo_subset,
        convert_tuples_to_lists,
        create_cell_montage,
        embed_by_pca,
        get_filename,
        intensity_filter,
        load_parquet_subset,
        missing_values_filter,
        nas_summary,
        pca_variance_plot,
        pd,
        perturbation_filter,
        plot_feature_distributions,
        plt,
        prepare_alignment_data,
        product,
        query_filter,
        random,
        split_cell_data,
        summarize_cell_data,
        tvn_on_controls,
        yaml,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Testing on subset of data

    - `TEST_PLATE`: Plate used for testing configuration
    - `TEST_WELL_1`: First well identifier used for testing configuration
    - `TEST_WELL_2`: Second well identifier used for testing configuration
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    TEST_PLATE = None
    TEST_WELL_1 = None
    TEST_WELL_2 = None
    # === END OPERATOR PARAMETERS ===
    return TEST_PLATE, TEST_WELL_1, TEST_WELL_2


@app.cell
def _(
    CONFIG_FILE_PATH,
    Path,
    TEST_PLATE,
    TEST_WELL_1,
    TEST_WELL_2,
    get_filename,
    load_parquet_subset,
    pd,
    yaml,
):
    # load config file and determine root path
    with open(CONFIG_FILE_PATH, 'r') as _config_file:
        config = yaml.safe_load(_config_file)
    ROOT_FP = Path(config['all']['root_fp'])
    merge_final_fp = ROOT_FP / 'merge' / 'parquets' / get_filename({'plate': TEST_PLATE, 'well': TEST_WELL_1}, 'merge_final', 'parquet')
    # Load subset of data
    # Takes ~1 minute
    cell_data = load_parquet_subset(merge_final_fp, n_rows=25000)
    merge_final_fp_2 = ROOT_FP / 'merge' / 'parquets' / get_filename({'plate': TEST_PLATE, 'well': TEST_WELL_2}, 'merge_final', 'parquet')
    cell_data_2 = load_parquet_subset(merge_final_fp_2, n_rows=25000)
    cell_data = pd.concat([cell_data, cell_data_2], ignore_index=True)
    cell_data
    return ROOT_FP, cell_data, config


@app.cell
def _(cell_data):
    for _col in cell_data.columns:
        print(_col)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Cell Data Metadata

    - `METADATA_COLS_FP`: Path to TSV to store metadata cols.
    - `METADATA_COLS`: Loaded from config (set in notebook 7). Modify if needed.
    """)
    return


@app.cell
def _(config, pd):
    # Load classification settings from config (set in notebook 7)
    from lib.phenotype.constants import DEFAULT_METADATA_COLS
    if 'classify' in config:
        METADATA_COLS_FP = config['classify']['metadata_cols_fp']
        CLASSIFIER_PATH = config['classify']['classifier_path']
        CONFIDENCE_THRESHOLDS = config['classify']['confidence_thresholds']
        CLASS_TITLE = config['classify']['class_title']
        CLASS_MAPPING = config['classify']['class_mapping']  # e.g., "cell_stage"
        METADATA_COLS = pd.read_csv(METADATA_COLS_FP, header=None, sep='\t')[0].tolist()  # e.g., {"label_to_class": {1: "Mitotic", 2: "Interphase"}}
        print(f'Loaded metadata columns from classify config: {METADATA_COLS_FP}')  # Load metadata columns from file
    else:
        METADATA_COLS_FP = 'config/cell_data_metadata_cols.tsv'
        CLASSIFIER_PATH = None
        CONFIDENCE_THRESHOLDS = None  # Fall back to defaults if classify notebook was skipped
        CLASS_TITLE = None
        CLASS_MAPPING = None
        METADATA_COLS = DEFAULT_METADATA_COLS.copy()
        pd.Series(METADATA_COLS).to_csv(METADATA_COLS_FP, index=False, header=False, sep='\t')
        print(f'Using DEFAULT_METADATA_COLS (classify notebook was skipped)')
        print(f'Saved to: {METADATA_COLS_FP}')
    print(f'\nClassifier path: {CLASSIFIER_PATH}')  # Save default metadata cols to file for pipeline
    print(f'Class title: {CLASS_TITLE}')
    print(f'Class mapping: {CLASS_MAPPING}')
    print(f'Confidence thresholds: {CONFIDENCE_THRESHOLDS}')
    print(f'\n{len(METADATA_COLS)} metadata columns:')
    # Always show the metadata columns so user can verify
    for _col in METADATA_COLS:
        print(f'  - {_col}')
    return (
        CLASSIFIER_PATH,
        CLASS_MAPPING,
        CLASS_TITLE,
        METADATA_COLS,
        METADATA_COLS_FP,
    )


@app.cell
def _(METADATA_COLS, cell_data, split_cell_data):
    # Split cell data into metadata and features
    metadata, features = split_cell_data(cell_data, METADATA_COLS)
    print(metadata.shape, features.shape)
    return features, metadata


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Split cells into classes

    - `CLASSIFIER_PATH`: Path to pickled Python object that can take a cell data dataframe and output cell classes

    ### Evaluate splitting

    - `COLLAPSE_COLS`: Cell data columns to collapse on when creating a summary of cell counts. This will show the number of cells in each cell class for these particular columns. Ex: `["cell_barcode_0", "gene_symbol_0"]`.
    - `TEST_MONTAGE_CHANNEL`: Channel to display in the notebook montage preview. Usually `DAPI`. Set to `None` to skip montage generation entirely. Note: montages are generated across **all** channels — this parameter only controls which channel is shown in the notebook for visual QC.
    - `MONTAGE_NUM_CELLS`: Number of cells to include in each montage. Default `30`.
    - `MONTAGE_CELL_SIZE`: Pixel size of each cell bounding box in the montage (zoom level).
    - `MONTAGE_SHAPE`: Grid shape of the montage as `(rows, cols)`. Default `(3, 10)`.

    **Notes**:
    - We generate cell classes for each of the classes listed in the classifier and an "all" class. So for a classifier that splits by mitotic or interphase the final classes will be `["mitotic", "interphase", "all"]`.
    - You must import necessary packages for the classifier in this notebook and add them to `scripts/aggregate/split_datasets.py` as well. Ex `import numpy as np` if the classifier requires `numpy`.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    TEST_MONTAGE_CHANNEL = None
    COLLAPSE_COLS = None               # e.g., ["sgRNA_0", "gene_symbol_0"]
    MONTAGE_CELL_SIZE = None           # e.g., 40 — zoom level (pixel size per cell bounding box)
    # === END OPERATOR PARAMETERS ===

    # Library defaults (auto bucket)
    MONTAGE_NUM_CELLS = 30
    MONTAGE_SHAPE = (3, 10)
    return (
        COLLAPSE_COLS,
        MONTAGE_CELL_SIZE,
        TEST_MONTAGE_CHANNEL,
        MONTAGE_NUM_CELLS,
        MONTAGE_SHAPE,
    )


@app.cell
def _(
    CLASSIFIER_PATH,
    CLASS_MAPPING,
    CLASS_TITLE,
    CellClassifier,
    features,
    metadata,
):
    classifier = CellClassifier.load(CLASSIFIER_PATH)

    # Classify cells with safety check
    if classifier is not None:
        print("Applying cell classification...")
        classified_metadata, classified_features = classifier.classify_cells(metadata, features)
    
        # Add standard 'class' and 'confidence' columns using the mapping
        confidence_col = f"{CLASS_TITLE}_confidence"
        if CLASS_MAPPING and "label_to_class" in CLASS_MAPPING:
            label_to_class = CLASS_MAPPING["label_to_class"]
            # Convert numeric IDs to string labels
            classified_metadata["class"] = classified_metadata[CLASS_TITLE].map(
                lambda x: label_to_class.get(x, label_to_class.get(str(x), str(x)))
            )
        else:
            # No mapping available, use numeric values as strings
            classified_metadata["class"] = classified_metadata[CLASS_TITLE].astype(str)
    
        # Add standard confidence column
        classified_metadata["confidence"] = classified_metadata[confidence_col]
    else:
        print("No classifier specified - using all cells as single class")
        classified_metadata, classified_features = metadata.copy(), features.copy()
        classified_metadata["class"] = "all"
        classified_metadata["confidence"] = 1.0

    # Create config var for cell classes
    if "class" in classified_metadata.columns:
        CELL_CLASSES = list(classified_metadata["class"].unique())
    else:
        CELL_CLASSES = []

    # Show cell class counts and distribution
    if CELL_CLASSES:
        print("\nCell class counts:")
        print(classified_metadata["class"].value_counts())

        print("\nCell class confidences:")
        classified_metadata["confidence"].hist()
    else:
        print("No cell classes available")
    return CELL_CLASSES, classified_features, classified_metadata, classifier


@app.cell
def _(
    CELL_CLASSES,
    COLLAPSE_COLS,
    MONTAGE_CELL_SIZE,
    TEST_MONTAGE_CHANNEL,
    MONTAGE_NUM_CELLS,
    MONTAGE_SHAPE,
    ROOT_FP,
    add_filenames,
    classified_metadata,
    classifier,
    config,
    create_cell_montage,
    mo,
    plt,
    summarize_cell_data,
):
    if classifier is not None:
        cell_classes = list(classified_metadata['class'].unique()) + ['all']
    else:
        cell_classes = list(classified_metadata['class'].unique())
    if TEST_MONTAGE_CHANNEL is not None:
        classified_metadata_copy = classified_metadata.copy(deep=True)
        classified_metadata_copy = add_filenames(classified_metadata_copy, ROOT_FP, img_fmt=config['all'].get('image_format', 'tiff'))
        cell_class_dfs = {cell_class: classified_metadata_copy[classified_metadata_copy['class'] == cell_class] for cell_class in CELL_CLASSES}
        title_templates = {True: 'Lowest Confidence {cell_class} Cells - {channel}', False: 'Highest Confidence {cell_class} Cells - {channel}'}
        montages, titles = ([], [])
        for cell_class, cell_df in cell_class_dfs.items():
            for ascending in [True, False]:
                montage = create_cell_montage(cell_data=cell_df, channels=config['phenotype']['channel_names'], num_cells=MONTAGE_NUM_CELLS, cell_size=MONTAGE_CELL_SIZE, shape=MONTAGE_SHAPE, selection_params={'method': 'sorted', 'sort_by': 'confidence', 'ascending': ascending})[TEST_MONTAGE_CHANNEL]
                montages.append(montage)
                titles.append(title_templates[ascending].format(cell_class=cell_class, channel=TEST_MONTAGE_CHANNEL))
        num_rows = len(CELL_CLASSES)
        _fig, axes = plt.subplots(num_rows, 2, figsize=(10, 3 * num_rows))
        for ax, title, montage in zip(axes.flat, titles, montages):
            ax.imshow(montage, cmap='gray')
            ax.set_title(title, fontsize=14)
            ax.axis('off')
        print('Montages of cell classes:')
        plt.tight_layout()
        plt.show()
    else:
        print('TEST_MONTAGE_CHANNEL is None, skipping montage generation')
    print('Split cell data summary:')
    _summary_df = summarize_cell_data(classified_metadata, CELL_CLASSES, COLLAPSE_COLS)
    mo.ui.table(_summary_df)
    return (cell_classes,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Aggregate by channel combos

    - `CHANNEL_COMBOS`: Combinations of channels to aggregate by. This is a list of lists with channel names, ex `[["DAPI", "CENPA"], ["DAPI", "WGA"]]`.
    - `AGGREGATE_COMBO_FP`: Location of aggregate combinations dataframe.
    - `TEST_CELL_CLASS`: Cell class to configure aggregate params with. Can be any of the cell classes or `all`.
    - `TEST_CHANNEL_COMBO`: Channel combo to configure aggregate params with; must be one of the channel combos. Ex `["DAPI", "CENPA"]`.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    CHANNEL_COMBOS = None              # e.g., [["DAPI", "COXIV", "CENPA", "WGA"], ["DAPI", "CENPA"]]
    AGGREGATE_COMBO_FP = "config/aggregate_combo.tsv"
    TEST_CELL_CLASS = None
    TEST_CHANNEL_COMBO = None
    # === END OPERATOR PARAMETERS ===
    return (
        AGGREGATE_COMBO_FP,
        CHANNEL_COMBOS,
        TEST_CELL_CLASS,
        TEST_CHANNEL_COMBO,
    )


@app.cell
def _(
    AGGREGATE_COMBO_FP,
    CHANNEL_COMBOS,
    Path,
    cell_classes,
    config,
    pd,
    product,
):
    # determine cell classes and channel combos
    channel_combos = ["_".join(combo) for combo in CHANNEL_COMBOS]

    # Load merge wildcard combos
    MERGE_COMBO_FP = Path(config["merge"]["merge_combo_fp"])
    merge_wildcard_combos = pd.read_csv(MERGE_COMBO_FP, sep="\t")

    # Generate aggregate wildcard combos
    aggregate_wildcard_combos = pd.DataFrame(
        product(
            merge_wildcard_combos.itertuples(index=False, name=None),
            cell_classes,
            channel_combos,
        ),
        columns=["plate_well", "cell_class", "channel_combo"],
    )
    aggregate_wildcard_combos[["plate", "well"]] = pd.DataFrame(
        aggregate_wildcard_combos["plate_well"].tolist(),
        index=aggregate_wildcard_combos.index,
    )
    aggregate_wildcard_combos = aggregate_wildcard_combos.drop(columns="plate_well")

    # Save aggregate wildcard combos
    aggregate_wildcard_combos.to_csv(AGGREGATE_COMBO_FP, sep="\t", index=False)

    print("Aggregate wildcard combos:")
    aggregate_wildcard_combos
    return


@app.cell
def _(
    TEST_CELL_CLASS,
    TEST_CHANNEL_COMBO,
    channel_combo_subset,
    classified_features,
    classified_metadata,
    config,
    mo,
):
    # subset cell class
    if TEST_CELL_CLASS != "all":
        cell_class_mask = classified_metadata["class"] == TEST_CELL_CLASS
        class_metadata = classified_metadata[cell_class_mask]
        class_features = classified_features[cell_class_mask]
    else:
        class_metadata = classified_metadata
        class_features = classified_features

    # subset features
    all_channels = config["phenotype"]["channel_names"]
    class_features = channel_combo_subset(class_features, TEST_CHANNEL_COMBO, all_channels)

    # copy metadata and features for later eval
    dataset_metadata = class_metadata.copy()
    dataset_features = class_features.copy()

    # preview metadata and features
    mo.ui.table(class_metadata)
    mo.ui.table(class_features)
    return class_features, class_metadata, dataset_features, dataset_metadata


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Perturbation filtering

    - `FILTER_QUERIES`: Queries to use for custom filtering; ex: `["mapped_single_gene == True", "cell_quality_score > 0.8"]`. Can be left as `None` for no filtering.
    - `PERTURBATION_NAME_COL`: Name of column used to identify perturbations. This is the column that aggregation takes place on. Ex "gene_symbol_0".
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    FILTER_QUERIES = None              # e.g., ["mapped_single_gene == True"]
    PERTURBATION_NAME_COL = None       # e.g., "gene_symbol_0"
    # === END OPERATOR PARAMETERS ===
    return FILTER_QUERIES, PERTURBATION_NAME_COL


@app.cell
def _(
    FILTER_QUERIES,
    PERTURBATION_NAME_COL,
    class_features,
    class_metadata,
    metadata,
    nas_summary,
    perturbation_filter,
    plt,
    query_filter,
):
    qf_metadata, qf_features = query_filter(class_metadata, class_features, FILTER_QUERIES)
    pf_metadata, pf_features = perturbation_filter(qf_metadata, qf_features, PERTURBATION_NAME_COL)
    print(f'Unique populations: {metadata[PERTURBATION_NAME_COL].nunique()}')
    _summary_df, _fig = nas_summary(pf_features)
    print(_summary_df[_summary_df['percent_na'] > 0.1])
    plt.show()
    return pf_features, pf_metadata


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Missing value filtering

    - `DROP_COLS_THRESHOLD`: Threshold of NA values above which an entire column is dropped. Usually `0.1`
    - `DROP_ROWS_THRESHOLD`: Threshold of NA values above which an entire row is dropped. Usually `0.01`
    - `IMPUTE`: Whether or not to impute remaining missing values. Usually `True`

    **Note**: All NAs must be dropped or imputed to perform feature alignment.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    DROP_COLS_THRESHOLD = None         # e.g., 0.1
    DROP_ROWS_THRESHOLD = None         # e.g., 0.01
    IMPUTE = None                      # True | False
    # === END OPERATOR PARAMETERS ===
    return DROP_COLS_THRESHOLD, DROP_ROWS_THRESHOLD, IMPUTE


@app.cell
def _(
    DROP_COLS_THRESHOLD,
    DROP_ROWS_THRESHOLD,
    missing_values_filter,
    pf_features,
    pf_metadata,
):
    # Filter by missing values
    mvf_metadata, mvf_features = missing_values_filter(
        pf_metadata,
        pf_features,
        drop_cols_threshold=DROP_COLS_THRESHOLD,
        drop_rows_threshold=DROP_ROWS_THRESHOLD,
        impute=True,
    )

    mvf_metadata.shape, mvf_features.shape
    return mvf_features, mvf_metadata


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Intensity filtering

    - `CONTAMINATION`: Expected proportion of outliers in dataset. Usually `0.01`
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    CONTAMINATION = None               # e.g., 0.01
    # === END OPERATOR PARAMETERS ===
    return (CONTAMINATION,)


@app.cell
def _(CONTAMINATION, config, intensity_filter, mvf_features, mvf_metadata):
    # Filter by intensity outliers
    if_metadata, if_features = intensity_filter(
        mvf_metadata,
        mvf_features,
        config["phenotype"]["channel_names"],
        CONTAMINATION,
    )

    if_metadata.shape, if_features.shape
    return if_features, if_metadata


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Perturbation Score Filtering

    One can optionally assigned perturbation scores to each cell with perturbation scoring and filtering. During scoring, we train a Logistic Regression classifier on perturbed and control cell features. The result of this training and classification process is:
    - `AUC Score` assinged per perturbation: this represents the classifier's ability to distinguish between perturbed and control cells -> higher AUC score, more clear effect on perturbation level
    - `Perturbation Probability` assigned per cell: this represents the classifier's assigned probability of the cell being perturbed -> higher perturbation probability, more clear effect on cell level

    Once perturbation scores are assigned, one can optionally filter with a probability or percentile threshold before aggregation. Control cells will not be filtered.

    Configure perturbation score filtering with:
    - `SKIP_PERTURBATION_SCORE`: Whether or not to skip perturbation scoring entirely. Usually `False`
    - `PS_PROBABILITY_THRESHOLD`: Probability threshold above which to keep perturbed cells. Usually `0.75`
    - `PS_PERCENTILE_THRESHOLD`: Percentile threshold above which to keep perturbed cells. Usually `0.75`

    Leave `PS_PROBABILITY_THRESHOLD` and `PS_PERCENTILE_THRESHOLD` as `None` if no filtering is desired.

    **Notes:**
    - We don't test perturbation scoring within this notebook as it requires sampling many cells with the same perturbation across plates and wells
    - Both types of threshold will remove cells, and probability threshold can potentially eliminate all cells in a perturbation
    - Perturbation scoring can take hours per dataset
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    SKIP_PERTURBATION_SCORE = False
    PS_PROBABILITY_THRESHOLD = None
    PS_PERCENTILE_THRESHOLD = None
    # === END OPERATOR PARAMETERS ===
    return (
        PS_PERCENTILE_THRESHOLD,
        PS_PROBABILITY_THRESHOLD,
        SKIP_PERTURBATION_SCORE,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Prepare alignment data

    - `BATCH_COLS`: Which columns of metadata have batch-specific information. Usually `["plate", "well"]`.
    - `CONTROL_KEY`: Name of perturbation in `PERTURBATION_NAME_COL` that indicates a control cell.
    - `PERTURBATION_ID_COL`: Name of column that identifies unique perturbations. Only needed if you want your controls to have different perturbation names, ex `cell_barcode_0`. Otherwise, can leave this as `None`.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    BATCH_COLS = None                  # e.g., ["plate", "well"]
    CONTROL_KEY = None                 # e.g., "nontargeting"
    PERTURBATION_ID_COL = None         # e.g., "sgRNA_0"
    # === END OPERATOR PARAMETERS ===
    return BATCH_COLS, CONTROL_KEY, PERTURBATION_ID_COL


@app.cell
def _(
    BATCH_COLS,
    CONTROL_KEY,
    PERTURBATION_ID_COL,
    PERTURBATION_NAME_COL,
    if_features,
    if_metadata,
    pca_variance_plot,
    plt,
    prepare_alignment_data,
):
    pad_metadata, pad_features = prepare_alignment_data(if_metadata, if_features, BATCH_COLS, PERTURBATION_NAME_COL, CONTROL_KEY, PERTURBATION_ID_COL)
    n_components, _fig = pca_variance_plot(pad_features, variance_threshold=0.99)
    plt.show()
    return pad_features, pad_metadata


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Align and aggregate

    - `VARIANCE_OR_NCOMP`: Variance or number of components to keep after PCA.
    - `NUM_ALIGN_BATCHES`: Number of batches to use when aligning, usually `1`. Increase this if you are running out of memory while aligning. We were able to barely fit 8 plates with 6 wells each in 1 TB of memory with `NUM_ALIGN_BATCHES=1`.
    - `AGG_METHOD`: Method used to aggregate features. Can be `mean` or `median`. Usually `median`.

    While we use a simplified aggregate method in the notebook, the way this works during a normal run is:
    1) Take a subset of 1,000,000 cells, or the entire dataset, whichever is smaller and compute a PCA transform with `VARIANCE_OR_NCOMP`.
    2) Subset the entire dataset `NUM_BATCHES` number of times and align cells in this batch.
    3) Aggregate across all aligned cell data.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    VARIANCE_OR_NCOMP = None           # e.g., 0.99 (variance retained) or integer n_components
    NUM_ALIGN_BATCHES = None           # e.g., 1
    AGG_METHOD = None                  # e.g., "median"
    # === END OPERATOR PARAMETERS ===
    return AGG_METHOD, NUM_ALIGN_BATCHES, VARIANCE_OR_NCOMP


@app.cell
def _(
    AGG_METHOD,
    CONTROL_KEY,
    PERTURBATION_NAME_COL,
    VARIANCE_OR_NCOMP,
    aggregate,
    embed_by_pca,
    pad_features,
    pad_metadata,
    pd,
    tvn_on_controls,
):
    pca_embeddings = embed_by_pca(
        pad_features,
        pad_metadata,
        variance_or_ncomp=VARIANCE_OR_NCOMP,
        batch_col="batch_values",
    )

    tvn_normalized = tvn_on_controls(
        pca_embeddings, pad_metadata, PERTURBATION_NAME_COL, CONTROL_KEY, "batch_values"
    )

    aggregated_embeddings, aggregated_metadata = aggregate(
        tvn_normalized, pad_metadata, PERTURBATION_NAME_COL, AGG_METHOD
    )

    feature_columns = [f"PC_{i}" for i in range(tvn_normalized.shape[1])]

    tvn_normalized_df = pd.DataFrame(
        tvn_normalized, index=pad_metadata.index, columns=feature_columns
    )
    aligned_cell_data = pd.concat([pad_metadata, tvn_normalized_df], axis=1)

    aggregated_embeddings_df = pd.DataFrame(
        aggregated_embeddings, index=aggregated_metadata.index, columns=feature_columns
    )
    aggregated_cell_data = (
        pd.concat([aggregated_metadata, aggregated_embeddings_df], axis=1)
        .sort_values("cell_count", ascending=False)
        .reset_index(drop=True)
    )
    return aggregated_cell_data, aligned_cell_data


@app.cell
def _(
    aggregated_cell_data,
    aligned_cell_data,
    dataset_features,
    dataset_metadata,
    pd,
    plot_feature_distributions,
    plt,
    random,
):
    original_feature_cols = [_col for _col in dataset_features.columns if 'cell_' in _col and _col.endswith('_mean')]
    pc_cols = [_col for _col in aggregated_cell_data.columns if _col.startswith('PC_')]
    aligned_feature_cols = random.sample(pc_cols, k=min(len(original_feature_cols), len(pc_cols)))
    original_cell_data = pd.concat([dataset_metadata, dataset_features], axis=1)
    original_cell_data
    feature_distributions_fig = plot_feature_distributions(original_feature_cols, original_cell_data, aligned_feature_cols, aligned_cell_data)
    plt.show()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>
    ### Generate feature table & bootstrapping

    Bootstrapping is a statistical resampling method used to determine if perturbations (gene knockdowns, drug treatments, etc.) cause statistically significant changes compared to controls. The method works by:
    1. Taking your control population and repeatedly resampling it to create thousands of "null" distributions
    2. Comparing each perturbation's effect size against these null distributions
    3. Calculating p-values based on how often the null distributions produce effects as large as the real perturbation

    - `FEATURE_NORMALIZATION`: Method for normalizing features before bootstrapping. Options: `"standard"` (standard scalar) or `"mad"` (median absolute deviation).
    - `NUM_SIMS`: Number of bootstrap simulations to run for statistical testing. Ex: `100000`.
    - `EXCLUSION_STRING`: String to exclude certain constructs from analysis (optional). Ex: `"nontargeting_noncutting_"` or `None`.
    - `BOOTSTRAP_CELL_CLASS`: Cell class to run bootstrapping on. Ex: `"Interphase"` or `"all"`.
    - `BOOTSTRAP_CHANNEL_COMBO`: Channel combination to run bootstrapping on. Ex: `"DAPI_Ki-67_COXIV_Caspase-3_WGA_aTubulin_Vimentin_gH2AX_Phalloidin"`.
    - `PSEUDOGENE_PATTERNS`: Dictionary defining how to group single-construct genes into pseudo-genes for more robust statistical testing. For each pattern category, specify:
      - `pattern`: Regex pattern to match gene names
      - `constructs_per_pseudogene`: Number of constructs to group together

    **Note**: Without the combinations configured, bootstrapping will be skipped entirely. Bootstrap analysis can take hours to days depending on `NUM_SIMS` and dataset size.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS (BOOTSTRAP — optional) ===
    FEATURE_NORMALIZATION = "standard"
    NUM_SIMS = None
    EXCLUSION_STRING = None
    PSEUDOGENE_PATTERNS = None
    # === END OPERATOR PARAMETERS ===
    return (
        EXCLUSION_STRING,
        FEATURE_NORMALIZATION,
        NUM_SIMS,
        PSEUDOGENE_PATTERNS,
    )


@app.cell
def _(CHANNEL_COMBOS, CELL_CLASSES):
    # Bootstrap targets default to the largest configured channel combo (most
    # channels) and all available cell classes.
    BOOTSTRAP_CHANNEL_COMBO = (
        "_".join(max(CHANNEL_COMBOS, key=len)) if CHANNEL_COMBOS else None
    )
    BOOTSTRAP_CELL_CLASS = list(CELL_CLASSES) if CELL_CLASSES else None
    return BOOTSTRAP_CELL_CLASS, BOOTSTRAP_CHANNEL_COMBO


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Add aggregate parameters to config file
    """)
    return


@app.cell
def _(
    AGGREGATE_COMBO_FP,
    AGG_METHOD,
    BATCH_COLS,
    BOOTSTRAP_CELL_CLASS,
    BOOTSTRAP_CHANNEL_COMBO,
    COLLAPSE_COLS,
    CONFIG_FILE_HEADER,
    CONFIG_FILE_PATH,
    CONTAMINATION,
    CONTROL_KEY,
    DROP_COLS_THRESHOLD,
    DROP_ROWS_THRESHOLD,
    EXCLUSION_STRING,
    FEATURE_NORMALIZATION,
    FILTER_QUERIES,
    IMPUTE,
    METADATA_COLS_FP,
    MONTAGE_CELL_SIZE,
    MONTAGE_NUM_CELLS,
    MONTAGE_SHAPE,
    NUM_ALIGN_BATCHES,
    NUM_SIMS,
    PERTURBATION_ID_COL,
    PERTURBATION_NAME_COL,
    PSEUDOGENE_PATTERNS,
    PS_PERCENTILE_THRESHOLD,
    PS_PROBABILITY_THRESHOLD,
    SKIP_PERTURBATION_SCORE,
    VARIANCE_OR_NCOMP,
    config,
    convert_tuples_to_lists,
    product,
    yaml,
):
    # Add aggregate section (classifier settings are in config["classify"] from notebook 7)
    config['aggregate'] = {'metadata_cols_fp': METADATA_COLS_FP, 'collapse_cols': COLLAPSE_COLS, 'aggregate_combo_fp': AGGREGATE_COMBO_FP, 'filter_queries': FILTER_QUERIES, 'perturbation_name_col': PERTURBATION_NAME_COL, 'drop_cols_threshold': DROP_COLS_THRESHOLD, 'drop_rows_threshold': DROP_ROWS_THRESHOLD, 'impute': IMPUTE, 'contamination': CONTAMINATION, 'batch_cols': BATCH_COLS, 'control_key': CONTROL_KEY, 'perturbation_id_col': PERTURBATION_ID_COL, 'variance_or_ncomp': VARIANCE_OR_NCOMP, 'num_align_batches': NUM_ALIGN_BATCHES, 'agg_method': AGG_METHOD, 'skip_perturbation_score': SKIP_PERTURBATION_SCORE, 'ps_probability_threshold': PS_PROBABILITY_THRESHOLD, 'ps_percentile_threshold': PS_PERCENTILE_THRESHOLD, 'montage_num_cells': MONTAGE_NUM_CELLS, 'montage_cell_size': MONTAGE_CELL_SIZE, 'montage_shape': list(MONTAGE_SHAPE)}
    if BOOTSTRAP_CELL_CLASS and BOOTSTRAP_CHANNEL_COMBO:
        cell_classes_list = BOOTSTRAP_CELL_CLASS if isinstance(BOOTSTRAP_CELL_CLASS, list) else [BOOTSTRAP_CELL_CLASS]
        channel_combos_list = BOOTSTRAP_CHANNEL_COMBO if isinstance(BOOTSTRAP_CHANNEL_COMBO, list) else [BOOTSTRAP_CHANNEL_COMBO]
        BOOTSTRAP_COMBINATIONS = [{'cell_class': cc, 'channel_combo': ch} for cc, ch in product(cell_classes_list, channel_combos_list)]
        config['aggregate'].update({'feature_normalization': FEATURE_NORMALIZATION, 'num_sims': NUM_SIMS, 'exclusion_string': EXCLUSION_STRING, 'bootstrap_combinations': BOOTSTRAP_COMBINATIONS, 'pseudogene_patterns': PSEUDOGENE_PATTERNS})
    safe_config = convert_tuples_to_lists(config)
    with open(CONFIG_FILE_PATH, 'w') as _config_file:
        _config_file.write(CONFIG_FILE_HEADER)
    # Convert tuples to lists before dumping
    # Write the updated configuration
        yaml.dump(safe_config, _config_file, default_flow_style=False, sort_keys=False)  # Normalize to lists for iteration (supports both single values and lists)  # Create all combinations  # Write the introductory comments  # Dump the updated YAML structure, keeping markdown comments for sections
    return


@app.cell
def _():
    # === TUNED EXPORT ===
    # No notebook-derived tuned values for aggregate (DROP_COLS_THRESHOLD,
    # DROP_ROWS_THRESHOLD, CONTAMINATION, NUM_ALIGN_BATCHES are operator-set
    # upfront, not notebook-derived). Empty export for symmetry.
    import json as _je
    from pathlib import Path as _Pe
    _t = {}
    _out = _Pe(".brieflow") / "tuned_aggregate.json"
    _out.parent.mkdir(exist_ok=True)
    _out.write_text(_je.dumps(_t, indent=2, default=str))
    # === END TUNED EXPORT ===
    return


if __name__ == "__main__":
    app.run()
