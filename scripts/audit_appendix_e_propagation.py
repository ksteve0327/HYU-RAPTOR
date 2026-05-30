#!/usr/bin/env python3
"""Audit whether Appendix E unsupported claims propagated to ancestor nodes."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path


START = "<!-- appendix-e-propagation-check:start -->"
END = "<!-- appendix-e-propagation-check:end -->"


def clean_text(value: str, limit: int | None = None) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if limit and len(text) > limit:
        return text[: limit - 1].rstrip() + "..."
    return text


def load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_tree(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(node["index"]): node for node in data["nodes"]}


def parse_claims(value: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return [clean_text(value)] if value else []
    if isinstance(parsed, list):
        return [clean_text(item) for item in parsed if clean_text(item)]
    return [clean_text(parsed)]


def ancestors_for(node_id: str, nodes: dict[str, dict]) -> list[str]:
    ancestors: list[str] = []
    queue = list(nodes[node_id].get("parents") or [])
    while queue:
        parent = str(queue.pop(0))
        if parent in ancestors:
            continue
        ancestors.append(parent)
        queue.extend(str(value) for value in nodes[parent].get("parents") or [])
    return ancestors


def parse_json_object(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def proxy_chat(base_url: str, model: str, reasoning_effort: str, messages: list[dict], max_tokens: int) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
        "reasoning_effort": reasoning_effort,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer codex-proxy",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def judge_propagation(
    row: dict,
    claims: list[str],
    ancestor_ids: list[str],
    nodes: dict[str, dict],
    base_url: str,
    model: str,
    reasoning_effort: str,
) -> dict:
    source_id = str(row["node_index"])
    source = nodes[source_id]
    ancestors = [
        {
            "ancestor_node": ancestor_id,
            "layer": nodes[ancestor_id].get("layer"),
            "summary": nodes[ancestor_id].get("text_preview", ""),
        }
        for ancestor_id in ancestor_ids
    ]
    prompt = {
        "task": (
            "Check whether unsupported claims from a lower RAPTOR summary are repeated "
            "or semantically carried into ancestor summaries. Treat broad topic overlap as not propagated "
            "unless the same unsupported technical claim, component, effect, or purpose is repeated."
        ),
        "source_node": {
            "node_index": source_id,
            "layer": source.get("layer"),
            "summary": source.get("text_preview", ""),
            "unsupported_claims": claims,
        },
        "ancestor_summaries": ancestors,
        "output_schema": {
            "ancestor_results": [
                {
                    "ancestor_node": "string",
                    "propagated": "boolean",
                    "matching_claims": ["string"],
                    "explanation": "short Korean explanation",
                }
            ]
        },
    }
    raw = proxy_chat(
        base_url,
        model,
        reasoning_effort,
        [
            {
                "role": "system",
                "content": (
                    "You audit summarization hallucination propagation. "
                    "Return JSON only. Be strict: do not mark propagation for mere category similarity."
                ),
            },
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        max_tokens=1200,
    )
    return parse_json_object(raw)


def build_records(args: argparse.Namespace) -> list[dict]:
    rows = load_csv(args.appendix_e_audit)
    nodes = load_tree(args.tree_data)
    records: list[dict] = []
    hallucinated = [
        row
        for row in rows
        if str(row.get("has_hallucination", "")).lower() == "true"
    ]
    for completed, row in enumerate(hallucinated, start=1):
        node_id = str(row["node_index"])
        claims = parse_claims(row.get("unsupported_claims", ""))
        ancestor_ids = ancestors_for(node_id, nodes)
        print(f"[{completed}/{len(hallucinated)}] audit propagation for node #{node_id} -> {ancestor_ids}", flush=True)
        try:
            judged = judge_propagation(
                row,
                claims,
                ancestor_ids,
                nodes,
                args.base_url,
                args.model,
                args.reasoning_effort,
            )
            results = judged.get("ancestor_results", [])
        except (urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
            results = [
                {
                    "ancestor_node": ancestor_id,
                    "propagated": "",
                    "matching_claims": [],
                    "explanation": f"audit failed: {exc}",
                }
                for ancestor_id in ancestor_ids
            ]
        result_by_ancestor = {str(item.get("ancestor_node")): item for item in results}
        for distance, ancestor_id in enumerate(ancestor_ids, start=1):
            result = result_by_ancestor.get(ancestor_id, {})
            records.append(
                {
                    "source_node": node_id,
                    "source_layer": nodes[node_id].get("layer"),
                    "source_severity": row.get("severity", ""),
                    "ancestor_node": ancestor_id,
                    "ancestor_layer": nodes[ancestor_id].get("layer"),
                    "distance": distance,
                    "propagated": result.get("propagated", ""),
                    "matching_claims": json.dumps(
                        result.get("matching_claims", []), ensure_ascii=False
                    ),
                    "explanation": clean_text(result.get("explanation", "")),
                }
            )
    return records


def write_csv(path: Path, records: list[dict]) -> None:
    fieldnames = [
        "source_node",
        "source_layer",
        "source_severity",
        "ancestor_node",
        "ancestor_layer",
        "distance",
        "propagated",
        "matching_claims",
        "explanation",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def html_section(records: list[dict]) -> str:
    by_source = defaultdict(list)
    for record in records:
        by_source[record["source_node"]].append(record)
    source_count = len(by_source)
    pair_count = len(records)
    direct = [
        record
        for record in records
        if str(record.get("distance")) == "1" and str(record.get("propagated")).lower() == "true"
    ]
    any_propagated = {
        source
        for source, source_records in by_source.items()
        if any(str(record.get("propagated")).lower() == "true" for record in source_records)
    }
    lines = [
        START,
        "<h2>Appendix E Propagation Check</h2>",
        (
            "<p>Appendix E에서 hallucination으로 표시된 summary node의 unsupported claim이 "
            "상위 ancestor summary로 반복되었는지 별도 점검했습니다. "
            "이 검사는 논문의 Appendix E 설명처럼 parent node propagation 여부를 보기 위한 보조 audit입니다.</p>"
        ),
        (
            f"<p>Checked hallucinated source nodes: {source_count}. Ancestor pairs: {pair_count}. "
            f"Direct-parent propagation: {len(direct)}. Any-ancestor propagation: {len(any_propagated)}.</p>"
        ),
        "<table><thead><tr><th>Source Node</th><th>Propagated Ancestors</th><th>Interpretation</th></tr></thead><tbody>",
    ]
    for source, source_records in sorted(by_source.items(), key=lambda item: int(item[0])):
        propagated = [
            record
            for record in source_records
            if str(record.get("propagated")).lower() == "true"
        ]
        if propagated:
            ancestor_text = "; ".join(
                f"#{record['ancestor_node']} L{record['ancestor_layer']} d{record['distance']}"
                for record in propagated
            )
            interpretation = propagated[0].get("explanation", "")
        else:
            ancestor_text = "-"
            interpretation = "상위 summary에서 동일 unsupported claim 반복은 확인되지 않았습니다."
        lines.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(f"#{source}"),
                html.escape(ancestor_text),
                html.escape(clean_text(interpretation, 260)),
            )
        )
    lines.extend(["</tbody></table>", END])
    return "\n".join(lines)


def inject_html(path: Path, section: str) -> None:
    text = path.read_text(encoding="utf-8")
    if START in text and END in text:
        start = text.index(START)
        end = text.index(END, start) + len(END)
        text = text[:start] + text[end:]
    marker = "<h2>Qualitative Samples</h2>"
    if marker in text:
        text = text.replace(marker, section + "\n" + marker, 1)
    elif "</body>" in text:
        text = text.replace("</body>", section + "\n</body>", 1)
    else:
        text = text.rstrip() + "\n" + section + "\n"
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appendix-e-audit", required=True, type=Path)
    parser.add_argument("--tree-data", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--html-report", type=Path)
    parser.add_argument("--base-url", default="http://localhost:11435/v1")
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--reasoning-effort", default="high")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = build_records(args)
    write_csv(args.output_csv, records)
    print(f"Wrote {args.output_csv}")
    if args.html_report:
        inject_html(args.html_report, html_section(records))
        print(f"Updated {args.html_report}")


if __name__ == "__main__":
    main()
