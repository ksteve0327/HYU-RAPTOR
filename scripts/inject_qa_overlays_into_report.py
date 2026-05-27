#!/usr/bin/env python3
"""Inject per-question QA source mini-tree overlays into an existing report.html."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Dict, List


METHOD_ORDER = ["traverse_tree", "collapsed_tree", "bm25_leaf", "dpr_leaf"]


def compact_node(node: Dict) -> Dict:
    return {
        "id": str(node["id"]),
        "index": node["index"],
        "layer": node["layer"],
        "node_type": node.get("node_type", ""),
        "children": [str(value) for value in node.get("children", [])],
        "parents": [str(value) for value in node.get("parents", [])],
        "patent_id": node.get("patent_id", ""),
        "title": node.get("title", ""),
        "category": node.get("category", ""),
        "category_name": node.get("category_name", ""),
        "dominant_category": node.get("dominant_category", ""),
        "descendant_leaf_count": node.get("descendant_leaf_count", 0),
        "text_preview": node.get("text_preview", ""),
    }


def compact_source(source: Dict) -> Dict:
    return {
        "rank": source.get("rank", ""),
        "node_index": source.get("node_index", ""),
        "layer": source.get("layer", ""),
        "score": source.get("score", ""),
        "token_count": source.get("token_count", ""),
        "contains_expected": source.get("contains_expected", False),
        "descendant_patent_ids": source.get("descendant_patent_ids", [])[:8],
    }


def compact_method(method: Dict) -> Dict:
    return {
        "method": method.get("method", ""),
        "answer": method.get("answer", ""),
        "judge_score": method.get("judge_score", ""),
        "judge_supported": method.get("judge_supported", ""),
        "judge_explanation": method.get("judge_explanation", ""),
        "hit": method.get("hit", ""),
        "rank": method.get("rank", ""),
        "mrr": method.get("mrr", ""),
        "latency_seconds": method.get("latency_seconds", ""),
        "source_nodes": [
            compact_source(source) for source in method.get("source_nodes", [])
        ],
        "source_node_indices": method.get("source_node_indices", []),
        "path_node_indices": method.get("path_node_indices", []),
    }


def compact_qa(qa: Dict) -> Dict:
    methods = {}
    for method_name in METHOD_ORDER:
        if method_name in qa.get("methods", {}):
            methods[method_name] = compact_method(qa["methods"][method_name])
    return {
        "qa_index": qa.get("qa_index"),
        "question": qa.get("question", ""),
        "reference_answer": qa.get("reference_answer", ""),
        "expected_patent_ids": qa.get("expected_patent_ids", []),
        "expected_node_indices": qa.get("expected_node_indices", []),
        "category": qa.get("category", ""),
        "category_name": qa.get("category_name", ""),
        "question_type": qa.get("question_type", ""),
        "methods": methods,
    }


def build_payload(tree_data: Dict, qa_sources: Dict) -> Dict:
    return {
        "meta": {
            "num_layers": tree_data["meta"]["num_layers"],
            "category_names": tree_data["meta"].get("category_names", {}),
        },
        "nodes": [compact_node(node) for node in tree_data["nodes"]],
        "qa_items": [compact_qa(qa) for qa in qa_sources["qa_items"]],
        "method_order": METHOD_ORDER,
    }


def json_for_script(payload: Dict) -> str:
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def section_html(payload: Dict) -> str:
    payload_json = json_for_script(payload)
    return """<!-- qa-source-overlays:start -->
