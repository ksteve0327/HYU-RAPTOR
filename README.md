# HYU-RAPTOR Patent Experiment

This repository contains a patent-domain RAPTOR implementation and comparison report.

The main version is **V3**. V1 and V2 are kept as baselines so the repository history shows how the experiment evolved from a basic RAPTOR/BM25 comparison into Global/Local QA, dense retrieval, and a paper-aligned with/without RAPTOR evaluation.

## Experiment Goal

The experiment asks whether a RAPTOR-style hierarchical summary tree is useful for patent retrieval and question answering compared with lexical and dense retrieval baselines.

The target corpus is a sampled patent dataset:

- 200 patent summaries.
- 4 middle categories, 50 patents each.
- Indexed text column: `요약`.
- Metadata: `patent_id`, `중분류`, `중분류명`.

The raw `patent_rawdata.csv` is intentionally excluded from git.

## RAPTOR Analysis Pipeline

The implemented pipeline follows this flow:

1. Sample patent summaries by middle category.
2. Embed patent summaries with the configured multilingual embedding model.
3. Build a RAPTOR tree with hard K-means clustering.
4. Summarize child nodes into parent summary nodes through `codex-proxy`.
5. Retrieve context using multiple methods.
6. Generate reader answers with the same context budget.
7. Judge answer quality with GPT-5.5.
8. Render the final HTML report and interactive tree/source overlay.

The visualization shows:

- Full RAPTOR tree structure.
- Leaf patent IDs.
- Summary node text.
- Retrieved source nodes per QA.
- Retrieved source nodes and method-specific overlays for comparison.

## V1 Baseline

V1 compares the original RAPTOR retrieval modes with BM25 baselines.

Methods:

- `traverse_tree`
- `collapsed_tree`
- `bm25_leaf`
- `bm25_all_nodes`

V1 QA setup:

- 20 synthetic QA items.
- Questions generated from category-level patent summaries.
- Same reader and judge flow across methods.

V1 answer score results:

| Method | Avg Answer Score |
| --- | ---: |
| `collapsed_tree` | 4.25 |
| `bm25_all_nodes` | 3.30 |
| `bm25_leaf` | 2.45 |
| `traverse_tree` | 1.90 |

V1 retrieval results:

| Method | Hit Rate | MRR |
| --- | ---: | ---: |
| `traverse_tree` | 1.000 | 0.958 |
| `bm25_leaf` | 0.885 | 0.731 |
| `bm25_all_nodes` | 0.885 | 0.722 |
| `collapsed_tree` | 0.845 | 0.555 |

V1 interpretation:

- `collapsed_tree` produced the strongest answer quality.
- `traverse_tree` had the strongest retrieval hit/MRR but weak reader answer quality.
- BM25 performed well when the query contained rare technical terms that directly overlapped with patent summaries.
- V1 was useful as a baseline, but it did not separate global synthesis questions from local lookup questions.

V1 artifacts:

- `runs/patent_raptor_full_20260527_144357/report.html`
- `runs/patent_raptor_full_20260527_144357/tree_visualization.html`
- `versions/v1/README.md`

## Why V2 Was Added

V1 exposed several limitations:

- It used one broad synthetic QA style, so global synthesis and local fact lookup were mixed together.
- It compared RAPTOR mostly against BM25, without a dense retriever baseline.
- It scored each method independently, but did not clearly identify the best answer per question.
- The report was less explicit about where each answer source came from in the RAPTOR tree.

V2 addresses these limitations:

- Adds `global` and `local` QA types.
- Adds DPR as a dense retrieval baseline.
- Uses GPT-5.5 hybrid judging with both per-method scores and best-method ranking.
- Keeps source overlays so each QA answer can be inspected against the tree path.

## V2 Main Version

V2 compares four methods:

- `traverse_tree`
- `collapsed_tree`
- `bm25_leaf`
- `dpr_leaf`

V2 QA setup:

- 10 total questions.
- 5 global questions requiring cross-patent synthesis.
- 5 local questions answerable from a single patent.
- GPT-5.5 generates pseudo-gold reference answers from source patents.
- GPT-5.5 judges method answers and selects the best method per QA.

V2 answer score results:

| Method | Avg Answer Score |
| --- | ---: |
| `collapsed_tree` | 3.60 |
| `traverse_tree` | 3.30 |
| `bm25_leaf` | 3.00 |
| `dpr_leaf` | 2.70 |

V2 answer score by question type:

