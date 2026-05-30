#!/usr/bin/env python3
"""Create an A4 print-friendly copy of a RAPTOR HTML report."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


PRINT_CSS = r"""
:root {
  color-scheme: light;
}

@page {
  size: A4 portrait;
  margin: 12mm 11mm 14mm;
}

* {
  box-sizing: border-box;
}

html,
body {
  background: #ffffff;
  color: #111827;
}

body {
  width: 210mm;
  max-width: 210mm;
  margin: 0 auto;
  padding: 12mm 11mm;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  font-size: 10.5pt;
  line-height: 1.45;
}

.print-toolbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin: -12mm -11mm 10mm;
  padding: 10px 11mm;
  border-bottom: 1px solid #d1d5db;
  background: #ffffff;
}

.print-toolbar a,
.print-toolbar button {
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #ffffff;
  color: #111827;
  font: inherit;
  padding: 6px 10px;
  text-decoration: none;
  cursor: pointer;
}

h1 {
  margin: 0 0 7mm;
  padding-bottom: 4mm;
  border-bottom: 2px solid #111827;
  color: #111827;
  font-size: 22pt;
  line-height: 1.15;
}

h2 {
  break-after: avoid;
  page-break-after: avoid;
  margin: 11mm 0 4mm;
  padding-bottom: 2mm;
  border-bottom: 1px solid #9ca3af;
  color: #111827;
  font-size: 15pt;
  line-height: 1.2;
}

h3 {
  break-after: avoid;
  page-break-after: avoid;
  margin: 7mm 0 2mm;
  color: #111827;
  font-size: 12pt;
  line-height: 1.25;
}

p {
  margin: 0 0 4mm;
}

a {
  color: #1d4ed8;
}

table {
  width: 100%;
  margin: 3mm 0 8mm;
  border-collapse: collapse;
  background: #ffffff;
  font-size: 8.8pt;
  page-break-inside: auto;
}

thead {
  display: table-header-group;
}

tr {
  break-inside: avoid;
  page-break-inside: avoid;
}

th,
td {
  border: 1px solid #cbd5e1;
  padding: 3.2pt 4pt;
  text-align: left;
  vertical-align: top;
  overflow-wrap: anywhere;
}

th {
  background: #eef2ff;
  color: #111827;
  font-weight: 700;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4mm;
  margin: 0 0 7mm;
}

.card,
.print-note {
  break-inside: avoid;
  page-break-inside: avoid;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  background: #ffffff;
  padding: 4mm;
}

.card strong,
.print-note strong {
  color: #111827;
}

.print-note {
  margin: 0 0 6mm;
  color: #374151;
  font-size: 9.2pt;
}

code,
pre {
  border: 1px solid #e5e7eb;
  border-radius: 3px;
  background: #f8fafc;
  color: #111827;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 8.8pt;
}

code {
  padding: 1pt 2pt;
}

pre {
  padding: 4pt;
  white-space: pre-wrap;
}

.small {
  color: #374151;
  font-size: 8.3pt;
  line-height: 1.35;
}

@media screen {
  body {
    margin: 24px auto;
    box-shadow: 0 8px 36px rgba(15, 23, 42, 0.12);
  }
}

@media print {
  body {
    width: auto;
    max-width: none;
    margin: 0;
    padding: 0;
    box-shadow: none;
  }

  .print-toolbar {
    display: none !important;
  }

  a {
    color: inherit;
    text-decoration: none;
  }
}
"""


PRINT_TOOLBAR = """<div class="print-toolbar">
  <a href="report.html">Screen report</a>
  <button type="button" onclick="window.print()">Print A4</button>
</div>
"""


PRINT_NOTE = """<div class="print-note">
  <strong>A4 print version.</strong>
  인터랙티브 QA source overlay와 full tree canvas는 인쇄 품질을 위해 출력본에서 제외했습니다.
  화면에서 source path를 확인하려면 <a href="report.html">report.html</a> 또는
  <a href="tree_visualization.html">tree_visualization.html</a>을 사용하세요.
</div>
"""


def replace_block(html: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = html.find(start_marker)
    end = html.find(end_marker)
    if start == -1 or end == -1:
        return html
    end += len(end_marker)
    return html[:start] + replacement + html[end:]


def build_print_report(source_html: str) -> str:
    html = source_html
    html = html.replace(
        "<title>RAPTOR Patent Experiment Report</title>",
        "<title>RAPTOR Patent Experiment Report - Print</title>",
        1,
    )
    html = re.sub(
        r"<style>.*?</style>",
        f"<style>\n{PRINT_CSS}\n</style>",
        html,
        count=1,
        flags=re.DOTALL,
    )
    html = replace_block(
        html,
        "<!-- tree-visualization-link:start -->",
        "<!-- tree-visualization-link:end -->",
        PRINT_NOTE,
    )
    html = replace_block(
        html,
        "<!-- qa-source-overlays:start -->",
        "<!-- qa-source-overlays:end -->",
        "",
    )
    html = html.replace("<body>", f"<body>\n{PRINT_TOOLBAR}", 1)
    return html


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Source report.html path")
    parser.add_argument("--output", required=True, type=Path, help="Print report output path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.input.read_text(encoding="utf-8")
    rendered = build_print_report(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {args.output} ({len(rendered):,} chars)")


if __name__ == "__main__":
    main()
