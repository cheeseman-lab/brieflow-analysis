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
    # Train Classifier

    This notebook provides tools for training custom cell or vacuole classifiers. It covers labeling data, training models, and selecting the best classifier.

    Cells marked with <font color='red'>SET PARAMETERS</font> contain crucial variables that need to be set according to your specific experimental setup and data organization.
    Please review and modify these variables as needed before proceeding with the analysis.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Fixed parameters for classify module

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
    from types import SimpleNamespace

    import numpy as np
    import pandas as pd
    import pyarrow.parquet as pq
    import yaml
    from matplotlib import pyplot as plt

    from lib.aggregate.cell_classification import CellClassifier
    from lib.aggregate.cell_data_utils import split_cell_data
    from lib.classify.apply import (
        apply_class_thresholds,
        build_master_phenotype_df,
        display_pngs_in_plots_and_list_models,
        plot_confidence_distribution,
        resolve_classifier_model_dill_path,
        show_model_evaluation_pngs,
        summarize_classification,
    )
    from lib.classify.calibration import calibrate_confidence
    from lib.classify.labeling import (
        _collect_and_advance_random as collect_labels_into_state,
        build_class_mapping,
        consolidate_manual_classifications,
        filter_existing_from_pools,
        get_checkpoint_path,
        initialize_labeling_state,
        load_checkpoint,
        load_existing_training_data,
        prepare_mask_dataframes,
        remove_seen_from_pools,
        resolve_channel_colors,
        select_next_batch_from_pools,
    )
    from lib.classify.path_utils import find_sample_parquet, get_parquet_config
    from lib.classify.shared import (
        compose_rgb_crops,
        compute_crop_bounds,
        get_latest_run_dir,
        load_aligned_stack,
        load_mask_labels,
        overlay_mask_boundary_inplace,
        overlay_scale_bar,
        to_png_bytes,
    )
    from lib.classify.train import (
        filter_classes,
        load_cellprofiler_data,
        train_classifier_pipeline,
    )
    from lib.shared.configuration_utils import CONFIG_FILE_HEADER, convert_tuples_to_lists

    return (
        CONFIG_FILE_HEADER,
        CellClassifier,
        Path,
        SimpleNamespace,
        apply_class_thresholds,
        build_class_mapping,
        build_master_phenotype_df,
        calibrate_confidence,
        collect_labels_into_state,
        compose_rgb_crops,
        compute_crop_bounds,
        consolidate_manual_classifications,
        convert_tuples_to_lists,
        display_pngs_in_plots_and_list_models,
        filter_classes,
        filter_existing_from_pools,
        find_sample_parquet,
        get_checkpoint_path,
        get_latest_run_dir,
        get_parquet_config,
        initialize_labeling_state,
        load_aligned_stack,
        load_cellprofiler_data,
        load_checkpoint,
        load_existing_training_data,
        load_mask_labels,
        np,
        overlay_mask_boundary_inplace,
        overlay_scale_bar,
        pd,
        plot_confidence_distribution,
        plt,
        pq,
        prepare_mask_dataframes,
        remove_seen_from_pools,
        resolve_channel_colors,
        resolve_classifier_model_dill_path,
        select_next_batch_from_pools,
        show_model_evaluation_pngs,
        split_cell_data,
        summarize_classification,
        to_png_bytes,
        train_classifier_pipeline,
        yaml,
    )


@app.cell
def _(CONFIG_FILE_PATH, Path, yaml):
    # load config file and determine root path
    with open(CONFIG_FILE_PATH, "r") as _config_file:
        config = yaml.safe_load(_config_file)
    ROOT_FP = Path(config["all"]["root_fp"])
    CLASSIFIER_OUTPUT_DIR = ROOT_FP / "classifier"
    CLASSIFIER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHANNEL_NAMES = config["phenotype"]["channel_names"]
    KEYS = ["plate", "well", "tile", "mask_label"]
    print(f"Root path: {ROOT_FP}")
    print(f"Classifier output: {CLASSIFIER_OUTPUT_DIR}")
    print(f"Phenotype channels: {CHANNEL_NAMES}")
    return CHANNEL_NAMES, CLASSIFIER_OUTPUT_DIR, KEYS, ROOT_FP, config


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. Labeling

    This section labels objects (ex. cells) to create training data for machine learning models.

    **Steps:** **1a)** Configure classification settings → **1b)** Set gating parameters to choose what objects will be displayed → **1c)** Configure display options → Label objects interactively → Save training dataset
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 1a. <font color='red'>SET PARAMETERS</font>: Classification Settings

    This section defines the training dataset and classes that will be used for labeling.

    **Classification parameters:**

    - `TRAINING_DATA_SOURCE`: Source of training data features. Ex. `"phenotype"` or `"merge"`.
    - `MODE`: Object to classify. Default: `"cell"`.
    - `CLASS_TITLE`: Name of the new column added to the phenotype dataframe.
    - `CLASSIFICATION`: List of categories for classification. Categories appear as 1, 2, 3... in output, corresponding to list order.
    - `PLATES_TO_CLASSIFY`: List of plates to include in classification.
    - `WELLS_TO_CLASSIFY`: List of wells among the specified plates to classify.

    **If adding to an existing training dataset:**

    - `ADD_TRAINING_DATA`: Set to `False` for first-time training, `True` to add to an existing dataset.
    - `EXISTING_TRAINING_DATA`: Only set if `ADD_TRAINING_DATA` is `True`. Specify the filepath of the existing training dataset.
    - `RELABEL_CLASSIFICATIONS`: Set to `True` to revisit and modify labels from the existing dataset. Previously labeled data will be shown first.

    **Data sampling (optional):**
    To prevent memory issues when working with many plates/wells, you can subsample the data. Sampling is applied AFTER gating thresholds are calculated, so percentile-based gates remain accurate. These settings apply to both training (labeling) and test (evaluation) sections.

    - `DATA_SAMPLE_FRACTION`: Fraction of data to sample (0-1). Set to `None` for all data.
    - `DATA_MAX_ROWS`: Maximum rows per pool. Set to `None` for no limit.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    ADD_TRAINING_DATA = False
    EXISTING_TRAINING_DATA = None
    RELABEL_CLASSIFICATIONS = True
    TRAINING_DATA_SOURCE = "merge"
    MODE = "cell"
    CLASS_TITLE = "cell_stage"
    CLASSIFICATION = ["Mitotic", "Interphase"]
    PLATES_TO_CLASSIFY = [1]
    WELLS_TO_CLASSIFY = ["A1"]
    DATA_SAMPLE_FRACTION = None
    DATA_MAX_ROWS = None
    # === END OPERATOR PARAMETERS ===
    return (
        ADD_TRAINING_DATA,
        CLASSIFICATION,
        CLASS_TITLE,
        DATA_MAX_ROWS,
        DATA_SAMPLE_FRACTION,
        EXISTING_TRAINING_DATA,
        MODE,
        PLATES_TO_CLASSIFY,
        RELABEL_CLASSIFICATIONS,
        TRAINING_DATA_SOURCE,
        WELLS_TO_CLASSIFY,
    )