<section id="qa-source-overlays" class="qa-source-overlays">
<style>
.qa-source-overlays{margin:28px 0}
.qa-source-intro{margin:0 0 14px;color:#4b5563}
.qa-card{display:grid;grid-template-columns:1fr;gap:14px;align-items:stretch;background:white;border:1px solid #d1d5db;border-radius:8px;padding:14px;margin:14px 0}
.qa-copy,.qa-viz-panel{min-width:0}
.qa-meta{font-size:12px;color:#64748b;font-weight:700;margin-bottom:6px}
.qa-question{font-size:16px;line-height:1.45;margin:0 0 10px;color:#111827}
.qa-control-row{display:grid;grid-template-columns:minmax(180px,240px) 1fr;gap:10px;align-items:center;margin:8px 0}
.qa-control-row label{font-size:12px;color:#475569;font-weight:700}
.qa-method-select{width:100%;border:1px solid #cbd5e1;border-radius:7px;padding:7px 8px;background:white;color:#111827}
.qa-metrics{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}
.qa-pill{display:inline-flex;align-items:center;border:1px solid #cbd5e1;border-radius:999px;padding:3px 8px;font-size:12px;color:#334155;background:#f8fafc}
.qa-answer-box,.qa-reference-box,.qa-explain-box{border:1px solid #e2e8f0;border-radius:8px;background:#fbfdff;padding:10px;margin-top:8px;font-size:13px;line-height:1.55;max-height:190px;overflow:auto}
.qa-reference-box{max-height:120px}
.qa-explain-box{max-height:100px;color:#475569}
.qa-viz-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px}
.qa-viz-title{font-size:13px;font-weight:800;color:#111827}
.qa-legend{display:flex;flex-wrap:wrap;gap:6px;font-size:11px;color:#475569}
.qa-key{display:inline-flex;align-items:center;gap:4px}
.qa-dot{width:10px;height:10px;border-radius:50%;border:2px solid #475569;background:#fff}
.qa-dot.source{border-color:#f59e0b}.qa-dot.expected{border-color:#dc2626}.qa-dot.both{border-color:#16a34a}
.qa-mini-svg{width:100%;min-height:640px;border:1px solid #e2e8f0;border-radius:8px;background:linear-gradient(90deg,rgba(100,116,139,.08) 1px,transparent 1px),linear-gradient(rgba(100,116,139,.06) 1px,transparent 1px);background-size:32px 32px}
.qa-source-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:6px;margin-top:8px}
.qa-source-item{border:1px solid #e2e8f0;border-radius:7px;background:#fbfdff;padding:7px;font-size:12px;color:#334155;text-align:left;cursor:pointer;font:inherit}
.qa-source-item:hover{border-color:#94a3b8;background:#f8fafc}
.qa-source-item.active{border-color:#2563eb;box-shadow:0 0 0 2px rgba(37,99,235,.16);background:#eff6ff}
.qa-source-item strong{color:#111827}
.qa-node-detail{border:1px solid #cbd5e1;border-radius:8px;background:#ffffff;padding:10px;margin-top:10px;font-size:13px;line-height:1.55;color:#334155}
.qa-node-detail h4{margin:0 0 6px;color:#111827;font-size:14px}
.qa-node-detail dl{display:grid;grid-template-columns:92px 1fr;gap:4px 8px;margin:8px 0}
.qa-node-detail dt{color:#64748b}
.qa-node-detail dd{margin:0;overflow-wrap:anywhere}
.qa-node-text{border:1px solid #e2e8f0;border-radius:7px;background:#fbfdff;padding:8px;max-height:220px;overflow:auto;white-space:pre-wrap}
.qa-svg-edge{fill:none;stroke:#cbd5e1;stroke-width:1.3}
.qa-svg-edge.hot{stroke:#2563eb;stroke-width:2}
.qa-svg-label{font-size:10px;fill:#475569;font-weight:700}
.qa-svg-node{cursor:pointer}
.qa-svg-node text{font-size:9px;fill:#111827;font-weight:800;pointer-events:none}
@media (max-width: 980px){.qa-control-row{grid-template-columns:1fr}}
</style>
<h2>QA Source Overlays</h2>
<p class="qa-source-intro">Each card places the question and reader answer beside a mini-tree of the tree/BM25 source nodes passed into the reader. Changing the method updates both the answer and the overlay.</p>
<div id="qaOverlayCards"></div>
<script type="application/json" id="qaOverlayData">__PAYLOAD__</script>
<script>
(function(){
  const data = JSON.parse(document.getElementById("qaOverlayData").textContent);
  const byId = new Map(data.nodes.map(node => [String(node.index), node]));
  const methodOrder = data.method_order || [];
  const maxLayer = Number(data.meta.num_layers || 0);
  const colors = ["#2563eb","#059669","#d97706","#7c3aed","#dc2626","#0891b2","#65a30d","#be123c"];
  const categories = Object.keys(data.meta.category_names || {}).sort();
  const colorByCategory = new Map(categories.map((key, index) => [key, colors[index % colors.length]]));

  function escapeHtml(value){
    return String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}[ch]));
  }
  function textHtml(value){
    return escapeHtml(value || "").replace(/\\n/g, "<br>");
  }
  function truncate(value, limit){
    const text = String(value || "");
    return text.length > limit ? text.slice(0, limit - 1) + "..." : text;
  }
  function numberText(value, digits){
    const n = Number(value);
    if (!Number.isFinite(n)) return "-";
    return n.toFixed(digits);
  }
  function nodeColor(node){
    const key = node.node_type === "leaf" ? node.category : (node.dominant_category || node.category);
    return colorByCategory.get(key) || "#94a3b8";
  }
  function methodNames(qa){
    return methodOrder.filter(method => qa.methods && qa.methods[method]);
  }
  function defaultMethod(qa){
    const names = methodNames(qa);
    if (!names.length) return "";
    return names.slice().sort((a, b) => {
      const ma = qa.methods[a], mb = qa.methods[b];
      const scoreDiff = Number(mb.judge_score || 0) - Number(ma.judge_score || 0);
      if (scoreDiff) return scoreDiff;
      return Number(mb.hit || 0) - Number(ma.hit || 0);
    })[0];
  }
  function relevantIds(qa, method){
    const ids = new Set();
    for (const value of method.path_node_indices || []) ids.add(String(value));
    for (const value of method.source_node_indices || []) ids.add(String(value));
    for (const value of qa.expected_node_indices || []) ids.add(String(value));
    return ids;
  }
  function makeSvg(tag){
    return document.createElementNS("http://www.w3.org/2000/svg", tag);
  }
  function edgePath(a, b){
    const dy = Math.max(28, (b.y - a.y) * .45);
    return `M ${a.x} ${a.y} C ${a.x} ${a.y + dy}, ${b.x} ${b.y - dy}, ${b.x} ${b.y}`;
  }
  function renderMiniTree(card, svg, qa, methodName, selectedNodeId){
    const method = qa.methods[methodName];
    const ids = relevantIds(qa, method);
    const sourceSet = new Set((method.source_node_indices || []).map(String));
    const expectedSet = new Set((qa.expected_node_indices || []).map(String));
    const rankById = new Map((method.source_nodes || []).map(source => [String(source.node_index), source.rank]));
    const nodes = Array.from(ids).map(id => byId.get(id)).filter(Boolean);
    const byLayer = new Map();
    for (const node of nodes) {
      if (!byLayer.has(node.layer)) byLayer.set(node.layer, []);
      byLayer.get(node.layer).push(node);
    }
    for (const layerNodes of byLayer.values()) {
      layerNodes.sort((a, b) => {
        const ar = rankById.get(String(a.index)) || 9999;
        const br = rankById.get(String(b.index)) || 9999;
        return ar - br || a.index - b.index;
      });
    }
    const maxCount = Math.max(1, ...Array.from(byLayer.values()).map(items => items.length));
    const width = Math.max(720, Math.min(1280, 140 + maxCount * 64));
    const height = 650;
    const topPad = 44;
    const bottomPad = 84;
    const leftPad = 92;
    const rightPad = 72;
    const positions = new Map();
    for (let layer = maxLayer; layer >= 0; layer--) {
      const layerNodes = byLayer.get(layer) || [];
      const y = topPad + (maxLayer - layer) * ((height - topPad - bottomPad) / Math.max(maxLayer, 1));
      const gap = (width - leftPad - rightPad) / (layerNodes.length + 1);
      layerNodes.forEach((node, index) => positions.set(String(node.index), {x: leftPad + gap * (index + 1), y}));
    }
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("height", String(height));
    svg.innerHTML = "";
    for (let layer = maxLayer; layer >= 0; layer--) {
      const y = topPad + (maxLayer - layer) * ((height - topPad - bottomPad) / Math.max(maxLayer, 1));
      const label = makeSvg("text");
      label.setAttribute("x", 12);
      label.setAttribute("y", y + 3);
      label.setAttribute("class", "qa-svg-label");
      label.textContent = layer === 0 ? "L0 leaves" : `L${layer}`;
      svg.appendChild(label);
    }
    for (const node of nodes) {
      const childPos = positions.get(String(node.index));
      if (!childPos) continue;
      for (const parentId of node.parents || []) {
        if (!ids.has(String(parentId))) continue;
        const parentPos = positions.get(String(parentId));
        if (!parentPos) continue;
        const path = makeSvg("path");
        path.setAttribute("d", edgePath(parentPos, childPos));
        path.setAttribute("class", "qa-svg-edge hot");
        svg.appendChild(path);
      }
    }
    for (const node of nodes) {
      const id = String(node.index);
      const pos = positions.get(id);
      if (!pos) continue;
      const isSource = sourceSet.has(id);
      const isExpected = expectedSet.has(id);
      const isSelected = selectedNodeId && id === String(selectedNodeId);
      const g = makeSvg("g");
      g.setAttribute("class", "qa-svg-node");
      g.setAttribute("transform", `translate(${pos.x},${pos.y})`);
      g.setAttribute("data-node-id", id);
      const c = makeSvg("circle");
      const radius = node.node_type === "leaf" ? 6 : 9;
      c.setAttribute("r", isSource || isExpected ? radius + 2 : radius);
      c.setAttribute("fill", nodeColor(node));
      c.setAttribute("stroke", isSelected ? "#111827" : isSource && isExpected ? "#16a34a" : isExpected ? "#dc2626" : isSource ? "#f59e0b" : "#475569");
      c.setAttribute("stroke-width", isSelected ? "4" : isSource || isExpected ? "3" : "1.3");
      g.appendChild(c);
      g.addEventListener("click", () => {
        card.dataset.selectedNodeId = id;
        renderCard(card, qa, methodName);
      });
      const title = makeSvg("title");
      title.textContent = `#${node.index} L${node.layer}\\n${node.patent_id || node.title || "summary node"}\\nleaves=${node.descendant_leaf_count}`;
      g.appendChild(title);
      if (rankById.has(id)) {
        const rank = makeSvg("text");
        rank.setAttribute("x", 0);
        rank.setAttribute("y", 3);
        rank.setAttribute("text-anchor", "middle");
        rank.textContent = rankById.get(id);
        g.appendChild(rank);
      }
      const label = makeSvg("text");
      if (node.layer === 0) {
        label.setAttribute("x", 0);
        label.setAttribute("y", radius + 12);
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("dominant-baseline", "hanging");
      } else {
        label.setAttribute("x", radius + 8);
        label.setAttribute("y", 3);
      }
      label.setAttribute("font-size", node.layer === 0 ? "8" : "9");
      label.setAttribute("font-weight", "700");
      label.textContent = node.node_type === "leaf" ? truncate(node.patent_id || `#${node.index}`, 14) : `#${node.index}`;
      g.appendChild(label);
      svg.appendChild(g);
    }
  }
  function sourceList(method, selectedNodeId){
    return (method.source_nodes || []).slice(0, 10).map(source => {
      const node = byId.get(String(source.node_index));
      const label = node ? (node.patent_id || node.title || `node ${node.index}`) : `node ${source.node_index}`;
      const active = String(source.node_index) === String(selectedNodeId) ? " active" : "";
      return `<button type="button" class="qa-source-item${active}" data-node-id="${escapeHtml(source.node_index)}"><strong>r${escapeHtml(source.rank)} #${escapeHtml(source.node_index)} L${escapeHtml(source.layer)}</strong><br>${escapeHtml(truncate(label, 72))}<br>score ${escapeHtml(numberText(source.score, 3))} | expected ${source.contains_expected ? "yes" : "no"}</button>`;
    }).join("");
  }
  function renderNodeDetail(card, method, selectedNodeId){
    const target = card.querySelector(".qa-node-detail");
    const node = byId.get(String(selectedNodeId));
    if (!node) {
      target.innerHTML = "<h4>Node detail</h4><p>Select a source node to inspect its summary text.</p>";
      return;
    }
    const source = (method.source_nodes || []).find(item => String(item.node_index) === String(selectedNodeId));
    const nodeTitle = node.node_type === "leaf" ? (node.patent_id || `node ${node.index}`) : `summary node #${node.index}`;
    target.innerHTML = `
      <h4>${escapeHtml(nodeTitle)}</h4>
      <dl>
        <dt>Node</dt><dd>#${escapeHtml(node.index)} / L${escapeHtml(node.layer)} / ${escapeHtml(node.node_type)}</dd>
        <dt>Category</dt><dd>${escapeHtml(node.category || node.dominant_category || "-")} ${escapeHtml(node.category_name || "")}</dd>
        <dt>Patent</dt><dd>${escapeHtml(node.patent_id || "-")}</dd>
        <dt>Source</dt><dd>${source ? `rank ${escapeHtml(source.rank)}, score ${escapeHtml(numberText(source.score, 3))}, expected ${source.contains_expected ? "yes" : "no"}` : "-"}</dd>
      </dl>
      <div class="qa-node-text">${textHtml(node.text_preview || "")}</div>
    `;
  }
  function renderCard(card, qa, methodName){
    const method = qa.methods[methodName];
    const firstSource = method.source_nodes && method.source_nodes.length ? String(method.source_nodes[0].node_index) : "";
    if (!card.dataset.selectedNodeId || !(method.path_node_indices || []).map(String).includes(String(card.dataset.selectedNodeId))) {
      card.dataset.selectedNodeId = firstSource;
    }
    const selectedNodeId = card.dataset.selectedNodeId;
    card.querySelector(".qa-metrics").innerHTML = [
      ["method", methodName],
      ["score", method.judge_score || "-"],
      ["hit/rank", `${method.hit || "-"}/${method.rank || "-"}`],
      ["mrr", numberText(method.mrr, 3)],
      ["latency", `${numberText(method.latency_seconds, 3)}s`],
      ["sources", (method.source_node_indices || []).length]
    ].map(([k, v]) => `<span class="qa-pill"><strong>${escapeHtml(k)}:</strong>&nbsp;${escapeHtml(v)}</span>`).join("");
    card.querySelector(".qa-answer-box").innerHTML = `<strong>Reader answer</strong><br>${textHtml(method.answer || "")}`;
    card.querySelector(".qa-reference-box").innerHTML = `<strong>Reference answer</strong><br>${textHtml(qa.reference_answer || "")}`;
    card.querySelector(".qa-explain-box").innerHTML = `<strong>Judge note</strong><br>${textHtml(method.judge_explanation || "")}`;
    card.querySelector(".qa-source-list").innerHTML = sourceList(method, selectedNodeId);
    card.querySelectorAll(".qa-source-item").forEach(item => {
      item.addEventListener("click", () => {
        card.dataset.selectedNodeId = item.dataset.nodeId;
        renderCard(card, qa, methodName);
      });
    });
    renderNodeDetail(card, method, selectedNodeId);
    renderMiniTree(card, card.querySelector("svg"), qa, methodName, selectedNodeId);
  }
  function createCard(qa){
    const method = defaultMethod(qa);
    const card = document.createElement("article");
    card.className = "qa-card";
    const options = methodNames(qa).map(name => `<option value="${escapeHtml(name)}" ${name === method ? "selected" : ""}>${escapeHtml(name)}</option>`).join("");
    card.innerHTML = `
      <div class="qa-copy">
        <div class="qa-meta">QA ${escapeHtml(qa.qa_index)} | ${escapeHtml(qa.question_type || "")} | ${escapeHtml(qa.category || "")} ${escapeHtml(qa.category_name || "")}</div>
        <h3 class="qa-question">${escapeHtml(qa.question)}</h3>
        <div class="qa-control-row">
          <label>Retrieval method<br><select class="qa-method-select">${options}</select></label>
          <div class="qa-metrics"></div>
        </div>
        <div class="qa-answer-box"></div>
        <div class="qa-reference-box"></div>
        <div class="qa-explain-box"></div>
      </div>
      <div class="qa-viz-panel">
        <div class="qa-viz-head">
          <div class="qa-viz-title">Source path mini-tree</div>
          <div class="qa-legend">
            <span class="qa-key"><span class="qa-dot source"></span>retrieved source</span>
            <span class="qa-key"><span class="qa-dot expected"></span>expected leaf</span>
            <span class="qa-key"><span class="qa-dot both"></span>both</span>
          </div>
        </div>
        <svg class="qa-mini-svg" role="img" aria-label="QA source tree"></svg>
        <div class="qa-source-list"></div>
        <div class="qa-node-detail"></div>
      </div>
    `;
    card.querySelector(".qa-method-select").addEventListener("change", event => renderCard(card, qa, event.target.value));
    renderCard(card, qa, method);
    return card;
  }
  const target = document.getElementById("qaOverlayCards");
  for (const qa of data.qa_items) target.appendChild(createCard(qa));
})();
</script>
</section>
<!-- qa-source-overlays:end -->""".replace("__PAYLOAD__", payload_json)


def replace_tree_iframe_block(report: str) -> str:
    start = "<!-- tree-visualization-link:start -->"
    end = "<!-- tree-visualization-link:end -->"
    if start not in report or end not in report:
        return report
    before = report.split(start, 1)[0]
    after = report.split(end, 1)[1]
    block = (
        f"{start}\n"
        '<div class="card" style="margin:16px 0"><strong>Full Tree Source Overlay</strong><br>'
        '<a href="tree_visualization.html">Open full-page RAPTOR tree source overlay</a></div>\n'
        f"{end}"
    )
    return before + block + after


def inject_section(report: str, section: str) -> str:
    start = "<!-- qa-source-overlays:start -->"
    end = "<!-- qa-source-overlays:end -->"
    if start in report and end in report:
        before = report.split(start, 1)[0]
        after = report.split(end, 1)[1]
        return before + section + after

    anchor = "<h2>Answer Scores</h2>"
    if anchor not in report:
        raise ValueError("Could not find insertion anchor: Answer Scores")
    return report.replace(anchor, section + "\n" + anchor, 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-html", required=True, type=Path)
    parser.add_argument("--tree-data", required=True, type=Path)
    parser.add_argument("--qa-sources", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tree_data = json.loads(args.tree_data.read_text(encoding="utf-8"))
    qa_sources = json.loads(args.qa_sources.read_text(encoding="utf-8"))
    payload = build_payload(tree_data, qa_sources)
    report = args.report_html.read_text(encoding="utf-8")
    report = replace_tree_iframe_block(report)
    report = inject_section(report, section_html(payload))
    args.report_html.write_text(report, encoding="utf-8")
    print(f"Updated {args.report_html}")


if __name__ == "__main__":
    main()
