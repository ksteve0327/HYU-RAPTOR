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

## What V1 Did Not Explain Well

V1 showed that RAPTOR and BM25 behave differently, but several questions remained:

- The QA set mixed broad synthesis questions and narrow patent lookup questions.
- There was no dense retrieval baseline.
- BM25 all-node retrieval was useful for lexical overlap analysis, but it did not answer whether a neural dense retriever could compete.
- The report gave method scores, but did not clearly show which answer was best for each individual question.

## V2 Improvements

V2 was built to address those gaps:

- Splits QA into `global` and `local` questions.
- Adds `dpr_leaf` as a dense retrieval baseline.
- Keeps `bm25_leaf` as the lexical baseline.
- Uses GPT-5.5 to judge each method and select a best method per QA.
- Adds source overlays so the retrieved answer path can be inspected in the RAPTOR tree visualization.

## Analysis Process

The V2 process was:

1. Reuse the same 200 sampled patents and RAPTOR tree from V1.
2. Generate 5 global questions from parent summary/source patent groups.
3. Generate 5 local questions from individual patent leaf summaries.
4. Retrieve context with Traverse Tree, Collapsed Tree, BM25 leaf, and DPR leaf.
5. Generate reader answers from the retrieved context.
6. Score each answer with GPT-5.5 against a pseudo-gold reference answer.
7. Ask GPT-5.5 to rank the four method answers for each QA item.
8. Render the final HTML report and source path overlays.

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

The main findings are:

- For global synthesis, `traverse_tree` worked best because top-down traversal retained high-level summary structure.
- For local lookup, `collapsed_tree` was more stable because it could choose directly relevant leaf or summary nodes from the flattened tree.
- `dpr_leaf` did not outperform RAPTOR or BM25 on this dataset, likely because the patent questions often contain exact technical terms and patent-specific phrasing.
- `bm25_leaf` remained useful for rare-term queries, but it was less robust for synthesis questions.
