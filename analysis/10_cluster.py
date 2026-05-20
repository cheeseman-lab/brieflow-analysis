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
    # Configure Cluster Module Params

    This notebook should be used as a test for ensuring correct cluster parameters before cluster processing.
    Cells marked with <font color='red'>SET PARAMETERS</font> contain crucial variables that need to be set according to your specific experimental setup and data organization.
    Please review and modify these variables as needed before proceeding with the analysis.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Fixed parameters for cluster module

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

    warnings.filterwarnings("ignore", category=UserWarning)  # filter Phate warnings

    import yaml
    import pandas as pd
    import numpy as np
    from matplotlib import pyplot as plt

    from lib.shared.file_utils import get_filename
    from lib.cluster.cluster_eval import plot_cell_histogram, plot_cluster_sizes
    from lib.cluster.phate_leiden_clustering import (
        phate_leiden_pipeline,
        plot_phate_leiden_clusters,
    )
    from lib.cluster.benchmark_clusters import (
        evaluate_resolution,
        run_benchmark_analysis,
    )
    from lib.cluster.scrape_benchmarks import (
        get_uniprot_data,
        generate_string_pair_benchmark,
        generate_corum_group_benchmark,
        generate_msigdb_group_benchmark,
        filter_complexes,
    )
    from lib.shared.configuration_utils import CONFIG_FILE_HEADER, convert_tuples_to_lists

    return (
        CONFIG_FILE_HEADER,
        Path,
        convert_tuples_to_lists,
        evaluate_resolution,
        filter_complexes,
        generate_corum_group_benchmark,
        generate_msigdb_group_benchmark,
        generate_string_pair_benchmark,
        get_filename,
        get_uniprot_data,
        np,
        pd,
        phate_leiden_pipeline,
        plot_cell_histogram,
        plot_cluster_sizes,
        plot_phate_leiden_clusters,
        plt,
        run_benchmark_analysis,
        yaml,
    )


@app.cell
def _(CONFIG_FILE_PATH, Path, pd, yaml):
    # load config file and determine root path
    with open(CONFIG_FILE_PATH, 'r') as _config_file:
        config = yaml.safe_load(_config_file)
        ROOT_FP = Path(config['all']['root_fp'])
    aggregate_combo_fp = config['aggregate']['aggregate_combo_fp']
    # load cell classes and channel combos
    aggregate_combos = pd.read_csv(aggregate_combo_fp, sep='\t')
    CHANNEL_COMBOS = aggregate_combos['channel_combo'].unique().tolist()
    print(f'Channel Combos: {CHANNEL_COMBOS}')
    CELL_CLASSES = list(aggregate_combos['cell_class'].unique())
    print(f'Cell classes: {CELL_CLASSES}')
    return CHANNEL_COMBOS, ROOT_FP, config


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Cluster preprocessing

    - `MIN_CELL_CUTOFFS`: Dictionary with minimum cells for each gene to be used in clusetering analysis. More cells per gene increases confidence, but some dataset types (ex mitotic) may have an inherently low number of cells for a particular perturbation. Ex `{"mitotic": 0, "interphase": 3, "all": 3}`.
    """)
    return


@app.cell
def _(config):
    # === OPERATOR PARAMETERS ===
    MIN_CELL_CUTOFFS = None            # e.g., {"all": 5, "Interphase": 5, "Mitotic": 5}
    # === END OPERATOR PARAMETERS ===

    PERTURBATION_NAME_COL = config["aggregate"]["perturbation_name_col"]
    return MIN_CELL_CUTOFFS, PERTURBATION_NAME_COL


@app.cell
def _(
    CHANNEL_COMBOS,
    MIN_CELL_CUTOFFS,
    PERTURBATION_NAME_COL,
    ROOT_FP,
    get_filename,
    pd,
    plot_cell_histogram,
    plt,
):
    # QC: cell-count histogram per cell class. Uses a cell-local `_data` so the
    # cross-cell-class loop result doesn't accidentally leak as the canonical
    # aggregated_data; the canonical load (for TEST_CELL_CLASS / TEST_CHANNEL_COMBO)
    # happens in a dedicated cell below.
    for cell_class, min_cell_cutoff in MIN_CELL_CUTOFFS.items():
        channel_combo = CHANNEL_COMBOS[0]
        _aggregated_data_path = ROOT_FP / 'aggregate' / 'tsvs' / get_filename({'cell_class': cell_class, 'channel_combo': channel_combo}, 'aggregated', 'tsv')
        _data = pd.read_csv(_aggregated_data_path, sep='\t')
        print(f'Cell count distribution for: {cell_class}')
        plot_cell_histogram(_data, min_cell_cutoff, PERTURBATION_NAME_COL)
        plt.show()  # show cell count distribution
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Benchmark Generation

    - `STRING_PAIR_BENCHMARK_FP`: Path to save and access STRING pair benchmark.
    - `CORUM_GROUP_BENCHMARK_FP`: Path to save and access CORUM group benchmark.
    - `KEGG_GROUP_BENCHMARK_FP`: Path to save and access KEGG group benchmark.

    **Note**: We use the following benchmark schemas:
    - Pair Bechmark: `gene_name` column for gene matching with a cluster gene (or does not exist in cluster genes); `pair` column with a pair ID. Used to benchmark known pair relationships in generated cluster.
    - Group Bechmark: `gene_name` column for gene matching with a cluster gene (or does not exist in cluster genes); `group` column with a group ID. Used to benchmark known group relationships in generated cluster, where a group represents genes involved in a pathway, protein complex, etc.
    """)
    return


