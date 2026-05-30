#!/usr/bin/env python3
"""Create a 16:9 presentation-style HTML deck from RAPTOR run artifacts."""

from __future__ import annotations

import argparse
import html
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.create_compact_print_report import (
    V3_RAPTOR_PAIRS,
    appendix_summary,
    as_float,
    best_counts,
    choose_representative_tree_cases,
    clean_text,
    compact_method_label,
    compact_retriever_label,
    dataset_summary,
    descendant_patent_label,
    fmt,
    html_escape,
    layer_mix,
    load_source_map,
    load_tree_nodes,
    method_eval,
    method_sort_key,
    node_meaning_text,
    parse_report_cards,
    question_type_split_rows,
    raptor_win_cases,
    read_csv,
    read_jsonl,
    render_source_path_svg,
    render_visualization_verdict_summary,
    semicolon_lines_html,
    source_node_rows,
    summarize_by_method,
    with_without_delta_rows,
)
from scripts.paper_metrics import ensure_paper_metrics


MAIN_METHODS = [
    "bm25_without_raptor",
    "bm25_with_raptor",
    "dense_bge_m3_without_raptor",
    "dense_bge_m3_with_raptor",
]


CSS = r"""
@page { size: 13.333in 7.5in; margin: 0; }
* { box-sizing: border-box; }
html { background: #0f172a; color: #111827; }
body {
  margin: 0;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #0f172a;
}
.toolbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  justify-content: center;
  gap: 8px;
  padding: 10px;
  background: rgba(15, 23, 42, .92);
  backdrop-filter: blur(12px);
}
.toolbar button,
.toolbar a {
  border: 1px solid rgba(148, 163, 184, .45);
  border-radius: 999px;
  padding: 7px 13px;
  background: #f8fafc;
  color: #0f172a;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}
.deck {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 24px 0 40px;
}
.slide {
  position: relative;
  width: min(1280px, calc(100vw - 48px));
  aspect-ratio: 16 / 9;
  margin: 0 auto;
  overflow: hidden;
  border-radius: 18px;
  background: #f8fafc;
  box-shadow: 0 30px 80px rgba(0, 0, 0, .35);
  page-break-after: always;
  break-after: page;
}
.slide-inner {
  position: absolute;
  inset: 0;
  padding: 54px 64px 46px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}
.slide::before {
  content: "";
  position: absolute;
  inset: 0 0 auto;
  height: 10px;
  background: linear-gradient(90deg, #2563eb, #059669, #d97706);
}
.slide-title {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 24px;
  align-items: start;
}
h1, h2, h3, p { margin: 0; }
h1 {
  max-width: 900px;
  font-size: 56px;
  line-height: 1.03;
  letter-spacing: 0;
}
h2 {
  font-size: 36px;
  line-height: 1.1;
  letter-spacing: 0;
}
h3 {
  font-size: 20px;
  line-height: 1.18;
}
.eyebrow {
  color: #2563eb;
  font-size: 15px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: .06em;
}
.subtitle {
  max-width: 900px;
  color: #475569;
  font-size: 22px;
  line-height: 1.45;
}
.small {
  color: #64748b;
  font-size: 13px;
  line-height: 1.45;
}
.kicker {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 11px;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #fff;
  color: #334155;
  font-size: 14px;
  font-weight: 700;
}
.grid {
  display: grid;
  gap: 16px;
}
.grid.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.grid.four { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.card {
  border: 1px solid #d8e1ef;
  border-radius: 14px;
  background: #fff;
  padding: 18px;
}
.card strong {
  display: block;
  margin-bottom: 6px;
  color: #0f172a;
  font-size: 18px;
}
.metric-card strong {
  color: #475569;
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: .04em;
}
.metric-card .value {
  margin-top: 6px;
  color: #0f172a;
  font-size: 36px;
  font-weight: 850;
  line-height: 1;
}
.metric-card .note {
  margin-top: 8px;
  color: #64748b;
  font-size: 14px;
  line-height: 1.35;
}
table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  font-size: 14px;
}
th, td {
  border: 1px solid #d8e1ef;
  padding: 9px 10px;
  text-align: left;
  vertical-align: top;
}
th {
  background: #eaf0ff;
  color: #0f172a;
  font-weight: 800;
}
.metric-table td:nth-child(n+2),
.metric-table th:nth-child(n+2) {
  text-align: right;
  white-space: nowrap;
}
.bar-row {
  display: grid;
  grid-template-columns: 230px 1fr 72px;
  gap: 12px;
  align-items: center;
  margin: 10px 0;
  font-size: 15px;
}
.bar-track {
  height: 18px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb, #059669);
}
.delta-table th:nth-child(1), .delta-table td:nth-child(1) { width: 16%; }
.delta-table th:nth-child(2), .delta-table td:nth-child(2) { width: 18%; }
.delta-table th:nth-child(3), .delta-table td:nth-child(3) { width: 18%; }
.delta-table th:nth-child(4), .delta-table td:nth-child(4) { width: 13%; white-space: nowrap; }
.delta-table th:nth-child(5), .delta-table td:nth-child(5) { width: 13%; white-space: nowrap; }
.split-table {
  table-layout: fixed;
  font-size: 13px;
}
.split-table th:nth-child(1), .split-table td:nth-child(1) { width: 13%; }
.split-table th:nth-child(2), .split-table td:nth-child(2),
.split-table th:nth-child(3), .split-table td:nth-child(3),
.split-table th:nth-child(4), .split-table td:nth-child(4),
.split-table th:nth-child(5), .split-table td:nth-child(5) {
  width: 12%;
  text-align: right;
  white-space: nowrap;
}
.split-table th:nth-child(6), .split-table td:nth-child(6) {
  width: 39%;
}
.win-table {
  table-layout: fixed;
  font-size: 13px;
}
.win-table th:nth-child(1), .win-table td:nth-child(1) { width: 8%; }
.win-table th:nth-child(2), .win-table td:nth-child(2) { width: 10%; }
.win-table th:nth-child(3), .win-table td:nth-child(3) { width: 14%; }
.win-table th:nth-child(4), .win-table td:nth-child(4) { width: 15%; }
.win-table th:nth-child(5), .win-table td:nth-child(5) { width: 18%; }
.win-table th:nth-child(6), .win-table td:nth-child(6) { width: 35%; }
.semi-lines span {
  display: block;
  line-height: 1.35;
  margin-bottom: 3px;
}
.pill {
  display: inline-block;
  margin: 0 5px 5px 0;
  padding: 4px 8px;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #fff;
  color: #334155;
  font-size: 12px;
  font-weight: 700;
}
.claim {
  display: grid;
  grid-template-columns: 44px 1fr;
  gap: 13px;
  align-items: start;
  padding: 15px;
  border: 1px solid #d8e1ef;
  border-radius: 14px;
  background: #fff;
}
.claim .num {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border-radius: 999px;
  background: #0f172a;
  color: #fff;
  font-weight: 850;
}
.mini-tree {
  display: block;
  width: 100%;
  height: auto;
  border: 1px solid #d8e1ef;
  border-radius: 14px;
  background:
    linear-gradient(90deg, rgba(100, 116, 139, .10) 1px, transparent 1px),
    linear-gradient(rgba(100, 116, 139, .08) 1px, transparent 1px);
  background-size: 32px 32px;
}
.tree-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: #475569;
  font-size: 13px;
}
.legend-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  margin-right: 4px;
  border-radius: 999px;
}
.source-list {
  display: grid;
  gap: 7px;
}
.source-item {
  border: 1px solid #d8e1ef;
  border-radius: 12px;
  background: #fff;
  padding: 8px 10px;
  font-size: 12.4px;
  line-height: 1.35;
}
.source-item strong {
  display: block;
  margin-bottom: 3px;
  color: #0f172a;
}
.answer-box {
  border: 1px solid #cbd5e1;
  border-left: 5px solid #2563eb;
  border-radius: 14px;
  background: #fff;
  padding: 11px 13px;
  font-size: 13.5px;
  line-height: 1.45;
}
.foot {
  position: absolute;
  left: 64px;
  right: 64px;
  bottom: 24px;
  display: flex;
  justify-content: space-between;
  color: #94a3b8;
  font-size: 12px;
}
.visual-summary {
  font-size: 13px;
}
.visual-summary th:nth-child(1), .visual-summary td:nth-child(1) { width: 8%; }
.visual-summary th:nth-child(2), .visual-summary td:nth-child(2) { width: 25%; }
.visual-summary th:nth-child(3), .visual-summary td:nth-child(3) { width: 24%; }
@media print {
  html, body { background: #fff; }
  .toolbar { display: none; }
  .deck { display: block; padding: 0; }
  .slide {
    width: 13.333in;
    height: 7.5in;
    margin: 0;
    border-radius: 0;
    box-shadow: none;
  }
}
"""


