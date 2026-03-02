OME-Zarr Overview

plate_001.zarr/
├── zarr.json                              # FILE 1: Plate metadata
├── A/
│   ├── 1/
│   │   ├── zarr.json                     # FILE 2a: Well A1 group metadata
│   │   └── 0/ (image chunks)
│   │   	    └── zarr.json	    # FILE 3a: chunk A/1/0 array metadata
│   ├── 2/
│   │   ├── zarr.json                # FILE 2b: Well A2 group metadata
│   │   └── 0/
│   │   	    └── zarr.json	    # FILE 3b: chunk A/2/0 array metadata
│   └── 3/
│       ├── zarr.json                      # FILE 2c: Well A3 group metadata
│       └── 0/
│   	    └── zarr.json	    # FILE 3c: chunk A/3/0 array metadata
└── metadata/
    ├── experiment_metadata.json         # FILE 6: Experiment-level OPS info
    ├── perturbation_library.tsv         # FILE 5: Gene library
    ├── cell_data.parquet                # FILE 3: Link table
    ├── cell_features.parquet            # FILE 4: Feature values
    └── feature_definitions.json         # FILE 7: Feature descriptions (optional)

 
json (plate and well) 
Plate and Well Metadata

There are two zarr.json files: 1) plate level 2) well level
Plate level: plate_001.zarr/zarr.json
Well level: plate_001.zarr/A/1/zarr.json

plate_001.zarr/zarr.json
OME-Zarr (plate level?)
●	attributes.ome.version
●	attributes.ome.plate.version
●	attributes.ome.plate.name
●	attributes.ome.plate.acquisitions
●	attributes.ome.plate.columns
●	attributes.ome.plate.rows
●	attributes.ome.plate.wells
●	attributes.ome.plate.field_count

Cross modality
●	Organism_ontology_term_id → from NCBI organism classifications
●	Organism → Ibid. ^
●	Tissue_ontology_term_id → from cell line ontology
●	Tissue → ^
●	Tissue_type → one of [‘cell culture’, ‘cell line’, ‘organelle’, ‘organoid’, ‘tissue’]
●	Disease_ontology_term_id → PATO:0000461 for normal/healthy or disease
●	Disease → Ibid. ^
●	Development_stage_ontology_term_id → “na” for cell line or from here if human
●	Development_stage → name associated with d_s_o_t_id ^
●	Assay_ontology_term_id → from experimental factor ontology
●	Assay → name from EFO ^

Optional experimental collection data
●	attributes.experiment_description
●	attributes.date_collected
●	attributes.institution_or_PI

plate_001.zarr/A/1/zarr.json
Multiscales
●	attributes.ome.multiscales[].name
●	attributes.ome.multiscales[].axes[] (with name, type, unit)
○	axes[].name (e.g., "t", "c", "z", "y", "x")
○	axes[].type (e.g., "time", "channel", "space")
○	axes[].unit (e.g., "micrometer", "millisecond")
●	attributes.ome.multiscales[].datasets[].path
●	attributes.ome.multiscales[].datasets[].coordinateTransformations[].type
●	attributes.ome.multiscales[].datasets[].coordinateTransformations[].scale

Microscopy
●	attributes.microscopy.microscope_type
●	attributes.microscopy.objective
●	attributes.microscopy.magnification
●	attributes.microscopy.numerical_aperture
●	attributes.microscopy.acquisition_mode (enum: "confocal", "widefield", "spinning_disk", "light_sheet")
●	attributes.microscopy.is_live_imaging (boolean)
●	attributes.microscopy.is_fixed_imaging (boolean)

Visualization
●	attributes.omero.name
●	attributes.omero.channels[] (array, one per channel)
○	Omero.channels[].label
○	omero.channels[].color (hex code)
○	Omero.channels[].window.start
○	Omero.channels[].window.end
○	Omero.channels[].window.min
○	Omero.channels[].window.max
○	omero.channels[].active (boolean)
○	Omero.channels[].coefficient
○	omero.channels[].family (e.g., "linear")
○	omero.channels[].inverted (boolean)
●	attributes.omero.rdefs.defaultZ
●	attributes.omero.rdefs.defaultT
●	attributes.omero.rdefs.model (e.g., "color")

OPS Channel Metadata
●	attributes.channels_metadata[] (array, one per channel)
○	Channels_metadata[].name
○	Channels_metadata[].index
○	channels_metadata[].channel_type (enum: "labelfree", "fluorescent", "virtual_stain")
○	Channels_metadata[].description
○	Channels_metadata[].biological_annotation.organelle
○	Channels_metadata[].biological_annotation.marker
○	Channels_metadata[].biological_annotation.marker_type
○	Channels_metadata[].biological_annotation.full_label
○	channels_metadata[].fluorophore (optional)
○	channels_metadata[].excitation_wavelength_nm (optional)
○	channels_metadata[].emission_wavelength_nm (optional)
○	channels_metadata[].antibody_catalog_id (optional)

Container/well information
●	attributes.container.container_uid
●	attributes.container.container_type
●	attributes.container.well_position
●	attributes.container.cell_line
●	attributes.container.culture_conditions.media
●	attributes.container.culture_conditions.temperature_celsius (optional)
●	attributes.container.culture_conditions.co2_percentage (optional)
●	attributes.container.cell_product_lot_id (optional)
●	attributes.container.passage_number (optional)

Acquisition information
●	attributes.acquisition_uid
●	attributes.acquisition_timestamp


