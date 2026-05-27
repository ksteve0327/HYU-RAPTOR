#!/usr/bin/env python3
"""Export an interactive RAPTOR tree visualization as a standalone HTML file."""

from __future__ import annotations

import argparse
import html
import json
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Set


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def short_text(text: str, limit: int) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1] + "..."


def descendant_leaf_ids(tree, node_index: int, cache: Dict[int, List[int]]) -> List[int]:
    if node_index in cache:
        return cache[node_index]

    node = tree.all_nodes[node_index]
    if not node.children:
        cache[node_index] = [node_index]
        return cache[node_index]

    leaves: List[int] = []
    for child_index in sorted(node.children):
        leaves.extend(descendant_leaf_ids(tree, child_index, cache))
    cache[node_index] = sorted(set(leaves))
    return cache[node_index]


def build_tree_payload(tree) -> Dict:
    layer_by_index = {}
    for layer, nodes in tree.layer_to_nodes.items():
        for node in nodes:
            layer_by_index[node.index] = layer

    parents = defaultdict(list)
    for node in tree.all_nodes.values():
        for child_index in node.children:
            parents[child_index].append(node.index)

    descendant_cache: Dict[int, List[int]] = {}
    category_names = {}
    categories = Counter()
    nodes = []

    for index in sorted(tree.all_nodes):
        node = tree.all_nodes[index]
        metadata = dict(node.metadata or {})
        layer = layer_by_index.get(index, 0)
        leaf_ids = descendant_leaf_ids(tree, index, descendant_cache)
        category_counts = Counter()
        child_leaf_summaries = []

        for leaf_index in leaf_ids:
            leaf = tree.all_nodes[leaf_index]
            leaf_meta = leaf.metadata or {}
            category = str(leaf_meta.get("category", "") or "unknown")
            category_name = str(leaf_meta.get("category_name", "") or category)
            category_counts[category] += 1
            category_names[category] = category_name
            if len(child_leaf_summaries) < 30:
                child_leaf_summaries.append(
                    {
                        "index": leaf.index,
                        "patent_id": leaf_meta.get("patent_id", ""),
                        "title": leaf_meta.get("title", ""),
                        "category": category,
                        "category_name": category_name,
                    }
                )

        if not node.children:
            own_category = str(metadata.get("category", "") or "unknown")
            own_category_name = str(metadata.get("category_name", "") or own_category)
            categories[own_category] += 1
            category_names[own_category] = own_category_name

        dominant_category = ""
        if category_counts:
            dominant_category = category_counts.most_common(1)[0][0]

        nodes.append(
            {
                "id": str(index),
                "index": index,
                "layer": layer,
                "node_type": metadata.get("node_type", "summary" if node.children else "leaf"),
                "children": [str(child) for child in sorted(node.children)],
                "parents": [str(parent) for parent in sorted(parents.get(index, []))],
                "child_count": len(node.children),
                "descendant_leaf_count": len(leaf_ids),
                "category": metadata.get("category", dominant_category),
                "category_name": metadata.get(
                    "category_name", category_names.get(dominant_category, dominant_category)
                ),
                "dominant_category": dominant_category,
                "category_counts": dict(sorted(category_counts.items())),
                "patent_id": metadata.get("patent_id", ""),
                "title": metadata.get("title", ""),
                "text_preview": short_text(node.text, 1800),
                "label": node_label(index, layer, metadata, len(leaf_ids)),
                "leaf_samples": child_leaf_summaries,
            }
        )

    return {
        "meta": {
            "total_nodes": len(tree.all_nodes),
            "root_nodes": [str(index) for index in sorted(tree.root_nodes)],
            "leaf_nodes": len(tree.leaf_nodes),
            "num_layers": tree.num_layers,
            "layer_sizes": {
                str(layer): len(nodes) for layer, nodes in sorted(tree.layer_to_nodes.items())
            },
            "categories": dict(sorted(categories.items())),
            "category_names": dict(sorted(category_names.items())),
        },
        "nodes": nodes,
    }


def node_label(index: int, layer: int, metadata: Dict, descendant_count: int) -> str:
    if metadata.get("node_type") == "leaf":
        patent_id = metadata.get("patent_id") or f"leaf {index}"
        title = metadata.get("title") or ""
        if title:
            return f"{patent_id} - {short_text(title, 64)}"
        return str(patent_id)
    return f"node {index} / layer {layer} / leaves {descendant_count}"


def html_template(payload: Dict) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False)
    template = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RAPTOR Tree Visualization</title>