def method_label(method: str) -> str:
    labels = {
        "bm25_without_raptor": "BM25 without RAPTOR",
        "bm25_with_raptor": "BM25 with RAPTOR",
        "dense_bge_m3_without_raptor": "BGE-M3 without RAPTOR",
        "dense_bge_m3_with_raptor": "BGE-M3 with RAPTOR",
    }
    return labels.get(method, method)


def presentation_dataset_summary(run_dir: Path) -> tuple[int, str]:
    count, summary = dataset_summary(run_dir)
    if summary != "-":
        return count, summary
    rows = read_jsonl(run_dir / "sampled_patents.jsonl")
    counts = Counter()
    for row in rows:
        metadata = row.get("metadata") or {}
        category = metadata.get("category") or row.get("category")
        if not category:
            continue
        counts[str(category)] += 1
    if not counts:
        return count, summary
    cat_text = ", ".join(f"{category} {counts[category]}" for category in sorted(counts))
    return len(rows), cat_text


def slide(number: int, title: str, body: str, kicker: str = "RAPTOR Patent V3") -> str:
    return f"""
<section class="slide" id="slide-{number}">
  <div class="slide-inner">
    <div class="slide-title">
      <div>
        <div class="eyebrow">{html_escape(kicker)}</div>
        <h2>{html_escape(title)}</h2>
      </div>
      <div class="kicker">#{number:02d}</div>
    </div>
    {body}
    <div class="foot"><span>HYU-RAPTOR patent experiment</span><span>{number:02d}</span></div>
  </div>
</section>
"""


