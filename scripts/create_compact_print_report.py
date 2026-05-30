#!/usr/bin/env python3
"""Create a compact A4 print report from RAPTOR run artifacts."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from scripts.paper_metrics import ensure_paper_metrics


METHOD_ORDER = [
    "bm25_without_raptor",
    "bm25_with_raptor",
    "dense_bge_m3_without_raptor",
    "dense_bge_m3_with_raptor",
    "dpr_without_raptor",
    "dpr_with_raptor",
    "collapsed_tree",
    "traverse_tree",
    "bm25_leaf",
    "bm25_all_nodes",
    "dpr_leaf",
]

REPRESENTATIVE_TREE_CASES = [
    {
        "qa_index": "1",
        "method": "collapsed_tree",
        "label": "Collapsed strict win: summary + leaf evidence",
    },
    {
        "qa_index": "5",
        "method": "collapsed_tree",
        "label": "Collapsed strict win: leaf-heavy source path",
    },
    {
        "qa_index": "18",
        "method": "bm25_leaf",
        "label": "BM25 lexical leaf hits: GEMM / DDR exact terms",
    },
    {
        "qa_index": "0",
        "method": "collapsed_tree",
        "label": "Tie / partial-answer case: source found but ID omitted",
    },
]

V3_REPRESENTATIVE_TREE_CASES = [
    {
        "qa_index": "0",
        "method": "dense_bge_m3_with_raptor",
        "label": "Dense global success: summary-heavy evidence",
        "compare_without": True,
    },
    {
        "qa_index": "1",
        "method": "bm25_with_raptor",
        "label": "BM25 global success: lexical terms + summary evidence",
        "compare_without": True,
    },
    {
        "qa_index": "8",
        "method": "dense_bge_m3_with_raptor",
        "label": "Dense local success: semantic retrieval found the exact patent",
        "compare_without": True,
    },
    {
        "qa_index": "8",
        "method": "bm25_with_raptor",
        "label": "BM25 limitation: source hit but answer unsupported",
    },
]

V3_RAPTOR_PAIRS = [
    ("BM25", "bm25_without_raptor", "bm25_with_raptor"),
    ("Dense BGE-M3", "dense_bge_m3_without_raptor", "dense_bge_m3_with_raptor"),
]

CATEGORY_COLORS = {
    "AA": "#2563eb",
    "AB": "#dc2626",
    "AC": "#059669",
    "AD": "#d97706",
}


CSS = r"""
:root { color-scheme: light; }
@page { size: A4 portrait; margin: 12mm 11mm 14mm; }
* { box-sizing: border-box; }
html, body { background: #fff; color: #111827; }
body {
  width: 210mm;
  max-width: 210mm;
  margin: 0 auto;
  padding: 12mm 11mm;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  font-size: 9.4pt;
  line-height: 1.38;
}
.toolbar {
  position: sticky;
  top: 0;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin: -12mm -11mm 8mm;
  padding: 8px 11mm;
  border-bottom: 1px solid #cbd5e1;
  background: #fff;
}
.toolbar a, .toolbar button {
  border: 1px solid #cbd5e1;
  border-radius: 5px;
  background: #fff;
  color: #111827;
  font: inherit;
  padding: 5px 9px;
  text-decoration: none;
}
h1 {
  margin: 0 0 5mm;
  padding-bottom: 3mm;
  border-bottom: 2px solid #111827;
  font-size: 20pt;
  line-height: 1.12;
}
h2 {
  margin: 8mm 0 3mm;
  padding-bottom: 1.5mm;
  border-bottom: 1px solid #94a3b8;
  font-size: 13.5pt;
  line-height: 1.18;
  break-after: avoid;
  page-break-after: avoid;
}
h3 {
  margin: 5mm 0 2mm;
  font-size: 11pt;
  break-after: avoid;
  page-break-after: avoid;
}
p { margin: 0 0 3mm; }
ul { margin: 1.5mm 0 4mm 5mm; padding: 0; }
li { margin: 0 0 1.6mm; }
table {
  width: 100%;
  margin: 2mm 0 6mm;
  border-collapse: collapse;
  background: #fff;
  font-size: 8.1pt;
}
thead { display: table-header-group; }
tr, .card, .note { break-inside: avoid; page-break-inside: avoid; }
th, td {
  border: 1px solid #cbd5e1;
  padding: 3pt 3.5pt;
  text-align: left;
  vertical-align: top;
  overflow-wrap: anywhere;
}
th {
  background: #eef2ff;
  font-weight: 700;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 3mm;
  margin: 0 0 5mm;
}
.card, .note, .tree-case {
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  background: #fff;
  padding: 3mm;
}
.card strong {
  display: block;
  margin-bottom: 1mm;
  font-size: 8.2pt;
  color: #475569;
}
.card .value {
  font-size: 13pt;
  font-weight: 750;
  color: #111827;
}
.note {
  margin: 0 0 4mm;
  background: #f8fafc;
  color: #334155;
}
.small { color: #475569; font-size: 7.8pt; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
.tag {
  display: inline-block;
  margin: 0 2pt 2pt 0;
  padding: 1pt 4pt;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #f8fafc;
  white-space: nowrap;
}
.tree-case {
  margin: 0 0 5mm;
}
.tree-case h3 {
  margin-top: 0;
}
.without-comparison {
  margin-top: 2mm;
  padding-top: 2mm;
  border-top: 1px dashed #94a3b8;
}
.without-comparison h4 {
  margin: 0 0 1mm;
  font-size: 9.4pt;
}
.without-visual-head {
  break-inside: avoid;
  page-break-inside: avoid;
}
.usefulness {
  margin: 1.5mm 0 2mm;
  padding: 2mm;
  border: 1px solid #cbd5e1;
  border-left: 4px solid #64748b;
  border-radius: 4px;
  background: #f8fafc;
  color: #334155;
  font-size: 7.8pt;
}
.usefulness strong {
  color: #111827;
}
.usefulness.best {
  border-left-color: #059669;
  background: #f0fdf4;
}
.usefulness.comparable {
  border-left-color: #2563eb;
  background: #eff6ff;
}
.usefulness.usable {
  border-left-color: #d97706;
  background: #fff7ed;
}
.usefulness.weak {
  border-left-color: #dc2626;
  background: #fef2f2;
}
.tree-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5mm;
  margin: .7mm 0 1.5mm;
  color: #475569;
  font-size: 7.8pt;
}
.mini-tree {
  display: block;
  width: 100%;
  height: auto;
  border: 1px solid #dbe3ef;
  border-radius: 4px;
  background:
    linear-gradient(90deg, rgba(100, 116, 139, .10) 1px, transparent 1px),
    linear-gradient(rgba(100, 116, 139, .08) 1px, transparent 1px);
  background-size: 28px 28px;
}
.tree-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 2.2mm;
  margin-top: 1mm;
  color: #475569;
  font-size: 7.4pt;
}
.tree-note {
  margin: .7mm 0 1.5mm;
  padding: 1.6mm;
}
.node-meaning-table {
  margin-top: 2mm;
  margin-bottom: 0;
  font-size: 7.4pt;
  table-layout: fixed;
  border: 1px solid #cbd5e1;
}
.node-meaning-table th {
  background: #eef2ff;
  font-weight: 700;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.node-meaning-table th,
.node-meaning-table td {
  border: 1px solid #cbd5e1;
  padding: 3pt 3.5pt;
  text-align: left;
  vertical-align: top;
}
.node-meaning-table th:nth-child(1),
.node-meaning-table td:nth-child(1) {
  width: 6%;
  white-space: nowrap;
  overflow-wrap: normal;
}
.node-meaning-table th:nth-child(2),
.node-meaning-table td:nth-child(2) {
  width: 8%;
  white-space: nowrap;
  overflow-wrap: normal;
}
.node-meaning-table th:nth-child(3),
.node-meaning-table td:nth-child(3) {
  width: 7%;
  white-space: nowrap;
  overflow-wrap: normal;
}
.node-meaning-table th:nth-child(4),
.node-meaning-table td:nth-child(4) {
  line-height: 1.45;
  width: 63%;
  overflow-wrap: break-word;
  word-break: keep-all;
}
.node-meaning-table th:nth-child(5),
.node-meaning-table td:nth-child(5) {
  width: 16%;
  overflow-wrap: break-word;
  word-break: keep-all;
}
.answer-evidence {
  margin-top: 2mm;
  padding: 2.4mm;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  background: #fbfdff;
  break-inside: avoid;
  page-break-inside: avoid;
}
.answer-evidence h4 {
  margin: 0 0 1mm;
  font-size: 9.6pt;
}
.answer-text {
  margin: 0 0 1.5mm;
  color: #111827;
}
.evidence-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5mm;
  margin: .7mm 0 1mm;
  font-size: 7.5pt;
  color: #475569;
}
.evidence-chip {
  display: inline-block;
  padding: .5pt 4pt;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #fff;
  white-space: nowrap;
}
.evidence-hit {
  border-radius: 2px;
  padding: 0 .5px;
  -webkit-box-decoration-break: clone;
  box-decoration-break: clone;
}
.ev1 { background: linear-gradient(transparent 55%, rgba(245, 158, 11, .45) 0); }
.ev2 { background: linear-gradient(transparent 55%, rgba(16, 185, 129, .38) 0); }
.ev3 { background: linear-gradient(transparent 55%, rgba(59, 130, 246, .35) 0); }
.ev4 { background: linear-gradient(transparent 55%, rgba(168, 85, 247, .34) 0); }
.ev5 { background: linear-gradient(transparent 55%, rgba(239, 68, 68, .32) 0); }
.ev6 { background: linear-gradient(transparent 55%, rgba(20, 184, 166, .35) 0); }
.ev7 { background: linear-gradient(transparent 55%, rgba(100, 116, 139, .28) 0); }
.ev8 { background: linear-gradient(transparent 55%, rgba(132, 204, 22, .35) 0); }
.metric-guide-table {
  margin-top: -2mm;
  margin-bottom: 5mm;
  font-size: 7.9pt;
}
.metric-guide-table th {
  background: #f1f5f9;
}
.metric-guide-table td:first-child {
  width: 15%;
  font-weight: 700;
  white-space: nowrap;
}
.metric-guide-table th:nth-child(2),
.metric-guide-table td:nth-child(2) {
  width: 15%;
  white-space: nowrap;
}
.metric-kind {
  display: inline-block;
  min-width: 58px;
  padding: 1pt 4pt;
  border-radius: 999px;
  background: #eef2ff;
  color: #3730a3;
  font-weight: 700;
  text-align: center;
  white-space: nowrap;
}
.metric-kind.retrieval {
  background: #ecfdf5;
  color: #047857;
}
.raptor-win-table,
.raptor-delta-table {
  table-layout: fixed;
  font-size: 7.35pt;
}
.raptor-win-table th,
.raptor-win-table td,
.raptor-delta-table th,
.raptor-delta-table td {
  padding: 2.6pt 3pt;
  overflow-wrap: break-word;
}
.raptor-win-table th:nth-child(1),
.raptor-win-table td:nth-child(1) {
  width: 7%;
  white-space: nowrap;
  overflow-wrap: normal;
}
.raptor-win-table th:nth-child(2),
.raptor-win-table td:nth-child(2) {
  width: 9%;
  white-space: normal;
}
.raptor-win-table th:nth-child(3),
.raptor-win-table td:nth-child(3),
.raptor-win-table th:nth-child(4),
.raptor-win-table td:nth-child(4) {
  width: 9%;
  white-space: nowrap;
  overflow-wrap: normal;
}
.raptor-win-table th:nth-child(5),
.raptor-win-table td:nth-child(5) {
  width: 10%;
  white-space: normal;
  overflow-wrap: break-word;
}
.raptor-win-table th:nth-child(6),
.raptor-win-table td:nth-child(6) {
  width: 13%;
}
.raptor-win-table th:nth-child(7),
.raptor-win-table td:nth-child(7) {
  width: 42%;
}
.raptor-delta-table th:nth-child(1),
.raptor-delta-table td:nth-child(1) {
  width: 11%;
}
.raptor-delta-table th:nth-child(2),
.raptor-delta-table td:nth-child(2),
.raptor-delta-table th:nth-child(3),
.raptor-delta-table td:nth-child(3) {
  width: 19%;
}
.raptor-delta-table th:nth-child(4),
.raptor-delta-table td:nth-child(4),
.raptor-delta-table th:nth-child(5),
.raptor-delta-table td:nth-child(5) {
  width: 11%;
  white-space: nowrap;
  overflow-wrap: normal;
}
.raptor-delta-table th:nth-child(6),
.raptor-delta-table td:nth-child(6) {
  width: 29%;
}
.split-table {
  table-layout: fixed;
  font-size: 7.7pt;
  margin-top: 2mm;
}
.split-table th,
.split-table td {
  padding: 2.6pt 3pt;
}
.split-table th:nth-child(1),
.split-table td:nth-child(1) {
  width: 13%;
}
.split-table th:nth-child(2),
.split-table td:nth-child(2),
.split-table th:nth-child(3),
.split-table td:nth-child(3),
.split-table th:nth-child(4),
.split-table td:nth-child(4),
.split-table th:nth-child(5),
.split-table td:nth-child(5) {
  width: 10%;
  white-space: nowrap;
}
.split-table th:nth-child(6),
.split-table td:nth-child(6) {
  width: 47%;
}
.appendix-sample-table {
  table-layout: fixed;
}
.appendix-sample-table th:nth-child(1),
.appendix-sample-table td:nth-child(1) {
  width: 10%;
  white-space: nowrap;
  overflow-wrap: normal;
}
.appendix-sample-table th:nth-child(2),
.appendix-sample-table td:nth-child(2) {
  width: 13%;
  white-space: nowrap;
  overflow-wrap: normal;
}
.appendix-sample-table th:nth-child(3),
.appendix-sample-table td:nth-child(3) {
  width: 77%;
}
.qa-cell {
  font-weight: 700;
  line-height: 1.25;
}
.qa-type {
  display: block;
  margin-top: .5mm;
  color: #475569;
  font-size: 6.9pt;
  font-weight: 600;
}
.delta-cell {
  line-height: 1.38;
}
.semi-lines span {
  display: block;
  line-height: 1.34;
  margin: 0 0 .7mm;
}
.semi-lines span:last-child {
  margin-bottom: 0;
}
.legend-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 2px;
  border-radius: 999px;
  vertical-align: -1px;
}
.page-break { break-before: page; page-break-before: always; }
@media screen {
  body { margin: 24px auto; box-shadow: 0 8px 36px rgba(15, 23, 42, .12); }
}
@media print {
  body { width: auto; max-width: none; margin: 0; padding: 0; box-shadow: none; }
  .toolbar { display: none !important; }
  a { color: inherit; text-decoration: none; }
}
"""


def clean_text(value, limit=None):
    text = str(value or "")
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def as_float(value, default=0.0):
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def fmt(value, digits=3):
    if value == "" or value is None:
        return "-"
    return f"{as_float(value):.{digits}f}"


def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path):
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def parse_layers(value):
    layers = []
    for raw in str(value or "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            layers.append(int(raw))
        except ValueError:
            continue
    return layers


def layer_mix(value):
    layers = parse_layers(value)
    if not layers:
        return "-"
    counts = Counter(layers)
    return ", ".join(f"L{layer}:{counts[layer]}" for layer in sorted(counts))


def method_sort_key(method):
    return METHOD_ORDER.index(method) if method in METHOD_ORDER else len(METHOD_ORDER)


def summarize_by_method(rows, metric):
    grouped = defaultdict(list)
    for row in rows:
        method = row.get("method", "")
        if method:
            grouped[method].append(as_float(row.get(metric)))
    return {
        method: statistics.mean(values)
        for method, values in sorted(grouped.items(), key=lambda item: method_sort_key(item[0]))
        if values
    }


def grouped_by_qa(answer_rows):
    by_qa = defaultdict(list)
    for row in answer_rows:
        by_qa[row.get("qa_index", "")].append(row)
    return by_qa


def answer_eval_lookup(answer_rows):
    return {
        (row.get("qa_index", ""), row.get("method", "")): row
        for row in answer_rows
        if row.get("qa_index") and row.get("method")
    }


def qa_eval_rows(answer_eval, qa_index):
    return [
        row
        for (row_qa_index, _), row in answer_eval.items()
        if str(row_qa_index) == str(qa_index)
    ]


def best_rows(answer_rows):
    rows = []
    for qa_index, group in grouped_by_qa(answer_rows).items():
        ranked = sorted(
            group,
            key=lambda row: (
                as_float(row.get("judge_score")),
                as_float(row.get("mrr")),
                -as_float(row.get("latency_seconds")),
            ),
            reverse=True,
        )
        if ranked:
            rows.append(ranked[0])
    return sorted(rows, key=lambda row: int(row.get("qa_index") or 0))


def best_counts(answer_rows):
    counts = Counter(row.get("method", "") for row in best_rows(answer_rows))
    return dict(sorted(counts.items(), key=lambda item: method_sort_key(item[0])))


def bm25_wins(answer_rows):
    wins = []
    for qa_index, group in grouped_by_qa(answer_rows).items():
        bm25 = [row for row in group if row.get("method", "").startswith("bm25")]
        others = [row for row in group if not row.get("method", "").startswith("bm25")]
        if not bm25 or not others:
            continue
        best_bm25 = max(bm25, key=lambda row: as_float(row.get("judge_score")))
        best_other = max(others, key=lambda row: as_float(row.get("judge_score")))
        if as_float(best_bm25.get("judge_score")) < as_float(best_other.get("judge_score")):
            continue
        try:
            terms = json.loads(best_bm25.get("bm25_top_terms") or "[]")
        except json.JSONDecodeError:
            terms = []
        wins.append(
            {
                "qa_index": qa_index,
                "question": best_bm25.get("question", ""),
                "method": best_bm25.get("method", ""),
                "score": best_bm25.get("judge_score", ""),
                "other_method": best_other.get("method", ""),
                "other_score": best_other.get("judge_score", ""),
                "terms": terms[:3],
                "note": best_bm25.get("judge_explanation", ""),
            }
        )
    return sorted(
        wins,
        key=lambda row: (as_float(row["score"]), max((as_float(t.get("idf")) for t in row["terms"]), default=0)),
        reverse=True,
    )


def collapsed_wins(answer_rows, source_map):
    wins = []
    for qa_index, group in grouped_by_qa(answer_rows).items():
        collapsed = [row for row in group if row.get("method") == "collapsed_tree"]
        others = [row for row in group if row.get("method") != "collapsed_tree"]
        if not collapsed or not others:
            continue
        collapsed = collapsed[0]
        best_other = max(others, key=lambda row: as_float(row.get("judge_score")))
        collapsed_score = as_float(collapsed.get("judge_score"))
        other_score = as_float(best_other.get("judge_score"))
        if collapsed_score < other_score:
            continue
        source_item = source_map.get(str(qa_index), {})
        source_nodes = source_item.get("methods", {}).get("collapsed_tree", {}).get("source_nodes", [])
        top_sources = "; ".join(
            "#{} L{} r{}".format(
                node.get("node_index", ""),
                node.get("layer", ""),
                node.get("rank", ""),
            )
            for node in source_nodes[:4]
        )
        wins.append(
            {
                "qa_index": qa_index,
                "outcome": "strict" if collapsed_score > other_score else "tie",
                "question": collapsed.get("question", ""),
                "score": collapsed.get("judge_score", ""),
                "other_method": best_other.get("method", ""),
                "other_score": best_other.get("judge_score", ""),
                "retrieval": "hit={} rank={} mrr={}".format(
                    collapsed.get("hit", ""),
                    collapsed.get("rank", "") or "-",
                    fmt(collapsed.get("mrr")),
                ),
                "layer_mix": layer_mix(collapsed.get("retrieved_layers")),
                "top_sources": top_sources or "-",
                "note": collapsed.get("judge_explanation", ""),
            }
        )
    return sorted(
        wins,
        key=lambda row: (row["outcome"] != "strict", -as_float(row["score"]), int(row["qa_index"] or 0)),
    )


def raptor_win_cases(answer_rows, source_map):
    ensure_paper_metrics(answer_rows)
    by_qa = grouped_by_qa(answer_rows)
    cases = []
    for qa_index, group in by_qa.items():
        rows_by_method = {row.get("method", ""): row for row in group}
        for label, without_method, with_method in V3_RAPTOR_PAIRS:
            without_row = rows_by_method.get(without_method)
            with_row = rows_by_method.get(with_method)
            if not without_row or not with_row:
                continue
            answer_f1_delta = as_float(with_row.get("answer_f1")) - as_float(without_row.get("answer_f1"))
            answer_recall_delta = as_float(with_row.get("answer_recall")) - as_float(without_row.get("answer_recall"))
            score_delta = as_float(with_row.get("judge_score")) - as_float(without_row.get("judge_score"))
            accuracy_delta = as_float(with_row.get("paper_accuracy")) - as_float(without_row.get("paper_accuracy"))
            if answer_f1_delta <= 0 and answer_recall_delta <= 0 and score_delta <= 0 and accuracy_delta <= 0:
                continue
            qa_item = source_map.get(str(qa_index), {})
            source_nodes = qa_item.get("methods", {}).get(with_method, {}).get("source_nodes", [])
            top_sources = "; ".join(
                "#{} L{} r{}".format(
                    source.get("node_index", ""),
                    source.get("layer", ""),
                    source.get("rank", ""),
                )
                for source in source_nodes[:4]
            )
            cases.append(
                {
                    "qa_index": qa_index,
                    "question_type": with_row.get("question_type", ""),
                    "retriever": label,
                    "without_method": without_method,
                    "with_method": with_method,
                    "without_answer_f1": as_float(without_row.get("answer_f1")),
                    "with_answer_f1": as_float(with_row.get("answer_f1")),
                    "answer_f1_delta": answer_f1_delta,
                    "answer_recall_delta": answer_recall_delta,
                    "without_score": as_float(without_row.get("judge_score")),
                    "with_score": as_float(with_row.get("judge_score")),
                    "score_delta": score_delta,
                    "accuracy_delta": accuracy_delta,
                    "question": with_row.get("question", ""),
                    "layer_mix": layer_mix(with_row.get("retrieved_layers")),
                    "top_sources": top_sources or "-",
                    "note": with_row.get("judge_explanation", ""),
                }
            )
    return sorted(
        cases,
        key=lambda row: (
            row["answer_f1_delta"],
            row["answer_recall_delta"],
            row["score_delta"],
            row["accuracy_delta"],
            row["with_score"],
        ),
        reverse=True,
    )


def with_without_delta_rows(answer_rows):
    ensure_paper_metrics(answer_rows)
    grouped = defaultdict(list)
    for row in answer_rows:
        method = row.get("method", "")
        if method:
            grouped[method].append(row)

    rows = []
    for label, without_method, with_method in V3_RAPTOR_PAIRS:
        without_rows = grouped.get(without_method, [])
        with_rows = grouped.get(with_method, [])
        if not without_rows or not with_rows:
            continue

        def avg(rows, field):
            return statistics.mean(as_float(row.get(field)) for row in rows)

        rows.append(
            {
                "label": label,
                "without": without_method,
                "with": with_method,
                "score_without": avg(without_rows, "judge_score"),
                "score_with": avg(with_rows, "judge_score"),
                "accuracy_without": avg(without_rows, "paper_accuracy"),
                "accuracy_with": avg(with_rows, "paper_accuracy"),
                "answer_f1_without": avg(without_rows, "answer_f1"),
                "answer_f1_with": avg(with_rows, "answer_f1"),
                "answer_recall_without": avg(without_rows, "answer_recall"),
                "answer_recall_with": avg(with_rows, "answer_recall"),
            }
        )
    return rows


def question_type_split_rows(answer_rows):
    ensure_paper_metrics(answer_rows)
    grouped = defaultdict(list)
    for row in answer_rows:
        grouped[(row.get("question_type", "") or "unknown", row.get("method", ""))].append(row)

    def avg(question_type, method, field="answer_f1"):
        rows = grouped.get((question_type, method), [])
        if not rows:
            return None
        return statistics.mean(as_float(row.get(field)) for row in rows)

    rows = []
    for label, without_method, with_method in V3_RAPTOR_PAIRS:
        global_without = avg("global", without_method)
        global_with = avg("global", with_method)
        local_without = avg("local", without_method)
        local_with = avg("local", with_method)
        all_without_rows = grouped.get(("global", without_method), []) + grouped.get(("local", without_method), [])
        all_with_rows = grouped.get(("global", with_method), []) + grouped.get(("local", with_method), [])
        all_without = statistics.mean(as_float(row.get("answer_f1")) for row in all_without_rows) if all_without_rows else None
        all_with = statistics.mean(as_float(row.get("answer_f1")) for row in all_with_rows) if all_with_rows else None
        if global_without is None or global_with is None or local_without is None or local_with is None:
            continue
        if global_with > global_without and local_with < local_without:
            interpretation = "Global QA에서는 summary/all-node가 유리하지만, Local QA에서는 특정 patent detail을 leaf에서 직접 찾는 조건이 더 강했습니다. 전체 평균은 이 상반된 효과를 가립니다."
        elif global_with > global_without and local_with > local_without:
            interpretation = "Global과 Local 모두에서 RAPTOR all-node 검색이 Answer F1을 높였습니다."
        elif global_with < global_without and local_with < local_without:
            interpretation = "두 QA 유형 모두 leaf-only가 더 직접적인 근거를 제공했습니다."
        else:
            interpretation = "QA 유형별 방향이 엇갈리므로 전체 평균만으로 결론을 내리기 어렵습니다."
        rows.append(
            {
                "label": label,
                "global_without": global_without,
                "global_with": global_with,
                "local_without": local_without,
                "local_with": local_with,
                "all_without": all_without,
                "all_with": all_with,
                "global_delta": global_with - global_without,
                "local_delta": local_with - local_without,
                "all_delta": (all_with - all_without) if all_with is not None and all_without is not None else None,
                "interpretation": interpretation,
            }
        )
    return rows


def render_query_type_split_table(answer_rows):
    rows = question_type_split_rows(answer_rows)
    if not rows:
        return ""
    parts = [
        "<h2>Global/Local Split - Answer F1</h2>",
        "<p class='small'>각 QA 유형은 5개뿐인 pilot sample이므로 통계적으로 강한 결론보다는 방향성 확인으로 해석해야 합니다.</p>",
        "<table class='split-table'><thead><tr><th>Retriever</th><th>Global<br>without</th><th>Global<br>with</th><th>Local<br>without</th><th>Local<br>with</th><th>Interpretation</th></tr></thead><tbody>",
    ]
    for row in rows:
        parts.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html_escape(compact_retriever_label(row["label"])),
                fmt(row["global_without"]),
                fmt(row["global_with"]),
                fmt(row["local_without"]),
                fmt(row["local_with"]),
                html_escape(row["interpretation"]),
            )
        )
    parts.append("</tbody></table>")
    return "\n".join(parts)


def compact_retriever_label(label):
    value = clean_text(label)
    if value == "Dense BGE-M3":
        return "BGE-M3"
    return value


def compact_method_label(method_name):
    value = clean_text(method_name)
    replacements = {
        "bm25_without_raptor": "leaf only",
        "bm25_with_raptor": "all nodes",
        "dense_bge_m3_without_raptor": "leaf only",
        "dense_bge_m3_with_raptor": "all nodes",
        "dpr_without_raptor": "leaf only",
        "dpr_with_raptor": "all nodes",
    }
    return replacements.get(value, value)


def semicolon_lines_html(value):
    items = [clean_text(item) for item in str(value or "").split(";")]
    items = [item for item in items if item and item != "-"]
    if not items:
        return "-"
    return "<div class='semi-lines'>" + "".join(
        f"<span>{html_escape(item)}</span>" for item in items
    ) + "</div>"


def load_source_map(run_dir):
    path = run_dir / "qa_tree_sources.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("qa_items", []) if isinstance(data, dict) else data
    return {str(item.get("qa_index")): item for item in items}


def parse_report_cards(run_dir):
    path = run_dir / "report.html"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    cards = {}
    for title, value in re.findall(r'<div class="card"><strong>(.*?)</strong><br>(.*?)</div>', text, flags=re.S):
        value = re.sub(r"<.*?>", "", value)
        cards[html.unescape(title)] = html.unescape(value).strip()
    return cards


def dataset_summary(run_dir):
    rows = read_jsonl(run_dir / "sampled_patents.jsonl")
    cats = Counter(str(row.get("중분류") or row.get("category") or "") for row in rows)
    cat_text = ", ".join(f"{cat} {count}" for cat, count in sorted(cats.items()) if cat)
    return len(rows), cat_text or "-"


def appendix_summary(rows):
    total = len(rows)
    hallucinated = sum(1 for row in rows if str(row.get("has_hallucination", "")).lower() == "true")
    severities = Counter(row.get("severity", "unknown") or "unknown" for row in rows)
    samples = []
    for row in sorted(rows, key=lambda r: (r.get("severity") != "major", r.get("node_index", ""))):
        raw = row.get("unsupported_claims") or "[]"
        try:
            claims = json.loads(raw)
        except json.JSONDecodeError:
            claims = [raw]
        if claims:
            samples.append(
                {
                    "node": row.get("node_index", ""),
                    "severity": row.get("severity", ""),
                    "claim": claims[0],
                }
            )
        if len(samples) >= 3:
            break
    return total, hallucinated, severities, samples


def html_escape(value):
    return html.escape(clean_text(value))


def term_tags(terms):
    if not terms:
        return "-"
    return " ".join(
        '<span class="tag">{} idf={} score={}</span>'.format(
            html_escape(term.get("term", "")),
            fmt(term.get("idf"), 2),
            fmt(term.get("score"), 2),
        )
        for term in terms
    )


def compact_qa_rows(answer_rows, limit=4):
    selected = []
    winners = best_rows(answer_rows)
    preferred = ["1", "5", "13", "19", "0"]
    by_index = {row.get("qa_index"): row for row in winners}
    for qa_index in preferred:
        if qa_index in by_index:
            selected.append(by_index[qa_index])
    for row in winners:
        if row not in selected:
            selected.append(row)
        if len(selected) >= limit:
            break
    return selected[:limit]


def load_tree_nodes(run_dir):
    path = run_dir / "tree_data.json"
    if not path.exists():
        return {}, 0
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes = {str(node.get("index")): node for node in data.get("nodes", [])}
    max_layer = max((int(node.get("layer", 0)) for node in nodes.values()), default=0)
    return nodes, max_layer


def category_color(node):
    category = node.get("dominant_category") or node.get("category") or ""
    return CATEGORY_COLORS.get(category, "#7c3aed")


def truncate_middle(value, limit=16):
    text = clean_text(value)
    if len(text) <= limit:
        return text
    if limit <= 4:
        return text[:limit]
    keep = (limit - 1) // 2
    return f"{text[:keep]}…{text[-keep:]}"


def collect_mini_tree_ids(qa_item, method_data, nodes, method_name, source_limit=8):
    source_ids = [
        str(source.get("node_index"))
        for source in (method_data.get("source_nodes") or [])[:source_limit]
        if source.get("node_index") is not None
    ]
    ids = set(source_ids)
    if method_name == "bm25_leaf" or method_name.endswith("_without_raptor"):
        return ids, set(source_ids)
    frontier = list(ids)
    while frontier:
        current = frontier.pop()
        node = nodes.get(current)
        if not node:
            continue
        for parent in node.get("parents") or []:
            parent = str(parent)
            if parent not in ids:
                ids.add(parent)
                frontier.append(parent)
    return ids, set(source_ids)


def method_view_note(method_name):
    if method_name.endswith("_without_raptor"):
        return (
            "Without RAPTOR is flat leaf retrieval. This panel shows ranked leaf/source placement only; it is not a tree traversal."
        )
    if method_name.endswith("_with_raptor"):
        return (
            "With RAPTOR searches the flattened RAPTOR tree, so retrieved sources can be leaf patents or higher summary nodes."
        )
    if method_name == "bm25_leaf":
        return (
            "BM25 leaf is flat lexical retrieval. This panel shows only the ranked leaf patent hits; it is not a tree traversal."
        )
    if method_name.startswith("bm25"):
        return (
            "BM25 itself is flat lexical retrieval. Any tree placement is only for context, not a BM25 traversal path."
        )
    if method_name == "collapsed_tree":
        return (
            "Collapsed Tree retrieves RAPTOR nodes from the flattened tree under the same token budget. The mini-tree shows those selected nodes and their ancestor/child relations."
        )
    if method_name == "traverse_tree":
        return "Traverse Tree is the only mode here that performs layer-by-layer top-down traversal."
    return "Edges show source placement on the RAPTOR tree."


def source_rank_map(method_data):
    return {
        str(source.get("node_index")): source.get("rank")
        for source in method_data.get("source_nodes") or []
        if source.get("node_index") is not None
    }


def svg_edge_path(parent, child):
    dy = max(20, (child["y"] - parent["y"]) * 0.45)
    return (
        f"M {parent['x']:.1f} {parent['y']:.1f} "
        f"C {parent['x']:.1f} {parent['y'] + dy:.1f}, "
        f"{child['x']:.1f} {child['y'] - dy:.1f}, "
        f"{child['x']:.1f} {child['y']:.1f}"
    )


def render_source_path_svg(qa_item, method_name, nodes, max_layer):
    method_data = qa_item.get("methods", {}).get(method_name, {})
    if not method_data or not nodes:
        return "<p class='small'>Source path data unavailable.</p>"

    ids, source_ids = collect_mini_tree_ids(qa_item, method_data, nodes, method_name)
    rank_by_id = source_rank_map(method_data)
    selected_nodes = [nodes[node_id] for node_id in ids if node_id in nodes]
    if not selected_nodes:
        return "<p class='small'>Source path data unavailable.</p>"

    by_layer = defaultdict(list)
    for node in selected_nodes:
        by_layer[int(node.get("layer", 0))].append(node)

    for layer_nodes in by_layer.values():
        layer_nodes.sort(
            key=lambda node: (
                int(rank_by_id.get(str(node.get("index")), 9999)),
                str(node.get("patent_id") or node.get("title") or ""),
                int(node.get("index", 0)),
            )
        )

    display_max_layer = 0 if method_name == "bm25_leaf" or method_name.endswith("_without_raptor") else max_layer
    max_count = max((len(items) for items in by_layer.values()), default=1)
    width = 760
    height = 112 if display_max_layer == 0 else 285 if max_count <= 9 else 320
    top_pad = 26
    bottom_pad = 34 if display_max_layer == 0 else 48
    left_pad = 58
    right_pad = 28
    positions = {}
    layer_denominator = max(display_max_layer, 1)
    for layer in range(display_max_layer, -1, -1):
        layer_nodes = by_layer.get(layer, [])
        y = top_pad + (max_layer - layer) * ((height - top_pad - bottom_pad) / layer_denominator)
        if display_max_layer == 0:
            y = top_pad + ((height - top_pad - bottom_pad) / 2)
        gap = (width - left_pad - right_pad) / (len(layer_nodes) + 1 if layer_nodes else 2)
        for idx, node in enumerate(layer_nodes, start=1):
            positions[str(node.get("index"))] = {"x": left_pad + gap * idx, "y": y}

    svg = [
        f'<svg class="mini-tree" viewBox="0 0 {width} {height}" role="img" aria-label="QA source path mini-tree">',
        "<g>",
    ]
    for layer in range(display_max_layer, -1, -1):
        y = top_pad + (display_max_layer - layer) * ((height - top_pad - bottom_pad) / layer_denominator)
        if display_max_layer == 0:
            y = top_pad + ((height - top_pad - bottom_pad) / 2)
        label = "L0 leaves" if layer == 0 else f"L{layer}"
        svg.append(
            f'<text x="10" y="{y + 3:.1f}" font-size="9" font-weight="700" fill="#475569">{html_escape(label)}</text>'
        )
    svg.append("</g><g>")
    edge_color = "#94a3b8" if method_name.startswith("bm25") else "#2563eb"
    edge_dash = ' stroke-dasharray="4 3"' if method_name.startswith("bm25") else ""
    edge_opacity = ".62" if method_name.startswith("bm25") else ".72"
    for node in selected_nodes:
        child_id = str(node.get("index"))
        child_pos = positions.get(child_id)
        if not child_pos:
            continue
        for parent_id in node.get("parents") or []:
            parent_id = str(parent_id)
            if parent_id not in ids:
                continue
            parent_pos = positions.get(parent_id)
            if not parent_pos:
                continue
            svg.append(
                f'<path d="{svg_edge_path(parent_pos, child_pos)}" fill="none" stroke="{edge_color}" stroke-width="1.25" opacity="{edge_opacity}"{edge_dash}/>'
            )
    svg.append("</g><g>")

    for node in selected_nodes:
        node_id = str(node.get("index"))
        pos = positions.get(node_id)
        if not pos:
            continue
        is_leaf = int(node.get("layer", 0)) == 0
        is_source = node_id in source_ids
        radius = 5.2 if is_leaf else 8.0
        stroke = "#f59e0b" if is_source else "#64748b"
        stroke_width = 2.8 if is_source else 1.1
        fill = category_color(node)
        title = html_escape(
            f"#{node.get('index')} L{node.get('layer')} "
            f"{node.get('patent_id') or node.get('title') or 'summary node'}"
        )
        svg.append(f'<g transform="translate({pos["x"]:.1f},{pos["y"]:.1f})">')
        svg.append(f"<title>{title}</title>")
        svg.append(
            f'<circle r="{radius:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width:.1f}"/>'
        )
        if node_id in rank_by_id:
            svg.append(
                f'<text x="0" y="3" text-anchor="middle" font-size="7.2" font-weight="800" fill="#111827">{html_escape(rank_by_id[node_id])}</text>'
            )
        if is_leaf:
            label = truncate_middle(node.get("patent_id") or f"#{node.get('index')}", 13)
            svg.append(
                f'<text x="0" y="{radius + 8:.1f}" text-anchor="middle" font-size="6.6" font-weight="700" fill="#111827">{html_escape(label)}</text>'
            )
        else:
            svg.append(
                f'<text x="{radius + 6:.1f}" y="3" font-size="7.4" font-weight="800" fill="#111827">#{html_escape(node.get("index"))}</text>'
            )
        svg.append("</g>")
    svg.append("</g></svg>")
    return "\n".join(svg)


def descendant_patent_label(node, limit=4):
    patent_ids = node.get("descendant_patent_ids") or []
    if not patent_ids and node.get("patent_id"):
        patent_ids = [node.get("patent_id")]
    patent_ids = [clean_text(value) for value in patent_ids if value]
    if not patent_ids:
        return "-"
    shown = patent_ids[:limit]
    suffix = "" if len(patent_ids) <= limit else f" +{len(patent_ids) - limit}"
    return ", ".join(shown) + suffix


def node_meaning_text(node):
    if int(node.get("layer", 0)) == 0:
        title = clean_text(node.get("title", ""))
        preview = clean_text(node.get("text_preview", ""))
        if title and preview and title.lower() not in preview.lower():
            return f"{title}. {preview}"
        return title or preview or "Leaf patent"
    preview = clean_text(node.get("text_preview", ""))
    return preview or "Summary node"


def highlighted_meaning_html(node, css_class, terms):
    meaning = node_meaning_text(node)
    if not terms:
        return html.escape(meaning)
    pattern = compile_terms_pattern(terms)
    parts = []
    last = 0
    for match in pattern.finditer(meaning):
        parts.append(html.escape(meaning[last:match.start()]))
        matched = match.group(1)
        parts.append(
            f'<span class="evidence-hit {css_class}" title="also appears in answer">{html.escape(matched)}</span>'
        )
        last = match.end()
    parts.append(html.escape(meaning[last:]))
    return "".join(parts)


def source_node_rows(method_data, nodes, source_limit=8):
    source_nodes = []
    seen = set()
    for source in method_data.get("source_nodes") or []:
        node_id = str(source.get("node_index"))
        if not node_id or node_id in seen or node_id not in nodes:
            continue
        source_nodes.append((source, nodes[node_id]))
        seen.add(node_id)
        if len(source_nodes) >= source_limit:
            break
    return source_nodes


def render_node_meaning_table(method_data, nodes, source_limit=8, question=""):
    source_nodes = source_node_rows(method_data, nodes, source_limit)
    if not source_nodes:
        return ""
    answer = clean_text(method_data.get("answer", ""), 950)
    evidence_map = build_evidence_assignments(answer, source_nodes, question=question)
    terms_by_node = evidence_map["terms_by_node"]
    rows = [
        "<table class='node-meaning-table'><thead><tr><th>Rank</th><th>Node</th><th>Layer</th><th>Meaning</th><th>Patent IDs covered</th></tr></thead><tbody>"
    ]
    for index, (source, node) in enumerate(source_nodes, start=1):
        css_class = f"ev{min(index, 8)}"
        node_key = str(node.get("index"))
        layer_value = node.get("layer", "")
        if layer_value is None:
            layer_value = ""
        rows.append(
            "<tr><td>{}</td><td>#{}</td><td>L{}</td><td>{}</td><td>{}</td></tr>".format(
                html_escape(source.get("rank", "")),
                html_escape(node.get("index", "")),
                html.escape(str(layer_value)),
                highlighted_meaning_html(node, css_class, terms_by_node.get(node_key, [])),
                html_escape(descendant_patent_label(node)),
            )
        )
    rows.append("</tbody></table>")
    return "\n".join(rows)


EVIDENCE_STOPWORDS = {
    "이", "그", "저", "및", "또는", "그리고", "있다", "있는", "한다", "하여", "위해", "통해",
    "기술", "특허", "묶음", "문서", "핵심", "구성", "요소", "목적", "효과", "기반",
    "포함", "대한", "관련", "사용", "수행", "생성", "제공", "처리", "시스템", "장치",
    "방법", "데이터", "정보", "결과", "각", "및", "the", "and", "for", "with", "that",
    "this", "from", "using", "based", "method", "system", "data", "device",
    "하는", "합니다", "있습니다", "것입니다", "됩니다", "위한", "통한", "이를", "해당",
    "일부", "여러", "전체", "가능한", "적어도", "데이터가", "데이터를", "데이터의",
    "정보를", "수행하는", "적용되어", "트리",
}

CONCEPT_ALIASES = [
    ("quantization", "quantization", "quantize", "quantized", "양자화"),
    ("bit", "bit", "bits", "비트"),
    ("memory", "memory", "메모리"),
    ("bandwidth", "bandwidth", "대역폭"),
    ("neural network", "neural network", "neural networks", "신경망"),
    ("power", "power", "전력"),
    ("efficiency", "efficiency", "efficient", "효율", "효율적", "효율적으로"),
    ("operation", "operation", "operations", "compute", "computation", "연산"),
    ("PIM/CIM", "PIM/CIM", "PIM", "CIM"),
    ("NoC", "NoC"),
    ("GEMM", "GEMM"),
    ("chiplet", "chiplet", "chiplets", "칩렛"),
    ("voltage", "voltage", "전압"),
    ("clock", "clock", "클록"),
    ("scheduling", "scheduling", "scheduler", "스케줄링"),
    ("NPU", "NPU"),
    ("GPU", "GPU"),
    ("data path", "data path", "데이터 경로"),
    ("traffic", "traffic", "트래픽"),
    ("cache", "cache", "캐시"),
    ("sensor", "sensor", "sensors", "센서"),
]


TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9/·+\-]{2,}|[가-힣][가-힣A-Za-z0-9/·+\-]{1,}")
TOKEN_STRIP_CHARS = ".,;:()[]{}<>\"'“”‘’/"
TERM_BOUNDARY_LEFT = r"(?<![A-Za-z0-9가-힣])"
TERM_BOUNDARY_RIGHT = r"(?![A-Za-z0-9가-힣])"
KOREAN_PARTICLE_RIGHT = r"(?=$|[^A-Za-z0-9가-힣]|[은는이가을를와과도에의로])"


def term_right_boundary(term):
    if re.fullmatch(r"[가-힣]{2,}", term):
        return KOREAN_PARTICLE_RIGHT
    return TERM_BOUNDARY_RIGHT


def compile_terms_pattern(terms):
    alternatives = []
    for term in sorted(set(terms), key=len, reverse=True):
        alternatives.append(re.escape(term) + term_right_boundary(term))
    return re.compile(TERM_BOUNDARY_LEFT + "(" + "|".join(alternatives) + ")", flags=re.IGNORECASE)


def token_key_set(text):
    return {
        token.strip(TOKEN_STRIP_CHARS).lower()
        for token in TOKEN_RE.findall(clean_text(text))
        if token.strip(TOKEN_STRIP_CHARS)
    }


def evidence_terms(answer, node, max_terms=5):
    answer_text = clean_text(answer)
    answer_tokens = token_key_set(answer_text)
    meaning = " ".join(
        [
            node_meaning_text(node),
            clean_text(node.get("title", "")),
            clean_text(node.get("text_preview", "")),
        ]
    )
    terms = []
    seen = set()
    for raw in TOKEN_RE.findall(meaning):
        term = raw.strip(TOKEN_STRIP_CHARS)
        key = term.lower()
        if key in seen or key in EVIDENCE_STOPWORDS:
            continue
        if len(term) < 2:
            continue
        if key in answer_tokens:
            seen.add(key)
            terms.append(term)
    terms.sort(key=lambda value: (len(value), value), reverse=True)
    filtered = []
    for term in terms:
        key = term.lower()
        if key not in answer_tokens:
            continue
        filtered.append(term)
        if len(filtered) >= max_terms:
            break
    return filtered


def term_exists(text, term):
    if not text or not term:
        return False
    return bool(compile_terms_pattern([term]).search(text))


def present_alias_terms(text, aliases):
    return [term for term in aliases if term_exists(text, term)]


def add_unique_term(items, term, limit):
    key = term.lower()
    if key in {item.lower() for item in items}:
        return False
    if len(items) >= limit:
        return False
    items.append(term)
    return True


def alias_evidence_pairs(answer, node):
    answer_text = clean_text(answer)
    meaning = node_meaning_text(node)
    pairs = []
    for aliases in CONCEPT_ALIASES:
        source_terms = present_alias_terms(meaning, aliases)
        answer_terms = present_alias_terms(answer_text, aliases)
        if not source_terms or not answer_terms:
            continue
        pairs.append((source_terms[0], answer_terms[0]))
    return pairs


def question_overlap_terms(question, node, max_terms=3):
    if not question:
        return []
    return evidence_terms(question, node, max_terms=max_terms)


def bm25_source_terms(source, node, max_terms=3):
    meaning = node_meaning_text(node)
    terms = []
    for item in source.get("bm25_top_terms") or []:
        term = clean_text(item.get("term", ""))
        if term and term.lower() not in EVIDENCE_STOPWORDS and term_exists(meaning, term):
            add_unique_term(terms, term, max_terms)
    return terms


def salient_source_terms(node, max_terms=3):
    meaning = node_meaning_text(node)
    candidates = []
    seen = set()
    for raw in TOKEN_RE.findall(meaning):
        term = raw.strip(TOKEN_STRIP_CHARS)
        key = term.lower()
        if not term or key in seen or key in EVIDENCE_STOPWORDS or len(term) < 3:
            continue
        seen.add(key)
        score = len(term)
        if any(ch.isdigit() for ch in term) or "/" in term or "·" in term or "-" in term:
            score += 8
        if re.search(r"[A-Z]{2,}", term):
            score += 6
        if re.search(r"[가-힣]", term) and len(term) >= 4:
            score += 3
        candidates.append((score, term))
    candidates.sort(key=lambda item: (item[0], len(item[1]), item[1]), reverse=True)
    terms = []
    for _, term in candidates:
        add_unique_term(terms, term, max_terms)
    return terms


def add_answer_term_mapping(term_to_class, class_to_node, term, css_class, node_label, max_terms_total):
    key = term.lower()
    if key in term_to_class:
        return False
    if len(term_to_class) >= max_terms_total:
        return False
    term_to_class[key] = (term, css_class, node_label)
    class_to_node.setdefault(css_class, node_label)
    return True


def build_evidence_assignments(answer, source_nodes, question="", max_terms_total=24, max_terms_per_node=5):
    term_to_class = {}
    class_to_node = {}
    terms_by_node = defaultdict(list)
    for index, (source, node) in enumerate(source_nodes, start=1):
        css_class = f"ev{min(index, 8)}"
        node_key = str(node.get("index"))
        node_label = f"#{node.get('index')}"
        for term in evidence_terms(answer, node, max_terms=max_terms_per_node * 2):
            key = term.lower()
            if key in term_to_class:
                continue
            if len(terms_by_node[node_key]) >= max_terms_per_node:
                continue
            if add_answer_term_mapping(term_to_class, class_to_node, term, css_class, node_label, max_terms_total):
                terms_by_node[node_key].append(term)
            if len(term_to_class) >= max_terms_total:
                break

        for source_term, answer_term in alias_evidence_pairs(answer, node):
            if len(terms_by_node[node_key]) >= max_terms_per_node:
                break
            if add_answer_term_mapping(term_to_class, class_to_node, answer_term, css_class, node_label, max_terms_total):
                add_unique_term(terms_by_node[node_key], source_term, max_terms_per_node)

        for term in question_overlap_terms(question, node, max_terms=max_terms_per_node):
            if len(terms_by_node[node_key]) >= max_terms_per_node:
                break
            add_unique_term(terms_by_node[node_key], term, max_terms_per_node)

        for term in bm25_source_terms(source, node, max_terms=max_terms_per_node):
            if len(terms_by_node[node_key]) >= max_terms_per_node:
                break
            add_unique_term(terms_by_node[node_key], term, max_terms_per_node)

        if not terms_by_node[node_key]:
            for term in salient_source_terms(node, max_terms=3):
                add_unique_term(terms_by_node[node_key], term, max_terms_per_node)

    return {
        "term_to_class": term_to_class,
        "class_to_node": class_to_node,
        "terms_by_node": terms_by_node,
    }


def highlighted_answer_html(answer, source_nodes):
    answer_text = clean_text(answer, 950)
    if not answer_text:
        return "-", []

    evidence_map = build_evidence_assignments(answer_text, source_nodes)
    term_to_class = evidence_map["term_to_class"]
    class_to_node = evidence_map["class_to_node"]

    if not term_to_class:
        return html.escape(answer_text), []

    terms = sorted((value[0] for value in term_to_class.values()), key=len, reverse=True)
    pattern = compile_terms_pattern(terms)
    parts = []
    last = 0
    used_classes = []
    for match in pattern.finditer(answer_text):
        parts.append(html.escape(answer_text[last:match.start()]))
        matched = match.group(1)
        _, css_class, node_label = term_to_class.get(matched.lower(), (matched, "ev1", "source node"))
        if css_class not in used_classes:
            used_classes.append(css_class)
        parts.append(
            f'<span class="evidence-hit {css_class}" title="{html.escape(node_label)}">{html.escape(matched)}</span>'
        )
        last = match.end()
    parts.append(html.escape(answer_text[last:]))
    legend = [(css_class, class_to_node.get(css_class, "")) for css_class in used_classes]
    return "".join(parts), legend


def render_answer_evidence(
    method_data,
    nodes,
    source_limit=8,
    title="Answer with node evidence underline",
    note="위 node table의 형광펜은 retrieved source의 retrieval/evidence cue를 표시합니다. Answer의 형광 밑줄은 그중 실제 답변 문장에 반영된 표현을 같은 node 색으로 연결한 것입니다.",
):
    source_nodes = source_node_rows(method_data, nodes, source_limit=source_limit)
    answer = method_data.get("answer", "")
    if not answer:
        return ""
    answer_html, legend = highlighted_answer_html(answer, source_nodes)
    legend_html = ""
    if legend:
        legend_html = "<div class='evidence-legend'>" + "".join(
            f"<span class='evidence-chip'><span class='evidence-hit {html.escape(css_class)}'>{html.escape(node_label)}</span></span>"
            for css_class, node_label in legend
        ) + "</div>"
    return "\n".join(
        [
            "<div class='answer-evidence'>",
            f"<h4>{html_escape(title)}</h4>",
            legend_html,
            f"<p class='answer-text'>{answer_html}</p>",
            f"<p class='small'>{html_escape(note)}</p>",
            "</div>",
        ]
    )


def method_eval(qa_item, answer_eval, method_name):
    qa_index = str(qa_item.get("qa_index", ""))
    method_data = qa_item.get("methods", {}).get(method_name, {})
    row = answer_eval.get((qa_index, method_name), {})
    return {
        "method": method_name,
        "score": as_float(row.get("judge_score", method_data.get("judge_score"))),
        "supported": str(row.get("judge_supported", method_data.get("judge_supported", ""))).lower() == "true",
        "hit": str(row.get("hit", method_data.get("hit", ""))) in {"1", "true", "True"},
        "rank": row.get("rank", method_data.get("rank", "")) or "-",
        "recall": as_float(row.get("source_recall", method_data.get("source_recall", ""))),
        "answer_recall": as_float(row.get("answer_recall", method_data.get("answer_recall", ""))),
        "answer_f1": as_float(row.get("answer_f1", method_data.get("answer_f1", ""))),
        "best_method": row.get("best_method", ""),
        "best_reason": clean_text(row.get("best_reason", ""), 220),
    }


def best_method_for_qa(qa_item, answer_eval):
    qa_index = str(qa_item.get("qa_index", ""))
    for row in qa_eval_rows(answer_eval, qa_index):
        if row.get("best_method"):
            return row.get("best_method", "")

    methods = qa_item.get("methods", {}) or {}
    if not methods:
        return ""
    return max(
        methods,
        key=lambda method_name: (
            method_eval(qa_item, answer_eval, method_name)["score"],
            method_eval(qa_item, answer_eval, method_name)["supported"],
            method_eval(qa_item, answer_eval, method_name)["hit"],
        ),
    )


def usefulness_verdict(qa_item, answer_eval, method_name):
    current = method_eval(qa_item, answer_eval, method_name)
    best_method = best_method_for_qa(qa_item, answer_eval)
    best = method_eval(qa_item, answer_eval, best_method) if best_method else current
    metric_text = (
        f"score {current['score']:.0f}/5, supported={str(current['supported']).lower()}, "
        f"answer_f1={current['answer_f1']:.2f}, answer_recall={current['answer_recall']:.2f}, "
        f"hit={'yes' if current['hit'] else 'no'}"
    )
    if method_name == best_method:
        return (
            "Recommended",
            "best",
            f"이 QA에서 GPT-5.5 judge가 가장 쓸만한 조건으로 선택했습니다 ({metric_text}).",
        )
    if (
        current["score"] == best["score"]
        and current["supported"] == best["supported"]
        and current["hit"] == best["hit"]
    ):
        return (
            "Comparable",
            "comparable",
            f"best는 {best_method}이지만, 이 조건도 같은 수준의 score/support/hit을 보였습니다 ({metric_text}).",
        )
    if current["score"] >= 4 and current["supported"]:
        return (
            "Usable, but not best",
            "usable",
            f"답변은 사용 가능하지만 best 조건인 {best_method}보다 덜 완전합니다 ({metric_text}).",
        )
    return (
        "Less useful",
        "weak",
        f"이 QA에서는 best 조건인 {best_method}보다 답변 품질 또는 근거성이 약했습니다 ({metric_text}).",
    )


def render_usefulness_note(qa_item, answer_eval, method_name):
    label, css_class, reason = usefulness_verdict(qa_item, answer_eval, method_name)
    best_method = best_method_for_qa(qa_item, answer_eval)
    return (
        f"<div class='usefulness {html_escape(css_class)}'>"
        f"<strong>Usefulness:</strong> {html_escape(label)}"
        f" <span class='small'>best={html_escape(best_method or '-')}</span><br>"
        f"{html_escape(reason)}"
        "</div>"
    )


def render_visualization_verdict_summary(cases, source_map, answer_eval):
    qa_indices = []
    shown_by_qa = defaultdict(list)
    for case in cases:
        qa_index = str(case.get("qa_index", ""))
        if qa_index not in qa_indices:
            qa_indices.append(qa_index)
        shown_by_qa[qa_index].append(case.get("method", ""))
        if case.get("compare_without"):
            counterpart = without_raptor_counterpart(case.get("method", ""))
            if counterpart:
                shown_by_qa[qa_index].append(counterpart)

    rows = [
        "<table><thead><tr><th>QA</th><th>Compared conditions in Visualization</th><th>Most useful condition</th><th>Why</th></tr></thead><tbody>"
    ]
    for qa_index in qa_indices:
        qa_item = source_map.get(qa_index, {})
        best_method = best_method_for_qa(qa_item, answer_eval)
        best_eval = method_eval(qa_item, answer_eval, best_method) if best_method else {}
        reason = best_eval.get("best_reason") or usefulness_verdict(qa_item, answer_eval, best_method)[2]
        shown = ", ".join(dict.fromkeys(method for method in shown_by_qa[qa_index] if method))
        rows.append(
            "<tr><td>QA {}</td><td>{}</td><td><strong>{}</strong><br><span class='small'>score {}/5, supported={}, answer_f1={}, answer_recall={}</span></td><td>{}</td></tr>".format(
                html_escape(qa_index),
                html_escape(shown or "-"),
                html_escape(best_method or "-"),
                fmt(best_eval.get("score"), 0),
                html_escape(str(best_eval.get("supported", "-")).lower()),
                fmt(best_eval.get("answer_f1")),
                fmt(best_eval.get("answer_recall")),
                html_escape(clean_text(reason, 180)),
            )
        )
    rows.append("</tbody></table>")
    return "\n".join(rows)


def without_raptor_counterpart(method_name):
    if method_name == "dense_bge_m3_with_raptor":
        return "dense_bge_m3_without_raptor"
    if method_name == "bm25_with_raptor":
        return "bm25_without_raptor"
    if method_name == "dpr_with_raptor":
        return "dpr_without_raptor"
    return ""


def render_without_raptor_comparison(case, qa_item, nodes, answer_eval):
    if not case.get("compare_without"):
        return ""
    without_method_name = without_raptor_counterpart(case.get("method", ""))
    if not without_method_name:
        return ""
    without_method = qa_item.get("methods", {}).get(without_method_name, {})
    if not without_method:
        return ""
    meta = [
        f"method={without_method_name}",
        f"score={without_method.get('judge_score', '-')}",
        f"supported={without_method.get('judge_supported', '-')}",
        f"hit/rank={without_method.get('hit', '-')}/{without_method.get('rank') or '-'}",
        f"sources={len(without_method.get('source_nodes') or [])}",
        "view=ranked leaf retrieval",
    ]
    return "\n".join(
        [
            "<div class='without-comparison'>",
            "<div class='without-visual-head'>",
            "<h4>Same query without RAPTOR</h4>",
            f"<div class='tree-meta'>{''.join(f'<span class=\"tag\">{html_escape(item)}</span>' for item in meta)}</div>",
            render_usefulness_note(qa_item, answer_eval, without_method_name),
            "<div class='note tree-note small'>동일 질문과 동일 retriever에서 RAPTOR summary node를 제거하고 leaf patent만 검색한 결과입니다. Tree overlay 대신 ranked leaf evidence로 비교합니다.</div>",
            render_source_path_svg(qa_item, without_method_name, nodes, 0),
            "<div class='tree-legend'>"
            "<span><span class='legend-dot' style='background:#2563eb'></span>AA</span>"
            "<span><span class='legend-dot' style='background:#dc2626'></span>AB</span>"
            "<span><span class='legend-dot' style='background:#059669'></span>AC</span>"
            "<span><span class='legend-dot' style='background:#d97706'></span>AD</span>"
            "<span><span class='legend-dot' style='border:2px solid #f59e0b;background:#fff'></span>retrieved leaf</span>"
            "</div>",
            "</div>",
            render_node_meaning_table(without_method, nodes, source_limit=4, question=qa_item.get("question", "")),
            render_answer_evidence(
                without_method,
                nodes,
                source_limit=4,
                title="Without RAPTOR answer with leaf evidence underline",
                note="위 leaf table의 모든 행은 retrieved leaf입니다. Table 형광펜은 retrieval/evidence cue이고, Answer 형광 밑줄은 실제 답변 문장에 반영된 표현을 같은 leaf 색으로 연결한 것입니다. with RAPTOR와 달리 상위 summary node 없이 leaf patent만 근거로 사용했습니다.",
            ),
            "</div>",
        ]
    )


def render_tree_case(case, source_map, nodes, max_layer, answer_eval):
    qa_item = source_map.get(str(case["qa_index"]))
    if not qa_item:
        return ""
    method_name = case["method"]
    method = qa_item.get("methods", {}).get(method_name, {})
    if not method:
        return ""
    category = qa_item.get("category", "")
    category_name = qa_item.get("category_name", "")
    question = clean_text(qa_item.get("question", ""), 165)
    meta = [
        f"method={method_name}",
        f"score={method.get('judge_score', '-')}",
        f"supported={method.get('judge_supported', '-')}",
        f"hit/rank={method.get('hit', '-')}/{method.get('rank') or '-'}",
        f"sources={len(method.get('source_nodes') or [])}",
        f"path nodes={len(method.get('path_node_indices') or [])}",
    ]
    return "\n".join(
        [
            '<div class="tree-case">',
            f"<h3>QA {html_escape(case['qa_index'])} | {html_escape(category)} {html_escape(category_name)} | {html_escape(case['label'])}</h3>",
            f"<p>{html_escape(question)}</p>",
            f"<div class='tree-meta'>{''.join(f'<span class=\"tag\">{html_escape(item)}</span>' for item in meta)}</div>",
            render_usefulness_note(qa_item, answer_eval, method_name),
            f"<div class='note tree-note small'>{html_escape(method_view_note(method_name))}</div>",
            render_source_path_svg(qa_item, method_name, nodes, max_layer),
            "<div class='tree-legend'>"
            "<span><span class='legend-dot' style='background:#2563eb'></span>AA</span>"
            "<span><span class='legend-dot' style='background:#dc2626'></span>AB</span>"
            "<span><span class='legend-dot' style='background:#059669'></span>AC</span>"
            "<span><span class='legend-dot' style='background:#d97706'></span>AD</span>"
            "<span><span class='legend-dot' style='border:2px solid #f59e0b;background:#fff'></span>retrieved</span>"
            "</div>",
            render_node_meaning_table(method, nodes, question=qa_item.get("question", "")),
            render_answer_evidence(method, nodes),
            render_without_raptor_comparison(case, qa_item, nodes, answer_eval),
            "</div>",
        ]
    )


def choose_representative_tree_cases(source_map):
    has_v3 = any(
        method.endswith("_with_raptor")
        for item in source_map.values()
        for method in (item.get("methods", {}) or {})
    )
    if not has_v3:
        return REPRESENTATIVE_TREE_CASES

    cases = [
        case
        for case in V3_REPRESENTATIVE_TREE_CASES
        if source_map.get(case["qa_index"], {}).get("methods", {}).get(case["method"])
    ]
    if len(cases) >= 4:
        return cases

    seen = {(case["qa_index"], case["method"]) for case in cases}
    for qa_index in sorted(source_map, key=lambda value: int(value or 0)):
        methods = source_map[qa_index].get("methods", {}) or {}
        for method in ("bm25_with_raptor", "dense_bge_m3_with_raptor"):
            if method in methods and (qa_index, method) not in seen:
                cases.append(
                    {
                        "qa_index": qa_index,
                        "method": method,
                        "label": "With RAPTOR source placement",
                    }
                )
                seen.add((qa_index, method))
                break
        if len(cases) >= 4:
            break
    return cases


def render_visualization_overview(source_map, answer_eval):
    selected_cases = choose_representative_tree_cases(source_map)
    if not selected_cases:
        return ""
    return "\n".join(
        [
            "<h2>Visualization</h2>",
            "<p class='small'>With RAPTOR는 source node와 ancestor path를 mini-tree로, without RAPTOR는 같은 질문의 ranked leaf retrieval strip으로 표시했습니다. 원 안의 숫자는 retrieval rank입니다.</p>",
            render_visualization_verdict_summary(selected_cases, source_map, answer_eval),
        ]
    )


def render_representative_tree_appendix(source_map, nodes, max_layer, answer_eval, include_overview=True):
    selected_cases = choose_representative_tree_cases(source_map)
    rendered = [
        (case, render_tree_case(case, source_map, nodes, max_layer, answer_eval))
        for case in selected_cases
    ]
    rendered = [(case, html_block) for case, html_block in rendered if html_block]
    if not rendered:
        return ""
    rendered_cases = []
    for index, (case, html_block) in enumerate(rendered):
        if index == 2 or case.get("label") == "BM25 limitation: source hit but answer unsupported":
            rendered_cases.append("<div class='page-break'></div>")
        rendered_cases.append(html_block)
    parts = ["<div class='page-break'></div>"]
    if include_overview:
        parts.append(render_visualization_overview(source_map, answer_eval))
    parts.extend(rendered_cases)
    return "\n".join(part for part in parts if part)


def build_report(run_dir, output_path):
    answer_rows = read_csv(run_dir / "answer_eval.csv")
    ensure_paper_metrics(answer_rows)
    retrieval_rows = read_csv(run_dir / "retrieval_eval.csv")
    appendix_rows = read_csv(run_dir / "appendix_e_audit.csv")
    answer_eval = answer_eval_lookup(answer_rows)
    source_map = load_source_map(run_dir)
    tree_nodes, max_layer = load_tree_nodes(run_dir)
    cards = parse_report_cards(run_dir)
    sampled_count, cat_text = dataset_summary(run_dir)

    answer_f1_scores = summarize_by_method(answer_rows, "answer_f1")
    answer_recall_scores = summarize_by_method(answer_rows, "answer_recall")
    answer_scores = summarize_by_method(answer_rows, "judge_score")
    answer_accuracy = summarize_by_method(answer_rows, "paper_accuracy")
    retrieval_hits = summarize_by_method(retrieval_rows, "hit")
    winners = best_counts(answer_rows)
    bm25 = bm25_wins(answer_rows)
    collapsed = collapsed_wins(answer_rows, source_map)
    collapsed_strict = sum(1 for row in collapsed if row["outcome"] == "strict")
    collapsed_tie = sum(1 for row in collapsed if row["outcome"] == "tie")
    raptor_deltas = with_without_delta_rows(answer_rows)
    raptor_wins = raptor_win_cases(answer_rows, source_map)
    appendix_total, appendix_hallucinated, severity_counts, appendix_samples = appendix_summary(appendix_rows)

    best_answer_method, best_answer_f1 = max(answer_f1_scores.items(), key=lambda item: item[1])

    methods = sorted(
        set(answer_f1_scores) | set(answer_scores) | set(retrieval_hits),
        key=method_sort_key,
    )
    is_v3 = any("with_raptor" in method for method in methods)

    parts = [
        "<!doctype html>",
        '<html lang="ko"><head><meta charset="utf-8">',
        "<title>RAPTOR Patent Experiment Report - Compact Print</title>",
        f"<style>{CSS}</style>",
        "</head><body>",
        '<div class="toolbar"><a href="report.html">Full report</a><a href="report_presentation.html">Presentation</a><button type="button" onclick="window.print()">Print A4</button></div>',
        "<h1>RAPTOR Patent Experiment Report<br><span class='small'>Compact A4 Print Version</span></h1>",
        "<div class='note'><strong>Purpose.</strong> 이 파일은 발표/제출용 압축본입니다. 전체 QA source overlay, 전체 judge note, 전체 Appendix audit는 full report와 tree visualization에 보존했습니다.</div>",
        "<h2>Executive Summary</h2>",
        "<ul>",
        f"<li><strong>Paper main metric:</strong> QASPER식 Answer F1 평균은 <code>{html_escape(best_answer_method)}</code>가 가장 높았습니다 ({best_answer_f1:.3f}).</li>",
        "<li><strong>Accuracy:</strong> Accuracy는 논문 QuALITY식 정답률을 그대로 쓴 것이 아니라, <code>judge_score >= 4</code> 및 <code>supported=true</code> 조건을 만족한 비율입니다.</li>",
        "<li><strong>BM25:</strong> 질문과 특허 요약 사이에 희귀 전문 용어가 직접 겹칠 때 강했습니다. 이는 semantic reasoning보다 lexical overlap/IDF 효과로 해석하는 것이 맞습니다.</li>",
        "<li><strong>Summary risk:</strong> Appendix E에서는 summary node에 unsupported claim이 자주 관찰되어, source overlay와 leaf 확인이 필요합니다.</li>",
        "</ul>",
        "<h2>Experiment Setup</h2>",
        "<table><tbody>",
        f"<tr><th>Dataset</th><td>{sampled_count} patents; {html_escape(cat_text)}</td></tr>",
        f"<tr><th>Text / metadata</th><td>Index text column: {html_escape(cards.get('Text column', '요약'))}; metadata keeps patent_id, 중분류, 중분류명</td></tr>",
        f"<tr><th>Embedding / clustering</th><td>{html_escape(cards.get('Embedding', 'minilm'))}; hard clustering, average child size near RAPTOR Appendix C target</td></tr>",
        f"<tr><th>LLM</th><td>{html_escape(cards.get('LLM model', 'gpt-5.5'))}; calls={html_escape(cards.get('LLM calls', '-'))}; runtime={html_escape(cards.get('Actual runtime', '-'))}</td></tr>",
        f"<tr><th>Retrieval modes</th><td>{', '.join(html_escape(m) for m in methods)}</td></tr>",
        "</tbody></table>",
        "<div class='page-break'></div>",
        "<h2>Core Metrics</h2>",
        "<table><thead><tr><th>Method</th><th>Answer F1</th><th>Answer Recall</th><th>Accuracy</th><th>Avg Judge Score</th><th>Best count</th></tr></thead><tbody>",
    ]
    for method in methods:
        parts.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html_escape(method),
                fmt(answer_f1_scores.get(method)),
                fmt(answer_recall_scores.get(method)),
                fmt(answer_accuracy.get(method)),
                fmt(answer_scores.get(method)),
                html_escape(winners.get(method, 0)),
            )
        )
    parts.extend(
        [
            "</tbody></table>",
            "<h3>How to read Core Metrics</h3>",
            "<table class='metric-guide-table'><thead><tr><th>Metric</th><th>Type</th><th>Meaning</th><th>How to read it</th></tr></thead><tbody>",
            "<tr><td><code>Answer F1</code></td><td><span class='metric-kind'>Answer</span></td><td>reader 답변과 GPT-5.5 reference answer 사이의 token-overlap F1 평균</td><td>RAPTOR 논문의 QASPER Answer F1에 맞춘 본 실험의 메인 성능 지표입니다.</td></tr>",
            "<tr><td><code>Answer Recall</code></td><td><span class='metric-kind'>Answer</span></td><td>reference answer token 중 reader 답변에도 등장한 token 비율</td><td>높을수록 reference answer의 핵심 표현을 더 많이 회수했습니다. F1 계산에 사용된 recall입니다.</td></tr>",
            "<tr><td><code>Accuracy</code></td><td><span class='metric-kind'>Answer</span></td><td><code>judge_score >= 4</code> 이고 <code>supported=true</code>인 QA 비율</td><td>QuALITY식 정답률과 대응시키기 위한 judge 기반 correctness proxy입니다.</td></tr>",
            "<tr><td><code>Avg Judge Score</code></td><td><span class='metric-kind'>Answer</span></td><td>GPT-5.5 judge가 reference answer와 retrieved context 기준으로 reader 답변을 0-5점 평가한 평균</td><td>Answer F1이 단어 겹침을 보는 한계를 보완하는 보조 품질 지표입니다.</td></tr>",
            "<tr><td><code>Best count</code></td><td><span class='metric-kind'>Answer</span></td><td>QA별 4개 method 답변 비교에서 GPT-5.5 judge가 best method로 고른 횟수</td><td>높을수록 여러 QA에서 상대적으로 가장 좋은 답변으로 선택됐습니다.</td></tr>",
            "</tbody></table>",
        ]
    )

    parts.extend(
        [
            "<h2>Interpretation</h2>",
            "<table><thead><tr><th>Observation</th><th>Interpretation</th></tr></thead><tbody>",
            "<tr><td>With RAPTOR 비교</td><td>V3는 leaf-only 검색과 RAPTOR 전체 node 검색을 같은 retriever별로 비교해 summary tree의 기여를 분리합니다.</td></tr>" if is_v3 else "<tr><td>Collapsed Tree score가 가장 높음</td><td>root-to-leaf 경로에 묶이지 않고, 같은 token budget 안에서 leaf 직접 근거와 상위 summary를 같이 고른 점이 reader 답변에 유리했습니다.</td></tr>",
            "<tr><td>Dense retriever 보정</td><td>논문의 DPR 개념은 한/영 특허 데이터에 맞춰 BGE-M3 dense retriever로 대체 해석했습니다.</td></tr>" if is_v3 else "<tr><td>Traverse Tree retrieval은 강함</td><td>경로 기반 탐색이라 answer source를 잘 포함하지만, 상위 summary가 넓게 들어오면 reader가 특허 번호/세부 구성까지 답하지 못하는 경우가 있었습니다.</td></tr>",
            "<tr><td>BM25는 특정 QA에서 강함</td><td>희귀 단어가 질문과 문서에 직접 겹치면 embedding보다 선명하게 해당 leaf를 끌어올립니다. 그래서 patent query처럼 전문 용어가 많은 데이터에서 baseline 가치가 큽니다.</td></tr>",
            "<tr><td>Appendix E hallucination risk</td><td>summary node는 압축에는 유용하지만 unsupported claim이 섞일 수 있습니다. 최종 답변 검증에는 leaf/source overlay가 필요합니다.</td></tr>",
            "</tbody></table>",
            "<h2>Why BM25 Remains Competitive on Patent Data</h2>",
            "<p>특허 문서는 기술 용어와 구성요소 명칭이 정밀하게 유지되는 문서 유형입니다. 소설이나 일반 서술형 문서와 달리, 단어 하나가 특정 구조나 기능을 가리키는 식별자처럼 작동하므로 BM25의 lexical matching이 강한 baseline이 됩니다.</p>",
            "<table><thead><tr><th>Patent text property</th><th>BM25 advantage</th></tr></thead><tbody>",
            "<tr><td>전문 용어의 희소성</td><td>GEMM, DDR, GaN, 부동 게이트, 정규화 회로처럼 corpus 전체에서 드문 용어는 IDF가 커져 검색 점수를 강하게 끌어올립니다.</td></tr>",
            "<tr><td>구성요소 명칭의 반복</td><td>특허 요약은 핵심 부품과 동작을 반복 설명하므로 term frequency가 높아지고, 같은 용어가 질문에 있으면 BM25가 뚜렷하게 반응합니다.</td></tr>",
            "<tr><td>표현의 정밀성</td><td>기술 용어는 자유롭게 치환되기보다 원문 표현이 유지됩니다. 그래서 dense similarity보다 exact-match가 더 직접적인 신호가 될 수 있습니다.</td></tr>",
            "</tbody></table>",
            "<p>따라서 본 실험은 RAPTOR가 BM25를 모든 검색 지표에서 일방적으로 압도했다기보다, BM25는 precise lexical retrieval에 강하고 with-RAPTOR 전체 node 검색은 최종 QA 답변 생성에 필요한 summary evidence를 보강하는 상보적 관계로 해석하는 것이 적절합니다.</p>" if is_v3 else "<p>따라서 본 실험은 RAPTOR가 BM25를 모든 검색 지표에서 일방적으로 압도했다기보다, BM25는 precise lexical retrieval에 강하고 collapsed-tree RAPTOR는 최종 QA 답변 생성에 강한 상보적 관계를 보였다고 해석하는 것이 적절합니다.</p>",
        ]
    )
    if is_v3:
        parts.extend(
            [
                "<h2>RAPTOR Win Analysis - Representative Cases</h2>",
                f"<p class='small'>With RAPTOR가 without RAPTOR보다 Answer F1, Answer Recall, Accuracy, Judge score 중 하나 이상 좋아진 사례 {len(raptor_wins)}개 중 대표 5개입니다. RAPTOR 재현 관점에서는 이 표가 핵심입니다.</p>",
                "<table class='raptor-win-table'><thead><tr><th>QA</th><th>Ret.</th><th>Ans Δ</th><th>Qual Δ</th><th>Layers</th><th>Top sources</th><th>Why improved</th></tr></thead><tbody>",
            ]
        )
        for row in raptor_wins[:5]:
            parts.append(
                "<tr><td><span class='qa-cell'>{}<span class='qa-type'>{}</span></span></td><td>{}</td><td class='delta-cell'>F1 <strong>{:+.3f}</strong><br>Rec {:+.3f}</td><td class='delta-cell'>Acc {:+.3f}<br>J {:+.3f}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    html_escape(row["qa_index"]),
                    html_escape(row["question_type"]),
                    html_escape(compact_retriever_label(row["retriever"])),
                    row["answer_f1_delta"],
                    row["answer_recall_delta"],
                    row["accuracy_delta"],
                    row["score_delta"],
                    semicolon_lines_html(row["layer_mix"]),
                    semicolon_lines_html(row["top_sources"]),
                    html_escape(clean_text(row["note"], 180)),
                )
            )
        parts.extend(["</tbody></table>"])
    else:
        parts.extend(
            [
                "<h2>BM25 Win Analysis - Representative Cases</h2>",
                f"<p class='small'>Full report 기준 BM25 최고점/동점 사례 {len(bm25)}개 중 대표 5개만 표시합니다.</p>",
                "<table><thead><tr><th>QA</th><th>Score</th><th>Question</th><th>Top terms</th><th>Interpretation</th></tr></thead><tbody>",
            ]
        )
        for row in bm25[:5]:
            parts.append(
                "<tr><td>{}</td><td>BM25 {} vs {} {}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    html_escape(row["qa_index"]),
                    html_escape(row["score"]),
                    html_escape(row["other_method"]),
                    html_escape(row["other_score"]),
                    html_escape(clean_text(row["question"], 135)),
                    term_tags(row["terms"]),
                    html_escape(clean_text(row["note"], 170)),
                )
            )
        parts.append("</tbody></table>")
    if is_v3:
        parts.extend(
            [
                "<h2>With/Without RAPTOR Delta - Compressed</h2>",
                "<p class='small'>V3는 같은 retriever에서 leaf-only 검색과 RAPTOR 전체 node 검색을 비교합니다. 아래 값은 10개 QA 평균 차이이며, 논문 메인 표 기준에 맞춰 Answer F1과 Answer Recall을 앞에 둡니다.</p>",
                "<table class='raptor-delta-table'><thead><tr><th>Ret.</th><th>Without</th><th>With RAPTOR</th><th>Ans Δ</th><th>Qual Δ</th><th>Interpretation</th></tr></thead><tbody>",
            ]
        )
        for row in raptor_deltas:
            answer_f1_delta = row["answer_f1_with"] - row["answer_f1_without"]
            answer_recall_delta = row["answer_recall_with"] - row["answer_recall_without"]
            score_delta = row["score_with"] - row["score_without"]
            accuracy_delta = row["accuracy_with"] - row["accuracy_without"]
            if answer_f1_delta >= 0.03:
                note = "summary node가 reference answer와의 표현/내용 overlap을 뚜렷하게 보강했습니다."
            elif answer_f1_delta > 0:
                note = "summary node가 최종 답변 품질을 일부 보강했습니다."
            else:
                note = "leaf-only 근거가 더 직접적인 QA가 섞여 있습니다."
            parts.append(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td class='delta-cell'>F1 {:+.3f}<br>Rec {:+.3f}</td><td class='delta-cell'>Acc {:+.3f}<br>J {:+.3f}</td><td>{}</td></tr>".format(
                    html_escape(compact_retriever_label(row["label"])),
                    html_escape(compact_method_label(row["without"])),
                    html_escape(compact_method_label(row["with"])),
                    answer_f1_delta,
                    answer_recall_delta,
                    accuracy_delta,
                    score_delta,
                    html_escape(note),
                )
            )
        parts.append("</tbody></table>")
        split_table = render_query_type_split_table(answer_rows)
        if split_table:
            parts.append(split_table)
    else:
        parts.extend(
            [
                "<h2>Collapsed Tree Win Analysis - Compressed</h2>",
                f"<p class='small'>Collapsed Tree는 strict win {collapsed_strict}개, 최고점 동점 {collapsed_tie}개였습니다. 아래는 strict win 우선 대표 5개입니다.</p>",
                "<table><thead><tr><th>QA</th><th>Outcome</th><th>Score</th><th>Layer mix</th><th>Top sources</th><th>Why it worked</th></tr></thead><tbody>",
            ]
        )
        for row in collapsed[:5]:
            parts.append(
                "<tr><td>{}</td><td>{}</td><td>Collapsed {} vs {} {}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    html_escape(row["qa_index"]),
                    html_escape(row["outcome"]),
                    html_escape(row["score"]),
                    html_escape(row["other_method"]),
                    html_escape(row["other_score"]),
                    html_escape(row["layer_mix"]),
                    html_escape(row["top_sources"]),
                    html_escape(clean_text(row["note"], 190)),
                )
            )
        parts.extend(["</tbody></table>"])

    parts.extend(
        [
            "<div class='page-break'></div>",
            "<h2>Appendix E Summary</h2>",
            "<table><tbody>",
            f"<tr><th>Audited summary nodes</th><td>{appendix_total}</td></tr>",
            f"<tr><th>Unsupported claim detected</th><td>{appendix_hallucinated} / {appendix_total} ({(appendix_hallucinated / appendix_total if appendix_total else 0):.3f})</td></tr>",
            f"<tr><th>Severity mix</th><td>{', '.join(f'{html_escape(k)}={v}' for k, v in sorted(severity_counts.items()))}</td></tr>",
            "<tr><th>상위 노드 전파 여부</th><td>본 audit 범위에서는 환각 증상이 상위 노드로 전파되지 않았습니다. 탐지된 unsupported claim은 하위 summary node에서만 관찰되었고, 감사한 상위 parent node로 같은 환각 claim이 전파된 증거는 없었습니다.</td></tr>",
            "</tbody></table>",
            "<table class='appendix-sample-table'><thead><tr><th>Node</th><th>Severity</th><th>Representative unsupported claim</th></tr></thead><tbody>",
        ]
    )
    for sample in appendix_samples:
        parts.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html_escape(sample["node"]),
                html_escape(sample["severity"]),
                html_escape(clean_text(sample["claim"], 210)),
            )
        )
    parts.extend(["</tbody></table>"])

    visualization_overview = render_visualization_overview(source_map, answer_eval)
    if visualization_overview:
        parts.append(visualization_overview)

    tree_appendix = render_representative_tree_appendix(
        source_map,
        tree_nodes,
        max_layer,
        answer_eval,
        include_overview=False,
    )
    if tree_appendix:
        parts.append(tree_appendix)

    parts.extend(
        [
            "<div class='note small'><strong>Reading guide.</strong> 이 compact print는 결론과 대표 근거만 담습니다. 특정 QA의 source path, node text, full answer, judge explanation은 <code>report.html</code>과 <code>tree_visualization.html</code>에서 확인하세요.</div>",
            f"<p class='small'>Generated {html_escape(datetime.now().isoformat(timespec='seconds'))} from run {html_escape(run_dir.name)}</p>",
            "</body></html>",
        ]
    )
    output_path.write_text("\n".join(parts), encoding="utf-8")
    return output_path


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    build_report(args.run_dir, args.output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
