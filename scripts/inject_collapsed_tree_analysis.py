#!/usr/bin/env python3
"""Inject collapsed_tree win analysis into an existing RAPTOR report."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


START = "<!-- collapsed-tree-win-analysis:start -->"
END = "<!-- collapsed-tree-win-analysis:end -->"


def as_float(value, default=0.0):
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_layers(value):
    if not value:
        return []
    layers = []
    for raw in str(value).split(","):
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
    return ", ".join(f"L{layer}: {counts[layer]}" for layer in sorted(counts))


def source_summary(source_map, qa_index, method="collapsed_tree", limit=5):
    item = source_map.get(str(qa_index))
    if not item:
        return "-"
    method_data = item.get("methods", {}).get(method, {})
    nodes = method_data.get("source_nodes") or []
    parts = []
    for node in nodes[:limit]:
        parts.append(
            "#{} L{} r{}".format(
                node.get("node_index", ""),
                node.get("layer", ""),
                node.get("rank", ""),
            )
        )
    return "; ".join(parts) if parts else "-"


def load_answer_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_source_map(path):
    if not path or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("qa_items", []) if isinstance(data, dict) else data
    return {str(item.get("qa_index")): item for item in items}


def collapsed_tree_wins(answer_rows, source_map):
    by_qa = defaultdict(list)
    for row in answer_rows:
        by_qa[row.get("qa_index", "")].append(row)

    wins = []
    for qa_index, rows in sorted(
        by_qa.items(), key=lambda item: int(item[0]) if str(item[0]).isdigit() else 10**9
    ):
        collapsed_rows = [row for row in rows if row.get("method") == "collapsed_tree"]
        other_rows = [row for row in rows if row.get("method") != "collapsed_tree"]
        if not collapsed_rows or not other_rows:
            continue
        collapsed = collapsed_rows[0]
        collapsed_score = as_float(collapsed.get("judge_score"))
        best_other = max(other_rows, key=lambda row: as_float(row.get("judge_score")))
        best_other_score = as_float(best_other.get("judge_score"))
        if collapsed_score < best_other_score:
            continue

        layers = parse_layers(collapsed.get("retrieved_layers"))
        leaf_count = sum(1 for layer in layers if layer == 0)
        summary_count = sum(1 for layer in layers if layer > 0)
        if leaf_count and summary_count:
            why = "leaf 직접 근거와 summary 압축 문맥을 같은 token budget 안에서 함께 사용함"
        elif leaf_count:
            why = "상위 요약보다 leaf 특허 근거를 직접 많이 가져와 답변을 구성함"
        elif summary_count:
            why = "상위 summary node가 여러 특허의 공통 문맥을 압축해서 제공함"
        else:
            why = "retrieval layer 기록이 없어 judge 설명 중심으로 해석함"

        if str(collapsed.get("hit")) == "1":
            why += f"; retrieval hit rank {collapsed.get('rank') or '-'}"
        elif collapsed.get("hit") not in ("", None):
            why += "; retrieval hit 없음"

        wins.append(
            {
                "qa_index": qa_index,
                "outcome": "strict win" if collapsed_score > best_other_score else "tie",
                "question": collapsed.get("question", ""),
                "collapsed_score": collapsed.get("judge_score", ""),
                "best_other_method": best_other.get("method", ""),
                "best_other_score": best_other.get("judge_score", ""),
                "retrieval": "hit={} rank={} mrr={} nodes={}".format(
                    collapsed.get("hit", ""),
                    collapsed.get("rank", "") or "-",
                    collapsed.get("mrr", ""),
                    collapsed.get("retrieved_nodes", ""),
                ),
                "layer_mix": layer_mix(collapsed.get("retrieved_layers")),
                "top_sources": source_summary(source_map, qa_index),
                "why": why,
                "judge_note": collapsed.get("judge_explanation", ""),
            }
        )
    return wins


def html_section(wins):
    lines = [
        START,
        "<h2>Collapsed Tree Win Analysis</h2>",
        (
            "<p>Collapsed Tree가 이긴 경우는 전체 tree node를 flatten한 뒤 동일 token budget 안에서 "
            "leaf patent와 summary node를 함께 고르는 방식이 유리했던 사례입니다. "
            "아래 표는 <code>collapsed_tree</code>가 단독 최고점이거나 최고점 동점인 QA를 보여줍니다.</p>"
        ),
    ]
    if not wins:
        lines.append("<p>No collapsed_tree wins or ties in answer evaluation.</p>")
        lines.append(END)
        return "\n".join(lines)

    lines.append(
        "<table><thead><tr><th>QA</th><th>Outcome</th><th>Question</th><th>Scores</th>"
        "<th>Retrieval</th><th>Layer Mix</th><th>Top Sources</th><th>Why Collapsed Worked</th><th>Judge Note</th></tr></thead><tbody>"
    )
    for win in wins:
        score_text = "Collapsed {} vs {} {}".format(
            win["collapsed_score"], win["best_other_method"], win["best_other_score"]
        )
        lines.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(str(win["qa_index"])),
                html.escape(win["outcome"]),
                html.escape(win["question"]),
                html.escape(score_text),
                html.escape(win["retrieval"]),
                html.escape(win["layer_mix"]),
                html.escape(win["top_sources"]),
                html.escape(win["why"]),
                html.escape(win["judge_note"]),
            )
        )
    lines.extend(["</tbody></table>", END])
    return "\n".join(lines)


def md_section(wins):
    lines = [
        START,
        "## Collapsed Tree Win Analysis",
        "",
        (
            "Collapsed Tree가 단독 최고점이거나 최고점 동점인 QA입니다. "
            "해석 포인트는 leaf 직접 근거와 상위 summary node의 압축 문맥을 같은 token budget 안에서 함께 썼는지입니다."
        ),
        "",
    ]
    if not wins:
        lines.append("- No collapsed_tree wins or ties in answer evaluation.")
        lines.append(END)
        return "\n".join(lines)
    for win in wins:
        lines.append(
            "- QA {qa_index} ({outcome}): collapsed_tree {collapsed_score} vs {best_other_method} {best_other_score}; "
            "{retrieval}; layers={layer_mix}; sources={top_sources}; why={why}".format(**win)
        )
    lines.append(END)
    return "\n".join(lines)


def replace_or_insert(text, section, insert_before):
    if START in text and END in text:
        start = text.index(START)
        end = text.index(END, start) + len(END)
        return text[:start] + section + text[end:]
    marker = insert_before
    if marker in text:
        return text.replace(marker, section + "\n" + marker, 1)
    return text.rstrip() + "\n" + section + "\n"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answer-eval", required=True, type=Path)
    parser.add_argument("--source-map", type=Path)
    parser.add_argument("--html-report", type=Path)
    parser.add_argument("--md-report", type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    wins = collapsed_tree_wins(
        load_answer_rows(args.answer_eval), load_source_map(args.source_map)
    )

    if args.html_report:
        html_text = args.html_report.read_text(encoding="utf-8")
        html_text = replace_or_insert(
            html_text,
            html_section(wins),
            "<h2>Appendix E Hallucination Audit</h2>",
        )
        args.html_report.write_text(html_text, encoding="utf-8")

    if args.md_report:
        md_text = args.md_report.read_text(encoding="utf-8")
        md_text = replace_or_insert(
            md_text,
            md_section(wins),
            "\n## Qualitative Samples",
        )
        args.md_report.write_text(md_text, encoding="utf-8")

    print(f"Collapsed tree wins/ties: {len(wins)}")


if __name__ == "__main__":
    main()
