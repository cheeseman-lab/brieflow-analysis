================================================================================
METADATA VALIDATION SUMMARY
================================================================================

✅ All positions have valid OME-NGFF metadata

Validated 1 position(s):

✅ A/3/0
    Resolution levels: 5
    Channels: 6 (metadata) = 6 (data) ✅
    Channel names: Phase2D, Focus3D, GFP, mCherry, nuclei_prediction, membrane_prediction
    Axes: T, C, Z, Y, X
    OME version: 0.5

================================================================================

================================================================================
STRUCTURE SUMMARY
================================================================================

[ROOT METADATA]
  {
    "attributes": {
      "ome": {
        "plate": {
          "version": "0.5",
          "acquisitions": [
            { "id": 0 } ],
          "rows": [
            { "name": "A" } ],
          "columns": [
            { "name": "1" },
            { "name": "2" },
            { "name": "3" } ],
          "wells": [
            { "path": "A/1", "rowIndex": 0, "columnIndex": 0 },
            { "path": "A/2", "rowIndex": 0, "columnIndex": 1 },
            { "path": "A/3", "rowIndex": 0, "columnIndex": 2 } ] },
        "version": "0.5" },
      "channels_metadata": [
        {
          "name": "Phase2D",
          "index": 0,
          "channel_type": "labelfree",
          "description": "Projected 2D reconstruction of label-free brightfield imaging" },
        {
          "name": "Focus3D",
          "index": 1,
          "channel_type": "labelfree",
          "description": "Reconstructed focal slice from 3D reconstruction of label-free brightfield" },
        {
          "name": "GFP",
          "index": 2,
          "channel_type": "fluorescent",
          "biological_annotation": {
            "organelle": "chaperones",
            "marker": "HSPA1B",
            "marker_type": "endogenous_tag",
            "full_label": "chaperones, HSPA1B" },
          "description": "Max projected chaperones visualized via HSPA1B" },
        {
          "name": "mCherry",
          "index": 3,
          "channel_type": "fluorescent",
          "biological_annotation": {
            "organelle": "actin filament",
            "marker": "FastAct_SPY555 Live Cell Dye",
            "marker_type": "live_cell_dye",
            "full_label": "actin filament, FastAct_SPY555 Live Cell Dye" },
          "description": "Max projected actin filament visualized via FastAct_SPY555 Live Cell Dye" },
        {
          "name": "nuclei_prediction",
          "index": 4,
          "channel_type": "virtual_stain",
          "biological_annotation": {
            "organelle": "nuclei",
            "marker": "virtual stain",
            "marker_type": "virtual_stain",
            "full_label": "nuclei, virtual stain" },
          "description": "Nuclei visualized via virtual stain" },
        {
          "name": "membrane_prediction",
          "index": 5,
          "channel_type": "virtual_stain",
          "biological_annotation": {
            "organelle": "membrane",
            "marker": "virtual stain",
            "marker_type": "virtual_stain",
            "full_label": "membrane, virtual stain" },
          "description": "Membrane visualized via virtual stain" } ] },
    "zarr_format": 3,
    "consolidated_metadata": null,
    "node_type": "group" }

