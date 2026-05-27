import csv
import json
import random
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


def format_seconds(seconds):
    if seconds is None:
        return "unknown"
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


class ProgressReporter:
    def __init__(
        self,
        report_interval_seconds=60,
        initial_eta_seconds=None,
        stream=None,
    ):
        self.report_interval_seconds = report_interval_seconds
        self.initial_eta_seconds = initial_eta_seconds
        self.stream = stream or sys.stderr
        self.started_at = time.time()
        self.stage_started_at = self.started_at
        self.stage_completed_base = 0
        self.stage = "starting"
        self.completed = 0
        self.total = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self.first_eta_seconds = initial_eta_seconds
        self.last_eta_seconds = initial_eta_seconds

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.report(force=True)

    def stop(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def set_stage(self, stage, completed=0, total=None):
        with self._lock:
            if stage != self.stage:
                self.stage_started_at = time.time()
                self.stage_completed_base = completed
            self.stage = stage
            self.completed = completed
            self.total = total

    def advance(self, amount=1, stage=None):
        with self._lock:
            if stage is not None:
                self.stage = stage
            self.completed += amount

    def _estimate_eta(self, stage_elapsed, completed, total):
        stage_completed = completed - self.stage_completed_base
        if total and stage_completed > 0:
            remaining = max(0, total - completed)
            rate = stage_completed / stage_elapsed if stage_elapsed > 0 else 0
            if rate > 0:
                return max(0, remaining / rate)
        return self.initial_eta_seconds

    def report(self, force=False):
        with self._lock:
            elapsed = time.time() - self.started_at
            stage_elapsed = time.time() - self.stage_started_at
            eta = self._estimate_eta(stage_elapsed, self.completed, self.total)
            self.last_eta_seconds = eta
            expected_end = (
                datetime.now() + timedelta(seconds=eta)
                if eta is not None
                else None
            )
            total_text = self.total if self.total is not None else "?"
            end_text = expected_end.strftime("%Y-%m-%d %H:%M:%S") if expected_end else "unknown"
            print(
                "[progress] stage={} completed={}/{} elapsed={} eta={} expected_end={}".format(
                    self.stage,
                    self.completed,
                    total_text,
                    format_seconds(elapsed),
                    format_seconds(eta),
                    end_text,
                ),
                file=self.stream,
                flush=True,
            )

    def _run(self):
        while not self._stop_event.wait(self.report_interval_seconds):
            self.report()

    def summary(self):
        actual_seconds = time.time() - self.started_at
        eta_error = (
            actual_seconds - self.first_eta_seconds
            if self.first_eta_seconds is not None
            else None
        )
        return {
            "actual_runtime_seconds": actual_seconds,
            "actual_runtime": format_seconds(actual_seconds),
            "initial_eta_seconds": self.first_eta_seconds,
            "initial_eta": format_seconds(self.first_eta_seconds),
            "final_eta_seconds": self.last_eta_seconds,
            "final_eta": format_seconds(self.last_eta_seconds),
            "initial_eta_error_seconds": eta_error,
            "initial_eta_error": format_seconds(abs(eta_error))
            if eta_error is not None
            else "unknown",
        }


def sample_patents(
    csv_path,
    per_category=50,
    seed=42,
    text_column="요약",
):
    csv_path = Path(csv_path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    grouped = defaultdict(list)
    for row in rows:
        text = (row.get(text_column) or "").strip()
        category = (row.get("중분류") or "").strip()
        if category and text:
            grouped[category].append(row)

    rng = random.Random(seed)
    sampled = []
    for category in sorted(grouped):
        candidates = grouped[category]
        if len(candidates) < per_category:
            raise ValueError(
                f"category {category} has {len(candidates)} rows, fewer than {per_category}"
            )
        selected = rng.sample(candidates, per_category)
        selected.sort(key=lambda row: row.get("patent_id", ""))
        sampled.extend(selected)

    return sampled


def patent_documents(rows, text_column="요약"):
    documents = []
    for row in rows:
        patent_id = row.get("patent_id") or row.get("출원번호")
        documents.append(
            {
                "id": patent_id,
                "text": (row.get(text_column) or "").strip(),
                "metadata": {
                    "patent_id": patent_id,
                    "title": row.get("발명의 명칭", ""),
                    "category": row.get("중분류", ""),
                    "category_name": row.get("중분류명", ""),
                    "query_title": row.get("발명의 명칭", ""),
                    "query_ai_summary": row.get("AI요약(목적+솔루션)", ""),
                },
            }
        )
    return documents


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path, rows, fieldnames=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_jsonl(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
