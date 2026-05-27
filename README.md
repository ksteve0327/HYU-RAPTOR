# HYU-RAPTOR Patent Experiment

This repository contains a patent-domain RAPTOR implementation and comparison report.

The main version is **V2**, which extends the V1 RAPTOR/BM25 baseline with Global/Local QA, DPR retrieval, and a GPT-5.5 hybrid judge.

## Main Results

V2 compares four reader/retrieval methods on 10 QA items:

- `traverse_tree`
- `collapsed_tree`
- `bm25_leaf`
- `dpr_leaf`

Question split:

- 5 global questions that require cross-patent synthesis.
- 5 local questions answerable from one target patent.

Main V2 artifacts:

- `runs/patent_raptor_v2_20260527_221004/report.html`
- `runs/patent_raptor_v2_20260527_221004/tree_visualization.html`
- `versions/v2/README.md`

V1 is retained as the first baseline:

- `runs/patent_raptor_full_20260527_144357/report.html`
- `runs/patent_raptor_full_20260527_144357/tree_visualization.html`
- `versions/v1/README.md`

## Implementation

The experiment code includes:

- Hard K-means RAPTOR tree building.
- Structured retrieval helpers for Traverse Tree and Collapsed Tree.
- BM25 leaf baseline.
- DPR leaf baseline.
- Codex proxy adapter for OpenAI-compatible local LLM calls.
- Progress reporter with elapsed time, rolling ETA, and expected end time.
- HTML report and tree/source overlay visualization generation.

## Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run a dependency-light smoke test:

```bash
python scripts/run_patent_raptor_experiment.py \
  --smoke \
  --skip-llm \
  --embedding-backend hash \
  --dpr-backend hash
```

Run a V2 experiment using an existing V1 tree:

```bash
python scripts/run_patent_raptor_experiment.py \
  --reuse-run-dir runs/patent_raptor_full_20260527_144357 \
  --progress-interval-seconds 60
```

The raw `patent_rawdata.csv`, local proxy health files, Python caches, and pickled tree files are intentionally excluded from git.

## Version Notes

- V1: RAPTOR Traverse/Collapsed Tree vs BM25 comparison on 20 synthetic QA items.
- V2: Global/Local QA, DPR baseline, four-method answer comparison, and GPT-5.5 hybrid best-method judging.