<style>
:root {{
  color-scheme: light;
  --bg: #f7f8fb;
  --panel: #ffffff;
  --ink: #172033;
  --muted: #5e6b80;
  --line: #cbd5e1;
  --strong-line: #64748b;
  --accent: #2563eb;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--ink);
}}
header {{
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 18px;
  background: rgba(255,255,255,.94);
  border-bottom: 1px solid #d8dee9;
  backdrop-filter: blur(8px);
}}
.header-actions {{
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}}
.zoom-controls {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
  padding: 4px;
}}
.zoom-controls button {{
  min-width: 36px;
  padding: 5px 8px;
}}
.zoom-level {{
  min-width: 50px;
  text-align: center;
  font-size: 13px;
  color: #334155;
  font-weight: 700;
}}
.panel-toggle {{
  min-width: 72px;
}}
h1 {{
  margin: 0;
  font-size: 19px;
  line-height: 1.2;
}}
.subtitle {{
  color: var(--muted);
  font-size: 13px;
  margin-top: 3px;
}}
.layout {{
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr) minmax(300px, 380px);
  height: calc(100vh - 64px);
  min-height: 0;
  overflow: hidden;
}}
.layout.left-collapsed {{
  grid-template-columns: 0 minmax(0, 1fr) minmax(300px, 380px);
}}
.layout.right-collapsed {{
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr) 0;
}}
.layout.left-collapsed.right-collapsed {{
  grid-template-columns: 0 minmax(0, 1fr) 0;
}}
aside, .details {{
  background: var(--panel);
  border-right: 1px solid #d8dee9;
  padding: 16px;
  overflow: auto;
  height: 100%;
  max-height: 100%;
}}
.layout.left-collapsed aside,
.layout.right-collapsed .details {{
  padding: 0;
  border: 0;
  overflow: hidden;
}}
.details {{
  border-right: 0;
  border-left: 1px solid #d8dee9;
}}
main {{
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: auto;
  overscroll-behavior: contain;
  cursor: grab;
  user-select: none;
  background:
    linear-gradient(90deg, rgba(100,116,139,.10) 1px, transparent 1px),
    linear-gradient(rgba(100,116,139,.08) 1px, transparent 1px);
  background-size: 40px 40px;
}}
main.panning {{
  cursor: grabbing;
}}
.controls {{
  display: grid;
  gap: 12px;
}}
.qa-panel {{
  display: grid;
  gap: 10px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid #d8dee9;
}}
.qa-summary {{
  border: 1px solid #d8dee9;
  border-radius: 8px;
  background: #fbfdff;
  padding: 10px;
  font-size: 12px;
  color: #334155;
}}
.qa-summary strong {{
  color: #172033;
}}
label {{
  display: grid;
  gap: 6px;
  color: #334155;
  font-size: 13px;
  font-weight: 650;
}}
input, select {{
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 7px;
  padding: 8px 9px;
  font: inherit;
  color: var(--ink);
  background: #fff;
}}
button {{
  border: 1px solid #cbd5e1;
  border-radius: 7px;
  padding: 8px 10px;
  font: inherit;
  color: var(--ink);
  background: #fff;
  cursor: pointer;
}}
button:hover {{ border-color: #94a3b8; background: #f8fafc; }}
.button-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
.stats {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin: 14px 0;
}}
.stat {{
  border: 1px solid #d8dee9;
  border-radius: 8px;
  padding: 10px;
  background: #fbfdff;
}}
.stat strong {{
  display: block;
  font-size: 20px;
}}
.stat span {{
  color: var(--muted);
  font-size: 12px;
}}
.legend, .layer-list {{
  margin-top: 16px;
  display: grid;
  gap: 8px;
}}
.legend h3, .layer-list h3 {{
  margin-bottom: 2px;
}}
.legend-note {{
  font-size: 12px;
  color: #64748b;
  line-height: 1.35;
}}
.legend-row, .layer-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}}
.swatch {{
  width: 13px;
  height: 13px;
  border-radius: 50%;
  border: 1px solid rgba(15,23,42,.25);
  flex: 0 0 auto;
}}
.legend-name {{
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}}
.legend-name span:last-child {{
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}
svg {{
  display: block;
  min-width: 100%;
  transform-origin: 0 0;
}}
.edge {{
  fill: none;
  stroke: var(--line);
  stroke-width: 1.2;
}}
.edge.highlight {{
  stroke: var(--accent);
  stroke-width: 2.2;
}}
.node circle {{
  stroke: #263241;
  stroke-width: 1.1;
  cursor: pointer;
}}
.node.summary circle {{
  stroke-width: 1.5;
}}
.node.selected circle {{
  stroke: var(--accent);
  stroke-width: 3;
}}
.node.qa-path circle {{
  stroke: #475569;
  stroke-dasharray: 4 2;
  stroke-width: 2;
}}
.node.source circle {{
  stroke: #111827;
  stroke-dasharray: none;
  stroke-width: 3.4;
}}
.node.expected circle {{
  stroke: #dc2626;
  stroke-dasharray: none;
  stroke-width: 3.4;
}}
.node.source.expected circle {{
  stroke: #16a34a;
  stroke-width: 4;
}}
.node.match circle {{
  stroke: #dc2626;
  stroke-width: 3;
}}
.source-rank {{
  font-size: 10px;
  font-weight: 800;
  fill: #111827;
  pointer-events: none;
}}
.node text {{
  font-size: 11px;
  dominant-baseline: central;
  pointer-events: none;
  fill: #1f2937;
}}
.node .muted-label {{
  fill: #64748b;
}}
.column-label {{
  font-size: 12px;
  font-weight: 700;
  fill: #475569;
}}
.empty {{
  padding: 18px;
  color: var(--muted);
}}
.details h2 {{
  margin: 0 0 8px;
  font-size: 18px;
}}
.detail-kv {{
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 6px 10px;
  margin: 12px 0;
  font-size: 13px;
}}
.detail-kv dt {{
  color: var(--muted);
}}
.detail-kv dd {{
  margin: 0;
  min-width: 0;
  overflow-wrap: anywhere;
}}
.bar {{
  display: grid;
  gap: 5px;
  margin: 12px 0 16px;
}}
.bar-row {{
  display: grid;
  grid-template-columns: 74px 1fr 34px;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}}
.bar-track {{
  height: 9px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}}
.bar-fill {{
  height: 100%;
  border-radius: inherit;
}}
.preview {{
  white-space: pre-wrap;
  font-size: 13px;
  color: #263241;
  line-height: 1.5;
  border: 1px solid #d8dee9;
  border-radius: 8px;
  background: #fbfdff;
  padding: 10px;
  max-height: 240px;
  overflow: auto;
}}
.leaf-list {{
  display: grid;
  gap: 8px;
  margin-top: 10px;
}}
.connected-leaves {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 6px;
  margin-top: 10px;
  max-height: 220px;
  overflow: auto;
}}
.connected-leaf {{
  border: 1px solid #d8dee9;
  border-radius: 7px;
  padding: 7px;
  background: #fbfdff;
  font-size: 12px;
  color: #334155;
}}
.connected-leaf strong {{
  display: block;
  color: #111827;
}}
.leaf-item {{
  border: 1px solid #d8dee9;
  border-radius: 7px;
  padding: 8px;
  background: #fbfdff;
  font-size: 12px;
}}
.leaf-item strong {{
  display: block;
  margin-bottom: 2px;
}}
.badge-row {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 8px 0 12px;
}}
.badge {{
  display: inline-flex;
  align-items: center;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  padding: 3px 8px;
  background: #fff;
  color: #334155;
  font-size: 12px;
}}
.badge.source {{ border-color: #111827; color: #111827; }}
.badge.expected {{ border-color: #dc2626; color: #991b1b; }}
.outline-legend {{
  display: grid;
  gap: 7px;
  margin-top: 10px;
}}
.outline-row {{
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #334155;
}}
.outline-swatch {{
  width: 15px;
  height: 15px;
  border-radius: 50%;
  background: #fff;
  border: 3px solid #94a3b8;
  flex: 0 0 auto;
}}
.outline-swatch.source {{ border-color: #111827; }}
.outline-swatch.expected {{ border-color: #dc2626; }}
.outline-swatch.both {{ border-color: #16a34a; }}
.outline-swatch.path {{
  border-color: #475569;
  border-style: dashed;
}}
@media (max-width: 1050px) {{
  .layout {{ grid-template-columns: 1fr; }}
  aside, .details {{ max-height: none; border-left: 0; border-right: 0; border-bottom: 1px solid #d8dee9; }}
  main {{ min-height: 620px; }}
}}
</style>
</head>
<body>
<header>
  <div>
    <h1>RAPTOR Tree Visualization</h1>
    <div class="subtitle">Interactive view of summary nodes, leaf patents, parent-child edges, and category mix.</div>
  </div>
  <div class="header-actions">
    <button id="leftPanelButton" class="panel-toggle" type="button">Hide left</button>
    <div class="zoom-controls" aria-label="Zoom controls">
      <button id="zoomOutButton" type="button" title="Zoom out">-</button>
      <span id="zoomLevel" class="zoom-level">100%</span>
      <button id="zoomInButton" type="button" title="Zoom in">+</button>
      <button id="zoomResetButton" type="button" title="Reset zoom">100%</button>
    </div>
    <button id="rightPanelButton" class="panel-toggle" type="button">Hide right</button>
    <button id="fitButton" type="button">Fit view</button>
  </div>
</header>
<div class="layout" id="layoutRoot">
  <aside>
    <div class="controls">
      <label>Search node, patent id, title, category
        <input id="searchBox" type="search" placeholder="e.g. 15-615713, retrieval, AA">
      </label>
      <label>Visible depth
        <select id="depthSelect">
          <option value="summary" selected>Summary groups only</option>
          <option value="all">All leaves</option>
          <option value="full">Full tree (200 patent IDs)</option>
          <option value="roots">Roots only</option>
        </select>
      </label>
      <div class="button-row">
        <button id="expandAll" type="button">Expand all</button>
        <button id="collapseAll" type="button">Collapse summaries</button>
      </div>
    </div>
    <div class="qa-panel" id="qaControls"></div>
    <div class="qa-summary" id="qaSummary"></div>
    <div class="stats" id="stats"></div>
    <div class="layer-list" id="layers"></div>
    <div class="legend" id="legend"></div>
  </aside>
  <main id="canvasWrap">
    <svg id="treeSvg" role="img" aria-label="RAPTOR tree structure"></svg>
  </main>
  <section class="details" id="details">
    <div class="empty">Select a node to inspect its summary text, child count, category mix, and sample patents.</div>
  </section>
</div>
<script>
const DATA = __TREE_DATA__;
const nodes = DATA.nodes;
const meta = DATA.meta;
const qaSources = DATA.qa_sources || {{ qa_items: [] }};
const byId = new Map(nodes.map(node => [node.id, node]));
const rootId = "__root__";
const roots = meta.root_nodes.slice();
const methodOrder = ["traverse_tree", "collapsed_tree", "bm25_leaf", "dpr_leaf"];
const colors = [
  "#2563eb", "#059669", "#d97706", "#dc2626", "#7c3aed", "#0891b2",
  "#4f46e5", "#65a30d", "#be123c", "#0f766e", "#9333ea", "#b45309"
];
const categoryKeys = Object.keys(meta.category_names).sort();
const colorByCategory = new Map(categoryKeys.map((key, index) => [key, colors[index % colors.length]]));
let collapsed = new Set();
let selectedId = roots[0] || "";
let activeQaIndex = qaSources.qa_items.length ? 0 : null;
let activeMethod = "traverse_tree";
let currentHighlights = emptyHighlights();
let zoomLevel = 1;
const minZoom = 0.35;
const maxZoom = 3.0;
const zoomStep = 0.15;

const svg = document.getElementById("treeSvg");
const canvasWrap = document.getElementById("canvasWrap");
const layoutRoot = document.getElementById("layoutRoot");
const searchBox = document.getElementById("searchBox");
const depthSelect = document.getElementById("depthSelect");
const details = document.getElementById("details");
const zoomLabel = document.getElementById("zoomLevel");
const leftPanelButton = document.getElementById("leftPanelButton");
const rightPanelButton = document.getElementById("rightPanelButton");
let isPanning = false;
let panStartX = 0;
let panStartY = 0;
let panStartLeft = 0;
let panStartTop = 0;

function clampZoom(value) {{
  return Math.max(minZoom, Math.min(maxZoom, value));
}}

function applyZoom(keepCenter = true, previousZoom = zoomLevel) {{
  const baseWidth = Number(svg.dataset.baseWidth || svg.getAttribute("width") || 0);
  const baseHeight = Number(svg.dataset.baseHeight || svg.getAttribute("height") || 0);
  const centerX = keepCenter && previousZoom
    ? (canvasWrap.scrollLeft + canvasWrap.clientWidth / 2) / previousZoom
    : 0;
  const centerY = keepCenter && previousZoom
    ? (canvasWrap.scrollTop + canvasWrap.clientHeight / 2) / previousZoom
    : 0;
  svg.style.width = `${{baseWidth * zoomLevel}}px`;
  svg.style.height = `${{baseHeight * zoomLevel}}px`;
  zoomLabel.textContent = `${{Math.round(zoomLevel * 100)}}%`;
  if (keepCenter) {{
    canvasWrap.scrollLeft = Math.max(0, centerX * zoomLevel - canvasWrap.clientWidth / 2);
    canvasWrap.scrollTop = Math.max(0, centerY * zoomLevel - canvasWrap.clientHeight / 2);
  }}
}}

function setZoom(nextZoom, keepCenter = true) {{
  const previousZoom = zoomLevel;
  zoomLevel = clampZoom(nextZoom);
  applyZoom(keepCenter, previousZoom);
}}

function updatePanelButtons() {{
  leftPanelButton.textContent = layoutRoot.classList.contains("left-collapsed")
    ? "Show left"
    : "Hide left";
  rightPanelButton.textContent = layoutRoot.classList.contains("right-collapsed")
    ? "Show right"
    : "Hide right";
}}

function setZoomAtPoint(nextZoom, clientX, clientY) {{
  const previousZoom = zoomLevel;
  const rect = canvasWrap.getBoundingClientRect();
  const localX = clientX - rect.left;
  const localY = clientY - rect.top;
  const contentX = (canvasWrap.scrollLeft + localX) / previousZoom;
  const contentY = (canvasWrap.scrollTop + localY) / previousZoom;
  zoomLevel = clampZoom(nextZoom);
  applyZoom(false, previousZoom);
  canvasWrap.scrollLeft = Math.max(0, contentX * zoomLevel - localX);
  canvasWrap.scrollTop = Math.max(0, contentY * zoomLevel - localY);
}}

function emptyHighlights() {{
  return {{
    source: new Set(),
    expected: new Set(),
    path: new Set(),
    rankById: new Map(),
    sourceById: new Map()
  }};
}}

function activeQa() {{
  if (activeQaIndex === null || activeQaIndex === undefined) return null;
  return qaSources.qa_items.find(item => Number(item.qa_index) === Number(activeQaIndex)) || null;
}}

function activeMethodData() {{
  const qa = activeQa();
  if (!qa || !qa.methods) return null;
  if (!qa.methods[activeMethod]) {{
    const firstMethod = methodOrder.find(method => qa.methods[method]) || Object.keys(qa.methods)[0];
    activeMethod = firstMethod || activeMethod;
  }}
  return qa.methods[activeMethod] || null;
}}

function activeSourceSets() {{
  const highlights = emptyHighlights();
  const qa = activeQa();
  const method = activeMethodData();
  if (!qa || !method) return highlights;

  for (const nodeIndex of method.source_node_indices || []) {{
    highlights.source.add(String(nodeIndex));
  }}
  for (const nodeIndex of qa.expected_node_indices || []) {{
    highlights.expected.add(String(nodeIndex));
  }}
  for (const nodeIndex of method.path_node_indices || []) {{
    highlights.path.add(String(nodeIndex));
  }}
  for (const source of method.source_nodes || []) {{
    const id = String(source.node_index);
    highlights.rankById.set(id, source.rank);
    highlights.sourceById.set(id, source);
  }}
  return highlights;
}}

function escapeHtml(value) {{
  return String(value ?? "").replace(/[&<>"']/g, char => ({{
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\\"": "&quot;", "'": "&#39;"
  }}[char]));
}}

function nodeColor(node) {{
  if (!node) return "#94a3b8";
  const key = node.node_type === "leaf" ? node.category : node.dominant_category;
  return colorByCategory.get(key) || "#94a3b8";
}}

function searchableText(node) {{
  return [
    node.index, node.layer, node.node_type, node.patent_id, node.title,
    node.category, node.category_name, node.label, node.text_preview
  ].join(" ").toLowerCase();
}}

function nodeMatches(node, query) {{
  if (!query) return false;
  return searchableText(node).includes(query);
}}

function descendantMatches(id, query, memo = new Map()) {{
  if (!query) return false;
  if (memo.has(id)) return memo.get(id);
  const node = byId.get(id);
  if (!node) return false;
  let found = nodeMatches(node, query);
  for (const childId of node.children) {{
    found = found || descendantMatches(childId, query, memo);
  }}
  memo.set(id, found);
  return found;
}}

function visibleChildren(node, query, mode) {{
  if (!node) return roots.filter(id => !query || descendantMatches(id, query));
  if (collapsed.has(node.id) && !query && mode !== "full") return [];
  if (mode === "roots") return [];

  const children = [];
  for (const childId of node.children) {{
    const child = byId.get(childId);
    if (!child) continue;
    const isQaVisibleLeaf = currentHighlights.source.has(childId) || currentHighlights.expected.has(childId);
    if (mode === "summary" && child.layer === 0 && !query && !isQaVisibleLeaf) continue;
    if (query && !descendantMatches(childId, query)) continue;
    children.push(childId);
  }}
  return children;
}}

function buildLayout() {{
  const query = searchBox.value.trim().toLowerCase();
  const mode = depthSelect.value;
  const rows = [];
  const edges = [];
  const positions = new Map();
  const visibleIds = new Set();
  const maxLayer = Number(meta.num_layers);
  let xCursor = 86;
  const xGap = mode === "full" ? 78 : mode === "all" || query ? 42 : 70;
  const yGap = 210;

  function place(id, depth) {{
    const node = byId.get(id);
    if (!node) return xCursor;
    visibleIds.add(id);
    const children = visibleChildren(node, query, mode);
    let x;
    if (children.length === 0) {{
      x = xCursor;
      xCursor += xGap;
    }} else {{
      const xs = children.map(childId => {{
        edges.push([id, childId]);
        return place(childId, depth + 1);
      }});
      x = xs.reduce((sum, value) => sum + value, 0) / xs.length;
    }}
    const y = 70 + (maxLayer - node.layer) * yGap;
    positions.set(id, {{ x, y, depth }});
    rows.push(id);
    return x;
  }}

  const rootChildren = visibleChildren(null, query, mode);
  const rootXs = rootChildren.map(childId => place(childId, 1));
  const width = Math.max(980, xCursor + 86);
  const height = Math.max(760, 160 + (maxLayer + 1) * yGap);
  const rootX = rootXs.length ? rootXs.reduce((sum, value) => sum + value, 0) / rootXs.length : 90;
  positions.set(rootId, {{ x: rootX, y: 28, depth: 0 }});
  return {{ positions, edges, visibleIds, width, height, query, mode }};
}}

function edgePath(a, b) {{
  const dy = Math.max(42, (b.y - a.y) * 0.45);
  return `M ${{a.x}} ${{a.y}} C ${{a.x}} ${{a.y + dy}}, ${{b.x}} ${{b.y - dy}}, ${{b.x}} ${{b.y}}`;
}}

function render() {{
  currentHighlights = activeSourceSets();
  const layout = buildLayout();
  svg.setAttribute("width", layout.width);
  svg.setAttribute("height", layout.height);
  svg.setAttribute("viewBox", `0 0 ${{layout.width}} ${{layout.height}}`);
  svg.dataset.baseWidth = String(layout.width);
  svg.dataset.baseHeight = String(layout.height);
  svg.innerHTML = "";

  const labelLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
  for (let layer = Number(meta.num_layers); layer >= 0; layer--) {{
    const y = 70 + (Number(meta.num_layers) - layer) * 210;
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", 18);
    text.setAttribute("y", y - 24);
    text.setAttribute("class", "column-label");
    text.textContent = layer === 0 ? `Layer 0 | leaves (${{meta.layer_sizes[String(layer)]}})` : `Layer ${{layer}} (${{meta.layer_sizes[String(layer)]}})`;
    labelLayer.appendChild(text);
  }}
  svg.appendChild(labelLayer);

  const edgeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
  for (const [sourceId, targetId] of layout.edges) {{
    const a = layout.positions.get(sourceId);
    const b = layout.positions.get(targetId);
    if (!a || !b) continue;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", edgePath(a, b));
    const selectedPath = selectedId && (sourceId === selectedId || targetId === selectedId);
    const qaPath = currentHighlights.path.has(sourceId) && currentHighlights.path.has(targetId);
    path.setAttribute("class", selectedPath || qaPath ? "edge highlight" : "edge");
    edgeLayer.appendChild(path);
  }}
  svg.appendChild(edgeLayer);

  const nodeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
  const renderedIds = Array.from(layout.visibleIds).sort((a, b) => {{
    const pa = layout.positions.get(a);
    const pb = layout.positions.get(b);
    return (pa?.x || 0) - (pb?.x || 0) || (pa?.y || 0) - (pb?.y || 0);
  }});
  for (const id of renderedIds) {{
    const node = byId.get(id);
    const pos = layout.positions.get(id);
    if (!node || !pos) continue;
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const matches = nodeMatches(node, layout.query);
    const isSource = currentHighlights.source.has(id);
    const isExpected = currentHighlights.expected.has(id);
    const isQaPath = currentHighlights.path.has(id);
    group.setAttribute(
      "class",
      `node ${{node.node_type}}${{isQaPath ? " qa-path" : ""}}${{isSource ? " source" : ""}}${{isExpected ? " expected" : ""}}${{id === selectedId ? " selected" : ""}}${{matches ? " match" : ""}}`
    );
    group.setAttribute("transform", `translate(${{pos.x}},${{pos.y}})`);
    group.setAttribute("data-id", id);
    group.addEventListener("click", () => {{
      selectedId = id;
      render();
      renderDetails(node);
    }});

    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    const radius = node.node_type === "leaf" ? 5 : Math.min(18, 8 + Math.sqrt(node.descendant_leaf_count) * 1.25);
    circle.setAttribute("r", radius);
    circle.setAttribute("fill", nodeColor(node));
    group.appendChild(circle);

    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    const sourceRank = currentHighlights.rankById.get(id);
    title.textContent = `${{node.label}}\\nchildren: ${{node.child_count}}\\nleaves: ${{node.descendant_leaf_count}}${{sourceRank ? "\\nsource rank: " + sourceRank : ""}}`;
    group.appendChild(title);

    const showLabel = layout.mode === "full"
      ? Number(node.layer) === 0
      : layout.mode === "all"
        ? node.node_type !== "leaf" || Number(node.layer) === 0 || matches
        : node.node_type !== "leaf" || matches;
    if (showLabel) {{
      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      if (node.layer === 0) {{
        text.setAttribute("x", 0);
        text.setAttribute("y", radius + 14);
        text.setAttribute("text-anchor", "middle");
      }} else {{
        text.setAttribute("x", radius + 7);
        text.setAttribute("y", 0);
      }}
      text.setAttribute("class", node.node_type === "leaf" ? "muted-label" : "");
      text.textContent = node.node_type === "leaf"
        ? truncate(node.patent_id || node.title || node.label, layout.mode === "full" ? 18 : 44)
        : `#${{node.index}} | ${{node.descendant_leaf_count}} leaves`;
      group.appendChild(text);
    }}
    if (sourceRank) {{
      const rankText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      rankText.setAttribute("x", -3);
      rankText.setAttribute("y", 1);
      rankText.setAttribute("text-anchor", "middle");
      rankText.setAttribute("class", "source-rank");
      rankText.textContent = sourceRank;
      group.appendChild(rankText);
    }}
    nodeLayer.appendChild(group);
  }}
  svg.appendChild(nodeLayer);
  updateStats(layout.visibleIds.size);
  renderQaSummary();
  applyZoom(false);
}}

function truncate(value, limit) {{
  const text = String(value || "");
  return text.length > limit ? text.slice(0, limit - 1) + "..." : text;
}}

function updateStats(visibleCount) {{
  document.getElementById("stats").innerHTML = [
    ["Nodes", meta.total_nodes],
    ["Visible", visibleCount],
    ["Leaves", meta.leaf_nodes],
    ["Roots", meta.root_nodes.length]
  ].map(([label, value]) => `<div class="stat"><strong>${{value}}</strong><span>${{label}}</span></div>`).join("");
}}

function renderLayers() {{
  const rows = Object.entries(meta.layer_sizes)
    .sort((a, b) => Number(b[0]) - Number(a[0]))
    .map(([layer, size]) => `<div class="layer-row"><span>Layer ${{escapeHtml(layer)}}</span><strong>${{size}}</strong></div>`)
    .join("");
  document.getElementById("layers").innerHTML = `<h3>Layer Sizes</h3>${{rows}}`;
}}

function renderLegend() {{
  const rows = categoryKeys.map(key => {{
    const name = meta.category_names[key] || key;
    const count = meta.categories[key] || 0;
    return `<div class="legend-row">
      <span class="legend-name"><span class="swatch" style="background:${{colorByCategory.get(key)}}"></span><span>${{escapeHtml(key)}} | ${{escapeHtml(name)}}</span></span>
      <strong>${{count}}</strong>
    </div>`;
  }}).join("");
  document.getElementById("legend").innerHTML = `
    <h3>Node Color</h3>
    <div class="legend-note">Node fill color is category color. Blue/orange/green/red filled nodes are categories, not retrieval status. For summary nodes, fill color is the dominant descendant leaf category.</div>
    ${{rows}}
    <h3>Node Outline</h3>
    <div class="outline-legend">
      <div class="outline-row"><span class="outline-swatch source"></span><span>Retrieved source context for the selected QA/method</span></div>
      <div class="outline-row"><span class="outline-swatch expected"></span><span>Expected answer patent leaf</span></div>
      <div class="outline-row"><span class="outline-swatch both"></span><span>Both retrieved source and expected answer</span></div>
      <div class="outline-row"><span class="outline-swatch path"></span><span>On the highlighted source/answer tree path</span></div>
    </div>
  `;
}}

function renderQaControls() {{
  const container = document.getElementById("qaControls");
  if (!qaSources.qa_items || !qaSources.qa_items.length) {{
    container.innerHTML = "<h3>QA Sources</h3><p class='subtitle'>No QA source map loaded.</p>";
    document.getElementById("qaSummary").style.display = "none";
    return;
  }}
  document.getElementById("qaSummary").style.display = "block";
  const qa = activeQa() || qaSources.qa_items[0];
  activeQaIndex = qa.qa_index;
  const availableMethods = methodOrder.filter(method => qa.methods && qa.methods[method]);
  if (!availableMethods.includes(activeMethod)) activeMethod = availableMethods[0] || activeMethod;

  const qaOptions = qaSources.qa_items.map(item => {{
    const label = `QA ${{item.qa_index}} | ${{item.category || ""}} | ${{truncate(item.question, 74)}}`;
    return `<option value="${{escapeHtml(item.qa_index)}}" ${{Number(item.qa_index) === Number(activeQaIndex) ? "selected" : ""}}>${{escapeHtml(label)}}</option>`;
  }}).join("");
  const methodOptions = availableMethods.map(method => (
    `<option value="${{escapeHtml(method)}}" ${{method === activeMethod ? "selected" : ""}}>${{escapeHtml(method)}}</option>`
  )).join("");

  container.innerHTML = `
    <h3>QA Source Overlay</h3>
    <label>QA item
      <select id="qaSelect">${{qaOptions}}</select>
    </label>
    <label>Retrieval method
      <select id="methodSelect">${{methodOptions}}</select>
    </label>
    <button id="focusSources" type="button">Select first source node</button>
  `;

  document.getElementById("qaSelect").addEventListener("change", event => {{
    activeQaIndex = Number(event.target.value);
    const nextQa = activeQa();
    const nextMethods = nextQa ? methodOrder.filter(method => nextQa.methods && nextQa.methods[method]) : [];
    if (!nextMethods.includes(activeMethod)) activeMethod = nextMethods[0] || activeMethod;
    renderQaControls();
    render();
    renderDetails(byId.get(selectedId));
  }});
  document.getElementById("methodSelect").addEventListener("change", event => {{
    activeMethod = event.target.value;
    render();
    renderDetails(byId.get(selectedId));
  }});
  document.getElementById("focusSources").addEventListener("click", () => {{
    const method = activeMethodData();
    const first = method && method.source_node_indices && method.source_node_indices.length
      ? String(method.source_node_indices[0])
      : null;
    if (first && byId.has(first)) {{
      selectedId = first;
      render();
      renderDetails(byId.get(first));
    }}
  }});
}}

function renderQaSummary() {{
  const target = document.getElementById("qaSummary");
  if (!qaSources.qa_items || !qaSources.qa_items.length) return;
  const qa = activeQa();
  const method = activeMethodData();
  if (!qa || !method) {{
    target.innerHTML = "No QA source selected.";
    return;
  }}
  const sourceCount = (method.source_node_indices || []).length;
  const expectedCount = (qa.expected_node_indices || []).length;
  const sourceList = (method.source_nodes || []).slice(0, 8).map(source => {{
    const expected = source.contains_expected ? "yes" : "no";
    return `#${{source.node_index}} L${{source.layer}} r${{source.rank}} expected=${{expected}}`;
  }}).join("<br>");
  target.innerHTML = `
    <strong>Question type</strong><br>${{escapeHtml(qa.question_type || "")}}<br><br>
    <strong>Question</strong><br>${{escapeHtml(qa.question)}}<br><br>
    <strong>Method</strong>: ${{escapeHtml(activeMethod)}} |
    <strong>score</strong>: ${{escapeHtml(method.judge_score || "-")}} |
    <strong>hit/rank</strong>: ${{escapeHtml(method.hit || "-")}}/${{escapeHtml(method.rank || "-")}}<br>
    <strong>source nodes</strong>: ${{sourceCount}} |
    <strong>expected leaves</strong>: ${{expectedCount}}<br>
    <span class="subtitle">Fill color = category. Black outline = retrieved context source. Red outline = expected answer patent leaf. Green outline = both. Dashed outline = highlighted path.</span><br><br>
    ${{sourceList ? `<strong>Top source nodes</strong><br>${{sourceList}}` : ""}}
  `;
}}

function categoryBars(node) {{
  const entries = Object.entries(node.category_counts || {}).sort((a, b) => b[1] - a[1]);
  if (!entries.length) return "";
  const max = Math.max(...entries.map(([, value]) => value));
  return `<div class="bar">${{entries.map(([key, value]) => {{
    const pct = max ? Math.round((value / max) * 100) : 0;
    return `<div class="bar-row">
      <span>${{escapeHtml(key)}}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${{pct}}%;background:${{colorByCategory.get(key) || "#94a3b8"}}"></span></span>
      <strong>${{value}}</strong>
    </div>`;
  }}).join("")}}</div>`;
}}

function connectedLeafList(node) {{
  if (Number(node.layer) !== 1) return "";
  const leaves = (node.children || [])
    .map(childId => byId.get(String(childId)))
    .filter(child => child && Number(child.layer) === 0)
    .sort((a, b) => Number(a.index) - Number(b.index));
  if (!leaves.length) return "";
  return leaves.map(leaf => `
    <div class="connected-leaf">
      <strong>#${{escapeHtml(leaf.index)}} ${{escapeHtml(leaf.patent_id || "")}}</strong>
      <span>${{escapeHtml(leaf.category || "")}} | ${{escapeHtml(truncate(leaf.title || leaf.text_preview || "", 92))}}</span>
    </div>
  `).join("");
}}

function renderDetails(node) {{
  if (!node) {{
    details.innerHTML = `<div class="empty">Select a node to inspect details.</div>`;
    return;
  }}
  const highlights = activeSourceSets();
  const nodeId = String(node.index);
  const source = highlights.sourceById.get(nodeId);
  const badges = [];
  if (source) {{
    badges.push(`<span class="badge source">QA source rank ${{escapeHtml(source.rank)}}</span>`);
    if (source.contains_expected) badges.push(`<span class="badge source">contains expected patent</span>`);
  }}
  if (highlights.expected.has(nodeId)) {{
    badges.push(`<span class="badge expected">expected answer patent leaf</span>`);
  }}
  const leafSamples = (node.leaf_samples || []).map(leaf => `
    <div class="leaf-item">
      <strong>${{escapeHtml(leaf.patent_id || "#" + leaf.index)}}</strong>
      <span>${{escapeHtml(leaf.category)}} | ${{escapeHtml(leaf.category_name)}}</span><br>
      <span>${{escapeHtml(truncate(leaf.title, 110))}}</span>
    </div>
  `).join("");
  const connectedLeaves = connectedLeafList(node);
  details.innerHTML = `
    <h2>${{escapeHtml(node.node_type === "leaf" ? "Leaf Patent" : "Summary Node")}} #${{escapeHtml(node.index)}}</h2>
    ${{badges.length ? `<div class="badge-row">${{badges.join("")}}</div>` : ""}}
    <dl class="detail-kv">
      <dt>Layer</dt><dd>${{escapeHtml(node.layer)}}</dd>
      <dt>Children</dt><dd>${{escapeHtml(node.child_count)}}</dd>
      <dt>Desc. leaves</dt><dd>${{escapeHtml(node.descendant_leaf_count)}}</dd>
      <dt>Patent ID</dt><dd>${{escapeHtml(node.patent_id || "-")}}</dd>
      <dt>Category</dt><dd>${{escapeHtml(node.category || node.dominant_category || "-")}} | ${{escapeHtml(node.category_name || "-")}}</dd>
      <dt>Parents</dt><dd>${{escapeHtml((node.parents || []).join(", ") || "-")}}</dd>
      <dt>Child IDs</dt><dd>${{escapeHtml((node.children || []).join(", ") || "-")}}</dd>
      <dt>Source score</dt><dd>${{source ? escapeHtml(Number(source.score || 0).toFixed(4)) : "-"}}</dd>
      <dt>Source tokens</dt><dd>${{source ? escapeHtml(source.token_count || "-") : "-"}}</dd>
    </dl>
    <h3>Category Mix</h3>
    ${{categoryBars(node) || "<p class='subtitle'>No category mix available.</p>"}}
    <h3>Text Preview</h3>
    <div class="preview">${{escapeHtml(node.text_preview || "")}}</div>
    ${{connectedLeaves ? `<h3>Connected L0 Leaves</h3><div class="connected-leaves">${{connectedLeaves}}</div>` : ""}}
    <h3>Sample Leaf Patents</h3>
    <div class="leaf-list">${{leafSamples || "<p class='subtitle'>No leaf samples.</p>"}}</div>
  `;
}}

function collapseSummaries() {{
  collapsed = new Set(nodes.filter(node => node.node_type !== "leaf" && node.layer < Number(meta.num_layers)).map(node => node.id));
  for (const root of roots) collapsed.delete(root);
  render();
}}

document.getElementById("expandAll").addEventListener("click", () => {{
  collapsed.clear();
  render();
}});
document.getElementById("collapseAll").addEventListener("click", collapseSummaries);
leftPanelButton.addEventListener("click", () => {{
  layoutRoot.classList.toggle("left-collapsed");
  updatePanelButtons();
  applyZoom(false);
}});
rightPanelButton.addEventListener("click", () => {{
  layoutRoot.classList.toggle("right-collapsed");
  updatePanelButtons();
  applyZoom(false);
}});
document.getElementById("zoomOutButton").addEventListener("click", () => {{
  setZoom(zoomLevel - zoomStep);
}});
document.getElementById("zoomInButton").addEventListener("click", () => {{
  setZoom(zoomLevel + zoomStep);
}});
document.getElementById("zoomResetButton").addEventListener("click", () => {{
  setZoom(1);
}});
document.getElementById("fitButton").addEventListener("click", () => {{
  setZoom(1, false);
  canvasWrap.scrollTo({{ top: 0, left: 0, behavior: "smooth" }});
}});
canvasWrap.addEventListener("wheel", event => {{
  event.preventDefault();
  const factor = event.deltaY < 0 ? 1.12 : 0.88;
  setZoomAtPoint(zoomLevel * factor, event.clientX, event.clientY);
}}, {{ passive: false }});
canvasWrap.addEventListener("mousedown", event => {{
  if (event.button !== 0) return;
  if (event.target.closest && event.target.closest(".node")) return;
  isPanning = true;
  panStartX = event.clientX;
  panStartY = event.clientY;
  panStartLeft = canvasWrap.scrollLeft;
  panStartTop = canvasWrap.scrollTop;
  canvasWrap.classList.add("panning");
  event.preventDefault();
}});
window.addEventListener("mousemove", event => {{
  if (!isPanning) return;
  const dx = event.clientX - panStartX;
  const dy = event.clientY - panStartY;
  canvasWrap.scrollLeft = panStartLeft - dx;
  canvasWrap.scrollTop = panStartTop - dy;
}});
window.addEventListener("mouseup", () => {{
  if (!isPanning) return;
  isPanning = false;
  canvasWrap.classList.remove("panning");
}});
searchBox.addEventListener("input", render);
depthSelect.addEventListener("change", render);

renderLayers();
renderLegend();
renderQaControls();
updatePanelButtons();
render();
renderDetails(byId.get(selectedId));
</script>
</body>
</html>
"""
    template = template.replace("{{", "{").replace("}}", "}")
    return template.replace("__TREE_DATA__", payload_json)


def update_report_link(report_html: Path, visualization_html: Path) -> None:
    if not report_html.exists():
        return

    relative = visualization_html.name
    marker_start = "<!-- tree-visualization-link:start -->"
    marker_end = "<!-- tree-visualization-link:end -->"
    block = (
        f"{marker_start}\n"
        '<div class="card" style="margin:16px 0">'
        "<strong>Full Tree Source Overlay</strong><br>"
        f'<a href="{html.escape(relative)}">Open full-page RAPTOR tree source overlay</a>'
        "</div>\n"
        f"{marker_end}"
    )
    content = report_html.read_text(encoding="utf-8")
    if marker_start in content and marker_end in content:
        before = content.split(marker_start, 1)[0]
        after = content.split(marker_end, 1)[1]
        content = before + block + after
    else:
        content = content.replace("<h1>RAPTOR Patent Experiment Report</h1>", "<h1>RAPTOR Patent Experiment Report</h1>\n" + block, 1)
    report_html.write_text(content, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree-pickle", required=True, type=Path)
    parser.add_argument("--output-html", required=True, type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--qa-sources-json", type=Path)
    parser.add_argument("--report-html", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with args.tree_pickle.open("rb") as handle:
        tree = pickle.load(handle)

    payload = build_tree_payload(tree)
    if args.qa_sources_json:
        payload["qa_sources"] = json.loads(args.qa_sources_json.read_text(encoding="utf-8"))
    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    args.output_html.write_text(html_template(payload), encoding="utf-8")

    if args.output_json:
        args.output_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if args.report_html:
        update_report_link(args.report_html, args.output_html)

    print(f"Wrote {args.output_html}")
    if args.output_json:
        print(f"Wrote {args.output_json}")
    if args.report_html:
        print(f"Updated {args.report_html}")


if __name__ == "__main__":
    main()