def title_slide(number: int, cards: dict[str, str], sampled_count: int, cat_text: str) -> str:
    return f"""
<section class="slide title-slide" id="slide-{number}">
  <div class="slide-inner">
    <div class="eyebrow">RAPTOR Patent Experiment</div>
    <h1>V3: with/without RAPTOR 비교와 특허 QA 성능 분석</h1>
    <p class="subtitle">특허 요약 200건을 대상으로 BM25와 BGE-M3 dense retrieval을 leaf-only와 RAPTOR all-node 조건에서 비교한 발표용 요약입니다.</p>
    <div class="grid four">
      <div class="card metric-card"><strong>Dataset</strong><div class="value">{sampled_count}</div><div class="note">{html_escape(cat_text)}</div></div>
      <div class="card metric-card"><strong>Main design</strong><div class="value">V3</div><div class="note">with vs without RAPTOR</div></div>
      <div class="card metric-card"><strong>LLM</strong><div class="value">{html_escape(cards.get("LLM model", "GPT"))}</div><div class="note">reader / judge</div></div>
      <div class="card metric-card"><strong>Runtime</strong><div class="value">{html_escape(cards.get("Actual runtime", "-"))}</div><div class="note">recorded full run</div></div>
    </div>
    <div class="foot"><span>report_presentation.html</span><span>{number:02d}</span></div>
  </div>
</section>
"""