Example of how this would look in OME-Zarr format for 1 plate, 2 wells

  plate_001.zarr/
  ├── zarr.json
  │   ├── zarr_format: 3
  │   ├── node_type: "group"
  │   └── attributes:
  │       ├── ome.plate.*
  │       ├── organism*
  │       └── tissue*
  │
  ├── A/1/zarr.json
  │   ├── zarr_format: 3
  │   ├── node_type: "group"
  │   └── attributes:
  │       ├── ome.multiscales
  │       ├── microscopy
  │       ├── omero
  │       ├── channels_metadata
  │       ├── container
  │       └── acquisition_uid
  │
  └── A/2/zarr.json
      ├── zarr_format: 3
      ├── node_type: "group"
      └── attributes:
          ├── ome.multiscales
          ├── microscopy
          ├── omero
          ├── channels_metadata
          ├── container
          └── acquisition_uid


 
experiment_metadata 
Experiment Metadata 

I’m unsure if this is needed… condensed experimental information, some is in other files

File name/location
-	metadata/experiment_metadata.json

Temporal Information:
●	endpoint_timepoint (ISO 8601 duration, e.g., "P5D")
●	days_in_vitro (optional)

Biological Markers (full list with details):
●	Biological_markers[]
○	All fields from channels_metadata, but consolidated here for experiment-wide reference

Data Provenance (optional?)
●	Dataset_version
●	Processing_pipeline_version
●	License
●	doi (optional)
●	related_publications[] (optional)
●	creator, contributor (optional)

Paired Experiments (optional but could allow for CROP-seq <> OPS linkage)
●	Paired_experiments[]
●	Paired_experiments[].experiment_id
●	Paired_experiments[].modality
●	Paired_experiments[].description
●	Paired_experiments[].data_location

 
cell_data 
Cell Data 

File name/location
-	metadata/cell_data.parquet

Required
●	Cell_uid
●	Container_uid
●	Acquisition_uid
●	Fov_index
●	X_global
●	Y_global
●	X_iss
●	Y_iss
●	Segmentation_id
●	Barcode
●	Guide_id
●	Gene_symbol
●	Gene_id
●	Is_control

Optional
●	og_index
●	x_local
●	y_local
●	tile_pheno
●	bounding_box
●	subpool
●	spacer
●	ncbi_id
●	depmap_gene
●	gene_effect
●	barcode_confidence_score
●	num_barcode_mismatches
●	passed_barcode_qc
●	passed_segmentation_qc
●	is_boundary_cell
●	track_id (if time-series)
○	 Not needed for V1?
●	y_tracking_t0, x_tracking_t0 (if time-series)
○	 Not required for V1?
●	y_tracking_t1, x_tracking_t1 (if time-series)
○	 Not required for V1? 
cell_features 
Cell Features 

File name/location
-	metadata/cell_features.parquet

This is the table that includes the imaging phenotypic readouts, likely pulled from CellProfiler. The goal is to align on a small set of required features. Suggestions below.

Required:
●	cell_uid 
○	must match link table to connect phenotype to perturbation

Phenotype categories
Morphology:
●	cell_area_um2
●	cell_perimeter_um
●	cell_eccentricity
●	cell_solidity
●	cell_aspect_ratio
●	cell_form_factor
●	nucleus_area_um2
●	nucleus_perimeter_um
●	nucleus_eccentricity
●	nucleus_solidity
●	Cytoplasm_area_um2

Intensity Features (per channel):
●	nucleus_mean_intensity_ch0
●	nucleus_mean_intensity_ch1
●	nucleus_mean_intensity_ch2
●	nucleus_integrated_intensity_ch0
●	nucleus_integrated_intensity_ch1
●	nucleus_integrated_intensity_ch2
●	cytoplasm_mean_intensity_ch0
●	cytoplasm_mean_intensity_ch1
●	cytoplasm_mean_intensity_ch2
●	nucleus_to_cytoplasm_ratio_ch0
●	nucleus_to_cytoplasm_ratio_ch1
●	nucleus_to_cytoplasm_ratio_ch2

Categorical Features:
●	nucleation_status 
○	(enum: "single_nucleus", "multinucleated", "anucleate", "fragmented")
●	mitotic_status 
○	(enum: "interphase", "prophase", "metaphase", "anaphase", "telophase")
●	cell_cycle_phase 
○	(enum: "G1", "S", "G2", "M")
●	apoptosis_status 
○	(enum: "healthy", "early_apoptotic", "late_apoptotic")

Texture:
●	nucleus_entropy
●	nucleus_correlation
●	cytoplasm_correlation
●	granularity_score

Granularity:
●	granularity_n_ch0
●	granularity_n_ch1
●	granularity_n_ch2 
Perturbation_library 
Perturbation Library

This is a .csv file containing metadata information about the specific perturbations applied (in both OPS and any corresponding CROPseq experiments)

It should contain the following required fields
●	guide_id 
●	spacer (aka perturbation_type)
●	barcode
●	is_control
●	gene_symbol 
●	gene_id 

The gene_symbols and gene_id should match those in the CROPseq H5AD files.

 
feature_definition 
Feature Definitions 

This will be needed if we start talking about new datasets from people who might use terms differently… essentially just a file to quantitatively (when possible) describe how features are being measured.

File name/location
-metadata/feature_definitions.json

Morphology
●	Feature_name
○	Description
○	Unit
○	Method
○	Software
○	version

Intensity
●	Feature_name
○	Description
○	Unit
○	Method
○	Software
○	Version
○	Channel_index
○	Channel_name
○	marker


categorical_features[]
●	Feature_name
○	Description
○	type ("categorical")
○	values (array of possible values)
○	method

Texture
●	Feature_name
○	Description
○	Unit
○	Method
○	Software
○	version

Granularity
●	Feature_name
○	Description
○	Unit
○	Method
○	Software
○	version