@app.cell
def _(CLASSIFICATION, ROOT_FP, TRAINING_DATA_SOURCE, build_class_mapping):
    class_mapping = build_class_mapping(CLASSIFICATION)

    if TRAINING_DATA_SOURCE == "merge":
        data_source = ROOT_FP / "merge"
        images_source = ROOT_FP / "phenotype"
    else:
        data_source = ROOT_FP / "phenotype"
        images_source = ROOT_FP / "phenotype"

    print(f"Class names to stored numeric values: {class_mapping}")
    print(f"Feature source: {data_source}")
    print(f"Image source: {images_source}")
    return class_mapping, data_source, images_source


@app.cell
def _(
    MODE,
    PLATES_TO_CLASSIFY,
    ROOT_FP,
    TRAINING_DATA_SOURCE,
    WELLS_TO_CLASSIFY,
    find_sample_parquet,
    get_parquet_config,
    mo,
    pd,
    pq,
):
    # preview available columns in the data source
    parquet_dir, name_suffix = get_parquet_config(
        mode=MODE, source=TRAINING_DATA_SOURCE, root_fp=ROOT_FP
    )
    sample_pq = find_sample_parquet(
        plates=[str(p) for p in PLATES_TO_CLASSIFY],
        wells=list(WELLS_TO_CLASSIFY),
        parquet_dir=parquet_dir,
        name_suffix=name_suffix,
    )

    if sample_pq:
        all_cols = pq.ParquetFile(sample_pq).schema.names
        print(f"Data source: {TRAINING_DATA_SOURCE}")
        print(f"Found {len(all_cols)} columns in {sample_pq}")
    else:
        all_cols = []
        print("Warning: No parquet files found for specified plates/wells")

    mo.ui.table(pd.DataFrame({"column": all_cols}))
    return all_cols, parquet_dir


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 1b. <font color='red'>SET PARAMETERS</font>: Gating Settings

    Use the parameters below to choose what subset of objects to display in the labeling interface.

    **Feature gating (optional):**
    Use gating to prioritize cells with specific characteristics for labeling. For example, to find mitotic cells, one might set `GATE_FEATURE = "nucleus_DAPI_mad"` with a high `GATE_MIN_PERCENTILE` to prioritize cells with bright nuclei.

    - `GATE_FEATURE`: Feature to gate by (e.g., `"nucleus_DAPI_mad"`). Set to `None` to skip gating.
    - `GATE_MIN`: Minimum value (exclusive). Cells below this will be deprioritized.
    - `GATE_MAX`: Maximum value (exclusive). Cells above this will be deprioritized.
    - `GATE_MIN_PERCENTILE`: Percentile minimum (0-1). Cells below this percentile will be deprioritized.
    - `GATE_MAX_PERCENTILE`: Percentile maximum (0-1). Cells above this percentile will be deprioritized.

    **Batch settings:**

    - `BATCH_SIZE`: Number of images to display per round of classification. Default is 10.
    - `OUT_OF_GATE_COUNT`: Number of out-of-gate images to include per batch for diversity (0 to `BATCH_SIZE`). Default is 1. Use this to come up with a balanced set of images for your classifier of interest.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    GATE_FEATURE = None
    GATE_MIN = None
    GATE_MAX = None
    GATE_MIN_PERCENTILE = None
    GATE_MAX_PERCENTILE = None
    BATCH_SIZE = 10
    OUT_OF_GATE_COUNT = 1
    # === END OPERATOR PARAMETERS ===
    return (
        BATCH_SIZE,
        GATE_FEATURE,
        GATE_MAX,
        GATE_MAX_PERCENTILE,
        GATE_MIN,
        GATE_MIN_PERCENTILE,
        OUT_OF_GATE_COUNT,
    )


@app.cell
def _(
    DATA_MAX_ROWS,
    DATA_SAMPLE_FRACTION,
    GATE_FEATURE,
    GATE_MAX,
    GATE_MAX_PERCENTILE,
    GATE_MIN,
    GATE_MIN_PERCENTILE,
    KEYS,
    MODE,
    PLATES_TO_CLASSIFY,
    WELLS_TO_CLASSIFY,
    data_source,
    prepare_mask_dataframes,
):
    # prepare dataframes for gating
    summary_df, in_gate_df, out_of_gate_df, gate_dbg = prepare_mask_dataframes(
        mode=MODE,
        data_source=data_source,
        plates=PLATES_TO_CLASSIFY,
        wells=WELLS_TO_CLASSIFY,
        keys=KEYS,
        gate_feature=GATE_FEATURE,
        gate_min=GATE_MIN,
        gate_max=GATE_MAX,
        gate_min_percentile=GATE_MIN_PERCENTILE,
        gate_max_percentile=GATE_MAX_PERCENTILE,
        sample_fraction=DATA_SAMPLE_FRACTION,
        max_rows=DATA_MAX_ROWS,
        verbose=True,
    )
    return gate_dbg, in_gate_df, out_of_gate_df, summary_df


