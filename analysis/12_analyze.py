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
    # Downstream Analysis

    This notebook should be used for downstream analysis of your OPS screen.
    Cells marked with <font color='red'>SET PARAMETERS</font> contain crucial variables that need to be set according to your specific experimental setup and data organization.
    Please review and modify these variables as needed before proceeding with the analysis.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Fixed parameters for analysis

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
    import json
    import os
    import re
    import warnings

    warnings.filterwarnings("ignore", category=UserWarning)

    import yaml
    import pandas as pd
    from matplotlib import pyplot as plt
    from skimage.exposure import rescale_intensity

    from lib.shared.file_utils import get_filename, load_parquet_subset
    from lib.shared.metrics import get_all_stats
    from lib.shared.configuration_utils import CONFIG_FILE_HEADER, convert_tuples_to_lists
    from lib.shared.compartment_utils import add_compartment_path
    from lib.aggregate.montage_utils import create_cell_montage, add_filenames
    from lib.cluster.cluster_analysis import (
        differential_analysis,
        waterfall_plot,
        two_feature_plot,
        cluster_heatmap,
        volcano_plot,
    )
    from lib.cluster.cluster_eval import (
        find_optimal_resolution,
        merge_bootstrap_with_genes,
        plot_resolution_comparison,
    )
    from lib.cluster.phate_leiden_clustering import plot_phate_leiden_clusters

    return (
        CONFIG_FILE_HEADER,
        Path,
        add_compartment_path,
        add_filenames,
        cluster_heatmap,
        convert_tuples_to_lists,
        create_cell_montage,
        differential_analysis,
        find_optimal_resolution,
        get_all_stats,
        get_filename,
        json,
        load_parquet_subset,
        merge_bootstrap_with_genes,
        os,
        pd,
        plot_phate_leiden_clusters,
        plot_resolution_comparison,
        plt,
        re,
        rescale_intensity,
        two_feature_plot,
        volcano_plot,
        waterfall_plot,
        yaml,
    )


@app.cell
def _(CONFIG_FILE_PATH, Path, yaml):
    # load config file and determine root path
    with open(CONFIG_FILE_PATH, "r") as _config_file:
        config = yaml.safe_load(_config_file)
    ROOT_FP = Path(config["all"]["root_fp"])
    PERTURBATION_NAME_COL = config["aggregate"]["perturbation_name_col"]
    CONTROL_KEY = config["aggregate"]["control_key"]
    IMAGE_FORMAT = config["all"].get("image_format", "tiff")
    SPLIT_BY_COMPARTMENT = config["aggregate"].get("split_by_compartment", False)
    print(f"Root path: {ROOT_FP}")
    print(f"Perturbation name column: {PERTURBATION_NAME_COL}")
    print(f"Control key: {CONTROL_KEY}")
    print(f"Image format: {IMAGE_FORMAT}")
    print(f"Split by compartment: {SPLIT_BY_COMPARTMENT}")
    return (
        CONTROL_KEY,
        IMAGE_FORMAT,
        PERTURBATION_NAME_COL,
        ROOT_FP,
        SPLIT_BY_COMPARTMENT,
        config,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Pipeline Statistics Report

    This function analyzes the entire data processing pipeline from raw microscopy images to clustered perturbation profiles. It reports:

    1. **Preprocessing**: Input files and generated image tiles
    2. **SBS**: Cell segmentation and barcode mapping success rates
    3. **Phenotype**: Cells and morphological features extracted
    4. **Merge**: Phenotype/SBS matching rates and single gene mapping
    5. **Aggregation**: Perturbation coverage and cell counts per class
    6. **Clustering**: Pathway enrichment metrics (CORUM, KEGG, STRING)

    To include batch effect metrics (slower), use: `get_all_stats(config, include_batch_effects=True)`
    """)
    return


@app.cell
def _(config, get_all_stats):
    statistics = get_all_stats(config)
    return (statistics,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Find Optimal Resolution

    Use benchmark results from Snakemake outputs to identify the best Leiden resolution for each cell class/channel combination.
    """)
    return


@app.cell
def _(config, mo, pd):
    # load cell classes and channel combos from config
    cluster_combos = pd.read_csv(config["cluster"]["cluster_combo_fp"], sep="\t")
    CHANNEL_COMBOS = list(cluster_combos["channel_combo"].unique())
    CELL_CLASSES = list(cluster_combos["cell_class"].unique())
    print(f"Channel Combos: {CHANNEL_COMBOS}")
    print(f"Cell classes: {CELL_CLASSES}")
    mo.ui.table(cluster_combos)
    return CELL_CLASSES, CHANNEL_COMBOS, cluster_combos


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Resolution search

    - `RESOLUTION_METRIC`: Benchmark metric used to rank Leiden resolutions. One of `"corum_enrichment"`, `"kegg_enrichment"`, `"string_f1"`, `"combined"`, or `"balanced"`.
    - `RESOLUTION_USE_FILTERED`: Read benchmark results from the `filtered/` subdirectory instead of the unfiltered one.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    RESOLUTION_METRIC = "corum_enrichment"
    RESOLUTION_USE_FILTERED = False
    # === END OPERATOR PARAMETERS ===
    return RESOLUTION_METRIC, RESOLUTION_USE_FILTERED


