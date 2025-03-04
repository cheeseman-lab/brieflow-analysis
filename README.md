# Brieflow Analysis Template

Template repository for storing processing optical pooled screen data with [Brieflow](https://github.com/cheeseman-lab/brieflow).


## Set Up

This repository is designed to work with Brieflow to analyze optical pooled screens.
Follow these steps to get set up for a screen analysis!

### 1. Screen Analysis Repository Setup

Brieflow-analysis is a template for each screen analysis.
Create a new respository for a screen to get started.

1) Create a new screen repository wih the "Use this template" button for each new screen analysis.

![use template](images/image.png)

2) *Optional*: Add template brieflow-analysis template as an upstream reference in screen repository:
`git remote add template https://github.com/cheeseman-lab/brieflow-analysis`

### 2. Brieflow Setup

We use [Brieflow](https://github.com/cheeseman-lab/brieflow) to process data on a very large scale from each screen.
**Note:** We use Brieflow as a git submodule in this repository.
Please see the [Git Submodules basic explanation](https://gist.github.com/gitaarik/8735255) for information on how to best install, use, and update this submodule.

1) Clone the Brieflow package into this repo using the following git submodule commands:

```sh
# init git submodule
git submodule init
# clone brieflow
git submodule update 
```

2) Set up Brieflow following the [setup instructions](https://github.com/cheeseman-lab/brieflow#brieflow-setup).
To set up the Brieflow Conda environment (~20 min):

```sh
# enter brieflow directory
cd brieflow/
# create brieflow_main_env conda environment
conda env create --file=brieflow_main_env.yml
# activate brieflow_main_env conda environment
conda activate brieflow_main_env
# set conda installation to use strict channel priorities
conda config --set channel_priority strict
```

**Note:** We recommend making a custom Brieflow environment if you need other packages for Brieflow modifications.
Simply change the name of the `brieflow_main_env` Conda environment and track your added packages in [brieflow/brieflow_main_env.yml](brieflow/brieflow_main_env.yml).

We use the HPC integration for Slurm as detailed in the setup instructions.
To use the Slurm integration for Brieflow configure the Slurm resources in [analysis/slurm/config.yaml](analysis/slurm/config.yaml).

3) *Optional*: Track changes to computational processing in a new branch on your fork.
Contribute these changes to the main version of Brieflow with a PR as described in the Brieflow [contribution notes](https://github.com/cheeseman-lab/brieflow?tab=readme-ov-file#contribution-notes).

### 3. Start Analysis

`analysis/` contains configuration notebooks used to configure processes and slurm scripts used to run full modules.
By default, results are output to `analysis/analysis_root` and organized by analysis module (preprocess, sbs, phenotype, etc).

Follow the full instructions below to run an analysis.


## Analysis Steps

Follow the instructions below to configure parameters and run modules.
All of these steps are done in the example analysis.
Use the following commands to enter this folder and activate the conda env:

```sh
# enter analysis directory
cd analysis/
# activate brieflow_main_env conda environment
conda activate brieflow_main_env
```

***Note**: Use `brieflow_main_env` Conda environment for each configuration notebook.

### Step 0: Configure preprocess parameters

Follow the steps in [0.configure_preprocess_params.ipynb](analysis/0.configure_preprocess_params.ipynb) to configure preprocess params.

**Note:** This step determines where ND2 data is loaded from (can be from anywhere) and where intermediate/output data is saved (can also be anywhere).
By default, results are output to `analysis/analysis_root`.

### Step 1: Run preprocessing module

**Local**:
```sh
sh 1.run_preprocessing.sh
```
**Slurm**:

Change `NUM_PLATES` in [1.run_preprocessing_slurm.sh](1.run_preprocessing_slurm.sh) to the number of plates you are processing (to process each plate separately).

```sh
# start a tmux session: 
tmux new-session -s preprocessing
# in the tmux session:
sh 1.run_preprocessing_slurm.sh
```

***Note**: For testing purposes, users may only have generated sbs or phenotype images.
It is possible to test only SBS/phenotype preprocessing in this notebook.
See notebook instructions for more details.

### Step 2: Configure SBS parameters

Follow the steps in [2.configure_sbs_params.ipynb](analysis/2.configure_sbs_params.ipynb) to configure SBS module parameters.

### Step 3: Configure phenotype parameters

Follow the steps in [3.configure_phenotype_params.ipynb](analysis/3.configure_phenotype_params.ipynb) to configure phenotype module parameters.

### Step 4: Run SBS/phenotype modules

**Local**:
```sh
sh 4.run_sbs_phenotype.sh
```
**Slurm**:

Change `NUM_PLATES` [4.run_sbs_phenotype_slurm.sh](4.run_sbs_phenotype_slurm.sh) to the number of plates you are processing (to process each plate separately).

```sh
# start a tmux session: 
tmux new-session -s sbs_phenotype
# in the tmux session:
sh 4.run_sbs_phenotype_slurm.sh
```

### Step 5: Configure merge process params

Follow the steps in [5.configure_merge_params.ipynb](analysis/5.configure_merge_params.ipynb) to configure merge process params.

### Step 6: Run merge process

**Local**:
```sh
sh 6.run_merge.sh
```
**Slurm**:
```sh
# start a tmux session: 
tmux new-session -s merge
# in the tmux session:
sh 6.run_merge_slurm.sh
```

### Step 7: Configure aggregate process params

Follow the steps in [7.configure_aggregate_params.ipynb](analysis/7.configure_aggregate_params.ipynb) to configure aggregate process params.

### Step 8: Run aggregate process

**Local**:
```sh
sh 8.run_aggregate.sh
```
**Slurm**:
```sh
# start a tmux session: 
tmux new-session -s aggregate
# in the tmux session:
sh 8.run_aggregate_slurm.sh
```

### Step 9: Configure cluster process params

Follow the steps in [9.configure_cluster_params.ipynb](analysis/9.configure_cluster_params.ipynb) to configure cluster process params.

### Step 10: Run cluster process

**Local**:
```sh
sh 10.run_cluster.sh
```
**Slurm**:
```sh
# start a tmux session: 
tmux new-session -s cluster
# in the tmux session:
sh 10.run_cluster_slurm.sh
```

***Note**: Many users will want to only run SBS or phenotype processing, independently.
It is possible to restrict the SBS/phenotype processing with the following:
1) If either of the sample dataframes defined in [0.configure_preprocess_params.ipynb](analysis/0.configure_preprocess_params.ipynb) are empty then no samples will be processed.
See the notebook for more details.
2) By varying the tags in the `4.run_sbs_phenotype` sh files (`--until all_sbs` or `--until all_phenotype`), the analysis will only run only the analysis of interest.

## Generate Rulegraph

Run the following script to generate a rulegraph of Brieflow:

```sh
sh generate_rulegraph.sh
```

## Contributing

- Core improvements should be contributed back to Brieflow
- If you have analyzed any of your optical pooled screening data using brieflow-analysis, please reach out and we will include you in the table below!

## Examples of brieflow-analysis usage:

| Study | Description | Analysis Repository | Publication |
|-------|-------------|---------------------|-------------|
| _Coming soon_ | | | |