@app.cell
def _(
    ADD_TRAINING_DATA,
    CLASS_TITLE,
    EXISTING_TRAINING_DATA,
    MODE,
    RELABEL_CLASSIFICATIONS,
    filter_existing_from_pools,
    in_gate_df,
    load_existing_training_data,
    out_of_gate_df,
):
    # load existing training data if adding
    if ADD_TRAINING_DATA and EXISTING_TRAINING_DATA:
        seeded_df, EXISTING_KEYS = load_existing_training_data(
            EXISTING_TRAINING_DATA, MODE, CLASS_TITLE
        )
        if RELABEL_CLASSIFICATIONS:
            in_pool_df, out_pool_df = in_gate_df, out_of_gate_df
        else:
            in_pool_df, out_pool_df = filter_existing_from_pools(
                in_gate_df, out_of_gate_df, EXISTING_KEYS
            )
    else:
        seeded_df = None
        EXISTING_KEYS = set()
        in_pool_df, out_pool_df = in_gate_df, out_of_gate_df

    print(f"[training] Existing keys loaded: {len(EXISTING_KEYS)}")
    return EXISTING_KEYS, in_pool_df, out_pool_df, seeded_df


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 1c. <font color='red'>SET PARAMETERS</font>: Display Settings

    This section sets how and in what order objects will be displayed by the labeler.

    **Channel visualization:**

    - `DISPLAY_CHANNEL`: Channels to display for manual classification.
    - `CHANNEL_COLORS`: Colors for each channel. Must align with `DISPLAY_CHANNEL` order. See [matplotlib colors](https://matplotlib.org/stable/gallery/color/named_colors.html).

    **Selection method:**

    - `TRAINING_DATASET_SELECTION`: Choose `"random"` or `"top_n"`. `"random"` randomly selects masks from the specified plates and wells; `"top_n"` ranks tiles by the number of objects in each and selects masks from those tiles.
    - `TOP_N`: If using `"top_n"`, specify which ranked tile to use. Ex. `1` would display cells (assuming `MODE="cell"`) from the tile that has the most cells.

    **Other settings:**

    - `SCALE_BAR`: Scale bar length in pixels. If value exceeds image size, displays as dashed lines.
    - `RANDOM_SEED`: Random seed for reproducibility.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    DISPLAY_CHANNEL = ["DAPI"]
    CHANNEL_COLORS = ["b"]
    TRAINING_DATASET_SELECTION = "random"
    TOP_N = 0
    SCALE_BAR = 30
    RANDOM_SEED = 42
    # === END OPERATOR PARAMETERS ===
    return (
        CHANNEL_COLORS,
        DISPLAY_CHANNEL,
        RANDOM_SEED,
        SCALE_BAR,
        TOP_N,
        TRAINING_DATASET_SELECTION,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Labeler

    The labeler shows one row per object: each displayed channel, then a merged view with the object's mask boundary and a scale bar drawn on it. Pick a class from the dropdown next to a row; the selection is recorded and checkpointed as soon as it is made, so a crashed or closed session resumes from the checkpoint under `classifier/checkpoints/`.

    Press **Save labels and load next batch** to drop the objects on screen from the pool and draw a new batch. Objects left unlabeled in a batch are recorded as uncategorized and are not shown again. Press **Save training dataset** once you are done labeling to join the labels back to their features and write the training parquet.
    """)
    return


@app.cell
def _(
    ADD_TRAINING_DATA,
    CHANNEL_COLORS,
    CHANNEL_NAMES,
    CLASSIFIER_OUTPUT_DIR,
    CLASS_TITLE,
    DISPLAY_CHANNEL,
    EXISTING_TRAINING_DATA,
    RANDOM_SEED,
    MODE,
    KEYS,
    get_checkpoint_path,
    in_pool_df,
    initialize_labeling_state,
    load_checkpoint,
    out_pool_df,
    pd,
    resolve_channel_colors,
    seeded_df,
):
    # initialize labeling state, channel rendering and the mask pools the labeler draws from
    CHANNEL_INDICES = [CHANNEL_NAMES.index(_ch) for _ch in DISPLAY_CHANNEL]
    resolved_colors = resolve_channel_colors(DISPLAY_CHANNEL, CHANNEL_COLORS)

    if ADD_TRAINING_DATA and EXISTING_TRAINING_DATA:
        _existing_df = seeded_df
        print(f"Using existing training data: {EXISTING_TRAINING_DATA}")
    else:
        _existing_df = load_checkpoint(CLASSIFIER_OUTPUT_DIR, CLASS_TITLE)

    label_state = initialize_labeling_state(
        random_seed=RANDOM_SEED,
        mode=MODE,
        class_title=CLASS_TITLE,
        keys=KEYS,
        existing_classified_df=_existing_df,
    )
    label_state["_checkpoint_path"] = get_checkpoint_path(CLASSIFIER_OUTPUT_DIR, CLASS_TITLE)
    label_state["_unclassified_committed"] = pd.DataFrame(columns=KEYS)

    label_pools = {"in": in_pool_df, "out": out_pool_df}
    return CHANNEL_INDICES, label_pools, label_state, resolved_colors


@app.cell
def _(KEYS, label_pools, label_state, mo, pd, remove_seen_from_pools):
    def _advance_batch(clicks):
        # the batch on screen has been collected already; retire it and keep its uncategorized rows
        label_state["_unclassified_committed"] = label_state.get(
            "manual_unclassified_df", pd.DataFrame(columns=KEYS)
        )
        label_pools["in"], label_pools["out"] = remove_seen_from_pools(
            label_pools["in"],
            label_pools["out"],
            label_state.get("last_batch_df", pd.DataFrame(columns=KEYS)),
            keys=KEYS,
        )
        return clicks + 1

    next_batch_button = mo.ui.button(
        value=0, on_click=_advance_batch, label="Save labels and load next batch"
    )
    save_training_button = mo.ui.run_button(label="Save training dataset")
    return next_batch_button, save_training_button


@app.cell
def _(
    ADD_TRAINING_DATA,
    BATCH_SIZE,
    CHANNEL_INDICES,
    CHANNEL_NAMES,
    CLASSIFICATION,
    CLASS_TITLE,
    EXISTING_KEYS,
    KEYS,
    MODE,
    OUT_OF_GATE_COUNT,
    RELABEL_CLASSIFICATIONS,
    SCALE_BAR,
    TRAINING_DATASET_SELECTION,
    compose_rgb_crops,
    compute_crop_bounds,
    images_source,
    label_pools,
    label_state,
    load_aligned_stack,
    load_mask_labels,
    mo,
    next_batch_button,
    np,
    overlay_mask_boundary_inplace,
    overlay_scale_bar,
    resolved_colors,
    select_next_batch_from_pools,
    summary_df,
    to_png_bytes,
):
    # draw the next batch of objects and build one class selector per object
    next_batch_button

    _in_pool = label_pools["in"]
    _out_pool = label_pools["out"]
    _out_keys = {
        (int(r.plate), str(r.well), int(r.tile), int(r.mask_label))
        for r in _out_pool.itertuples(index=False)
    }

    if ADD_TRAINING_DATA and RELABEL_CLASSIFICATIONS and EXISTING_KEYS:
        _in_keys = {
            (int(r.plate), str(r.well), int(r.tile), int(r.mask_label))
            for r in _in_pool.itertuples(index=False)
        }
        _pri_in = EXISTING_KEYS.intersection(_in_keys)
        _pri_out = EXISTING_KEYS.intersection(_out_keys)
    else:
        _pri_in, _pri_out = set(), set()

    if len(_in_pool) + len(_out_pool) == 0:
        label_metas = []
        label_crops = []
        print("All objects in the selected plates/wells have been shown.")
    else:
        _batch_df, _ = select_next_batch_from_pools(
            in_pool_df=_in_pool,
            out_pool_df=_out_pool,
            selection_mode=TRAINING_DATASET_SELECTION,
            batch_size=BATCH_SIZE,
            keys=KEYS,
            summary_df=summary_df,
            out_randomizer=OUT_OF_GATE_COUNT,
            prioritized_in_keys=_pri_in,
            prioritized_out_keys=_pri_out,
        )
        label_state["last_batch_df"] = _batch_df[KEYS].copy()

        _labeled = label_state.get("manual_classified_df")
        _key_to_class = {}
        if _labeled is not None and not _labeled.empty:
            for _p, _w, _t, _m, _c in _labeled[KEYS + [CLASS_TITLE]].itertuples(
                index=False, name=None
            ):
                _key_to_class[(int(_p), str(_w), int(_t), int(_m))] = int(_c)

        label_metas = []
        label_crops = []
        for _meta in _batch_df.to_dict(orient="records"):
            _key = (
                int(_meta["plate"]),
                str(_meta["well"]),
                int(_meta["tile"]),
                int(_meta["mask_label"]),
            )
            _prefill = _key_to_class.get(_key)
            _meta["_sprinkle"] = _key in _out_keys
            _meta["_existing"] = _key in EXISTING_KEYS
            _meta["_prefill_class_idx"] = (
                _prefill
                if (_prefill is not None and 1 <= _prefill <= len(CLASSIFICATION))
                else None
            )

            _stack = load_aligned_stack(
                images_source,
                CHANNEL_NAMES,
                _key[0],
                _key[1],
                _key[2],
                cache=label_state["aligned_cache"],
            )
            _y0, _y1, _x0, _x1 = compute_crop_bounds(
                images_source,
                MODE,
                _key[0],
                _key[1],
                _key[2],
                _key[3],
                (_stack.shape[1], _stack.shape[2]),
                mask_cache=label_state["mask_cache"],
                parquet_cache=label_state["parquet_cache"],
            )
            _imgs, _merged = compose_rgb_crops(
                _stack, _y0, _y1, _x0, _x1, CHANNEL_INDICES, resolved_colors
            )
            _labels_crop = load_mask_labels(
                images_source,
                MODE,
                _key[0],
                _key[1],
                _key[2],
                cache=label_state["mask_cache"],
            )[_y0:_y1, _x0:_x1]
            _mask_crop = _labels_crop == _key[3]
            if np.any(_mask_crop):
                overlay_mask_boundary_inplace(_merged, _mask_crop, step=2, value=1.0)
            if SCALE_BAR and SCALE_BAR > 0:
                overlay_scale_bar(_merged, int(SCALE_BAR))

            label_metas.append(_meta)
            label_crops.append([to_png_bytes(_arr) for _arr in _imgs + [_merged]])
            label_state["aligned_cache"].clear()
            label_state["mask_cache"].clear()

    label_selectors = mo.ui.array(
        [
            mo.ui.dropdown(
                options=CLASSIFICATION,
                value=(
                    CLASSIFICATION[_m["_prefill_class_idx"] - 1]
                    if _m["_prefill_class_idx"] is not None
                    else None
                ),
                label="class",
            )
            for _m in label_metas
        ]
    )
    return label_crops, label_metas, label_selectors


@app.cell
def _(
    DISPLAY_CHANNEL,
    label_crops,
    label_metas,
    label_selectors,
    mo,
    next_batch_button,
    save_training_button,
):
    _panel_labels = list(DISPLAY_CHANNEL) + ["merged"]
    _rows = []
    for _i, (_meta, _crops) in enumerate(zip(label_metas, label_crops)):
        _notes = []
        if _meta["_existing"]:
            _notes.append("_from existing training dataset_")
        if _meta["_sprinkle"]:
            _notes.append("_out of gate_")
        _side = mo.vstack(
            [
                mo.md(
                    f"**P-{_meta['plate']} W-{_meta['well']} T-{_meta['tile']}** "
                    f"mask {_meta['mask_label']}"
                ),
                label_selectors[_i],
                mo.md("<br>".join(_notes)) if _notes else mo.md(""),
            ]
        )
        _images = mo.hstack(
            [
                mo.vstack([mo.md(f"`{_name}`"), mo.image(_png, width=180)])
                for _name, _png in zip(_panel_labels, _crops)
            ],
            justify="start",
        )
        _rows.append(mo.hstack([_side, _images], justify="start", widths=[1, 4]))

    mo.vstack(_rows + [mo.hstack([next_batch_button, save_training_button], justify="start")])
    return


@app.cell
def _(
    CLASSIFICATION,
    CLASS_TITLE,
    KEYS,
    MODE,
    SimpleNamespace,
    collect_labels_into_state,
    label_metas,
    label_selectors,
    label_state,
    pd,
):
    # record the current selections into the labeling state and checkpoint them
    label_state["rows_state"] = [
        {
            "meta": _meta,
            "dropdown": SimpleNamespace(
                value=_choice if _choice is not None else "--select class--"
            ),
        }
        for _meta, _choice in zip(label_metas, label_selectors.value)
    ]
    label_state["manual_unclassified_df"] = label_state["_unclassified_committed"]
    collect_labels_into_state(label_state, CLASSIFICATION, CLASS_TITLE, KEYS)

    labeled_df = label_state.get("manual_classified_df")
    if labeled_df is None:
        labeled_df = pd.DataFrame(columns=KEYS + [CLASS_TITLE])
    _unit = "cells" if MODE == "cell" else "vacuoles"
    print(f"Total categorized: {len(labeled_df)} {_unit}")
    for _i, _name in enumerate(CLASSIFICATION, start=1):
        _count = int((labeled_df[CLASS_TITLE] == _i).sum()) if len(labeled_df) else 0
        _pct = round(100 * _count / len(labeled_df)) if len(labeled_df) else 0
        print(f"  {_name}: {_count} ({_pct}%)")
    print(f"Uncategorized (omitted): {len(label_state['manual_unclassified_df'])}")
    return (labeled_df,)


@app.cell
def _(
    CLASSIFIER_OUTPUT_DIR,
    CLASS_TITLE,
    MODE,
    consolidate_manual_classifications,
    data_source,
    labeled_df,
    mo,
    pd,
    save_training_button,
):
    if save_training_button.value and len(labeled_df) > 0:
        consolidated_df, training_dataset_out_path = consolidate_manual_classifications(
            manual_classified_df=labeled_df,
            class_title=CLASS_TITLE,
            mode=MODE,
            data_source=data_source,
            classifier_output_dir=CLASSIFIER_OUTPUT_DIR,
            write=True,
            verbose=True,
        )
        print(f"Training dataset written to: {training_dataset_out_path}")
    else:
        consolidated_df = None
        training_dataset_out_path = None
        print("Press 'Save training dataset' to join labels to features and write it out")

    mo.ui.table(consolidated_df if consolidated_df is not None else pd.DataFrame())
    return consolidated_df, training_dataset_out_path


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. Training

    Configure training parameters and train multiple model types to find the best classifier.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 2a. <font color='red'>SET PARAMETERS</font>: Training Dataset Configuration

    - `TRAINING_DATASET_FP`: Path to training dataset(s) in list format. Set to `None` to use the dataset just saved above.
    - `METADATA_COLS_FP`: Path to save metadata columns for use in aggregate pipeline.
    - `TRAINING_CHANNELS`: Channels to include in training features. Set to `None` to use all phenotype channels.
    - `TRAINING_OBJECT_TYPES`: Object types to include in training features, a subset of `["nucleus", "cell", "cytoplasm", "second_obj"]`. Set to `None` to use all of them.
    - `TRAINING_NAME`: Name identifier for this training run. Set to `None` to name the run by its timestamp.
    - `METADATA_COLS`: Columns to treat as metadata rather than features. Any candidate not present in the training data is dropped, and the classification target column is always added.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    TRAINING_DATASET_FP = None
    METADATA_COLS_FP = "config/cell_data_metadata_cols.tsv"
    TRAINING_CHANNELS = None
    TRAINING_OBJECT_TYPES = None
    TRAINING_NAME = None
    METADATA_COLS = [
        "label",
        "plate",
        "well",
        "tile",
        "cell_0",
        "i_0",
        "j_0",
        "site",
        "cell_1",
        "i_1",
        "j_1",
        "distance",
        "fov_distance_0",
        "fov_distance_1",
        "cell_barcode_0",
        "gene_symbol_0",
        "gene_id_0",
        "cell_barcode_1",
        "gene_symbol_1",
        "gene_id_1",
        "no_recomb_0",
        "no_recomb_1",
        "Q_min_0",
        "Q_min_1",
        "Q_recomb_0",
        "Q_recomb_1",
        "cell_barcode_peak_0",
        "cell_barcode_peak_1",
        "cell_barcode_count_0",
        "cell_barcode_count_1",
        "mapped_single_gene",
        "channels_min",
        "nucleus_i",
        "nucleus_j",
        "nucleus_bounds_0",
        "nucleus_bounds_1",
        "nucleus_bounds_2",
        "nucleus_bounds_3",
        "cell_i",
        "cell_j",
        "cell_bounds_0",
        "cell_bounds_1",
        "cell_bounds_2",
        "cell_bounds_3",
        "cytoplasm_i",
        "cytoplasm_j",
        "cytoplasm_bounds_0",
        "cytoplasm_bounds_1",
        "cytoplasm_bounds_2",
        "cytoplasm_bounds_3",
    ]
    # === END OPERATOR PARAMETERS ===
    return (
        METADATA_COLS,
        METADATA_COLS_FP,
        TRAINING_CHANNELS,
        TRAINING_DATASET_FP,
        TRAINING_NAME,
        TRAINING_OBJECT_TYPES,
    )


@app.cell
def _(
    CHANNEL_NAMES,
    CLASSIFICATION,
    CLASS_TITLE,
    METADATA_COLS,
    METADATA_COLS_FP,
    TRAINING_CHANNELS,
    TRAINING_DATASET_FP,
    TRAINING_OBJECT_TYPES,
    class_mapping,
    consolidated_df,
    load_cellprofiler_data,
    pd,
):
    # resolve the training table, then derive the metadata/feature split from its columns
    if TRAINING_DATASET_FP is not None:
        print("Loading training data from specified file")
        data = load_cellprofiler_data(
            TRAINING_DATASET_FP, class_title=CLASS_TITLE, metadata_cols=METADATA_COLS
        )
    else:
        print("Using last classified dataset")
        data = consolidated_df

    if data is None:
        metadata_cols = []
        feature_markers = {}
        exclude_markers = []
        print("No training data available - save a training dataset above first")
    else:
        metadata_cols = [col for col in METADATA_COLS if col in data.columns]
        metadata_cols.append(CLASS_TITLE)
        pd.Series(metadata_cols).to_csv(METADATA_COLS_FP, index=False, header=False, sep="\t")

        _training_channels = CHANNEL_NAMES if TRAINING_CHANNELS is None else TRAINING_CHANNELS
        feature_markers = {c: True for c in CHANNEL_NAMES if c in _training_channels}
        exclude_markers = [c for c in CHANNEL_NAMES if c not in _training_channels]

        _missing = [col for col in METADATA_COLS if col not in data.columns]
        print(f"Saved {len(metadata_cols)} metadata columns to {METADATA_COLS_FP}")
        print(f"Found: {len(metadata_cols) - 1}/{len(METADATA_COLS)} candidate columns")
        if _missing:
            print(f"Missing: {', '.join(_missing)}")
        print(f"Class names: {CLASSIFICATION}")
        print(f"Class names to stored numeric values: {class_mapping}")
        print(f"Features to train upon: {feature_markers}")
        print(f"Features to exclude: {exclude_markers}")
        if TRAINING_OBJECT_TYPES is not None:
            _excluded_objects = [
                obj
                for obj in ["nucleus", "cell", "cytoplasm", "second_obj"]
                if obj not in TRAINING_OBJECT_TYPES
            ]
            print(f"Object types to train upon: {TRAINING_OBJECT_TYPES}")
            print(f"Object types to exclude: {_excluded_objects}")
        else:
            print("Object types to train upon: All (nucleus, cell, cytoplasm, second_obj)")
        print(f"Target column: {CLASS_TITLE}")
    return data, exclude_markers, feature_markers, metadata_cols


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 2b. <font color='red'>SET PARAMETERS</font>: Filter Training Classes

    - `REMOVE_MASK_LABELS`: List of class labels to exclude from training (e.g., `unknown`). Set to `None` to keep all classes.
    """)
    return


@app.cell
def _(CLASSIFICATION, class_mapping, filter_classes):
    # === OPERATOR PARAMETERS ===
    REMOVE_MASK_LABELS = None
    # === END OPERATOR PARAMETERS ===

    class_labels, filtered_class_mapping, class_id = filter_classes(
        CLASSIFICATION, class_mapping, REMOVE_MASK_LABELS
    )
    return class_id, class_labels, filtered_class_mapping


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 2c. <font color='red'>SET PARAMETERS</font>: Model Configuration

    - `MODEL_CONFIGS`: Model configurations to train and evaluate, each a `(name, model_type, scaler, feature_options)` tuple.

    **Available model types:**

    - `lr`: Logistic Regression - linear baseline, fast, interpretable
    - `rf`: Random Forest - interpretable ensemble with feature importances
    - `svc`: Support Vector Classifier - works well for smaller datasets
    - `xgb`: XGBoost - gradient boosting, typically best performer
    - `lgb`: LightGBM - fast gradient boosting, handles large datasets well

    **Available scalers:**

    - `standard`: StandardScaler (zero mean, unit variance) - recommended for LR, SVC
    - `robust`: RobustScaler (median/IQR) - good for data with outliers
    - `minmax`: MinMaxScaler (0-1 range)
    - `none`: No scaling - recommended for tree-based models (RF, XGB, LGB)

    **Feature options (optional dict):**

    - `enhance`: Enable feature engineering
    - `remove_low_variance`: Remove near-constant features
    - `remove_correlated`: Remove highly correlated features
    - `select_k_best`: Keep only top K features by importance

    **Recommended configuration:** The default 4 models below cover linear (LR), ensemble (RF), and gradient boosting (XGB, LGB) approaches.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    MODEL_CONFIGS = [
        ("lr_standard", "lr", "standard", None),
        ("rf_standard", "rf", "standard", None),
        ("xgb_none", "xgb", "none", None),
        ("lgb_standard", "lgb", "standard", None),
    ]
    # === END OPERATOR PARAMETERS ===
    return (MODEL_CONFIGS,)


@app.cell
def _(
    CLASSIFIER_OUTPUT_DIR,
    CLASS_TITLE,
    MODEL_CONFIGS,
    Path,
    TRAINING_CHANNELS,
    TRAINING_NAME,
    TRAINING_OBJECT_TYPES,
    class_id,
    class_labels,
    data,
    exclude_markers,
    feature_markers,
    filtered_class_mapping,
    metadata_cols,
    mo,
    pd,
    train_classifier_pipeline,
):
    if data is None:
        multiclass_df = pd.DataFrame()
        last_training_run_dir = None
        print("No training data available - skipping training")
    else:
        _pipeline_result = train_classifier_pipeline(
            data=data,
            class_title=CLASS_TITLE,
            class_id=class_id,
            class_labels=class_labels,
            filtered_class_mapping=filtered_class_mapping,
            metadata_cols=metadata_cols,
            feature_markers=feature_markers,
            exclude_markers=exclude_markers,
            training_name=TRAINING_NAME,
            model_configs=MODEL_CONFIGS,
            classifier_output_dir=CLASSIFIER_OUTPUT_DIR,
            training_channels=TRAINING_CHANNELS,
            training_object_types=TRAINING_OBJECT_TYPES,
            verbose=True,
        )
        multiclass_df = _pipeline_result["metrics_df"]
        last_training_run_dir = _pipeline_result["dirs"]["run"]
        print(f"All outputs written to: {last_training_run_dir}")
        print(f"Saved run directory for evaluation: {Path(last_training_run_dir).name}")

    mo.ui.table(multiclass_df)
    return last_training_run_dir, multiclass_df


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. Selection

    Evaluate the trained models and select the best one with an appropriate confidence threshold.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 3a. <font color='red'>SET PARAMETERS</font>: Model Selection Settings

    - `MODEL_RUN_DIR`: Name of the model run directory to test (e.g., `"run_20250903_114514"`). Set to `None` to use the last training run.
    - `TEST_PLATES`: Plates to use for testing.
    - `TEST_WELLS`: Wells to use for testing.

    **Note:** Data sampling uses `DATA_SAMPLE_FRACTION` and `DATA_MAX_ROWS` from Section 1a.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    MODEL_RUN_DIR = None
    TEST_PLATES = ["1"]
    TEST_WELLS = ["A1", "A2", "A3"]
    # === END OPERATOR PARAMETERS ===
    return MODEL_RUN_DIR, TEST_PLATES, TEST_WELLS


@app.cell
def _(
    CLASSIFIER_OUTPUT_DIR,
    MODEL_RUN_DIR,
    Path,
    TEST_PLATES,
    TEST_WELLS,
    get_latest_run_dir,
):
    if MODEL_RUN_DIR is None:
        model_run_dir = get_latest_run_dir(CLASSIFIER_OUTPUT_DIR)
        print(f"Using most recent run directory: {model_run_dir}")
    else:
        model_run_dir = MODEL_RUN_DIR
        print(f"Using specified run directory: {model_run_dir}")

    CLASSIFIER_DIR_PATH = Path(CLASSIFIER_OUTPUT_DIR) / "classifier" / str(model_run_dir)
    test_plates = [str(p) for p in TEST_PLATES]
    test_wells = [str(w) for w in TEST_WELLS]
    print(f"Classifier run directory: {CLASSIFIER_DIR_PATH}")
    return CLASSIFIER_DIR_PATH, model_run_dir, test_plates, test_wells


@app.cell
def _(
    DATA_MAX_ROWS,
    DATA_SAMPLE_FRACTION,
    METADATA_COLS,
    MODE,
    build_master_phenotype_df,
    mo,
    parquet_dir,
    split_cell_data,
    test_plates,
    test_wells,
):
    master_phenotype_df, master_meta = build_master_phenotype_df(
        plates=test_plates,
        wells=test_wells,
        mode=MODE,
        parquet_dir=parquet_dir,
        verbose=True,
        max_rows=DATA_MAX_ROWS,
        sample_fraction=DATA_SAMPLE_FRACTION,
    )
    metadata, features = split_cell_data(master_phenotype_df, METADATA_COLS)
    print(f"Metadata: {metadata.shape}, features: {features.shape}")
    mo.ui.table(metadata.head(100))
    return features, master_meta, master_phenotype_df, metadata


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The cell below shows the evaluation plots for the selected model run and lists the models it trained. Based on the accuracy and F1 scores, pick a model in the following section; your selection is saved when you run the final cell of this notebook.
    """)
    return


@app.cell
def _(CLASSIFIER_DIR_PATH, display_pngs_in_plots_and_list_models, mo):
    run_plot_pngs, run_results_df, available_models, run_results_csv = (
        display_pngs_in_plots_and_list_models(CLASSIFIER_DIR_PATH)
    )
    mo.vstack([mo.image(str(_p)) for _p in run_plot_pngs])
    return available_models, run_plot_pngs, run_results_csv, run_results_df


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 3b. <font color='red'>SET PARAMETERS</font>: Model Settings

    - `CLASSIFIER_MODEL`: Name of the model to use (e.g., `"xgb_none"`), from the models listed above. Set to `None` to use the best performing model by accuracy.
    - `COLLAPSE_COLS`: Columns to collapse on when creating classification summaries (e.g., `["plate", "well"]`).
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    CLASSIFIER_MODEL = None
    COLLAPSE_COLS = ["plate", "well"]
    # === END OPERATOR PARAMETERS ===
    return CLASSIFIER_MODEL, COLLAPSE_COLS


@app.cell
def _(
    CLASSIFIER_DIR_PATH,
    CLASSIFIER_MODEL,
    mo,
    resolve_classifier_model_dill_path,
    show_model_evaluation_pngs,
):
    CLASSIFIER_PATH, model_name = resolve_classifier_model_dill_path(
        CLASSIFIER_DIR_PATH, CLASSIFIER_MODEL
    )
    print(f"Selected model: {model_name}")
    _eval_pngs = show_model_evaluation_pngs(CLASSIFIER_DIR_PATH, model_name)
    mo.vstack([mo.image(str(_p)) for _p in _eval_pngs])
    return CLASSIFIER_PATH, model_name


@app.cell
def _(
    CLASSIFIER_PATH,
    CLASS_TITLE,
    CellClassifier,
    class_mapping,
    features,
    metadata,
    plot_confidence_distribution,
    plt,
):
    classifier = CellClassifier.load(CLASSIFIER_PATH)
    raw_classified_metadata, classified_features = classifier.classify_cells(metadata, features)
    print(raw_classified_metadata[CLASS_TITLE].value_counts())

    plot_confidence_distribution(
        classified_metadata=raw_classified_metadata,
        class_title=CLASS_TITLE,
        class_mapping=class_mapping,
        thresholds=None,
        log_scale=True,
        figsize=(12, 4),
    )
    plt.show()
    return classified_features, classifier, raw_classified_metadata


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 3c. <font color='red'>SET PARAMETERS</font>: Confidence Calibration

    > **⚠️ Experimental Feature**: Confidence calibration is applied only within this notebook for evaluation and threshold selection. The calibrated confidences are **not** persisted or applied in the downstream aggregate pipeline. Set your thresholds based on raw (uncalibrated) confidence scores if you skip calibration, or be aware that thresholds chosen with calibration enabled may behave differently in production.

    When your classifier predicts whether an object belongs to a category, it also gives a confidence score. However, these confidence scores can be inaccurate - the model might say "80% confident" when it's actually only correct 60% of the time.

    **When to apply post-hoc correction:**

    - First, run with `CONFIDENCE_CORRECTION = None` and examine the confidence histogram and the ranked table below
    - If high-confidence predictions seem frequently wrong, or the confidence scores don't match reality, enable calibration
    - If your confidence scores already look reliable, you can skip calibration

    **Set parameters:**

    - `CONFIDENCE_CORRECTION`: Set to `"post-hoc"` to enable correction. Defaults to `None` (skip correction).
    - `CALIBRATION_DATASET_FP`: Path to additional calibration dataset (only used if correction enabled). Set to `None` to use the training dataset.
    - `CALIBRATION_METHOD`: Calibration method to use. Options are `"isotonic"` (recommended, works for most cases) or `"sigmoid"` (best for very small datasets < 100 objects).
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    CONFIDENCE_CORRECTION = None
    CALIBRATION_DATASET_FP = None
    CALIBRATION_METHOD = "isotonic"
    # === END OPERATOR PARAMETERS ===
    return CALIBRATION_DATASET_FP, CALIBRATION_METHOD, CONFIDENCE_CORRECTION


@app.cell
def _(
    CALIBRATION_DATASET_FP,
    CALIBRATION_METHOD,
    CLASSIFIER_PATH,
    CLASS_TITLE,
    CONFIDENCE_CORRECTION,
    MODE,
    TRAINING_DATASET_FP,
    calibrate_confidence,
    load_cellprofiler_data,
    master_phenotype_df,
    raw_classified_metadata,
    test_plates,
    test_wells,
):
    if CONFIDENCE_CORRECTION is None:
        classified_metadata = raw_classified_metadata
        calibration_meta = None
        print("Skipping confidence calibration")
    else:
        if CALIBRATION_DATASET_FP is not None:
            _manual_labeled_data = load_cellprofiler_data([CALIBRATION_DATASET_FP])
        elif TRAINING_DATASET_FP is None:
            raise ValueError("Set CALIBRATION_DATASET_FP or TRAINING_DATASET_FP for calibration")
        else:
            print(f"No calibration dataset provided, using: {TRAINING_DATASET_FP}")
            _manual_labeled_data = load_cellprofiler_data([TRAINING_DATASET_FP])

        classified_metadata, calibration_meta = calibrate_confidence(
            master_phenotype_df=master_phenotype_df,
            classified_metadata=raw_classified_metadata,
            manual_labeled_data=_manual_labeled_data,
            classify_by=MODE,
            class_title=CLASS_TITLE,
            classifier_path=CLASSIFIER_PATH,
            confidence_correction=CONFIDENCE_CORRECTION,
            calibration_method=CALIBRATION_METHOD,
            test_plate=test_plates,
            test_well=test_wells,
            min_samples_isotonic=50,
            verbose=True,
        )
    return calibration_meta, classified_metadata


@app.cell
def _(
    CLASS_TITLE,
    COLLAPSE_COLS,
    class_mapping,
    classified_metadata,
    mo,
    summarize_classification,
):
    classification_summary, ORDERED_CLASSES = summarize_classification(
        classified_metadata=classified_metadata,
        class_mapping=class_mapping,
        class_title=CLASS_TITLE,
        collapse_cols=COLLAPSE_COLS,
    )
    print(f"Ordered classes: {ORDERED_CLASSES}")
    mo.ui.table(classification_summary)
    return ORDERED_CLASSES, classification_summary


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 3d. <font color='red'>SET PARAMETERS</font>: Ranked Prediction Review

    The jupyter notebook browses predictions with an ipywidgets "rankline" that steps along the confidence axis. The table below is its replacement: objects of one class ranked by confidence, thinned so that consecutive rows differ by at least `MINIMUM_DIFFERENCE`, so a short table still spans the whole confidence range. Select rows in the table to render their crops underneath, the same rendering the labeler uses, and check whether the confidence the model reports matches what the image shows.

    - `RANKLINE_CLASS`: Class name to review, from `CLASSIFICATION`. Set to `None` to review the first class.
    - `MINIMUM_DIFFERENCE`: Minimum confidence difference between consecutive rows in the ranked table.
    - `RANKLINE_MAX_ROWS`: Maximum number of ranked rows to keep.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    RANKLINE_CLASS = None
    MINIMUM_DIFFERENCE = 0.001
    RANKLINE_MAX_ROWS = 200
    # === END OPERATOR PARAMETERS ===
    return MINIMUM_DIFFERENCE, RANKLINE_CLASS, RANKLINE_MAX_ROWS


@app.cell
def _(
    CLASSIFICATION,
    CLASS_TITLE,
    MINIMUM_DIFFERENCE,
    MODE,
    RANKLINE_CLASS,
    RANKLINE_MAX_ROWS,
    classified_metadata,
    mo,
    pd,
):
    _class_name = RANKLINE_CLASS if RANKLINE_CLASS is not None else CLASSIFICATION[0]
    _class_id = CLASSIFICATION.index(_class_name) + 1

    if MODE == "vacuole":
        _id_col = "vacuole_id"
    elif "cell_0" in classified_metadata.columns:
        _id_col = "cell_0"
    elif "cell_id" in classified_metadata.columns:
        _id_col = "cell_id"
    else:
        _id_col = "label"

    _ranked = (
        classified_metadata[classified_metadata[CLASS_TITLE] == _class_id]
        .sort_values("confidence", ascending=False)
        .loc[:, ["plate", "well", "tile", _id_col, CLASS_TITLE, "confidence"]]
        .rename(columns={_id_col: "mask_label"})
        .reset_index(drop=True)
    )

    # thin the ranking so consecutive rows are at least MINIMUM_DIFFERENCE apart in confidence
    _keep = []
    _last = None
    for _row in _ranked.itertuples(index=False):
        if _last is None or abs(_last - _row.confidence) >= MINIMUM_DIFFERENCE:
            _keep.append(_row._asdict())
            _last = _row.confidence
        if len(_keep) >= RANKLINE_MAX_ROWS:
            break

    rankline_df = pd.DataFrame(_keep) if _keep else _ranked.head(0)
    print(f"Reviewing class '{_class_name}' (id {_class_id})")
    print(f"{len(_ranked)} predictions, {len(rankline_df)} shown after thinning")
    rankline_table = mo.ui.table(rankline_df, selection="multi", page_size=25)
    rankline_table
    return rankline_df, rankline_table


@app.cell
def _(
    CHANNEL_INDICES,
    CHANNEL_NAMES,
    DISPLAY_CHANNEL,
    MODE,
    SCALE_BAR,
    compose_rgb_crops,
    compute_crop_bounds,
    images_source,
    load_aligned_stack,
    load_mask_labels,
    mo,
    np,
    overlay_mask_boundary_inplace,
    overlay_scale_bar,
    rankline_table,
    resolved_colors,
    to_png_bytes,
):
    _panel_names = list(DISPLAY_CHANNEL) + ["merged"]
    _selected = rankline_table.value
    _cards = []

    for _sel in _selected.to_dict(orient="records"):
        _plate, _well = int(_sel["plate"]), str(_sel["well"])
        _tile, _mask = int(_sel["tile"]), int(_sel["mask_label"])
        _stack = load_aligned_stack(images_source, CHANNEL_NAMES, _plate, _well, _tile)
        _y0, _y1, _x0, _x1 = compute_crop_bounds(
            images_source,
            MODE,
            _plate,
            _well,
            _tile,
            _mask,
            (_stack.shape[1], _stack.shape[2]),
        )
        _imgs, _merged = compose_rgb_crops(
            _stack, _y0, _y1, _x0, _x1, CHANNEL_INDICES, resolved_colors
        )
        _mask_crop = (
            load_mask_labels(images_source, MODE, _plate, _well, _tile)[_y0:_y1, _x0:_x1] == _mask
        )
        if np.any(_mask_crop):
            overlay_mask_boundary_inplace(_merged, _mask_crop, step=2, value=1.0)
        if SCALE_BAR and SCALE_BAR > 0:
            overlay_scale_bar(_merged, int(SCALE_BAR))

        _cards.append(
            mo.vstack(
                [
                    mo.md(
                        f"**P-{_plate} W-{_well} T-{_tile}** mask {_mask} - "
                        f"confidence {_sel['confidence']:.4f}"
                    ),
                    mo.hstack(
                        [
                            mo.vstack([mo.md(f"`{_n}`"), mo.image(to_png_bytes(_a), width=180)])
                            for _n, _a in zip(_panel_names, _imgs + [_merged])
                        ],
                        justify="start",
                    ),
                ]
            )
        )

    mo.vstack(_cards) if _cards else mo.md("Select rows in the table above to see crops.")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 3e. <font color='red'>SET PARAMETERS</font>: Per-Class Confidence Thresholds

    - `CONFIDENCE_THRESHOLDS`: Per-class confidence thresholds keyed by class ID, where class IDs follow `CLASSIFICATION` order (1, 2, 3, ...). Each entry is `{"threshold": float, "mode": str}`.

    ```python
    CONFIDENCE_THRESHOLDS = {
        1: {"threshold": 0.94, "mode": "exclude"},
        2: {"threshold": 0.50, "mode": "reassign"},
    }
    ```

    **Modes:**

    - `"exclude"` - Drops cells below threshold (default)
    - `"reassign"` - Attempts to reassign low-confidence cells to another class if they pass that class's threshold; drops if reassignment fails

    Higher thresholds = stricter filtering (fewer cells but higher quality). Use `"reassign"` for the majority class to recover borderline cells.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    CONFIDENCE_THRESHOLDS = {
        1: {"threshold": 0.5, "mode": "exclude"},
        2: {"threshold": 0.5, "mode": "exclude"},
    }
    # === END OPERATOR PARAMETERS ===
    return (CONFIDENCE_THRESHOLDS,)


@app.cell
def _(
    CLASS_TITLE,
    CONFIDENCE_THRESHOLDS,
    apply_class_thresholds,
    class_mapping,
    classified_metadata,
    mo,
    plot_confidence_distribution,
    plt,
):
    plot_confidence_distribution(
        classified_metadata=classified_metadata,
        class_title=CLASS_TITLE,
        class_mapping=class_mapping,
        thresholds=CONFIDENCE_THRESHOLDS,
        log_scale=True,
        figsize=(12, 4),
    )
    plt.show()

    filtered_df, threshold_summary = apply_class_thresholds(
        classified_metadata=classified_metadata,
        class_title=CLASS_TITLE,
        thresholds=CONFIDENCE_THRESHOLDS,
        class_mapping=class_mapping,
    )
    print(f"Cells retained after thresholding: {len(filtered_df)}")
    mo.ui.table(threshold_summary)
    return filtered_df, threshold_summary


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Add classify parameters to config file
    """)
    return


@app.cell
def _(
    CLASSIFIER_PATH,
    CLASS_TITLE,
    CONFIDENCE_THRESHOLDS,
    CONFIG_FILE_HEADER,
    CONFIG_FILE_PATH,
    METADATA_COLS_FP,
    class_mapping,
    config,
    convert_tuples_to_lists,
    yaml,
):
    # Add classify section
    config["classify"] = {
        "classifier_path": str(CLASSIFIER_PATH),
        "confidence_thresholds": CONFIDENCE_THRESHOLDS,
        "metadata_cols_fp": str(METADATA_COLS_FP),
        "class_title": CLASS_TITLE,
        "class_mapping": class_mapping,
    }
    safe_config = convert_tuples_to_lists(config)
    with open(CONFIG_FILE_PATH, "w") as _config_file:
        _config_file.write(CONFIG_FILE_HEADER)
        yaml.safe_dump(safe_config, _config_file, default_flow_style=False, sort_keys=False)

    print("Saved classifier settings to config.")
    return (safe_config,)


if __name__ == "__main__":
    app.run()
