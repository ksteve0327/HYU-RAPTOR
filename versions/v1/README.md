# RAPTOR Patent Experiment V1

V1 is the first experiment report for the patent RAPTOR pipeline.

## Setup

- Input sample: 200 patents, 50 each from four `중분류` groups.
- Indexed text: `요약`.
- Metadata retained: `patent_id`, `중분류`, `중분류명`.
- Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Clustering: hard K-means RAPTOR tree, target cluster size around 7.
- Reader/judge/summarizer: local `codex-proxy` compatible endpoint using `gpt-5.5`.

## Compared Methods

- `traverse_tree`
- `collapsed_tree`
- `bm25_leaf`
- `bm25_all_nodes`

## Artifacts

- Report: `../../runs/patent_raptor_full_20260527_144357/report.html`
- Tree visualization: `../../runs/patent_raptor_full_20260527_144357/tree_visualization.html`
- QA set: `../../runs/patent_raptor_full_20260527_144357/synthetic_qa.jsonl`
- Answer evaluation: `../../runs/patent_raptor_full_20260527_144357/answer_eval.csv`
- Retrieval evaluation: `../../runs/patent_raptor_full_20260527_144357/retrieval_eval.csv`

## Notes

V1 uses 20 synthetic QA items generated from category-level patent summaries. It is useful as the baseline for the original RAPTOR tree vs BM25 comparison. V2 extends this with Global/Local questions and DPR.
