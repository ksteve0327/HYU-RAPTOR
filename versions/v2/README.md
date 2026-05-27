# RAPTOR Patent Experiment V2

V2 is the main experiment version.

## Setup

- Base data: same 200 sampled patent summaries from V1.
- RAPTOR tree: reused from V1 for consistent comparison.
- QA set: 10 total questions.
  - 5 `global` questions for cross-patent synthesis.
  - 5 `local` questions for single-patent lookup.
- Reader/judge: `gpt-5.5` through a local OpenAI-compatible `codex-proxy` endpoint.
- Judge mode: hybrid scoring plus best-method ranking.

## Compared Methods

- `traverse_tree`
- `collapsed_tree`
- `bm25_leaf`
- `dpr_leaf`

## Headline Metrics

Average answer scores:

- `collapsed_tree`: 3.60
- `traverse_tree`: 3.30
- `bm25_leaf`: 3.00
- `dpr_leaf`: 2.70

By question type:

- Global: `traverse_tree` was strongest.
- Local: `collapsed_tree` was most stable.

Retrieval metrics on 200 title/AI-summary queries:

- `traverse_tree`: hit 1.000, MRR 0.958
- `bm25_leaf`: hit 0.885, MRR 0.731
- `collapsed_tree`: hit 0.845, MRR 0.555
- `dpr_leaf`: hit 0.745, MRR 0.385

## Artifacts

- Report: `../../runs/patent_raptor_v2_20260527_221004/report.html`
- Tree visualization: `../../runs/patent_raptor_v2_20260527_221004/tree_visualization.html`
- QA set: `../../runs/patent_raptor_v2_20260527_221004/synthetic_qa.jsonl`
- Answer evaluation: `../../runs/patent_raptor_v2_20260527_221004/answer_eval.csv`
- Retrieval evaluation: `../../runs/patent_raptor_v2_20260527_221004/retrieval_eval.csv`

## Interpretation

V2 is better suited as the final report because it tests both global and local retrieval behavior and adds DPR as a neural retrieval baseline. DPR underperformed in this corpus, while RAPTOR tree methods were stronger for synthesis-heavy questions.
