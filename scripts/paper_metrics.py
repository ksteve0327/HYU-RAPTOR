#!/usr/bin/env python3
"""Paper-style answer metrics for RAPTOR patent experiment reports."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


def as_float(value, default: float = 0.0) -> float:
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(str(text or ""))]


def answer_prf(prediction: str, reference: str) -> tuple[float, float, float]:
    """Token-overlap precision, recall, and F1 for generated answer text.

    RAPTOR reports QASPER with answer F1. Our patent QA is Korean open-ended QA,
    so this uses Unicode token overlap as a deterministic QASPER-style proxy.
    """

    pred_tokens = normalize_tokens(prediction)
    ref_tokens = normalize_tokens(reference)
    if not pred_tokens or not ref_tokens:
        return 0.0, 0.0, 0.0
    overlap = sum((Counter(pred_tokens) & Counter(ref_tokens)).values())
    if overlap == 0:
        return 0.0, 0.0, 0.0
    precision = overlap / len(pred_tokens)
    recall = overlap / len(ref_tokens)
    f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def answer_f1(prediction: str, reference: str) -> float:
    return answer_prf(prediction, reference)[2]


def paper_accuracy(row: dict) -> float:
    if str(row.get("accuracy", "")).strip() != "":
        return as_float(row.get("accuracy"))
    score = as_float(row.get("judge_score"))
    supported = str(row.get("judge_supported", "")).lower() == "true"
    return 1.0 if score >= 4 and supported else 0.0


def add_paper_metrics(row: dict) -> dict:
    precision, recall, f1 = answer_prf(
        row.get("answer", ""),
        row.get("reference_answer", ""),
    )
    row["answer_precision"] = precision
    row["answer_recall"] = recall
    row["answer_f1"] = f1
    row["paper_accuracy"] = paper_accuracy(row)
    return row


def ensure_paper_metrics(rows: list[dict]) -> list[dict]:
    return [add_paper_metrics(row) for row in rows]


def mean_by_method(rows: list[dict], metric: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        method = row.get("method", "")
        if not method:
            continue
        value = row.get(metric)
        if value == "" or value is None:
            continue
        grouped[method].append(as_float(value))
    return {
        method: sum(values) / len(values) if values else 0.0
        for method, values in sorted(grouped.items())
    }


def write_csv_with_metrics(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = ensure_paper_metrics(list(reader))
        fieldnames = list(reader.fieldnames or [])

    for field in ("answer_precision", "answer_recall", "answer_f1", "paper_accuracy"):
        if field not in fieldnames:
            fieldnames.append(field)

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return rows
