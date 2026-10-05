Unified diffs from `output_v5` to `output_v6` (the 222 side-by-side table pages switched to column-split
readings, 83 files). `output_v5` is not stored; rebuild it with `patch -R`:

    for p in $(find output_v5_diff -name '*.patch'); do f=${p#output_v5_diff/}; f=${f%.patch}; cp output_v6/$f output_v5/$f; patch -R output_v5/$f $p; done
The one image present only in v5 (vol008 ..._3_img.webp) is stored here as-is.