@app.cell
def _():
    UNIPROT_DATA_FP = "config/benchmark_clusters/uniprot_data.tsv"
    STRING_PAIR_BENCHMARK_FP = "config/benchmark_clusters/string_pair_benchmark.tsv"
    CORUM_GROUP_BENCHMARK_FP = "config/benchmark_clusters/corum_group_benchmark.tsv"
    KEGG_GROUP_BENCHMARK_FP = "config/benchmark_clusters/kegg_group_benchmark.tsv"
    return (
        CORUM_GROUP_BENCHMARK_FP,
        KEGG_GROUP_BENCHMARK_FP,
        STRING_PAIR_BENCHMARK_FP,
        UNIPROT_DATA_FP,
    )


@app.cell
def _(
    CORUM_GROUP_BENCHMARK_FP,
    KEGG_GROUP_BENCHMARK_FP,
    Path,
    STRING_PAIR_BENCHMARK_FP,
    UNIPROT_DATA_FP,
    aggregated_data,
    mo,
    generate_corum_group_benchmark,
    generate_msigdb_group_benchmark,
    generate_string_pair_benchmark,
    get_uniprot_data,
    pd,
):
    Path(STRING_PAIR_BENCHMARK_FP).parent.mkdir(parents=True, exist_ok=True)

    uniprot_data = get_uniprot_data()
    uniprot_data.to_csv(UNIPROT_DATA_FP, sep="\t", index=False)
    uniprot_data = pd.read_csv(UNIPROT_DATA_FP, sep="\t")
    mo.ui.table(uniprot_data)

    string_pair_benchmark = generate_string_pair_benchmark(
        aggregated_data, uniprot_data, "gene_symbol_0"
    )
    string_pair_benchmark.to_csv(STRING_PAIR_BENCHMARK_FP, sep="\t", index=False)
    string_pair_benchmark = pd.read_csv(STRING_PAIR_BENCHMARK_FP, sep="\t")
    mo.ui.table(string_pair_benchmark)

    corum_group_benchmark = generate_corum_group_benchmark()
    corum_group_benchmark.to_csv(CORUM_GROUP_BENCHMARK_FP, sep="\t", index=False)
    corum_group_benchmark = pd.read_csv(CORUM_GROUP_BENCHMARK_FP, sep="\t")
    mo.ui.table(corum_group_benchmark)

    kegg_group_benchmark = generate_msigdb_group_benchmark()
    kegg_group_benchmark.to_csv(KEGG_GROUP_BENCHMARK_FP, sep="\t", index=False)
    kegg_group_benchmark = pd.read_csv(KEGG_GROUP_BENCHMARK_FP, sep="\t")
    mo.ui.table(kegg_group_benchmark)
    return (
        corum_group_benchmark,
        kegg_group_benchmark,
        string_pair_benchmark,
        uniprot_data,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Test Dataset

    - `TEST_CELL_CLASS`: Cell class to test clustering on. Must be one of the values in `CELL_CLASSES` printed above (e.g., `"Uninfected"`, `"all"`).
    - `TEST_CHANNEL_COMBO`: Channel combo string to test clustering on. Must be one of the values in `CHANNEL_COMBOS` printed above (e.g., `"DAPI_NHS_ester_STAT6_Mitotracker_ConA_CDPK1_WGA_cMYC_Tubulin"`). This is an underscore-separated string, **not** a list.

    ### Phate/Leiden Clustering

    - `PHATE_DISTANCE_METRIC`: Distance metric used by phate during dimensionality reduction. Can be `euclidean` or `cosine`, `cosine` is recommended. Check out this [blog post](https://cmry.github.io/notes/euclidean-v-cosine) for more insight on how to choose a clustering metric.
    - `PERTURBATION_AUC_THRESHOLD`: AUC value used to filter out perturbations. Higher AUC value means more selective, usually `0.6`. Can be left as `None` for no filtering.
    - `TEST_LEIDEN_RESOLUTIONS`: Resolutions for Leiden clustering. Higher means more clusters (and therefore less genes per cluster). Should be a list of numbers. We recommend `[0.1, 1, 5, 7, 9, 11, 13, 15, 20, 100]`.

    **Notes**:
    - Every resolution takes about 1 minute to generate a cluster for.
    - `evaluate_resolution` automatically filters benchmarks to only include genes that we have in the perturbations column.
    """)
    return


@app.cell
def _(config):
    # === OPERATOR PARAMETERS ===
    TEST_CELL_CLASS = None
    TEST_CHANNEL_COMBO = None
    PHATE_DISTANCE_METRIC = None       # "cosine" | "euclidean"
    PERTURBATION_AUC_THRESHOLD = None
    TEST_LEIDEN_RESOLUTIONS = None     # e.g., [2, 3, 4, 5]
    # === END OPERATOR PARAMETERS ===

    CONTROL_KEY = config["aggregate"]["control_key"]
    return (
        CONTROL_KEY,
        PERTURBATION_AUC_THRESHOLD,
        PHATE_DISTANCE_METRIC,
        TEST_CELL_CLASS,
        TEST_CHANNEL_COMBO,
        TEST_LEIDEN_RESOLUTIONS,
    )


@app.cell
def _(ROOT_FP, TEST_CELL_CLASS, TEST_CHANNEL_COMBO, get_filename, mo, pd):
    # Canonical load: aggregated data for the test class/combo pair. Used by
    # every downstream cell that needs the aggregated table.
    _aggregated_data_path = ROOT_FP / 'aggregate' / 'tsvs' / get_filename({'cell_class': TEST_CELL_CLASS, 'channel_combo': TEST_CHANNEL_COMBO}, 'aggregated', 'tsv')
    aggregated_data = pd.read_csv(_aggregated_data_path, sep='\t')
    mo.ui.table(aggregated_data)
    return (aggregated_data,)


@app.cell
def _(
    CONTROL_KEY,
    PERTURBATION_NAME_COL,
    PHATE_DISTANCE_METRIC,
    TEST_LEIDEN_RESOLUTIONS,
    aggregated_data,
    corum_group_benchmark,
    evaluate_resolution,
    np,
    plt,
):
    shuffled_aggregated_data = aggregated_data.copy()
    feature_start_idx = shuffled_aggregated_data.columns.get_loc('PC_0')
    feature_cols = shuffled_aggregated_data.columns[feature_start_idx:]
    for col in feature_cols:
        shuffled_aggregated_data[col] = np.random.permutation(shuffled_aggregated_data[col].values)
    group_benchmarks = {'CORUM': corum_group_benchmark}
    results_df, thresholding_fig = evaluate_resolution(aggregated_data, PHATE_DISTANCE_METRIC, TEST_LEIDEN_RESOLUTIONS, group_benchmarks, PERTURBATION_NAME_COL, CONTROL_KEY)
    plt.figure(thresholding_fig.number)
    plt.show()
    return (shuffled_aggregated_data,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Phate/Leiden Clustering

    - `CLUSTER_COMBO_FP`: Location of cluster combinations dataframe.
    - `FINAL_LEIDEN_RESOLUTIONS`: Final list of resolutions for Leiden clustering. The snakmake cluster module will create and benchmark clusters for each of these resolutions. For the rest of the cluster testing in this notebook, we will show one example of this cluster generation and benchmarking (see below).
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    CLUSTER_COMBO_FP = "config/cluster_combo.tsv"
    FINAL_LEIDEN_RESOLUTIONS = None    # e.g., [2, 3, 4, 5, 6, 7, 8, 9, 10]
    # === END OPERATOR PARAMETERS ===
    return CLUSTER_COMBO_FP, FINAL_LEIDEN_RESOLUTIONS


@app.cell
def _(CLUSTER_COMBO_FP, FINAL_LEIDEN_RESOLUTIONS, Path, config, pd):
    # Load aggregate wildcard combos
    AGGREGATE_COMBO_FP = Path(config["aggregate"]["aggregate_combo_fp"])
    aggregate_wildcard_combos = pd.read_csv(AGGREGATE_COMBO_FP, sep="\t")

    # Generate cluster wildcard combos
    cluster_wildcard_combos = aggregate_wildcard_combos[
        ["cell_class", "channel_combo"]
    ].drop_duplicates()
    cluster_wildcard_combos["leiden_resolution"] = [FINAL_LEIDEN_RESOLUTIONS] * len(
        cluster_wildcard_combos
    )
    cluster_wildcard_combos = cluster_wildcard_combos.explode(
        "leiden_resolution", ignore_index=True
    )

    # Save aggregate wildcard combos
    cluster_wildcard_combos.to_csv(CLUSTER_COMBO_FP, sep="\t", index=False)

    print("Cluster wildcard combos:")
    cluster_wildcard_combos
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## <font color='red'>SET PARAMETERS</font>

    ### Cluster Generation/Benchmarking Test

    - `TEST_LEIDEN_RESOLUTION`: Resolution for testing Leiden cluster creation and evaluation within this notebook. Each leiden resolution listed in `LEIDEN_RESOLUTIONS` above will be used during snakemake run to generate separate clusterings (see above).
    """)
    return


@app.cell
def _():
    # === OPERATOR PARAMETERS ===
    TEST_LEIDEN_RESOLUTION = None
    # === END OPERATOR PARAMETERS ===
    return (TEST_LEIDEN_RESOLUTION,)


@app.cell
def _(
    CONTROL_KEY,
    PERTURBATION_NAME_COL,
    PHATE_DISTANCE_METRIC,
    TEST_LEIDEN_RESOLUTION,
    aggregated_data,
    mo,
    phate_leiden_pipeline,
    plot_cluster_sizes,
    plot_phate_leiden_clusters,
    plt,
    uniprot_data,
):
    phate_leiden_clustering = phate_leiden_pipeline(aggregated_data, TEST_LEIDEN_RESOLUTION, PHATE_DISTANCE_METRIC)
    uniprot_data['gene_name'] = uniprot_data['gene_names'].str.split().str[0]
    uniprot_data_1 = uniprot_data.drop_duplicates('gene_name', keep='first')
    uniprot_subset = uniprot_data_1[['gene_name', 'entry', 'function', 'link']].rename(columns={'entry': 'uniprot_entry', 'function': 'uniprot_function', 'link': 'uniprot_link'})
    phate_leiden_clustering = phate_leiden_clustering.merge(uniprot_subset, how='left', left_on='gene_symbol_0', right_on='gene_name').drop(columns='gene_name')
    mo.ui.table(phate_leiden_clustering)
    cluster_size_fig = plot_cluster_sizes(phate_leiden_clustering)
    plt.show()
    clusters_fig = plot_phate_leiden_clusters(phate_leiden_clustering, PERTURBATION_NAME_COL, CONTROL_KEY)
    plt.show()
    return (phate_leiden_clustering,)


@app.cell
def _(
    CONTROL_KEY,
    PERTURBATION_NAME_COL,
    PHATE_DISTANCE_METRIC,
    TEST_LEIDEN_RESOLUTION,
    corum_group_benchmark,
    filter_complexes,
    kegg_group_benchmark,
    phate_leiden_clustering,
    phate_leiden_pipeline,
    run_benchmark_analysis,
    shuffled_aggregated_data,
    string_pair_benchmark,
):
    phate_leiden_clustering_shuffled = phate_leiden_pipeline(
        shuffled_aggregated_data,
        TEST_LEIDEN_RESOLUTION,
        PHATE_DISTANCE_METRIC,
    )

    cluster_datasets = {
        "Real": phate_leiden_clustering,
        "Shuffled": phate_leiden_clustering_shuffled,
    }

    pair_recall_benchmarks = {
        "STRING": string_pair_benchmark,
    }

    group_enrichment_benchmarks = {
        "CORUM": filter_complexes(
            corum_group_benchmark,
            phate_leiden_clustering,
            perturbation_col_name=PERTURBATION_NAME_COL,
            control_key=CONTROL_KEY,
        ),
        "KEGG": filter_complexes(
            kegg_group_benchmark,
            phate_leiden_clustering,
            perturbation_col_name=PERTURBATION_NAME_COL,
            control_key=CONTROL_KEY,
        ),
    }

    (
        integrated_results,
        combined_tables,
        global_metrics,
        pie_charts,
        cluster_enrichment_plots,
    ) = run_benchmark_analysis(
        cluster_datasets,
        string_pair_benchmark,
        corum_group_benchmark,
        kegg_group_benchmark,
        PERTURBATION_NAME_COL,
        CONTROL_KEY,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Add cluster parameters to config file
    """)
    return


@app.cell
def _(
    CLUSTER_COMBO_FP,
    CONFIG_FILE_HEADER,
    CONFIG_FILE_PATH,
    CORUM_GROUP_BENCHMARK_FP,
    FINAL_LEIDEN_RESOLUTIONS,
    KEGG_GROUP_BENCHMARK_FP,
    MIN_CELL_CUTOFFS,
    PERTURBATION_AUC_THRESHOLD,
    PHATE_DISTANCE_METRIC,
    STRING_PAIR_BENCHMARK_FP,
    UNIPROT_DATA_FP,
    config,
    convert_tuples_to_lists,
    yaml,
):
    # Add cluster section
    config['cluster'] = {'min_cell_cutoffs': MIN_CELL_CUTOFFS, 'leiden_resolutions': FINAL_LEIDEN_RESOLUTIONS, 'phate_distance_metric': PHATE_DISTANCE_METRIC, 'cluster_combo_fp': CLUSTER_COMBO_FP, 'uniprot_data_fp': UNIPROT_DATA_FP, 'string_pair_benchmark_fp': STRING_PAIR_BENCHMARK_FP, 'corum_group_benchmark_fp': CORUM_GROUP_BENCHMARK_FP, 'kegg_group_benchmark_fp': KEGG_GROUP_BENCHMARK_FP, 'perturbation_auc_threshold': PERTURBATION_AUC_THRESHOLD}
    safe_config = convert_tuples_to_lists(config)
    with open(CONFIG_FILE_PATH, 'w') as _config_file:
        _config_file.write(CONFIG_FILE_HEADER)
    # Convert tuples to lists before dumping
    # Write the updated configuration
        yaml.dump(safe_config, _config_file, default_flow_style=False, sort_keys=False)  # Write the introductory comments  # Dump the updated YAML structure, keeping markdown comments for sections
    return


@app.cell
def _():
    # === TUNED EXPORT ===
    # No notebook-derived tuned values for cluster (resolutions + cell_cutoffs
    # are operator-set upfront, not notebook-derived). Empty export for symmetry.
    import json as _je
    from pathlib import Path as _Pe
    _t = {}
    _out = _Pe(".brieflow") / "tuned_cluster.json"
    _out.parent.mkdir(exist_ok=True)
    _out.write_text(_je.dumps(_t, indent=2, default=str))
    # === END TUNED EXPORT ===
    return


if __name__ == "__main__":
    app.run()