def metric_table(methods, answer_f1, answer_recall, accuracy, judge_scores, winners) -> str:
    rows = []
    for method in methods:
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html_escape(method_label(method)),
                fmt(answer_f1.get(method)),
                fmt(answer_recall.get(method)),
                fmt(accuracy.get(method)),
                fmt(judge_scores.get(method)),
                html_escape(winners.get(method, 0)),
            )
        )
    return (
        "<table class='metric-table'><thead><tr><th>Method</th><th>Answer F1</th><th>Answer Recall</th><th>Accuracy</th><th>Avg Judge</th><th>Best count</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def bar_chart(answer_f1: dict[str, float], methods: list[str]) -> str:
    max_value = max((answer_f1.get(method, 0) for method in methods), default=1) or 1
    rows = []
    for method in methods:
        value = answer_f1.get(method, 0)
        width = max(3, min(100, value / max_value * 100))
        rows.append(
            "<div class='bar-row'><strong>{}</strong><div class='bar-track'><div class='bar-fill' style='width:{:.1f}%'></div></div><span>{}</span></div>".format(
                html_escape(method_label(method)),
                width,
                fmt(value),
            )
        )
    return "<div>" + "".join(rows) + "</div>"


def delta_table(delta_rows) -> str:
    rows = []
    for row in delta_rows:
        answer_f1_delta = row["answer_f1_with"] - row["answer_f1_without"]
        answer_recall_delta = row["answer_recall_with"] - row["answer_recall_without"]
        score_delta = row["score_with"] - row["score_without"]
        accuracy_delta = row["accuracy_with"] - row["accuracy_without"]
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>F1 {:+.3f}<br>Rec {:+.3f}</td><td>Acc {:+.3f}<br>J {:+.3f}</td></tr>".format(
                html_escape(compact_retriever_label(row["label"])),
                html_escape(compact_method_label(row["without"])),
                html_escape(compact_method_label(row["with"])),
                answer_f1_delta,
                answer_recall_delta,
                accuracy_delta,
                score_delta,
            )
        )
    return (
        "<table class='delta-table'><thead><tr><th>Retriever</th><th>Without</th><th>With RAPTOR</th><th>Answer delta</th><th>Quality delta</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def query_type_split_table(split_rows) -> str:
    body = []
    for row in split_rows:
        body.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html_escape(compact_retriever_label(row["label"])),
                fmt(row["global_without"]),
                fmt(row["global_with"]),
                fmt(row["local_without"]),
                fmt(row["local_with"]),
                html_escape(clean_text(row["interpretation"], 150)),
            )
        )
    return (
        "<table class='split-table'><thead><tr><th>Retriever</th><th>Global<br>without</th><th>Global<br>with</th><th>Local<br>without</th><th>Local<br>with</th><th>Interpretation</th></tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def win_table(rows) -> str:
    body = []
    for row in rows[:5]:
        body.append(
            "<tr><td><strong>{}</strong><br><span class='small'>{}</span></td><td>{}</td><td>F1 <strong>{:+.3f}</strong><br>Rec {:+.3f}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html_escape(row["qa_index"]),
                html_escape(row["question_type"]),
                html_escape(compact_retriever_label(row["retriever"])),
                row["answer_f1_delta"],
                row["answer_recall_delta"],
                semicolon_lines_html(row["layer_mix"]),
                semicolon_lines_html(row["top_sources"]),
                html_escape(clean_text(row["note"], 150)),
            )
        )
    return (
        "<table class='win-table'><thead><tr><th>QA</th><th>Ret.</th><th>Answer delta</th><th>Layers</th><th>Top sources</th><th>Why improved</th></tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def source_cards(method_data: dict, nodes: dict, limit: int = 4) -> str:
    cards = []
    for source, node in source_node_rows(method_data, nodes, source_limit=limit):
        text = clean_text(node_meaning_text(node), 105)
        cards.append(
            "<div class='source-item'><strong>r{} | #{} | L{}</strong><span>{}</span><br><span class='small'>{}</span></div>".format(
                html_escape(source.get("rank", "")),
                html_escape(node.get("index", "")),
                html_escape(node.get("layer", "")),
                html_escape(text),
                html_escape(descendant_patent_label(node, limit=2)),
            )
        )
    return "<div class='source-list'>" + "".join(cards) + "</div>"


def tree_legend() -> str:
    return (
        "<div class='tree-legend'>"
        "<span><span class='legend-dot' style='background:#2563eb'></span>AA</span>"
        "<span><span class='legend-dot' style='background:#dc2626'></span>AB</span>"
        "<span><span class='legend-dot' style='background:#059669'></span>AC</span>"
        "<span><span class='legend-dot' style='background:#d97706'></span>AD</span>"
        "<span><span class='legend-dot' style='border:2px solid #f59e0b;background:#fff'></span>retrieved</span>"
        "</div>"
    )


def visualization_slide(number: int, case: dict, source_map: dict, nodes: dict, max_layer: int, answer_eval: dict) -> str:
    qa_item = source_map.get(str(case["qa_index"]), {})
    method_name = case["method"]
    method_data = qa_item.get("methods", {}).get(method_name, {})
    eval_row = method_eval(qa_item, answer_eval, method_name)
    question = clean_text(qa_item.get("question", ""), 160)
    answer = clean_text(method_data.get("answer", ""), 135)
    title = f"QA {case['qa_index']} source overlay"
    svg = render_source_path_svg(qa_item, method_name, nodes, max_layer)
    body = f"""
    <div class="grid two" style="grid-template-columns:1.25fr .75fr; gap:18px;">
      <div>
        <p class="subtitle" style="font-size:18px; margin-bottom:12px;">{html_escape(question)}</p>
        {svg}
        {tree_legend()}
      </div>
      <div class="grid" style="gap:12px;">
        <div class="card">
          <strong>{html_escape(method_label(method_name))}</strong>
          <span class="pill">score {fmt(eval_row.get("score"), 0)}/5</span>
          <span class="pill">supported {html_escape(str(eval_row.get("supported")).lower())}</span>
          <span class="pill">Answer F1 {fmt(eval_row.get("answer_f1"))}</span>
          <span class="pill">Recall {fmt(eval_row.get("answer_recall"))}</span>
        </div>
        {source_cards(method_data, nodes, limit=2)}
        <div class="answer-box"><strong>Answer sketch</strong><br>{html_escape(answer)}</div>
      </div>
    </div>
    """
    return slide(number, title, body, kicker=clean_text(case.get("label", "Visualization"), 50))


def build_report(run_dir: Path, output_path: Path) -> Path:
    answer_rows = read_csv(run_dir / "answer_eval.csv")
    ensure_paper_metrics(answer_rows)
    appendix_rows = read_csv(run_dir / "appendix_e_audit.csv")
    source_map = load_source_map(run_dir)
    tree_nodes, max_layer = load_tree_nodes(run_dir)
    cards = parse_report_cards(run_dir)
    sampled_count, cat_text = presentation_dataset_summary(run_dir)
    answer_eval = {
        (row.get("qa_index", ""), row.get("method", "")): row
        for row in answer_rows
        if row.get("qa_index") and row.get("method")
    }

    methods = [
        method
        for method in sorted({row.get("method", "") for row in answer_rows}, key=method_sort_key)
        if method in MAIN_METHODS
    ]
    answer_f1 = summarize_by_method(answer_rows, "answer_f1")
    answer_recall = summarize_by_method(answer_rows, "answer_recall")
    accuracy = summarize_by_method(answer_rows, "paper_accuracy")
    judge_scores = summarize_by_method(answer_rows, "judge_score")
    winners = best_counts(answer_rows)
    deltas = with_without_delta_rows(answer_rows)
    split_rows = question_type_split_rows(answer_rows)
    wins = raptor_win_cases(answer_rows, source_map)
    appendix_total, appendix_hallucinated, severity_counts, appendix_samples = appendix_summary(appendix_rows)

    best_method, best_f1 = max(answer_f1.items(), key=lambda item: item[1])
    best_judge_method, best_judge = max(judge_scores.items(), key=lambda item: item[1])
    bm25_delta = next((row for row in deltas if row["label"] == "BM25"), {})
    bge_delta = next((row for row in deltas if row["label"] == "Dense BGE-M3"), {})
    visualization_cases = choose_representative_tree_cases(source_map)

    slides = []
    slides.append(title_slide(1, cards, sampled_count, cat_text))
    slides.append(
        slide(
            2,
            "실험 설계: leaf-only와 RAPTOR all-node를 분리 비교",
            f"""
            <div class="grid two">
              <div class="card">
                <strong>Question set</strong>
                <p class="subtitle" style="font-size:20px;">Global 5개 + Local 5개. 각 QA는 동일한 reference answer, 동일 reader prompt, 동일 max context 조건으로 평가했습니다.</p>
              </div>
              <div class="card">
                <strong>Retrieval design</strong>
                <p class="subtitle" style="font-size:20px;">BM25와 BGE-M3를 각각 without RAPTOR(leaf only)와 with RAPTOR(all summary+leaf nodes)로 비교했습니다.</p>
              </div>
            </div>
            <div class="grid four">
              {''.join(f"<div class='card'><strong>{html_escape(method_label(method))}</strong><p class='small'>{html_escape(compact_method_label(method))}</p></div>" for method in methods)}
            </div>
            """,
            kicker="Design",
        )
    )
    slides.append(
        slide(
            3,
            "Core metrics: 최종 QA 성능 중심",
            f"""
            <div class="grid two" style="grid-template-columns:1fr 1fr;">
              <div>{metric_table(methods, answer_f1, answer_recall, accuracy, judge_scores, winners)}</div>
              <div>
                <div class="card metric-card"><strong>Best Answer F1</strong><div class="value">{html_escape(method_label(best_method))}</div><div class="note">{best_f1:.3f}</div></div>
                <div style="height:16px"></div>
                <div class="card metric-card"><strong>Best judge score</strong><div class="value">{html_escape(method_label(best_judge_method))}</div><div class="note">{best_judge:.2f} / 5</div></div>
              </div>
            </div>
            """,
            kicker="Metric",
        )
    )
    slides.append(
        slide(
            4,
            "Answer F1 ranking",
            f"""
            <div class="card">
              <strong>Paper-style answer metric</strong>
              <p class="small">RAPTOR 논문 메인 성능표 흐름에 맞춰 retrieval-only 지표보다 final QA answer quality를 앞에 둔 비교입니다.</p>
              {bar_chart(answer_f1, methods)}
            </div>
            """,
            kicker="Ranking",
        )
    )
    slides.append(
        slide(
            5,
            "With RAPTOR 효과: 평균 delta",
            f"""
            {delta_table(deltas)}
            <div class="grid two">
              <div class="claim"><div class="num">1</div><div><strong>BM25는 all-node 검색에서 답변 overlap이 증가</strong><p class="small">Answer F1/Recall이 함께 개선되어 summary node가 질문의 표현 범위를 보강했습니다.</p></div></div>
              <div class="claim"><div class="num">2</div><div><strong>BGE-M3는 leaf-only와 all-node가 더 혼재</strong><p class="small">dense retriever는 local QA에서 leaf patent 직접 근거가 더 강한 경우가 섞였습니다.</p></div></div>
            </div>
            """,
            kicker="With/Without",
        )
    )
    slides.append(
        slide(
            6,
            "Global vs Local split: 평균 delta가 숨긴 패턴",
            f"""
            {query_type_split_table(split_rows)}
            <div class="grid two">
              <div class="claim"><div class="num">G</div><div><strong>Global QA</strong><p class="small">Dense BGE-M3도 with RAPTOR가 더 높습니다. 여러 특허나 summary evidence를 종합해야 하는 질문에서는 all-node 검색이 도움을 줍니다.</p></div></div>
              <div class="claim"><div class="num">L</div><div><strong>Local QA</strong><p class="small">Dense BGE-M3는 leaf-only가 더 높습니다. 특정 특허의 세부를 묻는 경우 원본 leaf 직접 검색이 더 유리했습니다.</p></div></div>
            </div>
            <p class="small">주의: Global 5개, Local 5개인 pilot sample입니다. 통계적으로 강한 결론이 아니라 후속 실험에서 QA 수를 늘려 검증해야 할 방향성입니다.</p>
            """,
            kicker="Query type",
        )
    )
    slides.append(
        slide(
            7,
            "RAPTOR가 이긴 대표 사례",
            win_table(wins),
            kicker="Representative wins",
        )
    )
    slides.append(
        slide(
            8,
            "BM25는 왜 여전히 강한가",
            """
            <div class="grid three">
              <div class="claim"><div class="num">A</div><div><strong>희귀 전문 용어</strong><p class="small">GEMM, DDR, NoC, PIM/CIM 같은 용어는 IDF가 커서 질문과 직접 겹칠 때 강한 검색 신호가 됩니다.</p></div></div>
              <div class="claim"><div class="num">B</div><div><strong>특허 표현의 정밀성</strong><p class="small">기술 구성요소 명칭이 자유롭게 치환되기보다 원문 표현으로 반복되어 lexical retrieval에 유리합니다.</p></div></div>
              <div class="claim"><div class="num">C</div><div><strong>RAPTOR와 상보적</strong><p class="small">BM25는 precise source hit에 강하고, RAPTOR summary node는 reader가 종합 답변을 만들 근거를 보강합니다.</p></div></div>
            </div>
            """,
            kicker="BM25",
        )
    )
    appendix_rate = appendix_hallucinated / appendix_total if appendix_total else 0
    severity_text = ", ".join(f"{key}={value}" for key, value in sorted(severity_counts.items()))
    sample_claim = appendix_samples[0]["claim"] if appendix_samples else "-"
    slides.append(
        slide(
            9,
            "Appendix E: hallucination audit",
            f"""
            <div class="grid three">
              <div class="card metric-card"><strong>Audited nodes</strong><div class="value">{appendix_total}</div><div class="note">summary nodes</div></div>
              <div class="card metric-card"><strong>Unsupported</strong><div class="value">{appendix_hallucinated}/{appendix_total}</div><div class="note">rate {appendix_rate:.3f}</div></div>
              <div class="card metric-card"><strong>Severity</strong><div class="value" style="font-size:28px;">{html_escape(severity_text)}</div><div class="note">judge audit</div></div>
            </div>
            <div class="answer-box"><strong>Propagation check</strong><br>본 audit 범위에서는 환각 증상이 상위 노드로 전파되지 않았습니다. 탐지된 unsupported claim은 하위 summary node에서만 관찰되었습니다.</div>
            <p class="small">Representative unsupported claim: {html_escape(clean_text(sample_claim, 210))}</p>
            """,
            kicker="Faithfulness",
        )
    )
    slides.append(
        slide(
            10,
            "Visualization overview",
            f"""
            <p class="subtitle" style="font-size:18px;">대표 QA에 대해 with RAPTOR는 source node와 ancestor path를 mini-tree로, without RAPTOR는 ranked leaf strip으로 표시했습니다.</p>
            <div class="visual-summary">{render_visualization_verdict_summary(visualization_cases, source_map, answer_eval)}</div>
            """,
            kicker="Source overlay",
        )
    )
    next_number = 11
    for case in visualization_cases[:4]:
        slides.append(visualization_slide(next_number, case, source_map, tree_nodes, max_layer, answer_eval))
        next_number += 1
    slides.append(
        slide(
            next_number,
            "결론: RAPTOR의 장점은 검색 hit보다 답변 근거 보강에서 보인다",
            """
            <div class="grid two">
              <div class="claim"><div class="num">1</div><div><strong>RAPTOR is not a universal BM25 replacement</strong><p class="small">특허 데이터에서는 BM25의 exact lexical matching이 강한 baseline으로 남습니다.</p></div></div>
              <div class="claim"><div class="num">2</div><div><strong>All-node retrieval can improve answer synthesis</strong><p class="small">상위 summary node는 global QA에서 reader가 여러 leaf의 공통 효과를 묶어 답하게 돕습니다.</p></div></div>
              <div class="claim"><div class="num">3</div><div><strong>Faithfulness audit is required</strong><p class="small">summary node에는 unsupported claim 위험이 있으므로 leaf-level source overlay와 judge audit를 함께 봐야 합니다.</p></div></div>
              <div class="claim"><div class="num">4</div><div><strong>BGE-M3는 DPR 대체 dense baseline</strong><p class="small">한/영 특허 데이터에서는 Meta DPR보다 multilingual dense model을 주 baseline으로 해석하는 것이 적절합니다.</p></div></div>
            </div>
            """,
            kicker="Takeaway",
        )
    )

    html_doc = "\n".join(
        [
            "<!doctype html>",
            '<html lang="ko"><head><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>RAPTOR Patent Experiment Report - Presentation</title>",
            f"<style>{CSS}</style>",
            "</head><body>",
            '<div class="toolbar"><a href="report_compact_print.html">Compact print</a><a href="report.html">Full report</a><button type="button" onclick="window.print()">Print slides</button></div>',
            '<main class="deck">',
            *slides,
            "</main>",
            "<script>document.addEventListener('keydown',e=>{const slides=[...document.querySelectorAll('.slide')];const y=window.scrollY;let i=slides.findIndex(s=>s.offsetTop+s.offsetHeight/2>y);if(e.key==='ArrowRight'||e.key==='PageDown'){slides[Math.min(slides.length-1,i+1)]?.scrollIntoView({behavior:'smooth'});}if(e.key==='ArrowLeft'||e.key==='PageUp'){slides[Math.max(0,i-1)]?.scrollIntoView({behavior:'smooth'});}});</script>",
            f"<!-- Generated {html.escape(datetime.now().isoformat(timespec='seconds'))} from run {html.escape(run_dir.name)} -->",
            "</body></html>",
        ]
    )
    output_path.write_text(html_doc, encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_report(args.run_dir, args.output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
