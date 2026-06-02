# RAPTOR Patent Experiment V4-mini

V4-mini is a pilot reproduction evaluation built on top of V3. It does not rebuild the RAPTOR tree. Instead, it reuses the V3 sampled patents, RAPTOR tree, retrieval contexts, and reader answers, then recalculates open-ended answer metrics against review-sheet gold answers.

## What Changed

- V3 used LLM-generated pseudo-gold reference answers.
- V4-mini creates `qa_review_sheet.html` and `qa_review_sheet.csv` for human review.
- Accepted or edited rows become `gold_qa.jsonl`.
- `Answer F1`, `Answer Recall`, and `Answer Precision` are recalculated against `gold_reference_answer`.
- Judge pass rate remains auxiliary and is not reported as paper-style Accuracy.

## Evaluation

V4-mini keeps the same 10 QA items from V3:

- 5 `global` questions requiring cross-patent synthesis.
- 5 `local` questions answerable from one source patent.

The main metric is open-ended `Answer F1`, following the QASPER-style answer comparison direction used in the RAPTOR paper. Because the QA set is not multiple-choice, QuALITY-style Accuracy is not used as a main metric.

## Outputs

A V4-mini run writes:

- `qa_review_sheet.html`
- `qa_review_sheet.csv`
- `gold_qa.jsonl`
- `answer_eval.csv`
- `report.html`
- `report_print.html`
- `report_compact_print.html`
- `report_compact_print.pdf`
- `report_presentation.html`
- `report_presentation.pdf`
- `tree_visualization.html`
- `retrieval_visualization.html`

## Run

```bash
python scripts/build_v4_mini.py --make-pdf
```

To update the gold answers, edit `qa_review_sheet.csv` and rerun the builder with the same `--output-dir` without `--overwrite-review`.

## Interpretation

V4-mini is intended for reproduction and inspection, not for a submission-grade benchmark claim. The QA count is small, but the evaluation is clearer than V3 because the main metric is tied to a fixed gold reference answer rather than GPT judge pass/fail.
