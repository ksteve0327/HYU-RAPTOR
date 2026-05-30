#!/usr/bin/env python3
"""Rebuild V3 reports after recalculating paper-style answer metrics."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_appendix_e_propagation import html_section, inject_html, load_csv as load_propagation_csv
from scripts.create_compact_print_report import build_report as build_compact_report
from scripts.create_compact_print_report import parse_report_cards, read_csv, read_jsonl
from scripts.create_presentation_report import build_report as build_presentation_report
from scripts.create_print_report import build_print_report
from scripts.export_tree_visualization import update_report_link
from scripts.inject_qa_overlays_into_report import (
    build_payload as build_overlay_payload,
    inject_section,
    replace_tree_iframe_block,
    section_html,
)
from scripts.paper_metrics import write_csv_with_metrics
from scripts.run_patent_raptor_experiment import write_report


class StaticReporter:
    def __init__(self, cards: dict[str, str]):
        self.cards = cards

    def summary(self) -> dict[str, str]:
        return {
            "actual_runtime": self.cards.get("Actual runtime", "-"),
            "initial_eta": self.cards.get("Initial ETA", "-"),
            "initial_eta_error": self.cards.get("ETA error", "-"),
        }


class StaticClient:
    def __init__(self, call_count: str):
        try:
            self.call_count = int(call_count)
        except (TypeError, ValueError):
            self.call_count = call_count or "-"


def int_card(cards: dict[str, str], key: str, default: int) -> int:
    try:
        return int(str(cards.get(key, "")).strip())
    except ValueError:
        return default


def build_args(cards: dict[str, str], answer_rows: list[dict]) -> SimpleNamespace:
    methods = {row.get("method", "") for row in answer_rows}
    return SimpleNamespace(
        run_label=cards.get("Run label", "v3"),
        text_column=cards.get("Text column", "요약"),
        sample_size_per_category=int_card(cards, "Sample/category", 50),
        embedding_backend=cards.get("Embedding", "minilm"),
        embedding_model=cards.get("Embedding model", "BAAI/bge-m3"),
        retrieval_design=cards.get("Retrieval design", "with_without_raptor"),
        qa_mode=cards.get("QA mode", "global_local"),
        dpr_backend=cards.get("DPR backend", "-"),
        llm_model=cards.get("LLM model", "gpt-5.5"),
        judge_reasoning_effort=cards.get("Reasoning", "high"),
        include_dpr_baseline=any(method.startswith("dpr_") for method in methods),
    )


def maybe_inject_propagation(run_dir: Path) -> None:
    propagation_csv = run_dir / "appendix_e_propagation_audit.csv"
    report_html = run_dir / "report.html"
    if not propagation_csv.exists() or not report_html.exists():
        return
    records = load_propagation_csv(propagation_csv)
    inject_html(report_html, html_section(records))


def maybe_inject_qa_overlays(run_dir: Path) -> None:
    report_html = run_dir / "report.html"
    tree_data = run_dir / "tree_data.json"
    qa_sources = run_dir / "qa_tree_sources.json"
    if not report_html.exists() or not tree_data.exists() or not qa_sources.exists():
        return
    update_report_link(report_html, run_dir / "tree_visualization.html")
    tree_payload = json_load(tree_data)
    source_payload = json_load(qa_sources)
    report = report_html.read_text(encoding="utf-8")
    report = replace_tree_iframe_block(report)
    report = inject_section(
        report,
        section_html(build_overlay_payload(tree_payload, source_payload)),
    )
    if "retrieval_visualization.html" not in report:
        report = report.replace(
            "</body></html>",
            '<p><a href="retrieval_visualization.html">Open retrieval-specific visualization</a></p>\n</body></html>',
            1,
        )
    report_html.write_text(report, encoding="utf-8")


def json_load(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


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


def rebuild(run_dir: Path, make_pdf: bool = False, pdf_copy: Path | None = None) -> None:
    cards = parse_report_cards(run_dir)
    answer_rows = write_csv_with_metrics(run_dir / "answer_eval.csv")
    retrieval_rows = read_csv(run_dir / "retrieval_eval.csv")
    appendix_rows = read_csv(run_dir / "appendix_e_audit.csv")
    qualitative_rows = read_jsonl(run_dir / "qualitative_samples.jsonl")
    summary_repair_rows = read_jsonl(run_dir / "summary_repair_log.jsonl")

    args = build_args(cards, answer_rows)
    reporter = StaticReporter(cards)
    client = StaticClient(cards.get("LLM calls", ""))
    write_report(
        run_dir,
        args,
        answer_rows,
        retrieval_rows,
        appendix_rows,
        qualitative_rows,
        reporter,
        client,
        summary_repair_rows=summary_repair_rows,
    )
    maybe_inject_qa_overlays(run_dir)
    maybe_inject_propagation(run_dir)

    report_html = run_dir / "report.html"
    (run_dir / "report_print.html").write_text(
        build_print_report(report_html.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    build_compact_report(run_dir, run_dir / "report_compact_print.html")
    build_presentation_report(run_dir, run_dir / "report_presentation.html")

    if make_pdf:
        pdf_path = run_dir / "report_compact_print.pdf"
        build_pdf(run_dir / "report_compact_print.html", pdf_path)
        build_pdf(run_dir / "report_presentation.html", run_dir / "report_presentation.pdf")
        if pdf_copy:
            pdf_copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf_path, pdf_copy)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--make-pdf", action="store_true")
    parser.add_argument("--pdf-copy", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rebuild(args.run_dir, make_pdf=args.make_pdf, pdf_copy=args.pdf_copy)
    print(f"Rebuilt paper-style reports in {args.run_dir}")


if __name__ == "__main__":
    main()
