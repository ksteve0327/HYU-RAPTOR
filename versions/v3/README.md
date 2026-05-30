# RAPTOR Patent Experiment V3

V3 is the current main experiment design. It moves away from the V1/V2 `traverse_tree` vs `collapsed_tree` framing and uses the RAPTOR paper's cleaner controlled comparison: each retriever is tested **without RAPTOR** on leaf patents and **with RAPTOR** on the flattened full RAPTOR tree.

## What Changed

- Main methods:
  - `bm25_without_raptor`
  - `bm25_with_raptor`
  - `dense_bge_m3_without_raptor`
  - `dense_bge_m3_with_raptor`
- Optional continuity methods:
  - `dpr_without_raptor`
  - `dpr_with_raptor`
- Dense retrieval uses `BAAI/bge-m3` because the patent corpus mixes Korean and English.
- Meta DPR is kept only as an auxiliary V2 continuity baseline.
- `traverse_tree` is excluded from the V3 main comparison.
- Global and Local QA are reported separately.
- Main metrics are `Accuracy`, `Recall@k`, `F1@k`, and `Avg Judge Score`; MRR is omitted from the main table.

## Evaluation

V3 keeps 10 QA items:

- 5 `global` questions requiring evidence from multiple patents or summary nodes.
- 5 `local` questions answerable from one source patent.

GPT-5.5 via codex-proxy generates reference answers and judges method answers. `Accuracy` is counted when the judge score is at least 4 and the answer is supported by retrieved context.

## Appendix E

V3 strengthens the Appendix E check:

- Parent summaries are audited against child text without the earlier `[:5000]` truncation.
- Summary nodes are sampled by seed-based stratification instead of taking the first N nodes.
- Unsupported claims can trigger up to two repair attempts during summary generation.
- The report records repair-before/after hallucination rates, layer-level audit rows, and ancestor propagation checks.

## Visualization

V3 uses method-specific visualization:

- `tree_visualization.html` shows where with-RAPTOR retrieval hits appear in the summary tree.
- `retrieval_visualization.html` shows ranked sources for every method.
- BM25 views emphasize matched terms, overlap, and IDF contribution.
- Dense/BGE-M3 views emphasize similarity ranks, score bars, and PCA-style query/source projection.

## Outputs

A full V3 run writes:

- `report.html`
- `report_print.html`
- `report_compact_print.html`
- `tree_visualization.html`
- `retrieval_visualization.html`
- `answer_eval.csv`
- `retrieval_eval.csv`
- `appendix_e_audit.csv`
- `appendix_e_propagation_audit.csv`

## Run

Smoke test:

```bash
python scripts/run_patent_raptor_experiment.py \
  --experiment-version v3 \
  --smoke \
  --skip-llm \
  --embedding-backend hash \
  --include-dpr-baseline \
  --dpr-backend hash
```

Full experiment:

```bash
python scripts/run_patent_raptor_experiment.py \
  --experiment-version v3 \
  --embedding-backend sentence-transformers \
  --dense-model BAAI/bge-m3 \
  --include-dpr-baseline \
  --progress-interval-seconds 60
```

The default full-run ETA starts at about 3 hours and is replaced by rolling ETA as stages report progress.
