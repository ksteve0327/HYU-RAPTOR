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

## Analysis Process

V1 was designed as a baseline to check whether RAPTOR tree retrieval can improve patent QA over lexical retrieval.

The process was:

1. Sample 50 patents from each of four `중분류` categories.
2. Build a RAPTOR tree from patent summaries.
3. Generate 20 synthetic QA items from category-level patent summaries.
4. Retrieve context with Traverse Tree, Collapsed Tree, BM25 leaf, and BM25 all-node modes.
5. Use the same reader prompt and `max_context_tokens=2000` across methods.
6. Judge answers with GPT-5.5.
7. Render a report and source-overlay tree visualization.

## Results

Average answer scores:

| Method | Avg Answer Score |
| --- | ---: |
| `collapsed_tree` | 4.25 |
| `bm25_all_nodes` | 3.30 |
| `bm25_leaf` | 2.45 |
| `traverse_tree` | 1.90 |

Retrieval metrics:

| Method | Hit Rate | MRR |
| --- | ---: | ---: |
| `traverse_tree` | 1.000 | 0.958 |
| `bm25_leaf` | 0.885 | 0.731 |
| `bm25_all_nodes` | 0.885 | 0.722 |
| `collapsed_tree` | 0.845 | 0.555 |

## Interpretation

- `collapsed_tree` gave the best answer quality because it could select useful nodes across the whole tree under the same token budget.
- `traverse_tree` had excellent retrieval hit/MRR, but its final answers were weaker because early traversal choices could pass broad or less directly useful context to the reader.
- BM25 performed well when query terms overlapped with rare patent terminology.
- V1 did not separate global synthesis questions from local lookup questions, which made it hard to explain which retrieval mode was best for which QA type.

## Artifacts

- Report: `../../runs/patent_raptor_full_20260527_144357/report.html`
- Tree visualization: `../../runs/patent_raptor_full_20260527_144357/tree_visualization.html`
- QA set: `../../runs/patent_raptor_full_20260527_144357/synthetic_qa.jsonl`
- Answer evaluation: `../../runs/patent_raptor_full_20260527_144357/answer_eval.csv`
- Retrieval evaluation: `../../runs/patent_raptor_full_20260527_144357/retrieval_eval.csv`

## Notes

V1 uses 20 synthetic QA items generated from category-level patent summaries. It is useful as the baseline for the original RAPTOR tree vs BM25 comparison. V2 extends this with Global/Local questions and DPR.
