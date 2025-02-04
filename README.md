# Brieflow Analysis Template

Template repository for storing configurations and outputs when analyzing optical pooled screens using [Brieflow](https://github.com/cheeseman-lab/brieflow).

## Overview

This repository is designed to work with Brieflow to analyze optical pooled screens. The recommended workflow is:

1. Brieflow (Core Package):
   - Install Brieflow following instructions in its repository
   - Create new branches for any core code modifications
   - Submit improvements back via pull requests

2. This Repository (Analysis):
   - Fork this repository for each new screen analysis 
   - Contains configuration parameters and analysis outputs
   - Results are organized by analysis module (preprocess, sbs_process, phenotype_process)

## Prerequisites

1. Install Brieflow following [installation instructions](https://github.com/cheeseman-lab/brieflow#set-up-workflowconfiguration-conda-environments)
2. Set up the required conda environments as described in the Brieflow documentation

## Setting Up Your Analysis

1. Fork this template repository:
   - Each screen analysis should have its own fork of brieflow-analysis
   - This keeps configurations and results separate for each screen

2. Core Processing (Brieflow):
   - If you need modifications to core processing code, create a branch in Brieflow 
   - Once tested, submit improvements back to Brieflow via pull requests

3. Analysis Configuration:
   - Configure parameters in analysis/*.ipynb notebooks
   - Results will be organized in analysis_root/ by module
   - All screen-specific files stay in your forked repository

### Analysis Steps

Follow the instructions below to configure parameters and run modules.
All of these steps are done in the analysis folder, but parameters that need to be filled out are blank.
These steps are equivalent to what is presented for the example analysis in [Brieflow](https://github.com/cheeseman-lab/brieflow).
Use the following command to enter this folder: `cd analysis/`. 

Deposit the data from your screen into a subfolder in `analysis/`

#### Step 0: Configure preprocess params

Follow the steps in [0.configure_preprocess_params.ipynb](analysis/0.configure_preprocess_params.ipynb) to configure preprocess params.

#### Step 1: Run preprocessing module

**Local**:
```sh
conda activate brieflow_workflows
sh 1.run_preprocessing.sh
```
**Slurm**:
```sh
sbatch 1.run_preprocessing_slurm.sh
```

***Note**: For testing purposes, users may only have generated sbs or phenotype images.
It is possible to test only SBS/phenotype preprocessing in this notebook.
See notebook instructions for more details.

#### Step 2: Configure SBS process params

Follow the steps in [2.configure_sbs_process_params.ipynb](analysis/2.configure_sbs_process_params.ipynb) to configure SBS process params.


#### Step 3: Configure phenotype process params

Follow the steps in  [3.configure_phenotype_process_params.ipynb](analysis/3.configure_phenotype_process_params.ipynb) to configure phenotype process params.

#### Step 4: Run SBS/phenotype process module

**Local**:
```sh
conda activate brieflow_workflows
sh 4.run_sbs_phenotype_processes.sh
```
**Slurm**:
```sh
sbatch 4.run_sbs_phenotype_processes_slurm.sh
```

***Note**: Use `brieflow_configuration` Conda environment for each configuration notebook.

***Note**: Many users will want to only run SBS or phenotype processing, independently.
It is possible to restrict the SBS/phenotype processing with the following:
1) If either of the sample dataframes defined in [0.configure_preprocess_params.ipynb](analysis/0.configure_preprocess_params.ipynb) are empty then no samples will be processed.
See the notebook for more details.
2) By varying the tags in the `4.run_sbs_phenotype_processing` sh files (`--until all_sbs_process` or `--until all_phenotype_process`), the analysis will only run only the analysis of interest.

### Run Entire Analysis

If all parameter configurations are known for the entire Brieflow pipeline, it is possible to run the entire pipeline with the following:

```sh
conda activate brieflow_workflows
sh run_entire_analysis.sh
sbatch run_entire_analysis.sh
```

## Contributing

- Core improvements should be contributed back to Brieflow
- If you have analyzed any of your optical pooled screening data using brieflow-analysis, please reach out and we will include you in the table below!

## Examples of brieflow-analysis usage:

| Study | Description | Analysis Repository | Publication |
|-------|-------------|---------------------|-------------|
| _Coming soon_ | | | |