@app.cell
def _(
    CELL_CLASSES,
    CHANNEL_COMBOS,
    RESOLUTION_METRIC,
    RESOLUTION_USE_FILTERED,
    ROOT_FP,
    find_optimal_resolution,
    plot_resolution_comparison,
    plt,
):
    # find optimal resolution for each cell class/channel combo
    optimal_resolutions = {}
    _summary_cols = [
        "resolution",
        "corum_enrichment",
        "kegg_enrichment",
        "string_f1",
        "corum_num_enriched",
    ]

    for _cell_class in CELL_CLASSES:
        for _channel_combo in CHANNEL_COMBOS:
            try:
                _result = find_optimal_resolution(
                    root_fp=ROOT_FP,
                    channel_combo=_channel_combo,
                    cell_class=_cell_class,
                    use_filtered=RESOLUTION_USE_FILTERED,
                    metric=RESOLUTION_METRIC,
                )
            except Exception as _err:
                print(f"\n{_cell_class} / {_channel_combo}: no benchmark results ({_err})")
                continue

            optimal_resolutions[f"{_cell_class}_{_channel_combo}"] = _result
            print(f"\n{_cell_class} / {_channel_combo}:")
            print(f"  Optimal resolution: {_result['optimal_resolution']}")
            print(f"  Metric used: {_result['metric_used']}")
            print(
                _result["all_results"][
                    [c for c in _summary_cols if c in _result["all_results"].columns]
                ].to_string(index=False)
            )

            plot_resolution_comparison(_result["all_results"], metric=RESOLUTION_METRIC)
            plt.suptitle(f"{_cell_class} / {_channel_combo}", fontsize=12)
            plt.tight_layout()
            plt.show()
    return (optimal_resolutions,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Cluster selection for analysis

    These parameters determine which folder of cluster data is analyzed, and they are also the clustering result handed to mozzarellm at the end of this notebook.

    - `CHANNEL_COMBO`: Channel combination to analyze, from the channel combos listed above.
    - `CELL_CLASS`: Cell class to analyze, from the cell classes listed above.
    - `LEIDEN_RESOLUTION`: Leiden resolution to analyze, ideally the optimal resolution reported above.
    - `COMPARTMENT_COMBO`: Compartment combo to analyze, ex `"nucleus"`. Only used when `aggregate.split_by_compartment` is on; leave `None` otherwise.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    CHANNEL_COMBO = None
    CELL_CLASS = None
    LEIDEN_RESOLUTION = None
    COMPARTMENT_COMBO = None
    # === END OPERATOR PARAMETERS ===
    return CELL_CLASS, CHANNEL_COMBO, COMPARTMENT_COMBO, LEIDEN_RESOLUTION


@app.cell
def _(
    CELL_CLASS,
    CHANNEL_COMBO,
    COMPARTMENT_COMBO,
    LEIDEN_RESOLUTION,
    ROOT_FP,
    SPLIT_BY_COMPARTMENT,
    add_compartment_path,
    get_filename,
):
    _selection_set = None not in (CHANNEL_COMBO, CELL_CLASS, LEIDEN_RESOLUTION) and (
        COMPARTMENT_COMBO is not None or not SPLIT_BY_COMPARTMENT
    )

    if _selection_set:
        # compartment segment/metadata only when the aggregate step split by compartment
        _compartment_metadata = (
            {"compartment_combo": COMPARTMENT_COMBO} if SPLIT_BY_COMPARTMENT else {}
        )
        aggregate_file = (
            ROOT_FP
            / "aggregate"
            / "tsvs"
            / get_filename(
                {
                    "cell_class": CELL_CLASS,
                    "channel_combo": CHANNEL_COMBO,
                    **_compartment_metadata,
                },
                "features_genes",
                "tsv",
            )
        )
        _cluster_base = add_compartment_path(
            ROOT_FP / "cluster" / CHANNEL_COMBO,
            COMPARTMENT_COMBO,
            SPLIT_BY_COMPARTMENT,
        )
        cluster_path = _cluster_base / CELL_CLASS / str(LEIDEN_RESOLUTION)
        cluster_h5ad = _cluster_base / CELL_CLASS / "h5ad" / get_filename({}, "cluster", "h5ad")
        print(f"Aggregate file: {aggregate_file}")
        print(f"  found: {aggregate_file.exists()}")
        print(f"Cluster path: {cluster_path}")
        print(f"  found: {cluster_path.exists()}")
        print(f"Cluster h5ad: {cluster_h5ad}")
        print(f"  found: {cluster_h5ad.exists()}")
    else:
        aggregate_file = None
        cluster_path = None
        cluster_h5ad = None
        print("Set CHANNEL_COMBO, CELL_CLASS and LEIDEN_RESOLUTION to continue")
    return aggregate_file, cluster_h5ad, cluster_path


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Feature Plot Analysis

    This section generates visualizations to explore the phenotypic effects of gene perturbations in your screen. The plots will help you:

    1. **Differential Feature Analysis**: Identify genes with significant phenotypic changes vs. controls
    2. **Waterfall Plots**: Rank genes by their effect on specific features of interest
    3. **Two-Feature Plots**: Discover relationships between different phenotypic measurements
    4. **Heatmaps**: Visualize patterns across multiple features and gene sets simultaneously

    The interactive analysis allows you to customize each visualization for your specific biological questions.
    """)
    return


@app.cell
def _(aggregate_file, cluster_path, mo, pd):
    if cluster_path is not None and cluster_path.exists():
        cluster_df = pd.read_csv(cluster_path / "phate_leiden_clustering.tsv", sep="\t")
        print(f"Clustering: {len(cluster_df)} rows, {cluster_df['cluster'].nunique()} clusters")
    else:
        cluster_df = None
        print("No clustering table loaded")

    if aggregate_file is not None and aggregate_file.exists():
        aggregate_df = pd.read_csv(aggregate_file, sep="\t")
        print(f"Gene feature table: {aggregate_df.shape[0]} genes, {aggregate_df.shape[1]} columns")
    else:
        aggregate_df = None
        print("No gene feature table loaded")

    mo.ui.table(cluster_df if cluster_df is not None else pd.DataFrame())
    return aggregate_df, cluster_df


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Cluster selection for visualization

    - `CLUSTER_ID`: The cluster of interest to generate plots for, from the `cluster` column of the clustering table above.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    CLUSTER_ID = None
    # === END OPERATOR PARAMETERS ===
    return (CLUSTER_ID,)


@app.cell
def _(
    CLUSTER_ID,
    CONTROL_KEY,
    PERTURBATION_NAME_COL,
    aggregate_df,
    cluster_df,
    differential_analysis,
    mo,
    pd,
):
    _display_cols = [
        "feature",
        "robust_zscore",
        "p_value",
        "median_test",
        "median_control",
    ]

    if CLUSTER_ID is not None and aggregate_df is not None and cluster_df is not None:
        _cluster_genes = cluster_df[cluster_df["cluster"] == CLUSTER_ID][PERTURBATION_NAME_COL]
        print(f"Analyzing cluster {CLUSTER_ID}")
        print(f"Genes in cluster: {', '.join(_cluster_genes.unique())}")

        diff_results = differential_analysis(
            feature_df=aggregate_df,
            cluster_df=cluster_df,
            cluster_id=CLUSTER_ID,
            control_type="nontargeting",
            control_label=CONTROL_KEY,
            use_nonparametric=True,
            normalize_method="robust_zscore",
        )

        _up_df = diff_results["top_up"][_display_cols].assign(direction="up")
        _down_df = diff_results["top_down"][_display_cols].assign(direction="down")
        diff_summary = pd.concat([_up_df, _down_df], ignore_index=True)
        print(f"Top differential features: {len(_up_df)} up, {len(_down_df)} down")
    else:
        diff_results = None
        diff_summary = pd.DataFrame(columns=_display_cols)
        print("Set CLUSTER_ID (and load the tables above) to run differential analysis")

    mo.ui.table(diff_summary)
    return diff_results, diff_summary


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Feature selection for visualization

    - `FEATURES_TO_ANALYZE`: Features from the differential analysis above to generate waterfall and two-feature plots for, ex `["nucleus_DAPI_mean", "cell_area"]`. Set to `None` to skip the feature plots.
    - `GENES_TO_LABEL`: Genes within the cluster to label on the plots, ex `["AURKB", "INCENP"]`. Set to `None` for no labels.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    FEATURES_TO_ANALYZE = None
    GENES_TO_LABEL = None
    # === END OPERATOR PARAMETERS ===
    return FEATURES_TO_ANALYZE, GENES_TO_LABEL


@app.cell
def _(
    CLUSTER_ID,
    CONTROL_KEY,
    FEATURES_TO_ANALYZE,
    GENES_TO_LABEL,
    PERTURBATION_NAME_COL,
    aggregate_df,
    cluster_df,
    cluster_heatmap,
    diff_results,
    plot_phate_leiden_clusters,
    plt,
    two_feature_plot,
    waterfall_plot,
):
    if FEATURES_TO_ANALYZE is not None and diff_results is not None:
        for _feature in FEATURES_TO_ANALYZE:
            waterfall_plot(
                feature_df=aggregate_df,
                feature=_feature,
                cluster_df=cluster_df,
                cluster_id=CLUSTER_ID,
                nontargeting_pattern=CONTROL_KEY,
                title=f"Cluster {CLUSTER_ID}: {_feature}",
                label_genes=GENES_TO_LABEL,
            )
            plt.show()

        _feature_pairs = [
            (FEATURES_TO_ANALYZE[i], FEATURES_TO_ANALYZE[j])
            for i in range(len(FEATURES_TO_ANALYZE))
            for j in range(i + 1, len(FEATURES_TO_ANALYZE))
        ]
        for _feature_1, _feature_2 in _feature_pairs:
            two_feature_plot(
                feature_df=aggregate_df,
                x=_feature_1,
                y=_feature_2,
                cluster_df=cluster_df,
                cluster_id=CLUSTER_ID,
                nontargeting_pattern=CONTROL_KEY,
                title=f"Cluster {CLUSTER_ID}: {_feature_1} vs {_feature_2}",
                label_genes=GENES_TO_LABEL,
            )
            plt.show()

        _top_up = diff_results["top_up"]["feature"].tolist()
        _top_down = diff_results["top_down"]["feature"].tolist()
        cluster_heatmap(
            feature_df=aggregate_df,
            cluster_df=cluster_df,
            cluster_ids=[CLUSTER_ID],
            features=_top_up + _top_down,
            perturbation_name_col=PERTURBATION_NAME_COL,
            z_score="global",
            title=f"Cluster {CLUSTER_ID}: Top Differential Features",
        )
        plt.show()

        plot_phate_leiden_clusters(
            phate_leiden_clustering=cluster_df,
            perturbation_name_col=PERTURBATION_NAME_COL,
            control_key=CONTROL_KEY,
            clusters_of_interest=[CLUSTER_ID],
        )
        plt.show()
    else:
        print("Set FEATURES_TO_ANALYZE (and run differential analysis) to draw feature plots")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Volcano Plot Analysis

    Volcano plots visualize the relationship between effect size (z-score) and statistical significance (-log10 p-value) from bootstrap analysis. This helps identify genes with both large effects and high confidence.

    **Prerequisites:** Bootstrap analysis must have been run during the aggregate step.
    """)
    return


