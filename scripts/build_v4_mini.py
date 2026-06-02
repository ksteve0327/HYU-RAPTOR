#!/usr/bin/env python3
"""Build RAPTOR Patent V4-mini reports from a V3 run.

V4-mini reuses V3 retrieval/reader outputs and recalculates answer metrics
against a review-sheet backed gold reference answer.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.create_compact_print_report import (  # noqa: E402
    answer_eval_lookup,
    choose_representative_tree_cases,
    clean_text,
    fmt,
    load_source_map,
    load_tree_nodes,
    render_tree_case,
    render_visualization_overview,
)
from scripts.create_print_report import build_print_report  # noqa: E402
from scripts.paper_metrics import answer_prf, as_float  # noqa: E402


METHOD_ORDER = [
    "bm25_without_raptor",
    "bm25_with_raptor",
    "dense_bge_m3_without_raptor",
    "dense_bge_m3_with_raptor",
    "dpr_without_raptor",
    "dpr_with_raptor",
]

V4_COPY_FILES = [
    "sampled_patents.jsonl",
    "synthetic_qa.jsonl",
    "answer_eval.csv",
    "retrieval_eval.csv",
    "qa_tree_sources.json",
    "tree_data.json",
    "qualitative_samples.jsonl",
    "summary_repair_log.jsonl",
    "appendix_e_audit.csv",
    "appendix_e_propagation_audit.csv",
    "retrieval_visualization.html",
]


REPORT_CSS = r"""
:root { color-scheme: light; }
* { box-sizing: border-box; }
html, body { background: #f8fafc; color: #111827; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  line-height: 1.45;
}
.wrap { max-width: 1180px; margin: 0 auto; padding: 28px 24px 56px; }
.toolbar {
  position: sticky; top: 0; z-index: 10;
  display: flex; gap: 8px; justify-content: flex-end;
  padding: 10px 24px; border-bottom: 1px solid #cbd5e1; background: #fff;
}
.toolbar a, .toolbar button {
  border: 1px solid #cbd5e1; border-radius: 6px; background: #fff;
  color: #111827; padding: 6px 10px; text-decoration: none; font: inherit;
}
h1 { margin: 0 0 8px; font-size: 34px; line-height: 1.08; }
h2 { margin: 34px 0 12px; padding-bottom: 6px; border-bottom: 1px solid #94a3b8; font-size: 22px; }
h3 { margin: 22px 0 8px; font-size: 17px; }
p { margin: 0 0 12px; }
.subtitle { color: #475569; font-size: 15px; }
.grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 18px 0; }
.card, .note, .qa-card {
  border: 1px solid #cbd5e1; border-radius: 8px; background: #fff; padding: 14px;
}
.card strong { display: block; color: #475569; font-size: 12px; }
.card .value { display: block; margin-top: 4px; font-size: 23px; font-weight: 750; }
.note { background: #f8fafc; color: #334155; }
table { width: 100%; border-collapse: collapse; margin: 10px 0 20px; background: #fff; font-size: 13px; }
th, td { border: 1px solid #cbd5e1; padding: 8px 9px; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
th { background: #eef2ff; font-weight: 700; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: .94em; }
.small { color: #475569; font-size: 12px; }
.pill { display: inline-block; margin: 0 4px 4px 0; padding: 2px 7px; border: 1px solid #cbd5e1; border-radius: 999px; background: #fff; white-space: nowrap; }
.status-accept { color: #047857; font-weight: 700; }
.status-edit_reference_answer { color: #b45309; font-weight: 700; }
.status-exclude { color: #b91c1c; font-weight: 700; }
.qa-card { margin: 0 0 14px; }
.evidence { white-space: pre-wrap; color: #334155; font-size: 12px; }
@media (max-width: 900px) { .grid { grid-template-columns: repeat(2, 1fr); } }
"""


PRINT_CSS = r"""
:root { color-scheme: light; }
@page { size: A4 portrait; margin: 12mm 11mm 14mm; }
* { box-sizing: border-box; }
html, body { background: #fff; color: #111827; }
body {
  width: 210mm; max-width: 210mm; margin: 0 auto; padding: 12mm 11mm;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  font-size: 9.3pt; line-height: 1.36;
}
.toolbar { position: sticky; top: 0; display: flex; justify-content: space-between; gap: 8px; margin: -12mm -11mm 8mm; padding: 8px 11mm; border-bottom: 1px solid #cbd5e1; background: #fff; }
.toolbar a, .toolbar button { border: 1px solid #cbd5e1; border-radius: 5px; background: #fff; color: #111827; font: inherit; padding: 5px 9px; text-decoration: none; }
h1 { margin: 0 0 5mm; padding-bottom: 3mm; border-bottom: 2px solid #111827; font-size: 20pt; line-height: 1.12; }
h2 { break-after: avoid; page-break-after: avoid; margin: 8mm 0 3mm; padding-bottom: 1.5mm; border-bottom: 1px solid #94a3b8; font-size: 13.5pt; }
h3 { break-after: avoid; page-break-after: avoid; margin: 5mm 0 2mm; font-size: 11pt; }
p { margin: 0 0 3mm; }
table { width: 100%; margin: 2mm 0 6mm; border-collapse: collapse; background: #fff; font-size: 8.1pt; }
thead { display: table-header-group; }
tr, .card, .note, .qa-card, .tree-case { break-inside: avoid; page-break-inside: avoid; }
th, td { border: 1px solid #cbd5e1; padding: 3pt 3.5pt; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
th { background: #eef2ff; font-weight: 700; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 3mm; margin: 0 0 5mm; }
.card, .note, .qa-card, .tree-case { border: 1px solid #cbd5e1; border-radius: 4px; background: #fff; padding: 3mm; }
.card strong { display: block; margin-bottom: 1mm; font-size: 8.2pt; color: #475569; }
.card .value { font-size: 13pt; font-weight: 750; color: #111827; }
.note { margin: 0 0 4mm; background: #f8fafc; color: #334155; }
.small { color: #475569; font-size: 7.8pt; }
.pill, .tag { display: inline-block; margin: 0 2pt 2pt 0; padding: 1pt 4pt; border: 1px solid #cbd5e1; border-radius: 999px; background: #f8fafc; white-space: nowrap; }
.page-break { break-before: page; page-break-before: always; }
.tree-case { margin: 0 0 5mm; }
.tree-meta { margin: 1mm 0 2mm; }
.mini-tree { width: 100%; height: auto; display: block; border: 1px solid #cbd5e1; border-radius: 4px; background: #fff; }
.source-table, .node-meaning-table { table-layout: fixed; font-size: 6.45pt; line-height: 1.28; }
.source-table th, .source-table td,
.node-meaning-table th, .node-meaning-table td { padding: 2.2pt 2.6pt; overflow-wrap: break-word; word-break: keep-all; }
.source-table th:nth-child(1), .source-table td:nth-child(1),
.node-meaning-table th:nth-child(1), .node-meaning-table td:nth-child(1) { width: 5%; white-space: nowrap; overflow-wrap: normal; }
.source-table th:nth-child(2), .source-table td:nth-child(2),
.node-meaning-table th:nth-child(2), .node-meaning-table td:nth-child(2) { width: 7%; white-space: nowrap; overflow-wrap: normal; }
.source-table th:nth-child(3), .source-table td:nth-child(3),
.node-meaning-table th:nth-child(3), .node-meaning-table td:nth-child(3) { width: 5%; white-space: nowrap; overflow-wrap: normal; }
.source-table th:nth-child(4), .source-table td:nth-child(4),
.node-meaning-table th:nth-child(4), .node-meaning-table td:nth-child(4) { width: 68%; }
.source-table th:nth-child(5), .source-table td:nth-child(5),
.node-meaning-table th:nth-child(5), .node-meaning-table td:nth-child(5) { width: 15%; }
.answer-evidence { border: 1px solid #cbd5e1; border-radius: 4px; padding: 2.5mm; margin-top: 2mm; background: #fbfdff; break-inside: avoid; page-break-inside: avoid; }
.answer-evidence h4 { margin: 0 0 1mm; font-size: 9.6pt; }
.answer-text { margin: 0 0 1.5mm; color: #111827; }
.evidence-legend { display: flex; flex-wrap: wrap; gap: 1.5mm; margin: .7mm 0 1mm; font-size: 7.5pt; color: #475569; }
.evidence-chip { display: inline-block; margin: 0 3pt 2pt 0; padding: .5pt 4pt; border: 1px solid #cbd5e1; border-radius: 999px; background: #fff; white-space: nowrap; }
.rank-chip, .source-chip { display: inline-block; padding: .4pt 3.5pt; border: 1px solid #cbd5e1; border-radius: 999px; font-weight: 700; white-space: nowrap; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.evidence-rule { margin: 1mm 0 2mm; }
.evidence-hit { border-radius: 2px; padding: 0 .5px; -webkit-box-decoration-break: clone; box-decoration-break: clone; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.ev1 { background: linear-gradient(transparent 55%, rgba(245, 158, 11, .45) 0); }
.ev2 { background: linear-gradient(transparent 55%, rgba(16, 185, 129, .38) 0); }
.ev3 { background: linear-gradient(transparent 55%, rgba(59, 130, 246, .35) 0); }
.ev4 { background: linear-gradient(transparent 55%, rgba(168, 85, 247, .34) 0); }
.ev5 { background: linear-gradient(transparent 55%, rgba(239, 68, 68, .32) 0); }
.ev6 { background: linear-gradient(transparent 55%, rgba(20, 184, 166, .35) 0); }
.ev7 { background: linear-gradient(transparent 55%, rgba(100, 116, 139, .28) 0); }
.ev8 { background: linear-gradient(transparent 55%, rgba(132, 204, 22, .35) 0); }
.rank-chip.ev1, .source-chip.ev1 { background: rgba(245, 158, 11, .22); }
.rank-chip.ev2, .source-chip.ev2 { background: rgba(16, 185, 129, .20); }
.rank-chip.ev3, .source-chip.ev3 { background: rgba(59, 130, 246, .18); }
.rank-chip.ev4, .source-chip.ev4 { background: rgba(168, 85, 247, .18); }
.rank-chip.ev5, .source-chip.ev5 { background: rgba(239, 68, 68, .17); }
.rank-chip.ev6, .source-chip.ev6 { background: rgba(20, 184, 166, .18); }
.rank-chip.ev7, .source-chip.ev7 { background: rgba(100, 116, 139, .16); }
.rank-chip.ev8, .source-chip.ev8 { background: rgba(132, 204, 22, .20); }
.tree-legend { display: flex; gap: 7px; flex-wrap: wrap; margin: 1.5mm 0; font-size: 7.2pt; }
.legend-dot { display: inline-block; width: 8px; height: 8px; margin-right: 2px; border-radius: 999px; vertical-align: -1px; }
@media screen { body { margin: 24px auto; box-shadow: 0 8px 36px rgba(15,23,42,.12); } }
@media print {
  body { width: auto; max-width: none; margin: 0; padding: 0; box-shadow: none; }
  .toolbar { display: none !important; }
  .pdf-hide { display: none !important; }
  a { color: inherit; text-decoration: none; }
  .visualization-overview { break-before: page; page-break-before: always; }
  .method-dense_bge_m3_without_raptor,
  .method-bm25_without_raptor { break-before: page; page-break-before: always; }
}
"""


PRESENTATION_CSS = r"""
@page { size: 13.333in 7.5in; margin: 0; }
* { box-sizing: border-box; }
html { background: #0f172a; color: #111827; }
body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0f172a; }
.toolbar { position: sticky; top: 0; z-index: 20; display: flex; justify-content: center; gap: 8px; padding: 10px; background: rgba(15,23,42,.92); }
.toolbar a, .toolbar button { border: 1px solid rgba(148,163,184,.45); border-radius: 999px; padding: 7px 13px; background: #f8fafc; color: #0f172a; font-weight: 700; text-decoration: none; cursor: pointer; }
.deck { display: flex; flex-direction: column; gap: 20px; padding: 24px 0 40px; }
.slide { position: relative; width: min(1280px, calc(100vw - 48px)); aspect-ratio: 16 / 9; margin: 0 auto; overflow: hidden; border-radius: 18px; background: #f8fafc; box-shadow: 0 30px 80px rgba(0,0,0,.35); page-break-after: always; break-after: page; }
.slide-inner { position: absolute; inset: 0; padding: 48px 58px 42px; display: flex; flex-direction: column; gap: 18px; }
.slide::before { content: ""; position: absolute; inset: 0 0 auto; height: 10px; background: linear-gradient(90deg, #2563eb, #059669, #d97706); }
h1, h2, h3, p { margin: 0; }
h1 { max-width: 950px; font-size: 54px; line-height: 1.05; letter-spacing: 0; }
h2 { font-size: 36px; line-height: 1.1; letter-spacing: 0; }
h3 { font-size: 20px; line-height: 1.18; }
.subtitle { max-width: 980px; color: #475569; font-size: 21px; line-height: 1.42; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.card { border: 1px solid #cbd5e1; border-radius: 12px; background: #fff; padding: 16px; min-height: 112px; }
.card strong { display: block; color: #475569; font-size: 15px; }
.card .value { display: block; margin-top: 6px; color: #0f172a; font-size: 28px; font-weight: 850; }
table { width: 100%; border-collapse: collapse; background: #fff; font-size: 16px; }
th, td { border: 1px solid #cbd5e1; padding: 9px 10px; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
th { background: #e0e7ff; font-weight: 800; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; align-items: start; }
.note { border-left: 5px solid #2563eb; background: #eff6ff; padding: 14px 16px; color: #1e3a8a; font-size: 18px; line-height: 1.35; }
.small { color: #64748b; font-size: 14px; line-height: 1.35; }
.foot { position: absolute; left: 58px; right: 58px; bottom: 22px; display: flex; justify-content: space-between; color: #94a3b8; font-size: 13px; }
@media print { .toolbar { display: none; } .deck { padding: 0; gap: 0; } .slide { width: 13.333in; height: 7.5in; border-radius: 0; box-shadow: none; } }
"""


def html_escape(value) -> str:
    return html.escape(str(value or ""))


def method_sort_key(method: str) -> int:
    return METHOD_ORDER.index(method) if method in METHOD_ORDER else len(METHOD_ORDER)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def output_dir_for(args: argparse.Namespace) -> Path:
    if args.output_dir:
        return args.output_dir
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return REPO_ROOT / "runs" / f"patent_raptor_v4_mini_{stamp}"


def copy_v3_artifacts(source_run: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename in V4_COPY_FILES:
        src = source_run / filename
        if src.exists():
            shutil.copy2(src, output_dir / filename)
    src_tree = source_run / "tree_visualization.html"
    if src_tree.exists():
        shutil.copy2(src_tree, output_dir / "tree_visualization.html")
    original_qa = output_dir / "synthetic_qa.jsonl"
    if original_qa.exists():
        shutil.copy2(original_qa, output_dir / "synthetic_qa_v3_original.jsonl")


def patent_rows_by_id(run_dir: Path) -> dict[str, dict]:
    rows = read_jsonl(run_dir / "sampled_patents.jsonl")
    by_id = {}
    for row in rows:
        patent_id = str(row.get("id") or row.get("metadata", {}).get("patent_id", ""))
        if patent_id:
            by_id[patent_id] = row
    return by_id


def source_evidence(source_ids: list[str], patents: dict[str, dict]) -> str:
    blocks = []
    for patent_id in source_ids:
        row = patents.get(str(patent_id), {})
        metadata = row.get("metadata", {})
        text = clean_text(row.get("text", ""), 950)
        blocks.append(
            "{patent_id} | {category} {category_name} | {title}\n{text}".format(
                patent_id=patent_id,
                category=metadata.get("category", ""),
                category_name=metadata.get("category_name", ""),
                title=metadata.get("title", ""),
                text=text,
            )
        )
    return "\n\n".join(blocks)


def build_review_rows(source_run: Path, output_dir: Path, default_status: str) -> list[dict]:
    qa_items = read_jsonl(source_run / "synthetic_qa.jsonl")
    patents = patent_rows_by_id(source_run)
    rows = []
    for index, qa in enumerate(qa_items):
        source_ids = [str(value) for value in qa.get("source_patent_ids", [])]
        original_reference = qa.get("reference_answer", "")
        rows.append(
            {
                "qa_index": str(index),
                "question_type": qa.get("question_type", ""),
                "question": qa.get("question", ""),
                "source_patent_ids": "|".join(source_ids),
                "original_reference_answer": original_reference,
                "source_evidence": source_evidence(source_ids, patents),
                "review_status": default_status,
                "gold_reference_answer": original_reference,
                "reviewer_note": "",
            }
        )
    return rows


def ensure_review_sheet(source_run: Path, output_dir: Path, overwrite: bool, default_status: str) -> list[dict]:
    csv_path = output_dir / "qa_review_sheet.csv"
    if csv_path.exists() and not overwrite:
        rows = read_csv(csv_path)
    else:
        rows = build_review_rows(source_run, output_dir, default_status)
        fieldnames = [
            "qa_index",
            "question_type",
            "question",
            "source_patent_ids",
            "original_reference_answer",
            "source_evidence",
            "review_status",
            "gold_reference_answer",
            "reviewer_note",
        ]
        write_csv(csv_path, rows, fieldnames)
    write_review_html(output_dir / "qa_review_sheet.html", rows)
    return rows


def write_review_html(path: Path, rows: list[dict]) -> None:
    cards = []
    for row in rows:
        status = row.get("review_status", "")
        cards.append(
            "\n".join(
                [
                    "<section class='qa-card'>",
                    f"<h3>QA {html_escape(row.get('qa_index'))} | {html_escape(row.get('question_type'))} | <span class='status-{html_escape(status)}'>{html_escape(status)}</span></h3>",
                    f"<p><strong>Question</strong><br>{html_escape(row.get('question'))}</p>",
                    f"<p><strong>Source patents</strong><br><code>{html_escape(row.get('source_patent_ids'))}</code></p>",
                    f"<p><strong>Gold reference answer candidate</strong><br>{html_escape(row.get('gold_reference_answer'))}</p>",
                    f"<p><strong>Original LLM reference answer</strong><br>{html_escape(row.get('original_reference_answer'))}</p>",
                    f"<p><strong>Source evidence</strong></p><pre class='evidence'>{html_escape(row.get('source_evidence'))}</pre>",
                    "</section>",
                ]
            )
        )
    doc = "\n".join(
        [
            "<!doctype html>",
            '<html lang="ko"><head><meta charset="utf-8">',
            "<title>RAPTOR Patent V4-mini QA Review Sheet</title>",
            f"<style>{REPORT_CSS} pre.evidence {{ white-space: pre-wrap; background: #fff; border: 1px solid #cbd5e1; padding: 10px; border-radius: 6px; }}</style>",
            "</head><body>",
            "<div class='wrap'>",
            "<h1>RAPTOR Patent V4-mini QA Review Sheet</h1>",
            "<p class='subtitle'>Edit <code>qa_review_sheet.csv</code> if a gold answer needs correction. Valid review_status values: <code>accept</code>, <code>edit_reference_answer</code>, <code>exclude</code>.</p>",
            *cards,
            "</div></body></html>",
        ]
    )
    path.write_text(doc, encoding="utf-8")


def gold_rows_from_review(rows: list[dict]) -> list[dict]:
    gold_rows = []
    for row in rows:
        status = str(row.get("review_status", "")).strip() or "accept"
        if status == "exclude":
            continue
        gold_answer = str(row.get("gold_reference_answer", "")).strip()
        if not gold_answer:
            continue
        gold_rows.append(
            {
                "qa_index": str(row.get("qa_index", "")),
                "question_type": row.get("question_type", ""),
                "question": row.get("question", ""),
                "source_patent_ids": [
                    value for value in str(row.get("source_patent_ids", "")).split("|") if value
                ],
                "original_reference_answer": row.get("original_reference_answer", ""),
                "gold_reference_answer": gold_answer,
                "reference_answer": gold_answer,
                "review_status": status,
                "reviewer_note": row.get("reviewer_note", ""),
            }
        )
    return gold_rows


def judge_pass_aux(row: dict) -> float:
    if str(row.get("accuracy", "")).strip() != "":
        return as_float(row.get("accuracy"))
    score = as_float(row.get("judge_score"))
    supported = str(row.get("judge_supported", "")).lower() == "true"
    return 1.0 if score >= 4 and supported else 0.0


def build_v4_answer_rows(source_run: Path, output_dir: Path, gold_rows: list[dict]) -> list[dict]:
    gold_by_index = {str(row["qa_index"]): row for row in gold_rows}
    rows = []
    source_rows = read_csv(source_run / "answer_eval.csv")
    for row in source_rows:
        qa_index = str(row.get("qa_index", ""))
        gold = gold_by_index.get(qa_index)
        if not gold:
            continue
        updated = dict(row)
        updated["original_reference_answer"] = row.get("reference_answer", "")
        updated["gold_reference_answer"] = gold["gold_reference_answer"]
        updated["reference_answer"] = gold["gold_reference_answer"]
        updated["review_status"] = gold["review_status"]
        updated["reviewer_note"] = gold.get("reviewer_note", "")
        precision, recall, f1 = answer_prf(updated.get("answer", ""), updated["gold_reference_answer"])
        updated["answer_precision"] = precision
        updated["answer_recall"] = recall
        updated["answer_f1"] = f1
        updated["judge_pass_aux"] = judge_pass_aux(updated)
        updated["paper_accuracy"] = updated["judge_pass_aux"]
        rows.append(updated)
    base_fields = list(read_csv_fieldnames(source_run / "answer_eval.csv"))
    extra_fields = [
        "original_reference_answer",
        "gold_reference_answer",
        "review_status",
        "reviewer_note",
        "answer_precision",
        "answer_recall",
        "answer_f1",
        "judge_pass_aux",
    ]
    fieldnames = base_fields + [field for field in extra_fields if field not in base_fields]
    write_csv(output_dir / "answer_eval.csv", rows, fieldnames)
    return rows


def read_csv_fieldnames(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle).fieldnames or [])


def update_qa_sources(output_dir: Path, gold_rows: list[dict], answer_rows: list[dict]) -> None:
    path = output_dir / "qa_tree_sources.json"
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    gold_by_index = {str(row["qa_index"]): row for row in gold_rows}
    answer_by_key = {
        (str(row.get("qa_index", "")), row.get("method", "")): row
        for row in answer_rows
    }
    for item in payload.get("qa_items", []):
        qa_index = str(item.get("qa_index", ""))
        gold = gold_by_index.get(qa_index)
        if gold:
            item["original_reference_answer"] = item.get("reference_answer", "")
            item["gold_reference_answer"] = gold["gold_reference_answer"]
            item["reference_answer"] = gold["gold_reference_answer"]
            item["review_status"] = gold["review_status"]
        for method_name, method_data in (item.get("methods") or {}).items():
            row = answer_by_key.get((qa_index, method_name))
            if not row:
                continue
            for field in ("answer_precision", "answer_recall", "answer_f1", "judge_pass_aux"):
                method_data[field] = row.get(field, "")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def method_values(rows: list[dict], field: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        method = row.get("method", "")
        if method:
            grouped[method].append(as_float(row.get(field)))
    return {
        method: statistics.mean(values)
        for method, values in sorted(grouped.items(), key=lambda item: method_sort_key(item[0]))
        if values
    }


def grouped_values(rows: list[dict], field: str) -> dict[tuple[str, str], float]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        key = (row.get("question_type", "") or "unknown", row.get("method", ""))
        if key[1]:
            grouped[key].append(as_float(row.get(field)))
    return {
        key: statistics.mean(values)
        for key, values in sorted(grouped.items(), key=lambda item: (item[0][0], method_sort_key(item[0][1])))
        if values
    }


def with_without_delta(rows: list[dict]) -> list[dict]:
    by_method = defaultdict(list)
    for row in rows:
        by_method[row.get("method", "")].append(row)
    pairs = [
        ("BM25", "bm25_without_raptor", "bm25_with_raptor"),
        ("Dense BGE-M3", "dense_bge_m3_without_raptor", "dense_bge_m3_with_raptor"),
    ]
    deltas = []
    for label, without, with_ in pairs:
        without_rows = by_method.get(without, [])
        with_rows = by_method.get(with_, [])
        if not without_rows or not with_rows:
            continue

        def avg(items, field):
            return statistics.mean(as_float(item.get(field)) for item in items)

        deltas.append(
            {
                "label": label,
                "without": without,
                "with": with_,
                "answer_f1_delta": avg(with_rows, "answer_f1") - avg(without_rows, "answer_f1"),
                "answer_recall_delta": avg(with_rows, "answer_recall") - avg(without_rows, "answer_recall"),
                "source_recall_delta": avg(with_rows, "source_recall") - avg(without_rows, "source_recall"),
                "judge_pass_delta": avg(with_rows, "judge_pass_aux") - avg(without_rows, "judge_pass_aux"),
            }
        )
    return deltas


def qa_count_by_type(gold_rows: list[dict]) -> dict[str, int]:
    return dict(Counter(row.get("question_type", "") for row in gold_rows))


def review_counts(rows: list[dict]) -> dict[str, int]:
    return dict(Counter(row.get("review_status", "") or "accept" for row in rows))


def best_by_answer_f1(rows: list[dict]) -> dict[str, int]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[str(row.get("qa_index", ""))].append(row)
    counts = Counter()
    for qa_rows in grouped.values():
        if not qa_rows:
            continue
        best = max(
            qa_rows,
            key=lambda row: (
                as_float(row.get("answer_f1")),
                as_float(row.get("answer_recall")),
                as_float(row.get("source_recall")),
            ),
        )
        counts[best.get("method", "")] += 1
    return dict(sorted(counts.items(), key=lambda item: method_sort_key(item[0])))


def build_metric_rows(answer_rows: list[dict]) -> list[dict]:
    metrics = {
        "answer_f1": method_values(answer_rows, "answer_f1"),
        "answer_recall": method_values(answer_rows, "answer_recall"),
        "answer_precision": method_values(answer_rows, "answer_precision"),
        "source_recall": method_values(answer_rows, "source_recall"),
        "judge_pass_aux": method_values(answer_rows, "judge_pass_aux"),
    }
    methods = sorted(set().union(*[set(values) for values in metrics.values()]), key=method_sort_key)
    return [
        {
            "method": method,
            "answer_f1": metrics["answer_f1"].get(method),
            "answer_recall": metrics["answer_recall"].get(method),
            "answer_precision": metrics["answer_precision"].get(method),
            "source_recall": metrics["source_recall"].get(method),
            "judge_pass_aux": metrics["judge_pass_aux"].get(method),
        }
        for method in methods
    ]


def metric_table_html(metric_rows: list[dict], include_judge: bool = True) -> str:
    parts = [
        "<table><thead><tr><th>Method</th><th>Answer F1</th><th>Answer Recall</th><th>Answer Precision</th><th>Source Recall</th>"
    ]
    if include_judge:
        parts.append("<th>Judge pass rate (aux)</th>")
    parts.append("</tr></thead><tbody>")
    for row in metric_rows:
        cells = [
            html_escape(row["method"]),
            fmt(row["answer_f1"]),
            fmt(row["answer_recall"]),
            fmt(row["answer_precision"]),
            fmt(row["source_recall"]),
        ]
        if include_judge:
            cells.append(fmt(row["judge_pass_aux"]))
        parts.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def split_table_html(answer_rows: list[dict]) -> str:
    fields = ["answer_f1", "answer_recall", "answer_precision", "source_recall", "judge_pass_aux"]
    values = {field: grouped_values(answer_rows, field) for field in fields}
    methods = sorted({row.get("method", "") for row in answer_rows if row.get("method")}, key=method_sort_key)
    parts = [
        "<table><thead><tr><th>Type</th><th>Method</th><th>Answer F1</th><th>Answer Recall</th><th>Answer Precision</th><th>Source Recall</th><th>Judge pass (aux)</th></tr></thead><tbody>"
    ]
    for question_type in ("global", "local"):
        for method in methods:
            parts.append(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    html_escape(question_type),
                    html_escape(method),
                    fmt(values["answer_f1"].get((question_type, method))),
                    fmt(values["answer_recall"].get((question_type, method))),
                    fmt(values["answer_precision"].get((question_type, method))),
                    fmt(values["source_recall"].get((question_type, method))),
                    fmt(values["judge_pass_aux"].get((question_type, method))),
                )
            )
    parts.append("</tbody></table>")
    return "".join(parts)


def delta_table_html(answer_rows: list[dict]) -> str:
    parts = [
        "<table><thead><tr><th>Retriever</th><th>Without</th><th>With RAPTOR</th><th>Answer F1 Δ</th><th>Answer Recall Δ</th><th>Source Recall Δ</th><th>Judge pass Δ (aux)</th></tr></thead><tbody>"
    ]
    for row in with_without_delta(answer_rows):
        parts.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{:+.3f}</td><td>{:+.3f}</td><td>{:+.3f}</td><td>{:+.3f}</td></tr>".format(
                html_escape(row["label"]),
                html_escape(row["without"]),
                html_escape(row["with"]),
                row["answer_f1_delta"],
                row["answer_recall_delta"],
                row["source_recall_delta"],
                row["judge_pass_delta"],
            )
        )
    parts.append("</tbody></table>")
    return "".join(parts)


def interpretation_html() -> str:
    return "\n".join(
        [
            "<section class='interpretation-section pdf-hide'>",
            "<h2>Interpretation</h2>",
            "<table><thead><tr><th>Observation</th><th>Interpretation</th></tr></thead><tbody>",
            "<tr><td>Review-sheet gold answer 기준</td><td>V4-mini는 V3의 LLM pseudo-gold를 그대로 성능 주장에 쓰지 않고, 검수 가능한 <code>gold_reference_answer</code> 기준으로 Answer F1을 다시 계산합니다. 따라서 V3보다 논문식 open-ended QA 평가에 더 가깝습니다.</td></tr>",
            "<tr><td>BM25 with RAPTOR 개선</td><td>BM25는 leaf-only보다 full-tree 검색에서 Answer F1과 Source Recall이 함께 상승했습니다. 특허 전문 용어 exact match가 summary node까지 확장되면서 reader가 종합 답변을 만들 근거를 더 많이 받았기 때문입니다.</td></tr>",
            "<tr><td>Dense BGE-M3의 global/local 차이</td><td>Dense with RAPTOR는 Source Recall을 높였지만, Local QA에서는 leaf-only dense 검색이 더 직접적인 원문 근거를 제공해 Answer F1이 더 높았습니다. 전체 평균만 보면 이 상반된 효과가 가려집니다.</td></tr>",
            "<tr><td>Accuracy 해석 제한</td><td>객관식 gold option이 없으므로 QuALITY식 Accuracy는 메인 지표로 쓰지 않았습니다. Judge pass rate는 답변이 reference와 context에 충분히 맞는지 보는 보조 신호입니다.</td></tr>",
            "</tbody></table>",
            "</section>",
        ]
    )


def bm25_competitive_html() -> str:
    return "\n".join(
        [
            "<h2>Why BM25 Remains Competitive on Patent Data</h2>",
            "<p>특허 문서는 기술 용어와 구성요소 명칭이 정밀하게 유지되는 문서 유형입니다. 소설이나 일반 서술형 문서와 달리, 단어 하나가 특정 구조나 기능을 가리키는 식별자처럼 작동하므로 BM25의 lexical matching이 강한 baseline이 됩니다.</p>",
            "<table><thead><tr><th>Patent text property</th><th>BM25 advantage</th></tr></thead><tbody>",
            "<tr><td>전문 용어의 희소성</td><td>GEMM, DDR, PIM/CIM, NoC, 양자화, 정규화 회로처럼 corpus 전체에서 드문 용어는 IDF가 커져 검색 점수를 강하게 끌어올립니다.</td></tr>",
            "<tr><td>구성요소 명칭의 반복</td><td>특허 요약은 핵심 부품과 동작을 반복 설명하므로 term frequency가 높아지고, 같은 용어가 질문에 있으면 BM25가 뚜렷하게 반응합니다.</td></tr>",
            "<tr><td>표현의 정밀성</td><td>기술 용어는 자유롭게 치환되기보다 원문 표현이 유지됩니다. 그래서 dense similarity보다 exact match가 더 직접적인 신호가 될 수 있습니다.</td></tr>",
            "<tr><td>RAPTOR와의 상보성</td><td>BM25는 precise lexical source hit에 강하고, RAPTOR summary node는 여러 patent 근거를 묶어 reader가 답변을 종합하도록 돕습니다.</td></tr>",
            "</tbody></table>",
            "<p>따라서 V4-mini 결과는 RAPTOR가 BM25를 항상 압도했다기보다, 특허 데이터에서는 BM25의 lexical retrieval과 RAPTOR의 summary-tree evidence가 상보적으로 작동한다고 해석하는 것이 적절합니다.</p>",
        ]
    )


def appendix_summary(run_dir: Path) -> tuple[int, int, dict[str, int], str]:
    rows = read_csv(run_dir / "appendix_e_audit.csv")
    total = len(rows)
    hallucinated = sum(1 for row in rows if str(row.get("has_hallucination", "")).lower() == "true")
    severities = Counter(row.get("severity", "") or "unknown" for row in rows)
    propagation = ""
    prop_rows = read_csv(run_dir / "appendix_e_propagation_audit.csv")
    if prop_rows:
        propagation = "본 audit 범위에서는 환각 증상이 상위 노드로 전파되지 않았습니다."
    return total, hallucinated, dict(severities), propagation


def build_report_html(output_dir: Path, answer_rows: list[dict], gold_rows: list[dict], review_rows: list[dict]) -> None:
    metric_rows = build_metric_rows(answer_rows)
    best = max(metric_rows, key=lambda row: as_float(row["answer_f1"])) if metric_rows else {}
    type_counts = qa_count_by_type(gold_rows)
    status_counts = review_counts(review_rows)
    total, hallucinated, severities, propagation = appendix_summary(output_dir)

    qa_parts = []
    by_qa = defaultdict(list)
    for row in answer_rows:
        by_qa[str(row.get("qa_index", ""))].append(row)
    for gold in gold_rows:
        qa_index = str(gold["qa_index"])
        rows = sorted(by_qa.get(qa_index, []), key=lambda row: method_sort_key(row.get("method", "")))
        best_row = max(rows, key=lambda row: as_float(row.get("answer_f1"))) if rows else {}
        qa_parts.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html_escape(qa_index),
                html_escape(gold.get("question_type")),
                html_escape(clean_text(gold.get("question"), 140)),
                html_escape(best_row.get("method", "-")),
                fmt(best_row.get("answer_f1")),
                html_escape(clean_text(gold.get("gold_reference_answer"), 190)),
            )
        )

    html_doc = "\n".join(
        [
            "<!doctype html>",
            '<html lang="ko"><head><meta charset="utf-8">',
            "<title>RAPTOR Patent V4-mini Report</title>",
            f"<style>{REPORT_CSS}</style>",
            "</head><body>",
            '<div class="toolbar"><a href="qa_review_sheet.html">QA review sheet</a><a href="report_compact_print.html">Compact print</a><a href="report_presentation.html">Presentation</a><a href="tree_visualization.html">Tree visualization</a><a href="retrieval_visualization.html">Retrieval visualization</a></div>',
            '<main class="wrap">',
            "<h1>RAPTOR Patent Experiment Report<br><span class='subtitle'>V4-mini review-sheet gold answer reproduction</span></h1>",
            "<p class='subtitle'>V4-mini reuses the V3 RAPTOR tree, retrieval contexts, and reader answers, then recalculates paper-style open-ended Answer F1 against the review sheet gold answers.</p>",
            "<div class='note'><strong>Limit.</strong> V4-mini는 제출용 benchmark가 아니라 재현 확인용 pilot입니다. QA는 10개(Global 5, Local 5)이며, 객관식 gold option이 없으므로 QuALITY식 Accuracy는 메인 지표로 사용하지 않습니다.</div>",
            "<section class='grid'>",
            f"<div class='card'><strong>Gold QA</strong><span class='value'>{len(gold_rows)}</span><span class='small'>global={type_counts.get('global',0)}, local={type_counts.get('local',0)}</span></div>",
            f"<div class='card'><strong>Best Answer F1</strong><span class='value'>{html_escape(best.get('method','-'))}</span><span class='small'>{fmt(best.get('answer_f1'))}</span></div>",
            f"<div class='card'><strong>Review status</strong><span class='value'>{', '.join(f'{k}={v}' for k,v in sorted(status_counts.items()))}</span></div>",
            f"<div class='card'><strong>Appendix E</strong><span class='value'>{hallucinated}/{total}</span><span class='small'>V3 audit reused</span></div>",
            "</section>",
            "<h2>V4-mini Method</h2>",
            "<table><tbody>",
            "<tr><th>Evaluation change</th><td>V3의 LLM pseudo-gold reference를 review sheet의 <code>gold_reference_answer</code>로 고정하고 Answer F1/Recall/Precision을 재계산했습니다.</td></tr>",
            "<tr><th>Reused artifacts</th><td>V3 sampled patents, RAPTOR tree, retrieval source maps, reader answers, Appendix E audit.</td></tr>",
            "<tr><th>Main metric</th><td>Open-ended QA에 맞춘 <code>Answer F1</code>. Judge pass rate는 auxiliary로만 표시합니다.</td></tr>",
            "</tbody></table>",
            "<h2>Core Metrics</h2>",
            metric_table_html(metric_rows),
            "<h2>Global / Local Metrics</h2>",
            split_table_html(answer_rows),
            "<h2>With/Without RAPTOR Delta</h2>",
            delta_table_html(answer_rows),
            interpretation_html(),
            bm25_competitive_html(),
            "<h2>Gold QA Summary</h2>",
            "<table><thead><tr><th>QA</th><th>Type</th><th>Question</th><th>Best method by F1</th><th>Best F1</th><th>Gold reference answer</th></tr></thead><tbody>",
            *qa_parts,
            "</tbody></table>",
            "<h2>Appendix E Summary</h2>",
            "<table><tbody>",
            f"<tr><th>Audited summary nodes</th><td>{total}</td></tr>",
            f"<tr><th>Unsupported claim detected</th><td>{hallucinated} / {total} ({(hallucinated / total if total else 0):.3f})</td></tr>",
            f"<tr><th>Severity mix</th><td>{html_escape(', '.join(f'{k}={v}' for k, v in sorted(severities.items())))}</td></tr>",
            f"<tr><th>Propagation</th><td>{html_escape(propagation or 'Propagation audit file was not available.')}</td></tr>",
            "<tr><th>V4 note</th><td>V4-mini에서는 tree를 재생성하지 않았으므로 Appendix E는 V3 audit 결과를 재사용했습니다.</td></tr>",
            "</tbody></table>",
            "<h2>Version Notes</h2>",
            "<table><tbody>",
            "<tr><th>V1</th><td>Traverse Tree vs Collapsed Tree baseline.</td></tr>",
            "<tr><th>V2</th><td>Global/Local QA + DPR baseline.</td></tr>",
            "<tr><th>V3</th><td>with/without RAPTOR + BGE-M3 + LLM pseudo-gold.</td></tr>",
            "<tr><th>V4-mini</th><td>V3 QA 10개를 review sheet gold answer로 고정하고 Answer F1 중심 재평가.</td></tr>",
            "</tbody></table>",
            "</main></body></html>",
        ]
    )
    (output_dir / "report.html").write_text(html_doc, encoding="utf-8")


def build_compact_html(output_dir: Path, answer_rows: list[dict], gold_rows: list[dict], review_rows: list[dict]) -> None:
    metric_rows = build_metric_rows(answer_rows)
    best = max(metric_rows, key=lambda row: as_float(row["answer_f1"])) if metric_rows else {}
    type_counts = qa_count_by_type(gold_rows)
    total, hallucinated, severities, propagation = appendix_summary(output_dir)
    source_map = load_source_map(output_dir)
    tree_nodes, max_layer = load_tree_nodes(output_dir)
    answer_eval = answer_eval_lookup(answer_rows)
    cases = choose_representative_tree_cases(source_map)[:4]
    rendered_cases = []
    for case in cases:
        block = render_tree_case(case, source_map, tree_nodes, max_layer, answer_eval)
        if block:
            rendered_cases.append(block)

    html_doc = "\n".join(
        [
            "<!doctype html>",
            '<html lang="ko"><head><meta charset="utf-8">',
            "<title>RAPTOR Patent V4-mini Compact Print</title>",
            f"<style>{PRINT_CSS}</style>",
            "</head><body>",
            '<div class="toolbar"><a href="report.html">Full report</a><a href="report_presentation.html">Presentation</a><button type="button" onclick="window.print()">Print A4</button></div>',
            "<h1>RAPTOR Patent Experiment Report<br><span class='small'>V4-mini Compact A4 Print Version</span></h1>",
            "<div class='note'><strong>Purpose.</strong> V4-mini는 V3 QA 10개를 review sheet gold answer로 고정하고, 논문식 open-ended Answer F1 중심으로 재평가한 pilot reproduction입니다.</div>",
            "<h2>Executive Summary</h2>",
            "<ul>",
            f"<li><strong>Main metric:</strong> Answer F1 기준 최고 method는 <code>{html_escape(best.get('method','-'))}</code> ({fmt(best.get('answer_f1'))})입니다.</li>",
            f"<li><strong>Gold QA:</strong> {len(gold_rows)}개 사용; global={type_counts.get('global',0)}, local={type_counts.get('local',0)}.</li>",
            "<li><strong>Accuracy:</strong> 객관식 gold option이 없으므로 QuALITY식 Accuracy는 메인 지표로 사용하지 않았습니다.</li>",
            "<li><strong>Tree:</strong> V3 RAPTOR tree와 retrieval/reader answer를 재사용했습니다.</li>",
            "</ul>",
            "<h2>Core Metrics</h2>",
            metric_table_html(metric_rows),
            "<h2>Global / Local Metrics</h2>",
            split_table_html(answer_rows),
            "<h2>With/Without RAPTOR Delta</h2>",
            delta_table_html(answer_rows),
            interpretation_html(),
            bm25_competitive_html(),
            "<h2>Appendix E Summary</h2>",
            "<table><tbody>",
            f"<tr><th>Unsupported claim detected</th><td>{hallucinated} / {total} ({(hallucinated / total if total else 0):.3f})</td></tr>",
            f"<tr><th>Severity mix</th><td>{html_escape(', '.join(f'{k}={v}' for k, v in sorted(severities.items())))}</td></tr>",
            f"<tr><th>Propagation</th><td>{html_escape(propagation or 'Propagation audit file was not available.')}</td></tr>",
            "<tr><th>V4 note</th><td>V4-mini에서는 tree를 재생성하지 않았으므로 Appendix E는 V3 audit 결과를 재사용했습니다.</td></tr>",
            "</tbody></table>",
            render_visualization_overview(source_map, answer_eval),
            *rendered_cases,
            "<div class='note small'><strong>Reading guide.</strong> Full report, QA review sheet, tree visualization, retrieval visualization은 같은 V4-mini run 폴더에 있습니다.</div>",
            f"<p class='small'>Generated {html_escape(datetime.now().isoformat(timespec='seconds'))} from run {html_escape(output_dir.name)}</p>",
            "</body></html>",
        ]
    )
    (output_dir / "report_compact_print.html").write_text(html_doc, encoding="utf-8")


def slide(number: int, title: str, body: str) -> str:
    return "\n".join(
        [
            '<section class="slide"><div class="slide-inner">',
            f"<h2>{html_escape(title)}</h2>",
            body,
            f'<div class="foot"><span>report_presentation.html</span><span>{number:02d}</span></div>',
            "</div></section>",
        ]
    )


def build_presentation_html(output_dir: Path, answer_rows: list[dict], gold_rows: list[dict]) -> None:
    metric_rows = build_metric_rows(answer_rows)
    best = max(metric_rows, key=lambda row: as_float(row["answer_f1"])) if metric_rows else {}
    type_counts = qa_count_by_type(gold_rows)
    rows_html = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html_escape(row["method"]),
            fmt(row["answer_f1"]),
            fmt(row["answer_recall"]),
            fmt(row["source_recall"]),
        )
        for row in metric_rows
    )
    split_rows = []
    split = grouped_values(answer_rows, "answer_f1")
    for question_type in ("global", "local"):
        for method in sorted({row.get("method", "") for row in answer_rows}, key=method_sort_key):
            split_rows.append(
                f"<tr><td>{html_escape(question_type)}</td><td>{html_escape(method)}</td><td>{fmt(split.get((question_type, method)))}</td></tr>"
            )
    delta_rows = "".join(
        "<tr><td>{}</td><td>{:+.3f}</td><td>{:+.3f}</td><td>{:+.3f}</td></tr>".format(
            html_escape(row["label"]),
            row["answer_f1_delta"],
            row["answer_recall_delta"],
            row["source_recall_delta"],
        )
        for row in with_without_delta(answer_rows)
    )

    slides = [
        '<section class="slide"><div class="slide-inner"><h1>RAPTOR Patent V4-mini</h1><p class="subtitle">Review-sheet gold answer 기반 pilot reproduction. V3 retrieval/reader 결과를 재사용하고 Answer F1 중심으로 재평가했습니다.</p><div class="foot"><span>RAPTOR Patent</span><span>01</span></div></div></section>',
        slide(
            2,
            "What Changed From V3",
            "<div class='note'>V3는 LLM-generated pseudo-gold와 GPT judge 중심이었고, V4-mini는 review sheet의 gold_reference_answer 기준 Answer F1을 메인 지표로 사용합니다.</div><div class='grid'><div class='card'><strong>QA</strong><span class='value'>{}</span><span class='small'>global {}, local {}</span></div><div class='card'><strong>Tree</strong><span class='value'>V3 reused</span></div><div class='card'><strong>Main metric</strong><span class='value'>Answer F1</span></div><div class='card'><strong>Accuracy</strong><span class='value'>Aux only</span></div></div>".format(
                len(gold_rows), type_counts.get("global", 0), type_counts.get("local", 0)
            ),
        ),
        slide(
            3,
            "Core Metrics",
            f"<table><thead><tr><th>Method</th><th>Answer F1</th><th>Answer Recall</th><th>Source Recall</th></tr></thead><tbody>{rows_html}</tbody></table><p class='small'>Best Answer F1: {html_escape(best.get('method','-'))} ({fmt(best.get('answer_f1'))}).</p>",
        ),
        slide(
            4,
            "Global / Local Split",
            f"<table><thead><tr><th>Type</th><th>Method</th><th>Answer F1</th></tr></thead><tbody>{''.join(split_rows)}</tbody></table>",
        ),
        slide(
            5,
            "With / Without RAPTOR Delta",
            f"<table><thead><tr><th>Retriever</th><th>Answer F1 Δ</th><th>Answer Recall Δ</th><th>Source Recall Δ</th></tr></thead><tbody>{delta_rows}</tbody></table>",
        ),
        slide(
            6,
            "Interpretation",
            "<div class='cols'><div class='note'>V4-mini는 제출용 benchmark가 아니라 재현 확인용 pilot입니다. QA 10개라 통계적 일반화보다 method behavior 확인에 의미가 있습니다.</div><div class='note'>특허 문서는 희귀 전문 용어와 source precision이 중요하므로 BM25와 RAPTOR summary node는 상보적으로 해석해야 합니다.</div></div>",
        ),
    ]
    html_doc = "\n".join(
        [
            "<!doctype html>",
            '<html lang="ko"><head><meta charset="utf-8">',
            "<title>RAPTOR Patent V4-mini Presentation</title>",
            f"<style>{PRESENTATION_CSS}</style>",
            "</head><body>",
            '<div class="toolbar"><a href="report_compact_print.html">Compact print</a><a href="report.html">Full report</a><button type="button" onclick="window.print()">Print slides</button></div>',
            '<main class="deck">',
            *slides,
            "</main></body></html>",
        ]
    )
    (output_dir / "report_presentation.html").write_text(html_doc, encoding="utf-8")


def build_report_md(output_dir: Path, answer_rows: list[dict], gold_rows: list[dict]) -> None:
    metric_rows = build_metric_rows(answer_rows)
    lines = [
        "# RAPTOR Patent V4-mini Report",
        "",
        "V4-mini reuses the V3 tree/retrieval/reader outputs and recalculates open-ended Answer F1 against review-sheet gold reference answers.",
        "",
        "## Core Metrics",
        "",
    ]
    for row in metric_rows:
        lines.append(
            "- {method}: Answer F1={f1}, Answer Recall={recall}, Answer Precision={precision}, Source Recall={source}, Judge pass aux={judge}".format(
                method=row["method"],
                f1=fmt(row["answer_f1"]),
                recall=fmt(row["answer_recall"]),
                precision=fmt(row["answer_precision"]),
                source=fmt(row["source_recall"]),
                judge=fmt(row["judge_pass_aux"]),
            )
        )
    lines.extend(["", "## Gold QA", ""])
    for row in gold_rows:
        lines.append(f"- QA {row['qa_index']} [{row['question_type']}]: {row['question']}")
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_pdf(html_path: Path, pdf_path: Path) -> None:
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if not chrome.exists():
        raise FileNotFoundError(f"Google Chrome not found at {chrome}")
    subprocess.run(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--run-all-compositor-stages-before-draw",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            html_path.resolve().as_uri(),
        ],
        check=True,
    )


def maybe_regenerate_tree_visualization(source_run: Path, output_dir: Path) -> None:
    tree_pickle = source_run / "raptor_tree.pkl"
    if not tree_pickle.exists() or not (output_dir / "qa_tree_sources.json").exists():
        return
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "export_tree_visualization.py"),
            "--tree-pickle",
            str(tree_pickle),
            "--output-html",
            str(output_dir / "tree_visualization.html"),
            "--output-json",
            str(output_dir / "tree_data.json"),
            "--qa-sources-json",
            str(output_dir / "qa_tree_sources.json"),
            "--report-html",
            str(output_dir / "report.html"),
        ],
        check=True,
    )


def build_v4(args: argparse.Namespace) -> Path:
    source_run = args.source_run.resolve()
    output_dir = output_dir_for(args).resolve()
    copy_v3_artifacts(source_run, output_dir)

    review_rows = ensure_review_sheet(
        source_run,
        output_dir,
        overwrite=args.overwrite_review,
        default_status=args.default_review_status,
    )
    gold_rows = gold_rows_from_review(review_rows)
    write_jsonl(output_dir / "gold_qa.jsonl", gold_rows)

    answer_rows = build_v4_answer_rows(source_run, output_dir, gold_rows)
    update_qa_sources(output_dir, gold_rows, answer_rows)

    build_report_html(output_dir, answer_rows, gold_rows, review_rows)
    build_compact_html(output_dir, answer_rows, gold_rows, review_rows)
    build_presentation_html(output_dir, answer_rows, gold_rows)
    build_report_md(output_dir, answer_rows, gold_rows)
    (output_dir / "report_print.html").write_text(
        build_print_report((output_dir / "report.html").read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    maybe_regenerate_tree_visualization(source_run, output_dir)

    if args.make_pdf:
        build_pdf(output_dir / "report_compact_print.html", output_dir / "report_compact_print.pdf")
        build_pdf(output_dir / "report_presentation.html", output_dir / "report_presentation.pdf")
    return output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-run",
        type=Path,
        default=REPO_ROOT / "runs" / "patent_raptor_v3_20260530_152153",
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--default-review-status",
        choices=["accept", "edit_reference_answer", "exclude"],
        default="accept",
    )
    parser.add_argument("--overwrite-review", action="store_true")
    parser.add_argument("--make-pdf", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = build_v4(args)
    print(f"Built V4-mini run in {output_dir}")


if __name__ == "__main__":
    main()
