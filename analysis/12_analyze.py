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
        load_parquet_subset,
        merge_bootstrap_with_genes,
        pd,
        plot_phate_leiden_clusters,
        plot_resolution_comparison,
        plt,
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
    return CELL_CLASSES, CHANNEL_COMBOS


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

    1. Configure the parameters below and write them to `config.yml` with the last cell of this notebook.
    2. Run `bash flow.sh mozzarellm`, which reads the `mozzarellm` config section and writes each run to `{cluster_path}/mozzarellm/run_<timestamp>/`.

    The clustering analyzed is the one selected above: `CHANNEL_COMBO` / `CELL_CLASS` / `LEIDEN_RESOLUTION` (and `COMPARTMENT_COMBO` when splitting). The screen description handed to the model is derived from `screen.yaml` rather than written by hand, so keep that file up to date.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Mozzarellm configuration

    - `MOZZARELLM_MODEL`: LLM model identifier passed to mozzarellm, ex `"claude-sonnet-5"`, `"gpt-5"` or `"gemini-2.5-pro"`. The API key for the corresponding provider must be present in `.env`.
    - `MOZZARELLM_MODE`: Prompting mode. `"cot"` reasons through the cluster in one call, `"standard"` is a single flat prompt, `"stepwise"` spends one API call per reasoning step.
    - `MOZZARELLM_MCP`: Give the model PubMed search tools so novel-role and uncharacterized calls are checked against retrieved literature. Substantially more expensive and slower (several extra API turns per cluster), and not combinable with phenotypic features.
    - `MOZZARELLM_INCLUDE_FEATURES`: Put each gene's phenotypic features into the bundle so the pathway call has to be consistent with the observed morphology. Supported for `"cot"` mode without MCP.
    - `MOZZARELLM_N_FEATURES`: Number of up and down features kept per gene when building the cluster table.
    - `MOZZARELLM_FDR_THRESHOLD`: FDR cutoff a feature must pass to be listed for a gene. `None` keeps the strongest features regardless of significance.
    - `MOZZARELLM_MAX_TOKENS`: Maximum tokens per model response. Raise it if long reasoning traces are being truncated.
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    MOZZARELLM_MODEL = "claude-sonnet-5"
    MOZZARELLM_MODE = "cot"
    MOZZARELLM_MCP = False
    MOZZARELLM_INCLUDE_FEATURES = True
    MOZZARELLM_N_FEATURES = 5
    MOZZARELLM_FDR_THRESHOLD = None
    MOZZARELLM_MAX_TOKENS = 16000
    # === END OPERATOR PARAMETERS ===
    return (
        MOZZARELLM_FDR_THRESHOLD,
        MOZZARELLM_INCLUDE_FEATURES,
        MOZZARELLM_MAX_TOKENS,
        MOZZARELLM_MCP,
        MOZZARELLM_MODE,
        MOZZARELLM_MODEL,
        MOZZARELLM_N_FEATURES,
    )


@app.cell
def _():
    # the mozzarellm adapter only imports if the brieflow mozzarellm extra is installed
    try:
        from lib.cluster.mozzarellm_io import (
            cluster_table_from_h5ad,
            screen_context_from_screen,
        )

        mozzarellm_import_error = None
    except ImportError as _err:
        cluster_table_from_h5ad = None
        screen_context_from_screen = None
        mozzarellm_import_error = _err
        print(f"mozzarellm support not available: {_err}")
        print('Install it with: python -m pip install -e "../brieflow[mozzarellm]"')
    return (
        cluster_table_from_h5ad,
        mozzarellm_import_error,
        screen_context_from_screen,
    )


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
    Path,
    config,
    mozzarellm_import_error,
    screen_context_from_screen,
    yaml,
):
    _screen_file = Path("screen.yaml")

    if mozzarellm_import_error is not None:
        screen_context = None
        print("mozzarellm support not available - see the cell above")
    elif not _screen_file.exists():
        screen_context = None
        print(f"screen.yaml not found: {_screen_file.resolve()}")
    elif LEIDEN_RESOLUTION is None:
        screen_context = None
        print("Set LEIDEN_RESOLUTION to build the screen context")
    else:
        with open(_screen_file, "r") as _screen_fh:
            screen = yaml.safe_load(_screen_fh)
        screen_context = screen_context_from_screen(screen, config, LEIDEN_RESOLUTION)
        print(yaml.dump(screen_context, default_flow_style=False, sort_keys=False))
    return (screen_context,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Cluster table preview

    The table below is exactly what mozzarellm receives: one row per gene, its cluster, its strongest up and down features, and its phenotypic strength. No API call is made here.
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
            control_key=CONTROL_KEY,
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
    MOZZARELLM_FDR_THRESHOLD,
    MOZZARELLM_INCLUDE_FEATURES,
    MOZZARELLM_MAX_TOKENS,
    MOZZARELLM_MCP,
    MOZZARELLM_MODE,
    MOZZARELLM_MODEL,
    MOZZARELLM_N_FEATURES,
    SPLIT_BY_COMPARTMENT,
    config,
    convert_tuples_to_lists,
    yaml,
):
    # Add mozzarellm section
    config["mozzarellm"] = {
        "cell_class": CELL_CLASS,
        "channel_combo": CHANNEL_COMBO,
        "leiden_resolution": LEIDEN_RESOLUTION,
        "model": MOZZARELLM_MODEL,
        "mode": MOZZARELLM_MODE,
        "mcp": MOZZARELLM_MCP,
        "include_features": MOZZARELLM_INCLUDE_FEATURES,
        "n_features": MOZZARELLM_N_FEATURES,
        "fdr_threshold": MOZZARELLM_FDR_THRESHOLD,
        "max_tokens": MOZZARELLM_MAX_TOKENS,
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