@app.cell
def _(
    CELL_CLASS,
    CHANNEL_COMBO,
    PERTURBATION_NAME_COL,
    ROOT_FP,
    aggregate_df,
    get_filename,
    merge_bootstrap_with_genes,
    mo,
    pd,
):
    if CELL_CLASS is not None and CHANNEL_COMBO is not None:
        bootstrap_file = (
            ROOT_FP
            / "aggregate"
            / "bootstrap"
            / get_filename(
                {"cell_class": CELL_CLASS, "channel_combo": CHANNEL_COMBO},
                "all_gene_bootstrap_results",
                "tsv",
            )
        )
    else:
        bootstrap_file = None

    if bootstrap_file is not None and bootstrap_file.exists() and aggregate_df is not None:
        _bootstrap_df = pd.read_csv(bootstrap_file, sep="\t")
        merged_df = merge_bootstrap_with_genes(
            bootstrap_df=_bootstrap_df,
            genes_df=aggregate_df,
            perturbation_name_col=PERTURBATION_NAME_COL,
            bootstrap_gene_col="gene",
        )
        _n_features = len([c for c in merged_df.columns if c.endswith("_fdr")])
        print(f"Loaded bootstrap results: {len(_bootstrap_df)} genes")
        print(f"Merged data: {len(merged_df)} genes with {_n_features} features tested")
    else:
        merged_df = None
        print(f"Bootstrap file not found: {bootstrap_file}")
        print("Run the aggregate module with bootstrap enabled to generate this data.")

    mo.ui.table(merged_df.head(100) if merged_df is not None else pd.DataFrame())
    return (merged_df,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Volcano plot configuration

    - `VOLCANO_FEATURE`: Feature to plot. Must be one of the bootstrapped features listed above. Set to `None` to skip the volcano plot.
    - `VOLCANO_FDR_THRESHOLD`: FDR threshold for calling a gene significant.
    - `VOLCANO_ZSCORE_THRESHOLD`: Absolute z-score threshold for calling an effect size meaningful.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    VOLCANO_FEATURE = None
    VOLCANO_FDR_THRESHOLD = 0.05
    VOLCANO_ZSCORE_THRESHOLD = 2.0
    # === END OPERATOR PARAMETERS ===
    return VOLCANO_FDR_THRESHOLD, VOLCANO_FEATURE, VOLCANO_ZSCORE_THRESHOLD


@app.cell
def _(
    CLUSTER_ID,
    GENES_TO_LABEL,
    PERTURBATION_NAME_COL,
    VOLCANO_FDR_THRESHOLD,
    VOLCANO_FEATURE,
    VOLCANO_ZSCORE_THRESHOLD,
    cluster_df,
    merged_df,
    plt,
    volcano_plot,
):
    if merged_df is None:
        print("No bootstrap data available - load bootstrap results first")
    elif VOLCANO_FEATURE is None:
        print("Set VOLCANO_FEATURE to create a volcano plot")
    elif f"{VOLCANO_FEATURE}_log10" not in merged_df.columns:
        _available = [c.replace("_log10", "") for c in merged_df.columns if c.endswith("_log10")]
        print(f"Feature '{VOLCANO_FEATURE}' not found in bootstrap results.")
        print(f"Available features: {_available[:10]}...")
    else:
        volcano_plot(
            merged_df=merged_df,
            feature=VOLCANO_FEATURE,
            perturbation_name_col=PERTURBATION_NAME_COL,
            cluster_df=cluster_df,
            cluster_id=CLUSTER_ID,
            fdr_threshold=VOLCANO_FDR_THRESHOLD,
            zscore_threshold=VOLCANO_ZSCORE_THRESHOLD,
            title=f"Cluster {CLUSTER_ID}: {VOLCANO_FEATURE}",
            label_genes=GENES_TO_LABEL,
        )
        plt.show()

        _fdr_col = f"{VOLCANO_FEATURE}_fdr"
        if _fdr_col in merged_df.columns:
            _significant = merged_df[_fdr_col] < VOLCANO_FDR_THRESHOLD
            _up = (_significant & (merged_df[VOLCANO_FEATURE] >= VOLCANO_ZSCORE_THRESHOLD)).sum()
            _down = (_significant & (merged_df[VOLCANO_FEATURE] <= -VOLCANO_ZSCORE_THRESHOLD)).sum()
            print(
                f"Significant genes (FDR < {VOLCANO_FDR_THRESHOLD}, "
                f"|z| >= {VOLCANO_ZSCORE_THRESHOLD}): {_up} up, {_down} down"
            )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Cell Montage Generation

    Generate montages of cells sorted by a specific feature value. This helps visualize the morphological phenotypes associated with perturbations.

    Cell-level data comes from the merge module's final per-well parquet, so a montage is built from one plate/well at a time. **Prerequisites:** merge outputs and the aligned phenotype images they point at must be available in the output directory.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Montage configuration

    - `MONTAGE_FEATURE`: Feature to sort cells by, ex a feature from the differential analysis above. Set to `None` to skip the montage.
    - `MONTAGE_PLATE`: Plate to draw cells from, ex `1`.
    - `MONTAGE_WELL`: Well to draw cells from, ex `"A1"`.
    - `MONTAGE_GENE`: Perturbation to restrict the montage to, ex `"AURKB"`. Set to `None` to use all perturbations in the well.
    - `MONTAGE_NUM_CELLS`: Number of cells to include in the montage.
    - `MONTAGE_CELL_SIZE`: Half-width, in pixels, of the bounding box cropped around each cell.
    - `MONTAGE_SHAPE`: Grid shape of the montage as `(rows, cols)`. Its product should match `MONTAGE_NUM_CELLS`.
    - `MONTAGE_ASCENDING`: Sort order. `True` puts the lowest feature values first, `False` the highest.
    - `MONTAGE_SUBSET_ROWS`: Number of rows sampled from the merge parquet before selecting cells, to keep memory bounded.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    MONTAGE_FEATURE = None
    MONTAGE_PLATE = None
    MONTAGE_WELL = None
    MONTAGE_GENE = None
    MONTAGE_NUM_CELLS = 30
    MONTAGE_CELL_SIZE = 40
    MONTAGE_SHAPE = (3, 10)
    MONTAGE_ASCENDING = False
    MONTAGE_SUBSET_ROWS = 25000
    # === END OPERATOR PARAMETERS ===
    return (
        MONTAGE_ASCENDING,
        MONTAGE_CELL_SIZE,
        MONTAGE_FEATURE,
        MONTAGE_GENE,
        MONTAGE_NUM_CELLS,
        MONTAGE_PLATE,
        MONTAGE_SHAPE,
        MONTAGE_SUBSET_ROWS,
        MONTAGE_WELL,
    )


@app.cell
def _(
    IMAGE_FORMAT,
    MONTAGE_ASCENDING,
    MONTAGE_CELL_SIZE,
    MONTAGE_FEATURE,
    MONTAGE_GENE,
    MONTAGE_NUM_CELLS,
    MONTAGE_PLATE,
    MONTAGE_SHAPE,
    MONTAGE_SUBSET_ROWS,
    MONTAGE_WELL,
    PERTURBATION_NAME_COL,
    ROOT_FP,
    add_filenames,
    config,
    create_cell_montage,
    get_filename,
    load_parquet_subset,
    plt,
    rescale_intensity,
):
    if MONTAGE_FEATURE is None or MONTAGE_PLATE is None or MONTAGE_WELL is None:
        print("Set MONTAGE_FEATURE, MONTAGE_PLATE and MONTAGE_WELL to generate a montage")
    else:
        _merge_fp = (
            ROOT_FP
            / "merge"
            / "parquets"
            / get_filename({"plate": MONTAGE_PLATE, "well": MONTAGE_WELL}, "merge_final", "parquet")
        )
        if not _merge_fp.exists():
            print(f"Merge data not found: {_merge_fp}")
        else:
            _cell_data = load_parquet_subset(_merge_fp, n_rows=MONTAGE_SUBSET_ROWS)
            _cell_data = add_filenames(_cell_data, ROOT_FP, img_fmt=IMAGE_FORMAT)

            if MONTAGE_GENE is not None:
                _cell_data = _cell_data[_cell_data[PERTURBATION_NAME_COL] == MONTAGE_GENE].copy()
                _title_suffix = f"Gene: {MONTAGE_GENE}"
            else:
                _title_suffix = "All perturbations"

            if len(_cell_data) == 0:
                print(f"No cells found for gene: {MONTAGE_GENE}")
            else:
                _channels = config["phenotype"]["channel_names"]
                _montages = create_cell_montage(
                    cell_data=_cell_data,
                    channels=_channels,
                    num_cells=MONTAGE_NUM_CELLS,
                    cell_size=MONTAGE_CELL_SIZE,
                    shape=MONTAGE_SHAPE,
                    selection_params={
                        "method": "sorted",
                        "sort_by": MONTAGE_FEATURE,
                        "ascending": MONTAGE_ASCENDING,
                    },
                )
                _fig, _axes = plt.subplots(
                    1, len(_channels), figsize=(4 * len(_channels), 4), squeeze=False
                )
                for _ax, (_channel, _montage) in zip(_axes.flat, _montages.items()):
                    _ax.imshow(
                        rescale_intensity(_montage, in_range="image", out_range=(0, 1)),
                        cmap="gray",
                    )
                    _ax.set_title(_channel)
                    _ax.axis("off")
                _sort_order = "ascending" if MONTAGE_ASCENDING else "descending"
                plt.suptitle(
                    f"Montage sorted by {MONTAGE_FEATURE} ({_sort_order})\n{_title_suffix}",
                    fontsize=12,
                )
                plt.tight_layout()
                plt.show()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Mozzarellm: LLM-based gene cluster analysis

    [Mozzarellm](https://github.com/cheeseman-lab/mozzarellm) reads the cluster AnnData written by the cluster module, builds one evidence bundle per cluster (functional annotations for every gene, plus that gene's strongest phenotypic features), and asks a large language model to name the pathway behind each cluster and to categorize every gene as established, novel-role or uncharacterized.

    ### Prerequisites

    Install the mozzarellm extra in your Brieflow environment:

    ```bash
    python -m pip install -e "../brieflow[mozzarellm]"
    ```

    Set up the API key for your model's provider in a `.env` file in the analysis directory:

    ```bash
    ANTHROPIC_API_KEY=your_key_here
    ```

    ### Workflow

    1. Configure the parameters below. The cells that follow write one screen context per selected clustering into `config/mozzarellm_context/`, the combo table `config/mozzarellm_combo.tsv`, and the `mozzarellm` config section.
    2. Read the dry run at the end of this notebook, which prices the whole selection before any model is called.
    3. Run `bash flow.sh mozzarellm --backend slurm`, which submits one low-memory job per row of the combo table and writes each run to `{cluster_path}/mozzarellm/{MOZZARELLM_RUN_NAME}/`.

    By default the clustering annotated is the one selected above for the plots (`CHANNEL_COMBO` / `CELL_CLASS` / `LEIDEN_RESOLUTION`); add more with `MOZZARELLM_EXTRA_CLUSTERINGS`.

    ### Who owns the screen contexts

    Each context is derived once from `screen.yaml` and `config.yml` as a starting point, and from then on it is yours: a context file that already exists is never overwritten. Edit the JSON in `config/mozzarellm_context/` for a one-off correction to a single clustering. Put anything that should follow a channel everywhere into `screen.yaml` instead, as that channel's `description` — every combo containing the channel then inherits it, and every future context starts closer to correct. Set `MOZZARELLM_REWRITE_CONTEXTS = True` only when you want your edits thrown away and the contexts re-derived.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Mozzarellm configuration

    - `MOZZARELLM_MODEL`: LLM model identifier passed to mozzarellm, ex `"claude-sonnet-5"`, `"gpt-5"` or `"gemini-2.5-pro"`. The API key for the corresponding provider must be present in `.env`.
    - `MOZZARELLM_MODE`: Prompting mode. `"cot"` reasons through the cluster in one call, `"standard"` is a single flat prompt, `"stepwise"` spends one API call per reasoning step.
    - `MOZZARELLM_MCP`: Give the model PubMed search tools so genes left unannotated are filled in from retrieved literature. On by default, with `"cot"`, as mozzarellm's benchmark-selected configuration; it costs several extra API turns per cluster.
    - `MOZZARELLM_SOURCE`: Which functional annotation each gene's bundle carries. `"affinage_then_uniprot"`, the default, uses Affinage's mechanistic narratives and falls back to UniProt's FUNCTION comment for the genes Affinage has nothing on, with each gene's `annotation_source` recording which one it got; `"affinage"` and `"uniprot"` use one source alone, leaving a gene that source lacks as a visible gap; `"both"` fetches each side by side as its own column. Stable accessions always come from UniProt regardless, because they are UniProt identifiers.
    - `MOZZARELLM_INCLUDE_FEATURES`: Put each gene's phenotypic features into the bundle so the pathway call has to be consistent with the observed morphology. `"auto"` lets mozzarellm include them whenever the bundles carry them; `True` requires them and `False` strips them.
    - `MOZZARELLM_INCLUDE_STRENGTH`: Put each gene's perturbation strength rank into the bundle so the model can weigh how strongly a gene moves the phenotype. Same `"auto"` / `True` / `False` contract as the features.
    - `MOZZARELLM_N_FEATURES`: Number of up and down features kept per gene when building the cluster table. mozzarellm only shows the model features shared by at least a quarter of a cluster's genes, so this has to be large enough for neighbouring genes' lists to overlap: at 5 most clusters show no feature at all, at 20 nearly every cluster does, and the shown table is bounded either way.
    - `MOZZARELLM_FDR_THRESHOLD`: FDR cutoff a feature must pass to be listed for a gene. `None` keeps the strongest features regardless of significance.
    - `MOZZARELLM_MAX_TOKENS`: Maximum tokens per model response. 64000 is the ceiling a feature-augmented run needs; lower it only to cap spend.
    - `MOZZARELLM_RUN_NAME`: Name of the run directory each annotation writes into, under `{cluster_path}/mozzarellm/`. Keep it stable to resume an interrupted run; change it to annotate the same clusterings again beside the answers already there.
    - `MOZZARELLM_MAX_WORKERS`: Clusters one job answers concurrently, and the cores that job asks slurm for.
    - `MOZZARELLM_MAX_FAILED_CLUSTERS`: Clusters a panel may lose before its job fails. A job that fails writes nothing, so one permanently unanswerable cluster would otherwise discard the whole panel; transient failures are already covered by the rule's retries plus resume.
    - `MOZZARELLM_RUNTIME`: Wall time in minutes each annotation job asks slurm for. These jobs run for hours where the rest of the pipeline runs for minutes, so a profile's short default would kill them.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    MOZZARELLM_MODEL = "claude-sonnet-5"
    MOZZARELLM_MODE = "cot"
    MOZZARELLM_MCP = True
    MOZZARELLM_SOURCE = "affinage_then_uniprot"
    MOZZARELLM_INCLUDE_FEATURES = "auto"
    MOZZARELLM_INCLUDE_STRENGTH = "auto"
    MOZZARELLM_N_FEATURES = 20
    MOZZARELLM_FDR_THRESHOLD = None
    MOZZARELLM_MAX_TOKENS = 64000
    MOZZARELLM_RUN_NAME = "run1"
    MOZZARELLM_MAX_WORKERS = 8
    MOZZARELLM_MAX_FAILED_CLUSTERS = 2
    MOZZARELLM_RUNTIME = 720
    # === END OPERATOR PARAMETERS ===
    return (
        MOZZARELLM_FDR_THRESHOLD,
        MOZZARELLM_INCLUDE_FEATURES,
        MOZZARELLM_INCLUDE_STRENGTH,
        MOZZARELLM_MAX_FAILED_CLUSTERS,
        MOZZARELLM_MAX_TOKENS,
        MOZZARELLM_MAX_WORKERS,
        MOZZARELLM_MCP,
        MOZZARELLM_MODE,
        MOZZARELLM_MODEL,
        MOZZARELLM_N_FEATURES,
        MOZZARELLM_RUNTIME,
        MOZZARELLM_RUN_NAME,
        MOZZARELLM_SOURCE,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Mozzarellm clustering selection

    Which clusterings are annotated. One combo table row, and so one job, is written per row.

    - `MOZZARELLM_ANNOTATE_SELECTED`: Annotate the clustering selected above (`CHANNEL_COMBO` / `CELL_CLASS` / `LEIDEN_RESOLUTION`), as one row. This is the usual case: annotate the clustering you have been looking at.
    - `MOZZARELLM_EXTRA_CLUSTERINGS`: Additional rows, each a dict of any of `channel_combo`, `cell_class`, `leiden_resolution`, `compartment_combo`. A key you leave out inherits the selection above, and any value may be a list, which expands as a cross product: `{"channel_combo": "DAPI_WGA", "leiden_resolution": [6, 8]}` is two rows.
    - `MOZZARELLM_REWRITE_CONTEXTS`: Re-derive every screen context from `screen.yaml`, discarding hand edits. Off by default, because a context belongs to you once it exists.

    Resolution defaults to your `LEIDEN_RESOLUTION`. The benchmark-derived pick is never an implicit fallback; ask for it by name with `{"leiden_resolution": "optimal"}`, which reads the resolution search above. That search ranks resolutions by CORUM, KEGG and STRING enrichment, so `"optimal"` favours the resolution that best recovers complexes that are already known.

    To annotate a whole screen, hand `MOZZARELLM_EXTRA_CLUSTERINGS` the lab's panel policy over the screen's own clusterings:

    ```python
    MOZZARELLM_EXTRA_CLUSTERINGS = panel_tier_clusterings(
        screen, config, cluster_combos, SPLIT_BY_COMPARTMENT
    )
    ```

    That keeps every full panel, every grouped panel, every single marker and the DNA-only baseline, and drops the DNA-plus-one-marker combos, whose clusters a grouped panel already covers. Set `MOZZARELLM_ANNOTATE_SELECTED = False` alongside it if you do not also want the clustering picked above.
    """)
    return


@app.cell
def _(SPLIT_BY_COMPARTMENT, cluster_combos, config, panel_tier_clusterings, screen):
    # === OPERATOR PARAMETERS ===
    MOZZARELLM_ANNOTATE_SELECTED = True
    MOZZARELLM_EXTRA_CLUSTERINGS = []
    MOZZARELLM_REWRITE_CONTEXTS = False
    # === END OPERATOR PARAMETERS ===
    return (
        MOZZARELLM_ANNOTATE_SELECTED,
        MOZZARELLM_EXTRA_CLUSTERINGS,
        MOZZARELLM_REWRITE_CONTEXTS,
    )


@app.cell
def _():
    # the mozzarellm adapter only imports if the brieflow mozzarellm extra is installed
    try:
        from dotenv import load_dotenv

        from lib.mozzarellm.annotate_clusters import (
            PROVIDER_KEY_ENV,
            cluster_table_from_h5ad,
            run_mozzarellm,
        )
        from lib.mozzarellm.selection import (
            expand_mozzarellm_selection,
            panel_tier_clusterings,
            screen_context_from_screen,
            write_mozzarellm_combo_table,
            write_screen_contexts,
        )

        load_dotenv()
        mozzarellm_import_error = None
    except ImportError as _err:
        PROVIDER_KEY_ENV = {}
        cluster_table_from_h5ad = None
        expand_mozzarellm_selection = None
        panel_tier_clusterings = None
        run_mozzarellm = None
        screen_context_from_screen = None
        write_mozzarellm_combo_table = None
        write_screen_contexts = None
        mozzarellm_import_error = _err
        print(f"mozzarellm support not available: {_err}")
        print('Install it with: python -m pip install -e "../brieflow[mozzarellm]"')
    return (
        PROVIDER_KEY_ENV,
        cluster_table_from_h5ad,
        expand_mozzarellm_selection,
        mozzarellm_import_error,
        panel_tier_clusterings,
        run_mozzarellm,
        screen_context_from_screen,
        write_mozzarellm_combo_table,
        write_screen_contexts,
    )


@app.cell
def _(Path, re, yaml):
    _screen_file = Path("screen.yaml")

    if _screen_file.exists():
        with open(_screen_file, "r") as _screen_fh:
            screen = yaml.safe_load(_screen_fh)
    else:
        screen = None
        print(f"screen.yaml not found: {_screen_file.resolve()}")

    # every run's output files are prefixed with this label, so keep it file-safe
    _screen_title = ((screen or {}).get("experiment") or {}).get("screen_title")
    MOZZARELLM_SCREEN_NAME = (
        re.sub(r"[^0-9A-Za-z_.-]+", "_", str(_screen_title)).strip("_")
        if _screen_title
        else ""
    ) or "screen"
    print(f"Screen name: {MOZZARELLM_SCREEN_NAME}")
    return MOZZARELLM_SCREEN_NAME, screen


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Derived screen context

    The description of the screen handed to the model is built from `screen.yaml` and `config.yml`: organism and cell line, perturbation library, imaging readout, clustering parameters and controls. Review it below and fix `screen.yaml` if anything is wrong or missing, since this is what the model reasons from.
    """)
    return


@app.cell
def _(
    LEIDEN_RESOLUTION,
    config,
    mozzarellm_import_error,
    screen,
    screen_context_from_screen,
    yaml,
):
    if mozzarellm_import_error is not None:
        screen_context = None
        print("mozzarellm support not available - see the cell above")
    elif screen is None:
        screen_context = None
        print("screen.yaml not found - see the cell above")
    elif LEIDEN_RESOLUTION is None:
        screen_context = None
        print("Set LEIDEN_RESOLUTION to build the screen context")
    else:
        screen_context = screen_context_from_screen(screen, config, LEIDEN_RESOLUTION)
        print(yaml.dump(screen_context, default_flow_style=False, sort_keys=False))
    return (screen_context,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Cluster table preview

    The table below is exactly what mozzarellm receives: one row per gene, its cluster, its strongest up and down features, and its perturbation strength (`perturbation_auc`). No API call is made here.
    """)
    return


@app.cell
def _(
    CONTROL_KEY,
    LEIDEN_RESOLUTION,
    MOZZARELLM_FDR_THRESHOLD,
    MOZZARELLM_N_FEATURES,
    cluster_h5ad,
    cluster_table_from_h5ad,
    mo,
    mozzarellm_import_error,
    pd,
):
    if mozzarellm_import_error is not None:
        mozzarellm_cluster_table = None
        print("mozzarellm support not available - see the cell above")
    elif cluster_h5ad is None:
        mozzarellm_cluster_table = None
        print("Set the cluster selection above to preview the cluster table")
    elif not cluster_h5ad.exists():
        mozzarellm_cluster_table = None
        print(f"Cluster h5ad not found: {cluster_h5ad}")
        print("Run the cluster module first")
    else:
        mozzarellm_cluster_table = cluster_table_from_h5ad(
            cluster_h5ad,
            LEIDEN_RESOLUTION,
            n_features=MOZZARELLM_N_FEATURES,
            fdr_threshold=MOZZARELLM_FDR_THRESHOLD,
        )
        print(
            f"Cluster table: {len(mozzarellm_cluster_table)} genes, "
            f"{mozzarellm_cluster_table['cluster'].nunique()} clusters"
        )

    mo.ui.table(
        mozzarellm_cluster_table.head(20)
        if mozzarellm_cluster_table is not None
        else pd.DataFrame()
    )
    return (mozzarellm_cluster_table,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Selected clusterings

    The clusterings the selection expands to, one row per job. A row naming a clustering the cluster phase never produced is an error rather than a silent drop.
    """)
    return


@app.cell
def _(
    CELL_CLASS,
    CHANNEL_COMBO,
    COMPARTMENT_COMBO,
    LEIDEN_RESOLUTION,
    MOZZARELLM_ANNOTATE_SELECTED,
    MOZZARELLM_EXTRA_CLUSTERINGS,
    SPLIT_BY_COMPARTMENT,
    cluster_combos,
    expand_mozzarellm_selection,
    mo,
    mozzarellm_import_error,
    optimal_resolutions,
    pd,
):
    # a row that names its own combo, class and resolution needs nothing from the
    # selection above, so a whole-screen sweep does not require picking one clustering
    _mozzarellm_needs_current_selection = MOZZARELLM_ANNOTATE_SELECTED or any(
        _key not in _entry
        for _entry in MOZZARELLM_EXTRA_CLUSTERINGS
        for _key in ("cell_class", "channel_combo", "leiden_resolution")
    )
    if mozzarellm_import_error is not None:
        mozzarellm_selection = pd.DataFrame()
        print("mozzarellm support not available - see the cell above")
    elif _mozzarellm_needs_current_selection and None in (
        CHANNEL_COMBO,
        CELL_CLASS,
        LEIDEN_RESOLUTION,
    ):
        mozzarellm_selection = pd.DataFrame()
        print("Set the cluster selection above to choose what is annotated")
    else:
        mozzarellm_selection = expand_mozzarellm_selection(
            cluster_combos,
            {
                "cell_class": CELL_CLASS,
                "channel_combo": CHANNEL_COMBO,
                "compartment_combo": COMPARTMENT_COMBO,
                "leiden_resolution": LEIDEN_RESOLUTION,
            },
            annotate_selected=MOZZARELLM_ANNOTATE_SELECTED,
            extra_clusterings=MOZZARELLM_EXTRA_CLUSTERINGS,
            optimal_resolutions=optimal_resolutions,
            split_by_compartment=SPLIT_BY_COMPARTMENT,
        )
        print(f"Annotating {len(mozzarellm_selection)} clusterings")

    mo.ui.table(mozzarellm_selection)
    return (mozzarellm_selection,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Screen contexts and combo table

    Each selected clustering gets its own screen context, describing the channels that clustering was built from rather than the screen's whole panel, and the combo table points each row at its context file. The rule reads these files, so they are written here before the stage runs.

    A context is derived once and then belongs to you: an existing file is left exactly as it is, and the output below says which contexts were derived fresh and which are your own. Edit the JSON for a one-off; put anything that should follow a channel into that channel's `description` in `screen.yaml`. `MOZZARELLM_REWRITE_CONTEXTS = True` discards your edits and re-derives everything.
    """)
    return


@app.cell
def _(
    MOZZARELLM_REWRITE_CONTEXTS,
    Path,
    config,
    mozzarellm_import_error,
    mozzarellm_selection,
    screen,
    write_screen_contexts,
):
    MOZZARELLM_CONTEXT_DIR = Path("config/mozzarellm_context")

    mozzarellm_context_paths = []
    if mozzarellm_import_error is not None:
        print("mozzarellm support not available - see the cell above")
    elif screen is None:
        print("screen.yaml not found - see the cell above")
    elif mozzarellm_selection.empty:
        print("No clusterings selected - no screen contexts written")
    else:
        mozzarellm_context_paths, _derived, _kept = write_screen_contexts(
            mozzarellm_selection,
            screen,
            config,
            MOZZARELLM_CONTEXT_DIR,
            rewrite=MOZZARELLM_REWRITE_CONTEXTS,
        )
        if MOZZARELLM_REWRITE_CONTEXTS:
            print("MOZZARELLM_REWRITE_CONTEXTS is on - any hand edits were discarded")
        print(f"Screen contexts in {MOZZARELLM_CONTEXT_DIR}: {len(mozzarellm_context_paths)}")
        for _path in _derived:
            print(f"  derived from screen.yaml: {_path}")
        for _path in _kept:
            print(f"  left as yours, not rewritten: {_path}")
    return MOZZARELLM_CONTEXT_DIR, mozzarellm_context_paths


@app.cell
def _(
    mo,
    mozzarellm_context_paths,
    mozzarellm_selection,
    pd,
    write_mozzarellm_combo_table,
):
    MOZZARELLM_COMBO_FP = "config/mozzarellm_combo.tsv"

    if not mozzarellm_context_paths:
        mozzarellm_combos = pd.DataFrame()
        print(f"No clusterings selected - {MOZZARELLM_COMBO_FP} not written")
    else:
        mozzarellm_combos = write_mozzarellm_combo_table(
            mozzarellm_selection, mozzarellm_context_paths, MOZZARELLM_COMBO_FP
        )
        print(f"Wrote {len(mozzarellm_combos)} rows to {MOZZARELLM_COMBO_FP}")

    mo.ui.table(mozzarellm_combos)
    return MOZZARELLM_COMBO_FP, mozzarellm_combos


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Dry run: what the selection costs

    Assembles every prompt for every selected clustering and prices the input side, without calling the model. mozzarellm still builds its client to price the prompts, so the provider's API key has to be in `.env` even though no request is made.
    """)
    return


@app.cell
def _(
    MOZZARELLM_FDR_THRESHOLD,
    MOZZARELLM_INCLUDE_FEATURES,
    MOZZARELLM_INCLUDE_STRENGTH,
    MOZZARELLM_MAX_TOKENS,
    MOZZARELLM_MCP,
    MOZZARELLM_MODE,
    MOZZARELLM_MODEL,
    MOZZARELLM_N_FEATURES,
    MOZZARELLM_RUN_NAME,
    MOZZARELLM_SCREEN_NAME,
    MOZZARELLM_SOURCE,
    PROVIDER_KEY_ENV,
    Path,
    ROOT_FP,
    SPLIT_BY_COMPARTMENT,
    add_compartment_path,
    get_filename,
    json,
    mo,
    mozzarellm_combos,
    mozzarellm_import_error,
    os,
    pd,
    run_mozzarellm,
):
    _key_var = next(
        (
            env_var
            for prefix, env_var in PROVIDER_KEY_ENV.items()
            if str(MOZZARELLM_MODEL).lower().startswith(prefix)
        ),
        "ANTHROPIC_API_KEY",
    )

    _estimates = []
    if mozzarellm_import_error is not None:
        print("mozzarellm support not available - see the cell above")
    elif mozzarellm_combos.empty:
        print("No clusterings selected - nothing to price")
    elif not os.environ.get(_key_var):
        print(f"{_key_var} is not set, and the dry run still builds a {MOZZARELLM_MODEL} client")
        print("Add the key to a .env file in this directory to price the run")
    else:
        for _combo_row in mozzarellm_combos.to_dict("records"):
            _cluster_base = add_compartment_path(
                ROOT_FP / "cluster" / _combo_row["channel_combo"],
                _combo_row.get("compartment_combo"),
                SPLIT_BY_COMPARTMENT,
            )
            _h5ad = (
                _cluster_base
                / _combo_row["cell_class"]
                / "h5ad"
                / get_filename({}, "cluster", "h5ad")
            )
            if not _h5ad.exists():
                print(f"Cluster h5ad not found, skipping: {_h5ad}")
                continue

            _context = json.loads(
                Path(_combo_row["screen_context_fp"]).read_text(encoding="utf-8")
            )
            try:
                _result = run_mozzarellm(
                    _h5ad,
                    _cluster_base
                    / _combo_row["cell_class"]
                    / str(_combo_row["leiden_resolution"]),
                    _combo_row["leiden_resolution"],
                    MOZZARELLM_MODEL,
                    _context,
                    mode=MOZZARELLM_MODE,
                    mcp=MOZZARELLM_MCP,
                    annotation_source=MOZZARELLM_SOURCE,
                    include_features=MOZZARELLM_INCLUDE_FEATURES,
                    include_strength=MOZZARELLM_INCLUDE_STRENGTH,
                    n_features=MOZZARELLM_N_FEATURES,
                    fdr_threshold=MOZZARELLM_FDR_THRESHOLD,
                    max_tokens=MOZZARELLM_MAX_TOKENS,
                    screen_name=MOZZARELLM_SCREEN_NAME,
                    run_name=MOZZARELLM_RUN_NAME,
                    dry_run=True,
                )
            except Exception as _err:
                print(
                    f"Dry run failed for {_combo_row['channel_combo']} / "
                    f"{_combo_row['cell_class']}: {_err}"
                )
                continue

            _clusters = _result["estimates"]
            _estimates.append(
                {
                    "channel_combo": _combo_row["channel_combo"],
                    "cell_class": _combo_row["cell_class"],
                    "leiden_resolution": _combo_row["leiden_resolution"],
                    "clusters": len(_clusters),
                    "genes": int(_clusters["n_genes"].sum()),
                    "est_input_cost_usd": float(_clusters["est_input_cost_usd"].sum()),
                }
            )

    mozzarellm_estimates = pd.DataFrame(_estimates)
    if not mozzarellm_estimates.empty:
        print(
            f"{mozzarellm_estimates['clusters'].sum()} clusters over "
            f"{len(mozzarellm_estimates)} clusterings, estimated input cost "
            f"${mozzarellm_estimates['est_input_cost_usd'].sum():.2f}"
        )

    mo.ui.table(mozzarellm_estimates)
    return (mozzarellm_estimates,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Add mozzarellm parameters to config file
    """)
    return


@app.cell
def _(
    CELL_CLASS,
    CHANNEL_COMBO,
    COMPARTMENT_COMBO,
    CONFIG_FILE_HEADER,
    CONFIG_FILE_PATH,
    LEIDEN_RESOLUTION,
    MOZZARELLM_COMBO_FP,
    MOZZARELLM_FDR_THRESHOLD,
    MOZZARELLM_INCLUDE_FEATURES,
    MOZZARELLM_INCLUDE_STRENGTH,
    MOZZARELLM_MAX_FAILED_CLUSTERS,
    MOZZARELLM_MAX_TOKENS,
    MOZZARELLM_MAX_WORKERS,
    MOZZARELLM_MCP,
    MOZZARELLM_MODE,
    MOZZARELLM_MODEL,
    MOZZARELLM_N_FEATURES,
    MOZZARELLM_RUNTIME,
    MOZZARELLM_RUN_NAME,
    MOZZARELLM_SCREEN_NAME,
    MOZZARELLM_SOURCE,
    SPLIT_BY_COMPARTMENT,
    config,
    convert_tuples_to_lists,
    yaml,
):
    # the first three keys are the clustering the visualizer opens on; the stage reads combo_fp
    config["mozzarellm"] = {
        "cell_class": CELL_CLASS,
        "channel_combo": CHANNEL_COMBO,
        "leiden_resolution": LEIDEN_RESOLUTION,
        "combo_fp": MOZZARELLM_COMBO_FP,
        "run_name": MOZZARELLM_RUN_NAME,
        "screen_name": MOZZARELLM_SCREEN_NAME,
        "model": MOZZARELLM_MODEL,
        "mode": MOZZARELLM_MODE,
        "mcp": MOZZARELLM_MCP,
        "source": MOZZARELLM_SOURCE,
        "include_features": MOZZARELLM_INCLUDE_FEATURES,
        "include_strength": MOZZARELLM_INCLUDE_STRENGTH,
        "n_features": MOZZARELLM_N_FEATURES,
        "fdr_threshold": MOZZARELLM_FDR_THRESHOLD,
        "max_tokens": MOZZARELLM_MAX_TOKENS,
        "max_workers": MOZZARELLM_MAX_WORKERS,
        "max_failed_clusters": MOZZARELLM_MAX_FAILED_CLUSTERS,
        "runtime": MOZZARELLM_RUNTIME,
    }
    if SPLIT_BY_COMPARTMENT:
        config["mozzarellm"]["compartment_combo"] = COMPARTMENT_COMBO
    safe_config = convert_tuples_to_lists(config)
    with open(CONFIG_FILE_PATH, "w") as _config_file:
        _config_file.write(CONFIG_FILE_HEADER)
        yaml.dump(safe_config, _config_file, default_flow_style=False, sort_keys=False)

    print("Saved mozzarellm settings to config.")
    return (safe_config,)


if __name__ == "__main__":
    app.run()