A/3/0/
  [POSITION METADATA]
    {
      "attributes": {
        "ome": {
          "multiscales": [
            {
              "version": "0.5",
              "axes": [
                { "name": "T", "type": "time", "unit": "second" },
                { "name": "C", "type": "channel" },
                { "name": "Z", "type": "space", "unit": "micrometer" },
                { "name": "Y", "type": "space", "unit": "micrometer" },
                { "name": "X", "type": "space", "unit": "micrometer" } ],
              "datasets": [
                {
                  "path": "0",
                  "coordinateTransformations": [
                    {
                      "type": "scale",
                      "scale": [1.0, 1.0, 2.0, 0.65, 0.65] } ] },
                {
                  "path": "1",
                  "coordinateTransformations": [
                    {
                      "type": "scale",
                      "scale": [1.0, 1.0, 4.0, 1.3, 1.3] } ] },
                {
                  "path": "2",
                  "coordinateTransformations": [
                    {
                      "type": "scale",
                      "scale": [1.0, 1.0, 8.0, 2.6, 2.6] } ] },
                {
                  "path": "3",
                  "coordinateTransformations": [
                    {
                      "type": "scale",
                      "scale": [1.0, 1.0, 16.0, 5.2, 5.2] } ] },
                {
                  "path": "4",
                  "coordinateTransformations": [
                    {
                      "type": "scale",
                      "scale": [1.0, 1.0, 32.0, 10.4, 10.4] } ] } ],
              "name": "0" } ],
          "omero": {
            "version": "0.5",
            "id": 0,
            "name": "0",
            "channels": [
              {
                "active": true,
                "coefficient": 1.0,
                "color": "FFFFFF",
                "family": "linear",
                "inverted": false,
                "label": "Phase2D",
                "window": { "start": -0.2, "end": 0.2, "min": -10.0, "max": 10.0 } },
              {
                "active": true,
                "coefficient": 1.0,
                "color": "FFFFFF",
                "family": "linear",
                "inverted": false,
                "label": "Focus3D",
                "window": { "start": 0.0, "end": 65535.0, "min": 0.0, "max": 65535.0 } },
              {
                "active": true,
                "coefficient": 1.0,
                "color": "00FF00",
                "family": "linear",
                "inverted": false,
                "label": "GFP",
                "window": { "start": 0.0, "end": 65535.0, "min": 0.0, "max": 65535.0 } },
              {
                "active": true,
                "coefficient": 1.0,
                "color": "FF00FF",
                "family": "linear",
                "inverted": false,
                "label": "mCherry",
                "window": { "start": 0.0, "end": 65535.0, "min": 0.0, "max": 65535.0 } },
              {
                "active": true,
                "coefficient": 1.0,
                "color": "FFFFFF",
                "family": "linear",
                "inverted": false,
                "label": "nuclei_prediction",
                "window": { "start": 0.0, "end": 65535.0, "min": 0.0, "max": 65535.0 } },
              {
                "active": true,
                "coefficient": 1.0,
                "color": "FFFFFF",
                "family": "linear",
                "inverted": false,
                "label": "membrane_prediction",
                "window": { "start": 0.0, "end": 65535.0, "min": 0.0, "max": 65535.0 } } ],
            "rdefs": {
              "defaultT": 0,
              "defaultZ": 0,
              "model": "color",
              "projection": "normal" } },
          "version": "0.5" },
        "custom_metadata": {
          "normalization": {
            "Focus3D": {
              "dataset_statistics": {
                "iqr": 0.19549519568681717,
                "mean": -1.5618346878909506e-05,
                "median": 0.0,
                "std": 0.30545443296432495 },
              "fov_statistics": {
                "iqr": 0.20100906118750572,
                "mean": -0.00014254111738409847,
                "median": 0.0,
                "std": 0.3106600344181061 } },
            "GFP": {
              "dataset_statistics": {
                "iqr": 188.08291625976562,
                "mean": 216.91880798339844,
                "median": 183.7686767578125,
                "std": 187.9684600830078 },
              "fov_statistics": {
                "iqr": 188.3078899383545,
                "mean": 217.34642028808594,
                "median": 182.46823120117188,
                "std": 189.9900360107422 } },
            "Phase2D": {
              "dataset_statistics": {
                "iqr": 0.1524878814816475,
                "mean": 0.00014505063882097602,
                "median": 0.0,
                "std": 0.2543972134590149 },
              "fov_statistics": {
                "iqr": 0.1513833198696375,
                "mean": 0.00017736417066771537,
                "median": 0.0,
                "std": 0.2555769383907318 } },
            "mCherry": {
              "dataset_statistics": {
                "iqr": 125.0,
                "mean": 185.00210571289062,
                "median": 202.0,
                "std": 143.55101013183594 },
              "fov_statistics": {
                "iqr": 117.19999694824219,
                "mean": 178.65740966796875,
                "median": 196.0,
                "std": 138.16148376464844 } },
            "membrane_prediction": {
              "dataset_statistics": {
                "iqr": 0.34214185178279877,
                "mean": 0.18426816165447235,
                "median": 0.0,
                "std": 0.5348054766654968 },
              "fov_statistics": {
                "iqr": 0.3493692053016275,
                "mean": 0.2075449824333191,
                "median": 0.014186184853315353,
                "std": 0.5403116345405579 } },
            "nuclei_prediction": {
              "dataset_statistics": {
                "iqr": 0.823859691619873,
                "mean": 2.121549129486084,
                "median": 0.3338435888290405,
                "std": 5.922773361206055 },
              "fov_statistics": {
                "iqr": 0.854180783033371,
                "mean": 2.119429588317871,
                "median": 0.38068878650665283,
                "std": 5.84276008605957 } } },
          "clims_per_level": {
            "0": {
              "contrast_limits": [-0.5, 0.85],
              "contrast_limits_per_channel": [
                [-0.5, 0.85],
                [-0.5, 0.85],
                [150.0, 67866.51116638233],
                [150.0, 36288.01898437502],
                [0.0, 456.5784022235888],
                [-0.2, 34.24247842550311] ],
              "contrast_limits_method": "p0.1-99.5-coarsest+scale2^steps" },
            "1": {
              "contrast_limits": [-8.393857477605353, 9.309195677340044],
              "contrast_limits_per_channel": [
                [-8.393857477605353, 9.309195677340044],
                [-0.9954447992704811, 0.93726326296106],
                [150.0, 36211.682382202416],
                [150.0, 19493.65710937501],
                [0.0, 241.7179776477823],
                [-0.2, 18.128370931148705] ],
              "contrast_limits_method": "p0.1-99.5-coarsest+scale2^steps" },
            "2": {
              "contrast_limits": [-3.968094188869004, 4.883432388603695],
              "contrast_limits_per_channel": [
                [-3.968094188869004, 4.883432388603695],
                [-0.5122677837125958, 0.45408624740317477],
                [150.0, 20384.267990112454],
                [150.0, 11096.476171875005],
                [0.0, 134.28776535987905],
                [-0.2, 10.071317183971502] ],
              "contrast_limits_method": "p0.1-99.5-coarsest+scale2^steps" },
            "3": {
              "contrast_limits": [-1.7552125445008293, 2.67055074423552],
              "contrast_limits_per_channel": [
                [-1.7552125445008293, 2.67055074423552],
                [-0.27067927593365315, 0.21249773962423213],
                [150.0, 12470.56079406747],
                [150.0, 6897.885703125004],
                [0.0, 80.57265921592743],
                [-0.2, 6.042790310382902] ],
              "contrast_limits_method": "p0.1-99.5-coarsest+scale2^steps" },
            "4": {
              "contrast_limits": [-0.648771722316742, 1.5641099220514327],
              "contrast_limits_per_channel": [
                [-0.648771722316742, 1.5641099220514327],
                [-0.14988502204418183, 0.09170348573476081],
                [150.0, 8513.707196044981],
                [150.0, 4798.590468750002],
                [0.0, 53.71510614395162],
                [0.0, 4.028526873588601] ],
              "contrast_limits_method": "p0.1-99.5-coarsest+scale2^steps" } } } },
      "zarr_format": 3,
      "consolidated_metadata": null,
      "node_type": "group" }
  ├─ 0/  (1, 6, 1, 104668, 104743) float32  245.05 GB  chunks=(1, 1, 1, 512, 512) [64 shards] ✅
  │   [ARRAY METADATA]
  │     {
  │       "shape": [1, 6, 1, 104668, 104743],
  │       "data_type": "float32",
  │       "chunk_grid": {
  │         "name": "regular",
  │         "configuration": {
  │           "chunk_shape": [1, 6, 1, 13312, 13312] } },
  │       "chunk_key_encoding": {
  │         "name": "default",
  │         "configuration": { "separator": "/" } },
  │       "fill_value": 0.0,
  │       "codecs": [
  │         {
  │           "name": "sharding_indexed",
  │           "configuration": {
  │             "chunk_shape": [1, 1, 1, 512, 512],
  │             "codecs": [
  │               {
  │                 "name": "bytes",
  │                 "configuration": { "endian": "little" } },
  │               {
  │                 "name": "blosc",
  │                 "configuration": {
  │                   "typesize": 4,
  │                   "cname": "zstd",
  │                   "clevel": 1,
  │                   "shuffle": "bitshuffle",
  │                   "blocksize": 0 } } ],
  │             "index_codecs": [
  │               {
  │                 "name": "bytes",
  │                 "configuration": { "endian": "little" } },
  │               { "name": "crc32c" } ],
  │             "index_location": "end" } } ],
  │       "attributes": {},
  │       "dimension_names": ["T", "C", "Z", "Y", "X"],
  │       "zarr_format": 3,
  │       "node_type": "array",
  │       "storage_transformers": [] }
  ├─ 1/  (1, 6, 1, 52334, 52372) float32  61.26 GB  chunks=(1, 1, 1, 512, 512) [16 shards] ✅
  ├─ 2/  (1, 6, 1, 26167, 26186) float32  15.32 GB  chunks=(1, 1, 1, 512, 512) [4 shards] ✅
  ├─ 3/  (1, 6, 1, 13084, 13093) float32  3.83 GB  chunks=(1, 1, 1, 512, 512) [1 shards] ✅
  ├─ 4/  (1, 6, 1, 6542, 6547) float32  980.31 MB  chunks=(1, 1, 1, 512, 512) [1 shards] ✅
  └─ labels/
     [LABELS GROUP METADATA]
       {
         "attributes": {
           "ome": {
             "version": "0.5",
             "labels": ["nuclear_seg", "seg", "cell_seg"] },
           "labels": ["grid_overlay", "nuclear_seg", "seg", "cell_seg"] },
         "zarr_format": 3,
         "consolidated_metadata": null,
         "node_type": "group" }
     ├─ seg/
     │   [LABEL METADATA]
     │     {
     │       "attributes": {
     │         "segmentation_metadata": {
     │           "label_name": "seg",
     │           "annotation_type": "cell_segmentation",
     │           "is_ome_label": true,
     │           "source_channel": {
     │             "name": "membrane_prediction",
     │             "index": 5,
     │             "type": "virtual_stain",
     │             "all_channels": [
     │               "Phase2D",
     │               "Focus3D",
     │               "GFP",
     │               "mCherry",
     │               "nuclei_prediction",
     │               "membrane_prediction" ] },
     │           "biological_annotation": {
     │             "organelle": "cell_membrane",
     │             "marker": "virtual stain",
     │             "marker_type": "virtual_stain",
     │             "full_label": "cell_membrane, virtual stain" },
     │           "segmentation": { "method": "cellpose", "version": "phenotyping-v3" },
     │           "description": "Cell segmentation from membrane virtual stain using Cellpose" },
     │         "custom_metadata": {
     │           "annotation_type": "cell_segmentation",
     │           "description": "Cell segmentation masks",
     │           "is_ome_label": true } },
     │       "zarr_format": 3,
     │       "consolidated_metadata": null,
     │       "node_type": "group" }
     │   ├─ 0/  (1, 1, 1, 104668, 104743) int32  40.84 GB  chunks=(1, 1, 1, 512, 512) [49 shards] ✅
     │   │  [ARRAY METADATA]
     │   │    {
     │   │      "shape": [1, 1, 1, 104668, 104743],
     │   │      "data_type": "int32",
     │   │      "chunk_grid": {
     │   │        "name": "regular",
     │   │        "configuration": {
     │   │          "chunk_shape": [1, 1, 1, 16384, 16384] } },
     │   │      "chunk_key_encoding": {
     │   │        "name": "default",
     │   │        "configuration": { "separator": "/" } },
     │   │      "fill_value": 0,
     │   │      "codecs": [
     │   │        {
     │   │          "name": "sharding_indexed",
     │   │          "configuration": {
     │   │            "chunk_shape": [1, 1, 1, 512, 512],
     │   │            "codecs": [
     │   │              {
     │   │                "name": "bytes",
     │   │                "configuration": { "endian": "little" } },
     │   │              {
     │   │                "name": "zstd",
     │   │                "configuration": { "level": 0, "checksum": false } } ],
     │   │            "index_codecs": [
     │   │              {
     │   │                "name": "bytes",
     │   │                "configuration": { "endian": "little" } },
     │   │              { "name": "crc32c" } ],
     │   │            "index_location": "end" } } ],
     │   │      "attributes": {},
     │   │      "zarr_format": 3,
     │   │      "node_type": "array",
     │   │      "storage_transformers": [] }
     │   ├─ 1/  (1, 1, 1, 52334, 52371) int32  10.21 GB  chunks=(1, 1, 1, 512, 512) [16 shards] ✅
     │   ├─ 2/  (1, 1, 1, 26167, 26185) int32  2.55 GB  chunks=(1, 1, 1, 512, 512) [4 shards] ✅
     │   ├─ 3/  (1, 1, 1, 13083, 13092) int32  653.39 MB  chunks=(1, 1, 1, 512, 512) [1 shards] ✅
     │   └─ 4/  (1, 1, 1, 6541, 6546) int32  163.34 MB  chunks=(1, 1, 1, 512, 512) [1 shards] ✅
     ├─ nuclear_seg/
     │   ├─ 0/  (1, 1, 1, 104668, 104740) int32  40.84 GB  chunks=(1, 1, 1, 512, 512) [49 shards] ✅
     │   ├─ 1/  (1, 1, 1, 52334, 52370) int32  10.21 GB  chunks=(1, 1, 1, 512, 512) [16 shards] ✅
     │   ├─ 2/  (1, 1, 1, 26167, 26185) int32  2.55 GB  chunks=(1, 1, 1, 512, 512) [4 shards] ✅
     │   ├─ 3/  (1, 1, 1, 13083, 13092) int32  653.39 MB  chunks=(1, 1, 1, 512, 512) [1 shards] ✅
     │   └─ 4/  (1, 1, 1, 6541, 6546) int32  163.34 MB  chunks=(1, 1, 1, 512, 512) [1 shards] ✅
     ├─ iss_guide_image/
     │   ├─ 0/  (104668, 104743, 4) uint8  40.84 GB  chunks=(1024, 1024, 4) [16 shards] ✅
     │   ├─ 1/  (52334, 52372, 4) uint8  10.21 GB  chunks=(1024, 1024, 4) [4 shards] ✅
     │   ├─ 2/  (26167, 26186, 4) uint8  2.55 GB  chunks=(1024, 1024, 4) [1 shards] ✅
     │   ├─ 3/  (13084, 13093, 4) uint8  653.49 MB  chunks=(1024, 1024, 4) [1 shards] ✅
     │   └─ 4/  (6542, 6547, 4) uint8  163.39 MB  chunks=(1024, 1024, 4) [1 shards] ✅
     ├─ cell_seg/
     │   ├─ 0/  (1, 1, 1, 104668, 104743) int32  40.84 GB  chunks=(1, 1, 1, 512, 512) [49 shards] ✅
     │   ├─ 1/  (1, 1, 1, 52334, 52371) int32  10.21 GB  chunks=(1, 1, 1, 512, 512) [16 shards] ✅
     │   ├─ 2/  (1, 1, 1, 26167, 26185) int32  2.55 GB  chunks=(1, 1, 1, 512, 512) [4 shards] ✅
     │   ├─ 3/  (1, 1, 1, 13083, 13092) int32  653.39 MB  chunks=(1, 1, 1, 512, 512) [1 shards] ✅
     │   └─ 4/  (1, 1, 1, 6541, 6546) int32  163.34 MB  chunks=(1, 1, 1, 512, 512) [1 shards] ✅
     ├─ grid_overlay/
     │   ├─ 0/  (104668, 104743, 4) uint8  40.84 GB  chunks=(1024, 1024, 4) [16 shards] ✅
     │   ├─ 1/  (52334, 52372, 4) uint8  10.21 GB  chunks=(1024, 1024, 4) [4 shards] ✅
     │   ├─ 2/  (26167, 26186, 4) uint8  2.55 GB  chunks=(1024, 1024, 4) [1 shards] ✅
     │   ├─ 3/  (13084, 13093, 4) uint8  653.49 MB  chunks=(1024, 1024, 4) [1 shards] ✅
     │   └─ 4/  (6542, 6547, 4) uint8  163.39 MB  chunks=(1024, 1024, 4) [1 shards] ✅
     └─ iss_gene_image/
        ├─ 0/  (104668, 104743, 4) uint8  40.84 GB  chunks=(1024, 1024, 4) [16 shards] ✅
        ├─ 1/  (52334, 52372, 4) uint8  10.21 GB  chunks=(1024, 1024, 4) [4 shards] ✅
        ├─ 2/  (26167, 26186, 4) uint8  2.55 GB  chunks=(1024, 1024, 4) [1 shards] ✅
        ├─ 3/  (13084, 13093, 4) uint8  653.49 MB  chunks=(1024, 1024, 4) [1 shards] ✅
        └─ 4/  (6542, 6547, 4) uint8  163.39 MB  chunks=(1024, 1024, 4) [1 shards] ✅

────────────────────────────────────────────────────────────────────────────────
TOTAL SIZE (all positions): 652.82 GB
================================================================================