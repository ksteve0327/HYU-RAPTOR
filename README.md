# HYU-RAPTOR Patent Experiment V1

This repository tracks a patent-domain RAPTOR implementation experiment.

V1 is the first public baseline report. It samples 200 patent summaries from four middle categories, builds a hard-clustered RAPTOR tree, and compares:

- `traverse_tree`
- `collapsed_tree`
- `bm25_leaf`
- `bm25_all_nodes`

The main V1 artifacts are in:

- `runs/patent_raptor_full_20260527_144357/report.html`
- `runs/patent_raptor_full_20260527_144357/tree_visualization.html`
- `versions/v1/README.md`

The raw `patent_rawdata.csv`, local proxy health files, Python caches, and pickled tree files are intentionally excluded from git.