| Question Type | Best Method | Score |
| --- | --- | ---: |
| Global | `traverse_tree` | 4.80 |
| Local | `collapsed_tree` | 3.20 |

V2 retrieval results:

| Method | Hit Rate | MRR |
| --- | ---: | ---: |
| `traverse_tree` | 1.000 | 0.958 |
| `bm25_leaf` | 0.885 | 0.731 |
| `collapsed_tree` | 0.845 | 0.555 |
| `dpr_leaf` | 0.745 | 0.385 |

V2 interpretation:

- V2 is the better final report because it tests both global and local retrieval behavior.
- `traverse_tree` was strongest for global synthesis questions.
- `collapsed_tree` was the most stable local-answer method.
- DPR underperformed on this patent corpus, especially for local patent lookup.
- BM25 remained competitive when exact technical terms appeared in the query.

V2 artifacts:

- `runs/patent_raptor_v2_20260527_221004/report.html`
- `runs/patent_raptor_v2_20260527_221004/tree_visualization.html`
- `versions/v2/README.md`

## V3 Main Version

V3 changes the comparison to match the RAPTOR paper's controlled setup more closely: each retriever is evaluated **without RAPTOR** on leaf patents and **with RAPTOR** on the flattened full tree.

Main V3 methods:

- `bm25_without_raptor`
- `bm25_with_raptor`
- `dense_bge_m3_without_raptor`
- `dense_bge_m3_with_raptor`

Optional auxiliary methods:

- `dpr_without_raptor`
- `dpr_with_raptor`

V3 design choices:

- The paper's DPR baseline is treated as a dense retriever concept; this patent corpus is Korean/English mixed, so the main dense retriever is `BAAI/bge-m3`.
- Meta DPR remains available only as a V2 continuity baseline.
- `traverse_tree` is not part of the V3 main table.
- Metrics are split into Global and Local QA tables with `Accuracy`, `Recall@k`, `F1@k`, and `Avg Judge Score`.
- MRR is still written to raw CSV for diagnostics but is not a V3 main report metric.
- Appendix E is strengthened with child-text faithfulness audit, optional summary repair, and propagation checking.
- BM25 analysis remains because patent documents often reward rare exact technical terms.

V3 artifacts:

- `runs/patent_raptor_v3_<timestamp>/report.html`
- `runs/patent_raptor_v3_<timestamp>/report_print.html`
- `runs/patent_raptor_v3_<timestamp>/report_compact_print.html`
- `runs/patent_raptor_v3_<timestamp>/tree_visualization.html`
- `runs/patent_raptor_v3_<timestamp>/retrieval_visualization.html`
- `versions/v3/README.md`

## Implementation

The experiment code includes:

- Hard K-means RAPTOR tree building.
- Structured retrieval helpers for Traverse Tree, Collapsed Tree, and V3 with/without RAPTOR evaluation.
- BM25 leaf and all-node baselines.
- BGE-M3 dense leaf and all-node baselines.
- Optional DPR leaf and all-node baselines.
- Codex proxy adapter for OpenAI-compatible local LLM calls.
- GPT-5.5 faithfulness audit and summary repair for Appendix E.
- Progress reporter with elapsed time, rolling ETA, and expected end time.
- HTML report, print reports, tree visualization, and retrieval-specific visualization generation.

## Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run a dependency-light smoke test:

```bash
python scripts/run_patent_raptor_experiment.py \
  --experiment-version v3 \
  --smoke \
  --skip-llm \
  --embedding-backend hash \
  --include-dpr-baseline \
  --dpr-backend hash
```

Run a V3 full experiment:

```bash
python scripts/run_patent_raptor_experiment.py \
  --experiment-version v3 \
  --embedding-backend sentence-transformers \
  --dense-model BAAI/bge-m3 \
  --include-dpr-baseline \
  --progress-interval-seconds 60
```

## Repository Safety

The public repository excludes:

- Raw patent CSV data.
- Local proxy health files containing local machine paths.
- Pickled tree artifacts.
- Python caches and local backup/smoke runs.

Only reproducible code, report artifacts, sampled JSONL data, and evaluation outputs are committed.

## Version Notes

- V1: RAPTOR Traverse/Collapsed Tree vs BM25 comparison on 20 synthetic QA items.
- V2: Global/Local QA, DPR baseline, four-method answer comparison, and GPT-5.5 hybrid best-method judging.
- V3: Paper-aligned with/without RAPTOR comparison, BGE-M3 dense retrieval, Global/Local quantitative tables, retrieval-specific visualization, and Appendix E audit/repair.
