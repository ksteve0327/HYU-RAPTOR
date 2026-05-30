#!/usr/bin/env python3
import argparse
import html
import json
import pickle
import random
import shutil
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from raptor.EmbeddingModels import HashEmbeddingModel, MiniLMKoreanEmbeddingModel
from raptor.RetrievalAugmentation import RetrievalAugmentation, RetrievalAugmentationConfig
from raptor.SummarizationModels import BaseSummarizationModel
from raptor.bm25 import BM25Retriever
from raptor.cluster_tree_builder import ClusterTreeConfig
from raptor.cluster_utils import HardKMeansClustering
from raptor.codex_proxy_models import (
    CodexProxyClient,
    CodexProxyQAModel,
    CodexProxySummarizationModel,
    parse_json_object,
)
from raptor.dense import DenseRetriever
from raptor.dpr import DPRRetriever
from raptor.experiment_utils import (
    ProgressReporter,
    patent_documents,
    read_jsonl,
    sample_patents,
    write_csv,
    write_jsonl,
)
from raptor.structured_retrieval import (
    descendant_patent_ids,
    retrieve_collapsed_tree,
    retrieve_traverse_tree,
)
from raptor.tokenization import get_tokenizer
from raptor.tree_retriever import TreeRetrieverConfig
from scripts.paper_metrics import add_paper_metrics, ensure_paper_metrics


V2_ANSWER_METHODS = ("traverse_tree", "collapsed_tree", "bm25_leaf", "dpr_leaf")
V3_MAIN_METHODS = (
    "bm25_without_raptor",
    "bm25_with_raptor",
    "dense_bge_m3_without_raptor",
    "dense_bge_m3_with_raptor",
)
V3_DPR_METHODS = ("dpr_without_raptor", "dpr_with_raptor")
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_DENSE_MODEL = "BAAI/bge-m3"


class ExtractiveSummarizationModel(BaseSummarizationModel):
    def summarize(self, context, max_tokens=500):
        return " ".join(context.split()[: max(20, max_tokens)])


class FaithfulnessRepairSummarizationModel(BaseSummarizationModel):
    def __init__(self, base_model, client, repair_attempts=2):
        self.base_model = base_model
        self.client = client
        self.repair_attempts = max(0, repair_attempts)
        self.records = []

    def _audit(self, context, summary):
        prompt = (
            "다음 parent summary가 child text에서 뒷받침되지 않는 주장을 포함하는지 "
            "엄격히 검사하세요. child text에 명시되거나 직접적으로 추론 가능한 내용만 supported입니다. "
            "JSON만 출력하세요: "
            '{"faithful":true,"unsupported_claims":[],"severity":"none|minor|major",'
            '"explanation":"..."}\n\n'
            f"Child text:\n{context}\n\nParent summary:\n{summary}"
        )
        raw = self.client.chat(
            [
                {"role": "system", "content": "You audit summarization faithfulness."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=700,
        )
        parsed = parse_json_object(raw)
        parsed.setdefault("unsupported_claims", [])
        parsed.setdefault("faithful", not bool(parsed.get("unsupported_claims")))
        return parsed

    def _repair(self, context, summary, audit, max_tokens):
        prompt = (
            "다음 parent summary를 child text에 근거한 내용만 남기도록 수정하세요. "
            "unsupported claim은 제거하거나 근거가 있는 더 약한 표현으로 바꾸고, 새로운 정보를 추가하지 마세요.\n\n"
            f"Unsupported claims:\n{json.dumps(audit.get('unsupported_claims', []), ensure_ascii=False)}\n\n"
            f"Child text:\n{context}\n\nCurrent summary:\n{summary}\n\nRewritten faithful Korean summary:"
        )
        return self.client.chat(
            [
                {"role": "system", "content": "You rewrite Korean patent summaries faithfully."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
        ).strip()

    def summarize(self, context, max_tokens=500):
        original = self.base_model.summarize(context, max_tokens=max_tokens)
        current = original
        initial_audit = None
        final_audit = None
        attempts_used = 0

        try:
            initial_audit = self._audit(context, current)
            final_audit = initial_audit
            for _ in range(self.repair_attempts):
                if str(final_audit.get("faithful")).lower() == "true":
                    break
                current = self._repair(context, current, final_audit, max_tokens)
                attempts_used += 1
                final_audit = self._audit(context, current)
        except Exception as exc:
            final_audit = {
                "faithful": "",
                "unsupported_claims": [f"faithfulness repair failed: {exc}"],
                "severity": "unknown",
                "explanation": str(exc),
            }

        self.records.append(
            {
                "summary_index": len(self.records),
                "attempts_used": attempts_used,
                "initial_faithful": (initial_audit or {}).get("faithful", ""),
                "initial_unsupported_claims": json.dumps(
                    (initial_audit or {}).get("unsupported_claims", []),
                    ensure_ascii=False,
                ),
                "initial_severity": (initial_audit or {}).get("severity", ""),
                "final_faithful": final_audit.get("faithful", ""),
                "final_unsupported_claims": json.dumps(
                    final_audit.get("unsupported_claims", []),
                    ensure_ascii=False,
                ),
                "final_severity": final_audit.get("severity", ""),
                "original_summary": original,
                "final_summary": current,
            }
        )
        return current


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run RAPTOR patent retrieval experiments on patent_rawdata.csv."
    )
    parser.add_argument("--csv-path", default=str(REPO_ROOT / "patent_rawdata.csv"))
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--run-label", default="v2")
    parser.add_argument(
        "--experiment-version",
        choices=["v2", "v3"],
        default="v2",
        help="v3 uses with/without RAPTOR retrieval comparisons.",
    )
    parser.add_argument(
        "--retrieval-design",
        choices=["v2", "with_without_raptor"],
        default="v2",
    )
    parser.add_argument(
        "--reuse-run-dir",
        default=None,
        help="Reuse sampled_patents.jsonl and raptor_tree.pkl from an existing run.",
    )
    parser.add_argument("--sample-size-per-category", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--text-column", default="요약")
    parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBEDDING_MODEL,
    )
    parser.add_argument("--dense-model", default=DEFAULT_DENSE_MODEL)
    parser.add_argument(
        "--embedding-backend",
        choices=["minilm", "sentence-transformers", "hash"],
        default="minilm",
        help="Use hash only for dependency-light smoke tests.",
    )
    parser.add_argument("--llm-base-url", default="http://localhost:11435/v1")
    parser.add_argument("--llm-model", default="gpt-5.5")
    parser.add_argument(
        "--judge-reasoning-effort",
        default="high",
        choices=["low", "medium", "high", "xhigh"],
    )
    parser.add_argument("--max-context-tokens", type=int, default=2000)
    parser.add_argument("--traverse-top-k", type=int, default=5)
    parser.add_argument("--collapsed-top-k", type=int, default=20)
    parser.add_argument("--bm25-top-k", type=int, default=20)
    parser.add_argument("--dpr-top-k", type=int, default=20)
    parser.add_argument("--dense-top-k", type=int, default=20)
    parser.add_argument(
        "--dpr-question-model",
        default="facebook/dpr-question_encoder-multiset-base",
    )
    parser.add_argument(
        "--dpr-context-model",
        default="facebook/dpr-ctx_encoder-multiset-base",
    )
    parser.add_argument(
        "--dpr-backend",
        choices=["hf", "hash"],
        default="hf",
        help="Use hash only for dependency-light DPR smoke tests.",
    )
    parser.add_argument("--num-layers", type=int, default=5)
    parser.add_argument("--summary-tokens", type=int, default=180)
    parser.add_argument("--target-cluster-size", type=int, default=7)
    parser.add_argument(
        "--qa-mode",
        choices=["global_local", "per_category"],
        default="global_local",
    )
    parser.add_argument("--qa-per-category", type=int, default=5)
    parser.add_argument("--qa-global-count", type=int, default=5)
    parser.add_argument("--qa-local-count", type=int, default=5)
    parser.add_argument("--qualitative-count", type=int, default=8)
    parser.add_argument("--appendix-e-samples", type=int, default=12)
    parser.add_argument("--faithfulness-repair-attempts", type=int, default=0)
    parser.add_argument("--include-dpr-baseline", action="store_true")
    parser.add_argument("--progress-interval-seconds", type=int, default=60)
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Use a tiny category sample and short progress interval.",
    )
    args = parser.parse_args()
    normalize_args(args)
    return args


def normalize_args(args):
    if args.experiment_version == "v3":
        if args.retrieval_design == "v2":
            args.retrieval_design = "with_without_raptor"
        if args.run_label == "v2":
            args.run_label = "v3"
        if args.embedding_model == DEFAULT_EMBEDDING_MODEL:
            args.embedding_model = args.dense_model
        if args.faithfulness_repair_attempts == 0:
            args.faithfulness_repair_attempts = 2
        args.qa_mode = "global_local"


def create_output_dir(args):
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        label = f"{args.run_label}_" if args.run_label else ""
        output_dir = REPO_ROOT / "runs" / f"patent_raptor_{label}{stamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def create_embedding_model(args):
    if args.embedding_backend == "hash":
        return HashEmbeddingModel(dimensions=96)
    return MiniLMKoreanEmbeddingModel(model_name=args.embedding_model)


def answer_methods(args):
    if args.retrieval_design == "with_without_raptor":
        methods = list(V3_MAIN_METHODS)
        if args.include_dpr_baseline:
            methods.extend(V3_DPR_METHODS)
        return tuple(methods)
    return V2_ANSWER_METHODS


def documents_to_rows(documents, text_column="요약"):
    rows = []
    for document in documents:
        metadata = document.get("metadata", {})
        rows.append(
            {
                "patent_id": document.get("id", ""),
                "출원번호": document.get("id", ""),
                "중분류": metadata.get("category", ""),
                "중분류명": metadata.get("category_name", ""),
                text_column: document.get("text", ""),
                "요약": document.get("text", ""),
                "발명의 명칭": metadata.get("title", ""),
                "AI요약(목적+솔루션)": metadata.get("query_ai_summary", ""),
            }
        )
    return rows


def copy_if_different(source, target):
    source = Path(source)
    target = Path(target)
    if source.resolve() != target.resolve():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def build_tree(args, documents, embedding_model, qa_model, summarizer, tokenizer, reporter):
    reporter.set_stage("building RAPTOR tree", completed=0, total=None)

    def tree_progress(event, **payload):
        if event == "layer_start":
            reporter.set_stage(
                "building RAPTOR tree layer {}".format(payload["layer"] + 1),
                completed=0,
                total=payload["total_clusters"],
            )
        elif event == "cluster_done":
            reporter.set_stage(
                "building RAPTOR tree layer {}".format(payload["layer"] + 1),
                completed=payload["completed_clusters"],
                total=payload["total_clusters"],
            )

    tree_builder_config = ClusterTreeConfig(
        tokenizer=tokenizer,
        max_tokens=100,
        num_layers=args.num_layers,
        summarization_length=args.summary_tokens,
        summarization_model=summarizer,
        embedding_models={"EMB": embedding_model},
        cluster_embedding_model="EMB",
        reduction_dimension=1,
        clustering_algorithm=HardKMeansClustering,
        clustering_params={
            "target_cluster_size": args.target_cluster_size,
            "random_state": args.seed,
        },
        progress_callback=tree_progress,
    )
    tree_retriever_config = TreeRetrieverConfig(
        tokenizer=tokenizer,
        top_k=args.traverse_top_k,
        context_embedding_model="EMB",
        embedding_model=embedding_model,
    )
    config = RetrievalAugmentationConfig(
        tree_builder_config=tree_builder_config,
        tree_retriever_config=tree_retriever_config,
        qa_model=qa_model,
    )
    retrieval_augmentation = RetrievalAugmentation(config=config)
    return retrieval_augmentation.tree_builder.build_from_documents(
        documents,
        text_key="text",
        metadata_key="metadata",
        use_multithreading=False,
    )


def fallback_qa(rows_by_category, qa_per_category):
    qa_items = []
    for category, rows in sorted(rows_by_category.items()):
        for row in rows[:qa_per_category]:
            patent_id = row.get("patent_id") or row.get("출원번호")
            title = row.get("발명의 명칭", "")
            summary = row.get("요약", "")
            qa_items.append(
                {
                    "category": category,
                    "category_name": row.get("중분류명", ""),
                    "question": f"'{title}' 특허의 핵심 기술은 무엇인가?",
                    "reference_answer": summary[:500],
                    "source_patent_ids": [patent_id],
                    "question_type": "local",
                    "generation_mode": "fallback",
                }
            )
    return qa_items


def fallback_qa_for_category(category, rows, qa_per_category):
    return fallback_qa({category: rows}, qa_per_category)


def row_patent_id(row):
    return str(row.get("patent_id") or row.get("출원번호") or "")


def row_summary(row, text_column="요약"):
    return (row.get(text_column) or row.get("요약") or "").strip()


def fallback_global_local_qa(rows, args):
    rows = sorted(rows, key=lambda row: (row.get("중분류", ""), row_patent_id(row)))
    qa_items = []
    if not rows:
        return qa_items

    for index in range(args.qa_global_count):
        group = [rows[(index * 3 + offset) % len(rows)] for offset in range(min(3, len(rows)))]
        patent_ids = [row_patent_id(row) for row in group if row_patent_id(row)]
        titles = ", ".join(row.get("발명의 명칭", "") for row in group if row.get("발명의 명칭"))
        answer = "\n".join(
            f"{row_patent_id(row)}: {row_summary(row, args.text_column)[:350]}"
            for row in group
        )
        qa_items.append(
            {
                "category": "GLOBAL",
                "category_name": "Global cross-patent",
                "question_type": "global",
                "question": f"다음 특허들({', '.join(patent_ids)})이 공통적으로 다루는 기술 목적과 차이는 무엇인가요?",
                "reference_answer": answer,
                "source_patent_ids": patent_ids,
                "source_titles": titles,
                "generation_mode": "fallback",
            }
        )

    for index, row in enumerate(rows[: args.qa_local_count]):
        patent_id = row_patent_id(row)
        title = row.get("발명의 명칭", "")
        qa_items.append(
            {
                "category": row.get("중분류", ""),
                "category_name": row.get("중분류명", ""),
                "question_type": "local",
                "question": f"'{title}' 특허의 핵심 기술과 효과는 무엇인가요?",
                "reference_answer": row_summary(row, args.text_column)[:700],
                "source_patent_ids": [patent_id],
                "generation_mode": "fallback",
            }
        )
    return qa_items


def sanitize_qa_items(items, question_type, count, rows_by_id, fallback_items):
    sanitized = []
    for item in items:
        source_ids = [str(value) for value in item.get("source_patent_ids", [])]
        source_ids = [value for value in source_ids if value in rows_by_id]
        if question_type == "global" and len(source_ids) < 2:
            continue
        if question_type == "local" and not source_ids:
            continue
        if question_type == "local":
            source_ids = source_ids[:1]
        source_row = rows_by_id[source_ids[0]]
        sanitized.append(
            {
                "category": "GLOBAL" if question_type == "global" else source_row.get("중분류", ""),
                "category_name": (
                    "Global cross-patent"
                    if question_type == "global"
                    else source_row.get("중분류명", "")
                ),
                "question_type": question_type,
                "question": item.get("question", "").strip(),
                "reference_answer": item.get("reference_answer", "").strip(),
                "source_patent_ids": source_ids,
                "generation_mode": "llm",
            }
        )
    for item in fallback_items:
        if len(sanitized) >= count:
            break
        if item.get("question_type") == question_type:
            sanitized.append(item)
    return sanitized[:count]


def build_global_qa_context(tree, rows, args, limit=10):
    if tree is None:
        by_category = defaultdict(list)
        for row in rows:
            by_category[row.get("중분류", "")].append(row)
        blocks = []
        for category, category_rows in sorted(by_category.items())[:limit]:
            selected = category_rows[: min(4, len(category_rows))]
            ids = [row_patent_id(row) for row in selected]
            summaries = "\n".join(
                f"- {row_patent_id(row)} | {row.get('발명의 명칭', '')}: {row_summary(row, args.text_column)[:450]}"
                for row in selected
            )
            blocks.append(f"group: {category}\nsource_patent_ids: {ids}\n{summaries}")
        return "\n\n".join(blocks)

    cache = {}
    layer_by_node = {}
    for layer, nodes in tree.layer_to_nodes.items():
        for node in nodes:
            layer_by_node[node.index] = layer
    candidates = []
    for node in tree.all_nodes.values():
        layer = layer_by_node.get(node.index, 0)
        if layer <= 0:
            continue
        source_ids = descendant_patent_ids(tree, node.index, cache)
        if len(source_ids) >= 2:
            candidates.append((layer, node.index, source_ids, node.text))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    blocks = []
    for layer, node_index, source_ids, text in candidates[:limit]:
        blocks.append(
            "node_index: {node_index}\nlayer: {layer}\nsource_patent_ids: {ids}\nsummary: {summary}".format(
                node_index=node_index,
                layer=layer,
                ids=source_ids[:8],
                summary=text[:1000],
            )
        )
    return "\n\n".join(blocks)


def build_local_qa_context(rows, args, limit=18):
    selected = sorted(rows, key=lambda row: (row.get("중분류", ""), row_patent_id(row)))[:limit]
    return "\n\n".join(
        "patent_id: {patent_id}\ncategory: {category} | {category_name}\ntitle: {title}\nsummary: {summary}".format(
            patent_id=row_patent_id(row),
            category=row.get("중분류", ""),
            category_name=row.get("중분류명", ""),
            title=row.get("발명의 명칭", ""),
            summary=row_summary(row, args.text_column)[:900],
        )
        for row in selected
    )


def generate_global_local_qa(args, rows, tree, client, reporter):
    fallback_items = fallback_global_local_qa(rows, args)
    if args.skip_llm:
        return fallback_items

    rows_by_id = {row_patent_id(row): row for row in rows if row_patent_id(row)}
    prompts = [
        (
            "global",
            args.qa_global_count,
            build_global_qa_context(tree, rows, args),
            (
                "아래 RAPTOR summary node와 source patent id만 근거로 global QA를 생성하세요. "
                f"서로 다른 여러 특허를 종합해야 답할 수 있는 질문 {args.qa_global_count}개를 만드세요. "
                "각 항목의 source_patent_ids는 반드시 2개 이상이어야 합니다. "
                "reference_answer는 source 내용에 근거해 한국어로 작성하세요. JSON만 출력하세요: "
                '{"items":[{"question":"...","reference_answer":"...","source_patent_ids":["...","..."]}]}'
            ),
        ),
        (
            "local",
            args.qa_local_count,
            build_local_qa_context(rows, args),
            (
                "아래 개별 특허 요약만 근거로 local QA를 생성하세요. "
                f"특정 특허 1개만으로 답할 수 있는 질문 {args.qa_local_count}개를 만드세요. "
                "각 항목의 source_patent_ids는 정확히 1개여야 합니다. "
                "reference_answer는 source 내용에 근거해 한국어로 작성하세요. JSON만 출력하세요: "
                '{"items":[{"question":"...","reference_answer":"...","source_patent_ids":["..."]}]}'
            ),
        ),
    ]

    qa_items = []
    reporter.set_stage("generating global/local QA", completed=0, total=len(prompts))
    for question_type, count, context, instruction in prompts:
        try:
            raw = client.chat(
                [
                    {
                        "role": "system",
                        "content": "You create grounded Korean patent QA data with source ids.",
                    },
                    {"role": "user", "content": f"{instruction}\n\n{context}"},
                ],
                max_tokens=1800,
            )
            parsed = parse_json_object(raw)
            items = parsed["items"] if isinstance(parsed, dict) else parsed
        except Exception as exc:
            print(
                f"[warning] {question_type} QA generation failed: {exc}",
                file=sys.stderr,
                flush=True,
            )
            items = []
        qa_items.extend(
            sanitize_qa_items(items, question_type, count, rows_by_id, fallback_items)
        )
        reporter.advance()
    return qa_items


def generate_synthetic_qa(args, rows, tree, client, reporter):
    if args.qa_mode == "global_local":
        return generate_global_local_qa(args, rows, tree, client, reporter)

    rows_by_category = defaultdict(list)
    for row in rows:
        rows_by_category[row.get("중분류", "")].append(row)

    if args.skip_llm:
        return fallback_qa(rows_by_category, args.qa_per_category)

    qa_items = []
    reporter.set_stage("generating synthetic QA", completed=0, total=len(rows_by_category))
    for category, category_rows in sorted(rows_by_category.items()):
        examples = category_rows[: min(12, len(category_rows))]
        context = "\n\n".join(
            "patent_id: {patent_id}\ntitle: {title}\nsummary: {summary}".format(
                patent_id=row.get("patent_id") or row.get("출원번호"),
                title=row.get("발명의 명칭", ""),
                summary=(row.get("요약", "") or "")[:900],
            )
            for row in examples
        )
        prompt = (
            "아래 특허 요약만 근거로 검색/QA 평가용 질문을 생성하세요. "
            f"중분류 {category}에서 {args.qa_per_category}개를 만들고, "
            "각 질문은 특정 특허 1개 이상으로 답할 수 있어야 합니다. "
            "JSON만 출력하세요: "
            '{"items":[{"question":"...","reference_answer":"...",'
            '"source_patent_ids":["..."]}]}\n\n'
            f"{context}"
        )
        raw = client.chat(
            [
                {"role": "system", "content": "You create grounded Korean patent QA data."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1200,
        )
        try:
            parsed = parse_json_object(raw)
            items = parsed["items"] if isinstance(parsed, dict) else parsed
        except Exception as exc:
            print(
                f"[warning] QA generation failed for category {category}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            items = fallback_qa_for_category(
                category, category_rows, args.qa_per_category
            )
        for item in items[: args.qa_per_category]:
            item["category"] = category
            item["category_name"] = examples[0].get("중분류명", "") if examples else ""
            item.setdefault("generation_mode", "llm")
            qa_items.append(item)
        reporter.advance()
    return qa_items


def expected_id_set(expected_patent_ids=None):
    if not expected_patent_ids:
        return set()
    if isinstance(expected_patent_ids, str):
        return {expected_patent_ids}
    return {str(value) for value in expected_patent_ids if value}


def retrieved_patent_ids_from_result(result):
    ids = []
    if hasattr(result, "nodes"):
        for node in result.nodes:
            ids.extend(str(value) for value in node.descendant_patent_ids)
    else:
        for hit in result.hits:
            descendants = hit.metadata.get("descendant_patent_ids")
            if descendants is None:
                descendants = [hit.metadata.get("patent_id") or hit.doc_id]
            ids.extend(str(value) for value in descendants if value)
    seen = set()
    deduped = []
    for value in ids:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def source_metric_values(result, expected_patent_ids=None):
    expected = expected_id_set(expected_patent_ids)
    retrieved = set(retrieved_patent_ids_from_result(result))
    if not expected:
        return {
            "source_precision": "",
            "source_recall": "",
            "source_f1": "",
        }
    overlap = len(expected & retrieved)
    precision = overlap / len(retrieved) if retrieved else 0.0
    recall = overlap / len(expected) if expected else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall > 0
        else 0.0
    )
    return {
        "source_precision": precision,
        "source_recall": recall,
        "source_f1": f1,
    }


def answer_accuracy_from_judgement(judgement):
    score = as_float(judgement.get("score"))
    supported = str(judgement.get("supported")).lower() == "true"
    return 1 if score >= 4 and supported else 0


def tree_retrieval_rows(result, expected_patent_ids=None):
    expected_ids = expected_id_set(expected_patent_ids)
    rank = None
    for index, node in enumerate(result.nodes, start=1):
        if expected_ids and expected_ids & set(node.descendant_patent_ids):
            rank = index
            break
    return {
        "method": result.method,
        "retrieved_nodes": len(result.nodes),
        "retrieved_layers": ",".join(str(node.layer_number) for node in result.nodes),
        "latency_seconds": result.elapsed_seconds,
        "hit": int(rank is not None) if expected_ids else "",
        "rank": rank or "",
        "mrr": (1 / rank) if rank else 0,
        **source_metric_values(result, expected_patent_ids),
        "context": result.context,
    }


def hit_retrieval_row(result, expected_patent_ids=None):
    expected_ids = expected_id_set(expected_patent_ids)
    rank = None
    for hit in result.hits:
        descendant_ids = hit.metadata.get("descendant_patent_ids", [hit.doc_id])
        if expected_ids and expected_ids & set(str(value) for value in descendant_ids):
            rank = hit.rank
            break
    return {
        "method": result.method,
        "retrieved_nodes": len(result.hits),
        "retrieved_layers": ",".join(
            str(hit.metadata.get("layer", 0)) for hit in result.hits
        ),
        "latency_seconds": result.elapsed_seconds,
        "hit": int(rank is not None) if expected_ids else "",
        "rank": rank or "",
        "mrr": (1 / rank) if rank else 0,
        **source_metric_values(result, expected_patent_ids),
        "bm25_top_terms": json.dumps(
            result.hits[0].contributions if result.hits else [],
            ensure_ascii=False,
        ),
        "context": result.context,
    }


bm25_retrieval_row = hit_retrieval_row


def judge_answer(client, question, reference_answer, answer, context, skip_llm=False):
    if skip_llm:
        ref_terms = set(reference_answer.split())
        ans_terms = set(answer.split())
        overlap = len(ref_terms & ans_terms)
        score = min(5, overlap)
        return {
            "score": score,
            "supported": bool(overlap),
            "explanation": "offline lexical overlap fallback",
        }

    prompt = (
        "다음 QA 결과를 0-5점으로 평가하세요. 기준은 reference answer와 의미적으로 "
        "일치하고 retrieved context로 뒷받침되는지입니다. JSON만 출력하세요: "
        '{"score":0,"supported":true,"explanation":"..."}\n\n'
        f"Question:\n{question}\n\nReference answer:\n{reference_answer}\n\n"
        f"Retrieved context:\n{context[:5000]}\n\nAnswer:\n{answer}"
    )
    try:
        raw = client.chat(
            [
                {"role": "system", "content": "You are a strict Korean patent QA evaluator."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=220,
        )
        return parse_json_object(raw)
    except Exception as exc:
        return {
            "score": 0,
            "supported": False,
            "explanation": f"judge failed: {exc}",
        }


def judge_method_comparison(client, question, reference_answer, rows, skip_llm=False):
    if skip_llm:
        ranked = sorted(
            rows,
            key=lambda row: (as_float(row.get("judge_score")), as_float(row.get("mrr"))),
            reverse=True,
        )
        ranking = [
            {
                "method": row["method"],
                "rank": index,
                "reason": "offline score ordering",
            }
            for index, row in enumerate(ranked, start=1)
        ]
        best_method = ranking[0]["method"] if ranking else ""
        return {
            "best_method": best_method,
            "best_reason": "offline score ordering",
            "ranking": ranking,
        }

    answer_blocks = "\n\n".join(
        "method: {method}\nscore: {score}\nsupported: {supported}\nanswer: {answer}\ncontext_preview: {context}".format(
            method=row["method"],
            score=row.get("judge_score", ""),
            supported=row.get("judge_supported", ""),
            answer=row.get("answer", "")[:1800],
            context=row.get("_context", "")[:1800],
        )
        for row in rows
    )
    prompt = (
        "다음은 같은 질문에 대한 retrieval method별 답변입니다. "
        "reference answer와 retrieved context 근거성을 함께 고려해 가장 좋은 답변을 고르고, "
        "모든 method의 순위를 매기세요. JSON만 출력하세요: "
        '{"best_method":"...","best_reason":"...",'
        '"ranking":[{"method":"...","rank":1,"reason":"..."}]}\n\n'
        f"Question:\n{question}\n\nReference answer:\n{reference_answer}\n\n"
        f"Candidate answers:\n{answer_blocks}"
    )
    try:
        raw = client.chat(
            [
                {"role": "system", "content": "You are a strict Korean patent QA comparison judge."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=700,
        )
        parsed = parse_json_object(raw)
        parsed.setdefault("ranking", [])
        return parsed
    except Exception as exc:
        ranked = sorted(rows, key=lambda row: as_float(row.get("judge_score")), reverse=True)
        ranking = [
            {
                "method": row["method"],
                "rank": index,
                "reason": f"comparison judge failed: {exc}",
            }
            for index, row in enumerate(ranked, start=1)
        ]
        return {
            "best_method": ranking[0]["method"] if ranking else "",
            "best_reason": f"comparison judge failed: {exc}",
            "ranking": ranking,
        }


def build_all_node_bm25_documents(tree):
    documents = []
    cache = {}
    layer_map = {}
    for layer, nodes in tree.layer_to_nodes.items():
        for node in nodes:
            layer_map[node.index] = layer
    for node_index, node in sorted(tree.all_nodes.items()):
        documents.append(
            {
                "id": str(node_index),
                "text": node.text,
                "metadata": {
                    "node_index": node_index,
                    "layer": layer_map.get(node_index, 0),
                    "node_type": node.metadata.get("node_type", ""),
                    "descendant_patent_ids": descendant_patent_ids(tree, node_index, cache),
                },
            }
        )
    return documents


def retrieval_results_for_query(
    args,
    query,
    tree,
    embedding_model,
    retrievers,
    tokenizer,
):
    if args.retrieval_design == "with_without_raptor":
        results = [
            retrievers["bm25_without_raptor"].search(
                query,
                top_k=args.bm25_top_k,
                max_context_tokens=args.max_context_tokens,
                tokenizer=tokenizer,
            ),
            retrievers["bm25_with_raptor"].search(
                query,
                top_k=args.bm25_top_k,
                max_context_tokens=args.max_context_tokens,
                tokenizer=tokenizer,
            ),
            retrievers["dense_bge_m3_without_raptor"].search(
                query,
                top_k=args.dense_top_k,
                max_context_tokens=args.max_context_tokens,
                tokenizer=tokenizer,
            ),
            retrieve_collapsed_tree(
                tree,
                query,
                embedding_model,
                "EMB",
                tokenizer,
                top_k=args.dense_top_k,
                max_tokens=args.max_context_tokens,
                method="dense_bge_m3_with_raptor",
            ),
        ]
        if args.include_dpr_baseline:
            results.extend(
                [
                    retrievers["dpr_without_raptor"].search(
                        query,
                        top_k=args.dpr_top_k,
                        max_context_tokens=args.max_context_tokens,
                        tokenizer=tokenizer,
                    ),
                    retrievers["dpr_with_raptor"].search(
                        query,
                        top_k=args.dpr_top_k,
                        max_context_tokens=args.max_context_tokens,
                        tokenizer=tokenizer,
                    ),
                ]
            )
        return results

    return [
        retrieve_traverse_tree(
            tree,
            query,
            embedding_model,
            "EMB",
            tokenizer,
            top_k=args.traverse_top_k,
            max_tokens=args.max_context_tokens,
        ),
        retrieve_collapsed_tree(
            tree,
            query,
            embedding_model,
            "EMB",
            tokenizer,
            top_k=args.collapsed_top_k,
            max_tokens=args.max_context_tokens,
        ),
        retrievers["bm25_leaf"].search(
            query,
            top_k=args.bm25_top_k,
            max_context_tokens=args.max_context_tokens,
            tokenizer=tokenizer,
        ),
        retrievers["dpr_leaf"].search(
            query,
            top_k=args.dpr_top_k,
            max_context_tokens=args.max_context_tokens,
            tokenizer=tokenizer,
        ),
    ]


def run_answer_evaluation(
    args,
    qa_items,
    tree,
    embedding_model,
    retrievers,
    qa_model,
    client,
    tokenizer,
    reporter,
):
    rows = []
    qualitative_rows = []
    methods = answer_methods(args)
    total = len(qa_items) * (len(methods) + 1)
    reporter.set_stage("answer evaluation", completed=0, total=total)
    for qa_index, qa in enumerate(qa_items):
        question = qa["question"]
        reference_answer = qa.get("reference_answer", "")
        expected_ids = [str(value) for value in qa.get("source_patent_ids", [])]

        retrieval_results = retrieval_results_for_query(
            args,
            question,
            tree,
            embedding_model,
            retrievers,
            tokenizer,
        )

        qa_rows = []
        for result in retrieval_results:
            context = result.context
            answer = qa_model.answer_question(context, question) if not args.skip_llm else context[:500]
            judgement = judge_answer(
                client,
                question,
                reference_answer,
                answer,
                context,
                skip_llm=args.skip_llm,
            )
            base = (
                tree_retrieval_rows(result, expected_ids)
                if hasattr(result, "nodes")
                else bm25_retrieval_row(result, expected_ids)
            )
            row = {
                "qa_index": qa_index,
                "question_type": qa.get("question_type", ""),
                "question": question,
                "reference_answer": reference_answer,
                "expected_patent_ids": "|".join(expected_ids),
                "answer": answer,
                "accuracy": answer_accuracy_from_judgement(judgement),
                "judge_score": judgement.get("score", ""),
                "judge_supported": judgement.get("supported", ""),
                "judge_explanation": judgement.get("explanation", ""),
                "best_method": "",
                "best_reason": "",
                "comparison_rank": "",
                "comparison_reason": "",
                **{key: value for key, value in base.items() if key != "context"},
                "_context": context,
            }
            add_paper_metrics(row)
            qa_rows.append(row)
            reporter.advance()

        comparison = judge_method_comparison(
            client,
            question,
            reference_answer,
            qa_rows,
            skip_llm=args.skip_llm,
        )
        ranking_by_method = {
            item.get("method"): item
            for item in comparison.get("ranking", [])
            if item.get("method")
        }
        for row in qa_rows:
            ranking = ranking_by_method.get(row["method"], {})
            row["best_method"] = comparison.get("best_method", "")
            row["best_reason"] = comparison.get("best_reason", "")
            row["comparison_rank"] = ranking.get("rank", "")
            row["comparison_reason"] = ranking.get("reason", "")
            row["comparison_ranking"] = json.dumps(
                comparison.get("ranking", []), ensure_ascii=False
            )
            public_row = {key: value for key, value in row.items() if key != "_context"}
            rows.append(public_row)
            if qa_index < args.qualitative_count:
                qualitative_rows.append(
                    {
                        **public_row,
                        "context_preview": row["_context"][:1200].replace("\n", " "),
                    }
                )
        reporter.advance()
    return rows, qualitative_rows


def run_retrieval_metrics(
    args,
    documents,
    tree,
    embedding_model,
    retrievers,
    tokenizer,
    reporter,
):
    rows = []
    total = len(documents) * len(answer_methods(args))
    reporter.set_stage("retrieval metrics", completed=0, total=total)
    for document in documents:
        metadata = document["metadata"]
        query = metadata.get("query_title") or metadata.get("query_ai_summary") or document["text"]
        expected_id = document["id"]
        results = retrieval_results_for_query(
            args,
            query,
            tree,
            embedding_model,
            retrievers,
            tokenizer,
        )
        for result in results:
            base = (
                tree_retrieval_rows(result, [expected_id])
                if hasattr(result, "nodes")
                else bm25_retrieval_row(result, [expected_id])
            )
            rows.append(
                {
                    "patent_id": expected_id,
                    "category": metadata.get("category", ""),
                    "query": query,
                    **{key: value for key, value in base.items() if key != "context"},
                }
            )
            reporter.advance()
    return rows


def run_appendix_e_audit(args, tree, client, reporter):
    layer_map = {}
    for layer, nodes in tree.layer_to_nodes.items():
        for node in nodes:
            layer_map[node.index] = layer
    summary_nodes = [
        node for node in tree.all_nodes.values() if node.metadata.get("node_type") == "summary"
    ]
    summary_nodes = select_appendix_e_nodes(summary_nodes, layer_map, args)
    rows = []
    if args.skip_llm:
        return rows

    reporter.set_stage("Appendix E hallucination audit", completed=0, total=len(summary_nodes))
    for node in summary_nodes:
        child_text = "\n\n".join(tree.all_nodes[index].text for index in sorted(node.children))
        prompt = (
            "다음 parent summary가 child text에서 뒷받침되지 않는 주장을 포함하는지 "
            "검토하세요. JSON만 출력하세요: "
            '{"unsupported_claims":[],"has_hallucination":false,"severity":"none|minor|major"}\n\n'
            f"Child text:\n{child_text}\n\nParent summary:\n{node.text}"
        )
        try:
            raw = client.chat(
                [
                    {"role": "system", "content": "You audit summarization faithfulness."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=600,
            )
            parsed = parse_json_object(raw)
        except Exception as exc:
            parsed = {
                "unsupported_claims": [f"audit failed: {exc}"],
                "has_hallucination": "",
                "severity": "unknown",
            }
        rows.append(
            {
                "node_index": node.index,
                "layer": layer_map.get(node.index, ""),
                "child_count": len(node.children),
                "has_hallucination": parsed.get("has_hallucination", ""),
                "severity": parsed.get("severity", ""),
                "unsupported_claims": json.dumps(
                    parsed.get("unsupported_claims", []), ensure_ascii=False
                ),
            }
        )
        reporter.advance()
    return rows


def select_appendix_e_nodes(summary_nodes, layer_map, args):
    summary_nodes = sorted(summary_nodes, key=lambda node: (layer_map.get(node.index, 0), node.index))
    if args.appendix_e_samples <= 0 or args.appendix_e_samples >= len(summary_nodes):
        return summary_nodes

    grouped = defaultdict(list)
    for node in summary_nodes:
        grouped[layer_map.get(node.index, 0)].append(node)

    selected = []
    rng = random.Random(args.seed)
    layers = sorted(grouped)
    base = max(1, args.appendix_e_samples // max(1, len(layers)))
    for layer in layers:
        candidates = list(grouped[layer])
        rng.shuffle(candidates)
        selected.extend(candidates[:base])

    remaining = [node for node in summary_nodes if node not in selected]
    rng.shuffle(remaining)
    selected.extend(remaining[: max(0, args.appendix_e_samples - len(selected))])
    return sorted(selected[: args.appendix_e_samples], key=lambda node: (layer_map.get(node.index, 0), node.index))


def summarize_by_method(rows, metric):
    grouped = defaultdict(list)
    for row in rows:
        value = row.get(metric)
        if value == "" or value is None:
            continue
        try:
            grouped[row["method"]].append(float(value))
        except ValueError:
            continue
    return {
        method: statistics.mean(values) if values else 0
        for method, values in sorted(grouped.items())
    }


def summarize_by_question_type_and_method(rows, metric):
    grouped = defaultdict(list)
    for row in rows:
        question_type = row.get("question_type", "") or "unknown"
        method = row.get("method", "")
        value = row.get(metric)
        if value == "" or value is None or not method:
            continue
        try:
            grouped[(question_type, method)].append(float(value))
        except ValueError:
            continue
    return {
        key: statistics.mean(values) if values else 0
        for key, values in sorted(grouped.items())
    }


def quantitative_metrics_by_type(answer_rows):
    ensure_paper_metrics(answer_rows)
    grouped = defaultdict(lambda: defaultdict(list))
    for row in answer_rows:
        question_type = row.get("question_type", "") or "unknown"
        method = row.get("method", "")
        if not method:
            continue
        for metric in ("answer_recall", "answer_f1", "paper_accuracy", "judge_score"):
            value = row.get(metric)
            if value == "" or value is None:
                continue
            grouped[(question_type, method)][metric].append(as_float(value))

    rows = []
    for (question_type, method), values in sorted(grouped.items()):
        rows.append(
            {
                "question_type": question_type,
                "method": method,
                "answer_recall": statistics.mean(values.get("answer_recall", [0])),
                "answer_f1": statistics.mean(values.get("answer_f1", [0])),
                "paper_accuracy": statistics.mean(values.get("paper_accuracy", [0])),
                "judge_score": statistics.mean(values.get("judge_score", [0])),
            }
        )
    return rows


def render_quantitative_tables(answer_rows):
    rows = quantitative_metrics_by_type(answer_rows)
    parts = [
        "<h2>Paper-style Main Performance</h2>",
        (
            "<p class='small'>RAPTOR 논문 메인 표는 retrieval recall이 아니라 task answer metric을 보고합니다. "
            "본 특허 QA는 QASPER처럼 open-ended QA이므로 Answer F1을 메인 지표로 두고, "
            "Answer Recall을 함께 표시합니다. Accuracy는 GPT-5.5 judge의 score>=4 및 supported=true 기준 proxy로 계산했습니다.</p>"
        ),
    ]
    for question_type in ("global", "local"):
        subset = [row for row in rows if row["question_type"] == question_type]
        if not subset:
            continue
        parts.append(f"<h3>{html.escape(question_type.title())} QA</h3>")
        parts.append(
            "<table><thead><tr><th>Method</th><th>Answer F1</th><th>Answer Recall</th><th>Accuracy</th><th>Avg Judge Score</th></tr></thead><tbody>"
        )
        for row in subset:
            parts.append(
                "<tr><td>{}</td><td>{:.3f}</td><td>{:.3f}</td><td>{:.3f}</td><td>{:.3f}</td></tr>".format(
                    html.escape(row["method"]),
                    row["answer_f1"],
                    row["answer_recall"],
                    row["paper_accuracy"],
                    row["judge_score"],
                )
            )
        parts.append("</tbody></table>")
    return "\n".join(parts)


def raptor_delta_rows(answer_rows):
    ensure_paper_metrics(answer_rows)
    pairs = [
        ("bm25_without_raptor", "bm25_with_raptor", "BM25"),
        (
            "dense_bge_m3_without_raptor",
            "dense_bge_m3_with_raptor",
            "Dense BGE-M3",
        ),
        ("dpr_without_raptor", "dpr_with_raptor", "Meta DPR"),
    ]
    by_qa = defaultdict(dict)
    for row in answer_rows:
        by_qa[row.get("qa_index")][row.get("method")] = row

    rows = []
    for without_method, with_method, label in pairs:
        deltas = []
        accuracy_deltas = []
        answer_f1_deltas = []
        answer_recall_deltas = []
        for qa_rows in by_qa.values():
            if without_method not in qa_rows or with_method not in qa_rows:
                continue
            without = qa_rows[without_method]
            with_ = qa_rows[with_method]
            deltas.append(
                as_float(with_.get("judge_score")) - as_float(without.get("judge_score"))
            )
            accuracy_deltas.append(
                as_float(with_.get("paper_accuracy")) - as_float(without.get("paper_accuracy"))
            )
            answer_f1_deltas.append(
                as_float(with_.get("answer_f1"))
                - as_float(without.get("answer_f1"))
            )
            answer_recall_deltas.append(
                as_float(with_.get("answer_recall"))
                - as_float(without.get("answer_recall"))
            )
        if deltas:
            rows.append(
                {
                    "label": label,
                    "without_method": without_method,
                    "with_method": with_method,
                    "score_delta": statistics.mean(deltas),
                    "accuracy_delta": statistics.mean(accuracy_deltas),
                    "answer_f1_delta": statistics.mean(answer_f1_deltas),
                    "answer_recall_delta": statistics.mean(answer_recall_deltas),
                    "count": len(deltas),
                }
            )
    return rows


def render_raptor_delta_table(answer_rows):
    rows = raptor_delta_rows(answer_rows)
    if not rows:
        return ""
    parts = [
        "<h2>With vs Without RAPTOR Delta</h2>",
        "<table><thead><tr><th>Retriever</th><th>Without</th><th>With RAPTOR</th><th>Answer F1 Δ</th><th>Answer Recall Δ</th><th>Accuracy Δ</th><th>Judge Score Δ</th><th>QA Count</th></tr></thead><tbody>",
    ]
    for row in rows:
        parts.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{:+.3f}</td><td>{:+.3f}</td><td>{:+.3f}</td><td>{:+.3f}</td><td>{}</td></tr>".format(
                html.escape(row["label"]),
                html.escape(row["without_method"]),
                html.escape(row["with_method"]),
                row["answer_f1_delta"],
                row["answer_recall_delta"],
                row["accuracy_delta"],
                row["score_delta"],
                row["count"],
            )
        )
    parts.append("</tbody></table>")
    return "\n".join(parts)


def query_type_split_rows(answer_rows):
    ensure_paper_metrics(answer_rows)
    pairs = [
        ("BM25", "bm25_without_raptor", "bm25_with_raptor"),
        ("Dense BGE-M3", "dense_bge_m3_without_raptor", "dense_bge_m3_with_raptor"),
        ("Meta DPR", "dpr_without_raptor", "dpr_with_raptor"),
    ]
    grouped = defaultdict(list)
    for row in answer_rows:
        grouped[(row.get("question_type", "") or "unknown", row.get("method", ""))].append(row)

    def avg(question_type, method, field="answer_f1"):
        rows = grouped.get((question_type, method), [])
        if not rows:
            return None
        return statistics.mean(as_float(row.get(field)) for row in rows)

    rows = []
    for label, without_method, with_method in pairs:
        global_without = avg("global", without_method)
        global_with = avg("global", with_method)
        local_without = avg("local", without_method)
        local_with = avg("local", with_method)
        if global_without is None or global_with is None or local_without is None or local_with is None:
            continue
        all_without = statistics.mean(
            as_float(row.get("answer_f1"))
            for row in grouped.get(("global", without_method), []) + grouped.get(("local", without_method), [])
        )
        all_with = statistics.mean(
            as_float(row.get("answer_f1"))
            for row in grouped.get(("global", with_method), []) + grouped.get(("local", with_method), [])
        )
        if global_with > global_without and local_with < local_without:
            interpretation = (
                "Global QA에서는 RAPTOR all-node가 상위 summary evidence를 보강했지만, "
                "Local QA에서는 특정 patent detail을 묻기 때문에 leaf-only 직접 검색이 더 강했습니다. "
                "전체 평균은 이 상반된 효과를 가립니다."
            )
        elif global_with > global_without and local_with > local_without:
            interpretation = "Global과 Local 모두에서 RAPTOR all-node 검색이 Answer F1을 높였습니다."
        elif global_with < global_without and local_with < local_without:
            interpretation = "두 QA 유형 모두 leaf-only 검색이 더 직접적인 근거를 제공했습니다."
        else:
            interpretation = "QA 유형별 방향이 엇갈리므로 전체 평균만으로 결론을 내리기 어렵습니다."
        rows.append(
            {
                "label": label,
                "without_method": without_method,
                "with_method": with_method,
                "global_without": global_without,
                "global_with": global_with,
                "local_without": local_without,
                "local_with": local_with,
                "all_without": all_without,
                "all_with": all_with,
                "global_delta": global_with - global_without,
                "local_delta": local_with - local_without,
                "all_delta": all_with - all_without,
                "interpretation": interpretation,
            }
        )
    return rows


def render_query_type_split_analysis(answer_rows):
    rows = query_type_split_rows(answer_rows)
    if not rows:
        return ""
    parts = [
        "<h2>Global vs Local Split Analysis</h2>",
        (
            "<p class='small'>Global 5개, Local 5개만 사용한 pilot result이므로 통계적으로 충분한 표본은 아닙니다. "
            "다만 Dense BGE-M3의 전체 평균 delta가 거의 0인 이유가 Global/Local 상쇄 때문인지 확인하는 데 중요한 진단 표입니다. "
            "RAPTOR Appendix I.1의 layer ablation처럼, 질문 유형에 따라 leaf layer와 summary layer의 유용성이 달라질 수 있습니다.</p>"
        ),
        "<table><thead><tr><th>Retriever</th><th>Global without</th><th>Global with RAPTOR</th><th>Local without</th><th>Local with RAPTOR</th><th>All without</th><th>All with RAPTOR</th><th>Interpretation</th></tr></thead><tbody>",
    ]
    for row in rows:
        parts.append(
            "<tr><td>{}</td><td>{:.3f}</td><td>{:.3f}</td><td>{:.3f}</td><td>{:.3f}</td><td>{:.3f}</td><td>{:.3f}</td><td>{}</td></tr>".format(
                html.escape(row["label"]),
                row["global_without"],
                row["global_with"],
                row["local_without"],
                row["local_with"],
                row["all_without"],
                row["all_with"],
                html.escape(row["interpretation"]),
            )
        )
    parts.append("</tbody></table>")
    return "\n".join(parts)


def best_method_counts(answer_rows):
    seen = set()
    counts = defaultdict(int)
    for row in answer_rows:
        qa_index = row.get("qa_index")
        best_method = row.get("best_method", "")
        if qa_index in seen or not best_method:
            continue
        seen.add(qa_index)
        counts[best_method] += 1
    return dict(sorted(counts.items()))


def best_method_rows(answer_rows):
    by_qa = defaultdict(list)
    for row in answer_rows:
        by_qa[row.get("qa_index")].append(row)
    rows = []
    for qa_index, qa_rows in sorted(by_qa.items(), key=lambda item: int(item[0])):
        first = qa_rows[0]
        method_scores = ", ".join(
            "{}={}".format(row.get("method", ""), row.get("judge_score", ""))
            for row in sorted(qa_rows, key=lambda row: row.get("method", ""))
        )
        rows.append(
            {
                "qa_index": qa_index,
                "question_type": first.get("question_type", ""),
                "question": first.get("question", ""),
                "best_method": first.get("best_method", ""),
                "best_reason": first.get("best_reason", ""),
                "method_scores": method_scores,
            }
        )
    return rows


def as_float(value, default=0.0):
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def analyze_bm25_wins(answer_rows):
    by_qa = defaultdict(list)
    for row in answer_rows:
        by_qa[row["qa_index"]].append(row)

    wins = []
    for qa_index, rows in sorted(by_qa.items()):
        bm25_rows = [row for row in rows if row["method"].startswith("bm25")]
        other_rows = [row for row in rows if not row["method"].startswith("bm25")]
        if not bm25_rows or not other_rows:
            continue

        best_bm25 = max(bm25_rows, key=lambda row: as_float(row.get("judge_score")))
        best_other = max(other_rows, key=lambda row: as_float(row.get("judge_score")))
        if as_float(best_bm25.get("judge_score")) >= as_float(best_other.get("judge_score")):
            try:
                top_terms = json.loads(best_bm25.get("bm25_top_terms") or "[]")
            except json.JSONDecodeError:
                top_terms = []
            wins.append(
                {
                    "qa_index": qa_index,
                    "question": best_bm25.get("question", ""),
                    "method": best_bm25["method"],
                    "bm25_score": best_bm25.get("judge_score", ""),
                    "best_non_bm25_method": best_other["method"],
                    "best_non_bm25_score": best_other.get("judge_score", ""),
                    "top_terms": top_terms[:6],
                    "explanation": best_bm25.get("judge_explanation", ""),
                }
            )
    return wins


def parse_retrieved_layers(value):
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


def format_layer_mix(value):
    layers = parse_retrieved_layers(value)
    if not layers:
        return "-"
    counts = Counter(layers)
    return ", ".join(
        f"L{layer}: {counts[layer]}" for layer in sorted(counts)
    )


def retrieval_family(method):
    if method.startswith("bm25"):
        return "lexical"
    if method.startswith("dense_bge_m3"):
        return "dense_bge_m3"
    if method.startswith("dpr"):
        return "dpr"
    if method in {"collapsed_tree", "traverse_tree"}:
        return "raptor_tree"
    return "retrieval"


def project_embeddings_2d(vectors, labels):
    try:
        import numpy as np
    except Exception:
        return []
    if len(vectors) < 2:
        return []
    matrix = np.array(vectors, dtype=np.float32)
    matrix = matrix - matrix.mean(axis=0, keepdims=True)
    try:
        _, _, vh = np.linalg.svd(matrix, full_matrices=False)
        components = vh[:2].T
        coords = matrix @ components
    except Exception:
        return []
    if coords.shape[1] < 2:
        coords = np.column_stack([coords[:, 0], np.zeros(coords.shape[0])])
    xs = coords[:, 0]
    ys = coords[:, 1]
    x_range = max(float(xs.max() - xs.min()), 1e-9)
    y_range = max(float(ys.max() - ys.min()), 1e-9)
    points = []
    for index, label in enumerate(labels):
        points.append(
            {
                **label,
                "x": float((coords[index, 0] - xs.min()) / x_range),
                "y": float((coords[index, 1] - ys.min()) / y_range),
            }
        )
    return points


def dense_projection_points(method, question, source_nodes, tree, embedding_model):
    if not method.startswith("dense_bge_m3"):
        return []
    vectors = [embedding_model.create_embedding(question)]
    labels = [{"kind": "query", "label": "query", "rank": 0, "score": 1.0}]
    for source in source_nodes[:12]:
        node = tree.all_nodes.get(int(source["node_index"]))
        if not node or "EMB" not in node.embeddings:
            continue
        vectors.append(node.embeddings["EMB"])
        labels.append(
            {
                "kind": "source",
                "label": f"#{source['node_index']} L{source.get('layer', 0)}",
                "rank": source.get("rank", ""),
                "score": source.get("score", 0),
            }
        )
    return project_embeddings_2d(vectors, labels)


def retrieval_visualization_html(qa_sources):
    payload = json.dumps(qa_sources, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>RAPTOR V3 Retrieval Visualization</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;color:#172033;background:#f8fafc}}
header{{padding:18px 22px;border-bottom:1px solid #d8e0ec;background:#fff}}
main{{display:grid;grid-template-columns:320px 1fr;min-height:calc(100vh - 72px)}}
aside{{padding:18px;border-right:1px solid #d8e0ec;background:#fff}}
section{{padding:18px 22px}}
label{{display:block;margin:0 0 12px;font-weight:700;font-size:13px}}
select{{width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;background:white}}
.grid{{display:grid;grid-template-columns:1.1fr .9fr;gap:16px}}
.card{{border:1px solid #d8e0ec;background:white;border-radius:8px;padding:14px;margin-bottom:14px}}
table{{border-collapse:collapse;width:100%;font-size:13px;background:white}}
th,td{{border:1px solid #d8e0ec;padding:7px;text-align:left;vertical-align:top}}
th{{background:#eef2ff}}
.bar{{height:18px;background:#e2e8f0;border-radius:4px;overflow:hidden}}
.fill{{height:100%;background:#2563eb}}
.term{{display:inline-block;border:1px solid #f59e0b;background:#fff7ed;border-radius:999px;padding:2px 7px;margin:2px;font-size:12px}}
svg{{width:100%;height:360px;border:1px solid #d8e0ec;border-radius:8px;background:#fff}}
.muted{{color:#64748b;font-size:13px}}
</style>
</head>
<body>
<header>
  <h1>RAPTOR V3 Retrieval Visualization</h1>
  <div class="muted">BM25는 lexical term contribution 중심, Dense/BGE-M3는 similarity rank와 embedding projection 중심으로 표시합니다.</div>
</header>
<main>
<aside>
  <label>QA item<select id="qaSelect"></select></label>
  <label>Method<select id="methodSelect"></select></label>
  <div id="summary" class="card"></div>
</aside>
<section>
  <div class="grid">
    <div class="card"><h2>Ranked Sources</h2><div id="ranked"></div></div>
    <div class="card"><h2>Similarity / Score Bars</h2><div id="bars"></div></div>
  </div>
  <div class="card"><h2>Dense Projection</h2><div id="projection"></div></div>
  <div class="card"><h2>BM25 Term Evidence</h2><div id="terms"></div></div>
</section>
</main>
<script>
const DATA = {payload};
const qaItems = DATA.qa_items || [];
const methodOrder = [
  "bm25_without_raptor","bm25_with_raptor",
  "dense_bge_m3_without_raptor","dense_bge_m3_with_raptor",
  "dpr_without_raptor","dpr_with_raptor",
  "traverse_tree","collapsed_tree","bm25_leaf","dpr_leaf"
];
let activeQa = qaItems.length ? qaItems[0].qa_index : null;
let activeMethod = "";
function esc(value){{return String(value ?? "").replace(/[&<>"']/g, ch => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[ch]));}}
function trunc(value, n=100){{value=String(value||""); return value.length>n ? value.slice(0,n-1)+"..." : value;}}
function qa(){{return qaItems.find(item => Number(item.qa_index) === Number(activeQa)) || qaItems[0];}}
function methodsFor(item){{return methodOrder.filter(method => item.methods && item.methods[method]);}}
function methodData(){{const item=qa(); return item && item.methods ? item.methods[activeMethod] : null;}}
function renderControls(){{
  const qaSelect=document.getElementById("qaSelect");
  qaSelect.innerHTML=qaItems.map(item => `<option value="${{esc(item.qa_index)}}" ${{Number(item.qa_index)===Number(activeQa)?"selected":""}}>QA ${{esc(item.qa_index)}} | ${{esc(item.question_type)}} | ${{esc(trunc(item.question, 64))}}</option>`).join("");
  const item=qa();
  const methods=methodsFor(item);
  if(!methods.includes(activeMethod)) activeMethod=methods[0] || "";
  document.getElementById("methodSelect").innerHTML=methods.map(method => `<option value="${{esc(method)}}" ${{method===activeMethod?"selected":""}}>${{esc(method)}}</option>`).join("");
  qaSelect.onchange=event=>{{activeQa=event.target.value; render();}};
  document.getElementById("methodSelect").onchange=event=>{{activeMethod=event.target.value; render();}};
}}
function renderSummary(){{
  const item=qa(), data=methodData();
  if(!item || !data) return;
  document.getElementById("summary").innerHTML = `
    <strong>Question type</strong><br>${{esc(item.question_type)}}<br><br>
    <strong>Question</strong><br>${{esc(item.question)}}<br><br>
    <strong>Method</strong><br>${{esc(activeMethod)}}<br>
    <strong>Family</strong> ${{esc(data.retrieval_family || "")}}<br>
    <strong>Score</strong> ${{esc(data.judge_score || "-")}} |
    <strong>Hit/rank</strong> ${{esc(data.hit || "-")}}/${{esc(data.rank || "-")}}
  `;
}}
function renderRanked(){{
  const data=methodData(); const sources=(data && data.source_nodes) || [];
  if(!sources.length){{document.getElementById("ranked").innerHTML="<p class='muted'>No retrieved sources.</p>"; return;}}
  document.getElementById("ranked").innerHTML = `<table><thead><tr><th>Rank</th><th>Node/Layer</th><th>Score</th><th>Descendant patents</th></tr></thead><tbody>${{sources.map(src => `<tr><td>${{esc(src.rank)}}</td><td>#${{esc(src.node_index)}} / L${{esc(src.layer)}}</td><td>${{Number(src.score || 0).toFixed(4)}}</td><td>${{esc((src.descendant_patent_ids || []).slice(0,8).join(", "))}}</td></tr>`).join("")}}</tbody></table>`;
}}
function renderBars(){{
  const data=methodData(); const sources=((data && data.source_nodes) || []).slice(0,12);
  if(!sources.length){{document.getElementById("bars").innerHTML="<p class='muted'>No scores.</p>"; return;}}
  const max=Math.max(...sources.map(src => Math.abs(Number(src.score || 0))), 1e-9);
  document.getElementById("bars").innerHTML=sources.map(src=>`<div style="display:grid;grid-template-columns:82px 1fr 70px;gap:8px;align-items:center;margin:7px 0"><span>r${{esc(src.rank)}} #${{esc(src.node_index)}}</span><span class="bar"><span class="fill" style="width:${{Math.max(2, Math.abs(Number(src.score || 0))/max*100)}}%"></span></span><span>${{Number(src.score || 0).toFixed(3)}}</span></div>`).join("");
}}
function renderTerms(){{
  const data=methodData(); const sources=(data && data.source_nodes) || [];
  const terms=sources.flatMap(src => src.bm25_top_terms || []);
  if(!activeMethod.startsWith("bm25") || !terms.length){{document.getElementById("terms").innerHTML="<p class='muted'>BM25 term contributions are shown only for BM25 methods.</p>"; return;}}
  document.getElementById("terms").innerHTML=terms.slice(0,24).map(term => `<span class="term">${{esc(term.term)}} | idf=${{Number(term.idf||0).toFixed(2)}} | score=${{Number(term.score||0).toFixed(2)}}</span>`).join("");
}}
function renderProjection(){{
  const data=methodData(); const points=(data && data.projection_points) || [];
  if(!points.length){{document.getElementById("projection").innerHTML="<p class='muted'>Dense PCA projection is available for BGE-M3 methods. DPR auxiliary baselines use score/rank views.</p>"; return;}}
  const circles=points.map(point=>{{
    const x=30+point.x*540, y=30+(1-point.y)*280;
    const fill=point.kind==="query" ? "#dc2626" : "#2563eb";
    const r=point.kind==="query" ? 7 : 5;
    return `<circle cx="${{x}}" cy="${{y}}" r="${{r}}" fill="${{fill}}"><title>${{esc(point.label)}} score=${{esc(point.score)}}</title></circle><text x="${{x+8}}" y="${{y+4}}" font-size="11">${{esc(point.label)}}</text>`;
  }}).join("");
  document.getElementById("projection").innerHTML=`<svg viewBox="0 0 620 340">${{circles}}</svg>`;
}}
function render(){{
  renderControls(); renderSummary(); renderRanked(); renderBars(); renderProjection(); renderTerms();
}}
render();
</script>
</body></html>"""


def analyze_collapsed_tree_wins(answer_rows):
    by_qa = defaultdict(list)
    for row in answer_rows:
        by_qa[row["qa_index"]].append(row)

    wins = []
    for qa_index, rows in sorted(by_qa.items(), key=lambda item: int(item[0])):
        collapsed = [row for row in rows if row.get("method") == "collapsed_tree"]
        other_rows = [row for row in rows if row.get("method") != "collapsed_tree"]
        if not collapsed or not other_rows:
            continue

        collapsed_row = collapsed[0]
        collapsed_score = as_float(collapsed_row.get("judge_score"))
        best_other = max(other_rows, key=lambda row: as_float(row.get("judge_score")))
        best_other_score = as_float(best_other.get("judge_score"))
        if collapsed_score < best_other_score:
            continue

        layers = parse_retrieved_layers(collapsed_row.get("retrieved_layers"))
        summary_count = sum(1 for layer in layers if layer > 0)
        leaf_count = sum(1 for layer in layers if layer == 0)
        if summary_count and leaf_count:
            retrieval_note = "leaf patents and summary nodes were combined under the same context budget."
        elif summary_count:
            retrieval_note = "summary nodes supplied compressed multi-patent context."
        elif leaf_count:
            retrieval_note = "leaf patents supplied direct evidence without relying on higher summaries."
        else:
            retrieval_note = "retrieval layer detail was not recorded."

        rank = collapsed_row.get("rank") or "-"
        hit = collapsed_row.get("hit")
        if str(hit) == "1":
            retrieval_note += f" Expected source appeared at rank {rank}."
        elif hit not in ("", None):
            retrieval_note += " Expected source was not found in retrieved context."

        wins.append(
            {
                "qa_index": qa_index,
                "question": collapsed_row.get("question", ""),
                "outcome": "strict win" if collapsed_score > best_other_score else "tie",
                "collapsed_score": collapsed_row.get("judge_score", ""),
                "best_other_method": best_other.get("method", ""),
                "best_other_score": best_other.get("judge_score", ""),
                "hit": collapsed_row.get("hit", ""),
                "rank": rank,
                "mrr": collapsed_row.get("mrr", ""),
                "retrieved_nodes": collapsed_row.get("retrieved_nodes", ""),
                "layer_mix": format_layer_mix(collapsed_row.get("retrieved_layers")),
                "retrieval_note": retrieval_note,
                "explanation": collapsed_row.get("judge_explanation", ""),
            }
        )
    return wins


def render_metric_table(title, metrics):
    lines = [f"<h2>{html.escape(title)}</h2>", "<table><thead><tr><th>Method</th><th>Value</th></tr></thead><tbody>"]
    for method, value in metrics.items():
        lines.append(
            f"<tr><td>{html.escape(method)}</td><td>{value:.3f}</td></tr>"
        )
    lines.append("</tbody></table>")
    return "\n".join(lines)


def render_question_type_metric_table(title, metrics):
    lines = [
        f"<h2>{html.escape(title)}</h2>",
        "<table><thead><tr><th>Question Type</th><th>Method</th><th>Value</th></tr></thead><tbody>",
    ]
    for (question_type, method), value in metrics.items():
        lines.append(
            "<tr><td>{}</td><td>{}</td><td>{:.3f}</td></tr>".format(
                html.escape(question_type),
                html.escape(method),
                value,
            )
        )
    lines.append("</tbody></table>")
    return "\n".join(lines)


def write_html_report(
    output_dir,
    args,
    answer_rows,
    retrieval_rows,
    appendix_rows,
    qualitative_rows,
    reporter,
    client,
    summary_repair_rows=None,
):
    ensure_paper_metrics(answer_rows)
    answer_recall_scores = summarize_by_method(answer_rows, "answer_recall")
    answer_recall_by_type = summarize_by_question_type_and_method(
        answer_rows, "answer_recall"
    )
    answer_f1_scores = summarize_by_method(answer_rows, "answer_f1")
    answer_f1_by_type = summarize_by_question_type_and_method(
        answer_rows, "answer_f1"
    )
    answer_scores = summarize_by_method(answer_rows, "judge_score")
    retrieval_hits = summarize_by_method(retrieval_rows, "hit")
    runtime = reporter.summary()
    bm25_wins = analyze_bm25_wins(answer_rows)
    best_counts = best_method_counts(answer_rows)
    best_rows = best_method_rows(answer_rows)
    methods = answer_methods(args)
    summary_repair_rows = summary_repair_rows or []
    hallucination_rate = None
    if appendix_rows:
        hallucination_rate = statistics.mean(
            1.0 if str(row.get("has_hallucination")).lower() == "true" else 0.0
            for row in appendix_rows
        )

    parts = [
        "<!doctype html>",
        '<html lang="ko"><head><meta charset="utf-8">',
        "<title>RAPTOR Patent Experiment Report</title>",
        "<style>",
        "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:32px;line-height:1.55;color:#1f2937;background:#f8fafc}",
        "h1,h2,h3{color:#111827} table{border-collapse:collapse;width:100%;margin:12px 0 28px;background:white}",
        "th,td{border:1px solid #d1d5db;padding:8px;vertical-align:top} th{background:#eef2ff;text-align:left}",
        ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.card{background:white;border:1px solid #d1d5db;padding:12px;border-radius:8px}",
        "code,pre{background:#f3f4f6;padding:2px 4px;border-radius:4px} .small{font-size:13px;color:#4b5563}",
        "</style></head><body>",
        "<h1>RAPTOR Patent Experiment Report</h1>",
        '<div class="grid">',
    ]

    summary_cards = {
        "Created": datetime.now().isoformat(timespec="seconds"),
        "Run label": args.run_label,
        "Text column": args.text_column,
        "Sample/category": str(args.sample_size_per_category),
        "Embedding": args.embedding_backend,
        "Embedding model": args.embedding_model,
        "Retrieval design": args.retrieval_design,
        "QA mode": args.qa_mode,
        "QA count": str(len({row["qa_index"] for row in answer_rows})),
        "Methods": ", ".join(methods),
        "DPR backend": args.dpr_backend,
        "LLM model": args.llm_model,
        "Reasoning": args.judge_reasoning_effort,
        "LLM calls": str(client.call_count),
        "Actual runtime": runtime["actual_runtime"],
        "Initial ETA": runtime["initial_eta"],
        "ETA error": runtime["initial_eta_error"],
    }
    for title, value in summary_cards.items():
        parts.append(
            f'<div class="card"><strong>{html.escape(title)}</strong><br>{html.escape(value)}</div>'
        )
    parts.append("</div>")

    parts.append(
        "<h2>Paper Metric Basis</h2>"
        "<p class='small'>RAPTOR 논문 메인 성능표는 retrieval recall이 아니라 task answer metric을 사용합니다. "
        "QASPER는 Answer F1, QuALITY는 Accuracy, NarrativeQA는 ROUGE/BLEU/METEOR를 보고합니다. "
        "본 특허 QA는 QASPER처럼 open-ended answer 비교이므로 Answer F1을 메인 지표로 재측정하고, "
        "같은 token-overlap 계산에서 나온 Answer Recall도 함께 표시했습니다.</p>"
    )
    parts.append(render_metric_table("Paper Main - Answer F1", answer_f1_scores))
    parts.append(render_metric_table("Answer Recall", answer_recall_scores))
    parts.append(render_question_type_metric_table("Global vs Local Answer F1", answer_f1_by_type))
    parts.append(render_question_type_metric_table("Global vs Local Answer Recall", answer_recall_by_type))
    parts.append(render_metric_table("Auxiliary Judge Score", answer_scores))
    parts.append(render_quantitative_tables(answer_rows))
    parts.append(render_raptor_delta_table(answer_rows))
    parts.append(render_query_type_split_analysis(answer_rows))
    parts.append("<h2>Best Method Selection Counts</h2>")
    if best_counts:
        parts.append("<table><thead><tr><th>Method</th><th>Best Count</th></tr></thead><tbody>")
        for method, count in best_counts.items():
            parts.append(
                f"<tr><td>{html.escape(method)}</td><td>{html.escape(str(count))}</td></tr>"
            )
        parts.append("</tbody></table>")
    else:
        parts.append("<p>No best-method selections recorded.</p>")

    parts.append("<h2>QA Best Method Summary</h2>")
    parts.append("<table><thead><tr><th>QA</th><th>Type</th><th>Question</th><th>Best Method</th><th>Scores</th><th>Reason</th></tr></thead><tbody>")
    for row in best_rows:
        parts.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(str(row["qa_index"])),
                html.escape(row["question_type"]),
                html.escape(row["question"]),
                html.escape(row["best_method"]),
                html.escape(row["method_scores"]),
                html.escape(row["best_reason"]),
            )
        )
    parts.append("</tbody></table>")
    parts.append(render_metric_table("Retrieval Hit Rate", retrieval_hits))

    parts.append("<h2>BM25 Win Analysis</h2>")
    parts.append(
        "<p>BM25가 이긴 경우는 질문의 표면 단어가 특허 요약 안의 희귀/전문 용어와 직접 겹치는 경우가 많습니다. "
        "아래 top terms는 해당 BM25 hit에서 점수 기여도가 큰 query term, term frequency, document frequency, IDF를 보여줍니다.</p>"
    )
    if bm25_wins:
        parts.append("<table><thead><tr><th>QA</th><th>Question</th><th>BM25 Method</th><th>Scores</th><th>Top Terms</th><th>Judge Note</th></tr></thead><tbody>")
        for win in bm25_wins:
            terms = "<br>".join(
                "{} (tf={}, df={}, idf={:.2f}, score={:.2f})".format(
                    html.escape(str(term.get("term", ""))),
                    term.get("term_frequency", ""),
                    term.get("document_frequency", ""),
                    as_float(term.get("idf")),
                    as_float(term.get("score")),
                )
                for term in win["top_terms"]
            )
            score_text = "BM25 {} vs {} {}".format(
                win["bm25_score"],
                win["best_non_bm25_method"],
                win["best_non_bm25_score"],
            )
            parts.append(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    html.escape(str(win["qa_index"])),
                    html.escape(win["question"]),
                    html.escape(win["method"]),
                    html.escape(score_text),
                    terms,
                    html.escape(win["explanation"]),
                )
            )
        parts.append("</tbody></table>")
    else:
        parts.append("<p>No BM25 wins over tree retrieval in answer evaluation.</p>")

    parts.append("<h2>Why BM25 Remains Competitive on Patent Data</h2>")
    parts.append(
        "<p>특허 문서는 소설이나 일반 서술형 문서와 달리 핵심 단어가 기술 구성요소의 정확한 식별자처럼 작동합니다. "
        "예를 들어 GEMM, DDR, GaN, 부동 게이트, 정규화 회로, PMOS 트랜지스터 같은 표현은 바꿔 쓰기보다 그대로 유지되는 경우가 많습니다. "
        "따라서 질문의 전문 용어가 특허 요약에도 동일하게 등장하면 BM25의 lexical matching이 매우 강한 신호가 됩니다.</p>"
    )
    parts.append(
        "<table><thead><tr><th>Reason</th><th>Effect on BM25</th><th>Implication</th></tr></thead><tbody>"
        "<tr><td>전문 용어의 희소성</td><td>특정 기술어의 document frequency가 낮아 IDF가 커집니다.</td><td>질문과 문서가 같은 희귀 용어를 공유하면 관련 특허가 상위로 올라옵니다.</td></tr>"
        "<tr><td>구성요소 명칭의 반복</td><td>특허 요약은 핵심 부품과 동작을 반복적으로 설명해 term frequency가 높아집니다.</td><td>핵심 용어가 반복된 문서는 BM25 점수에서 추가 이점을 얻습니다.</td></tr>"
        "<tr><td>표현의 정밀성</td><td>기술 용어는 문학적 표현처럼 자유롭게 치환되지 않고 원문 표현이 유지됩니다.</td><td>dense retrieval보다 단순 exact-match가 더 직접적인 검색 신호가 되는 경우가 있습니다.</td></tr>"
        "</tbody></table>"
    )
    if args.retrieval_design == "with_without_raptor":
        parts.append(
            "<p>따라서 본 실험 결과는 RAPTOR가 모든 검색 지표에서 BM25를 압도했다기보다, "
            "BM25는 특허의 precise lexical retrieval에 강하고 with-RAPTOR 전체 node 검색은 최종 QA 답변 생성에 필요한 summary evidence를 보강하는 상보적 관계로 해석하는 것이 적절합니다.</p>"
        )
    else:
        parts.append(
            "<p>따라서 본 실험 결과는 RAPTOR가 모든 검색 지표에서 BM25를 압도했다기보다, "
            "BM25는 특허의 precise lexical retrieval에 강하고 collapsed-tree RAPTOR는 retrieved context를 이용한 최종 QA 답변 생성에 강한 상보적 관계로 해석하는 것이 적절합니다.</p>"
        )

    parts.append("<h2>Appendix E Hallucination Audit</h2>")
    if summary_repair_rows:
        before = statistics.mean(
            0.0 if str(row.get("initial_faithful")).lower() == "true" else 1.0
            for row in summary_repair_rows
        )
        after = statistics.mean(
            0.0 if str(row.get("final_faithful")).lower() == "true" else 1.0
            for row in summary_repair_rows
        )
        repaired = sum(1 for row in summary_repair_rows if as_float(row.get("attempts_used")) > 0)
        parts.append(
            f"<p>Summary repair log: {len(summary_repair_rows)} generated summaries. "
            f"Unsupported claim rate before repair: {before:.3f}; after repair: {after:.3f}; repaired summaries: {repaired}.</p>"
        )
    if hallucination_rate is None:
        parts.append("<p>Skipped or no summary nodes audited.</p>")
    else:
        parts.append(
            f"<p>Audited summary nodes: {len(appendix_rows)}. Hallucination rate: {hallucination_rate:.3f}</p>"
        )
        parts.append("<table><thead><tr><th>Node</th><th>Child Count</th><th>Hallucination</th><th>Severity</th><th>Unsupported Claims</th></tr></thead><tbody>")
        for row in appendix_rows:
            parts.append(
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    html.escape(str(row.get("node_index", ""))),
                    html.escape(str(row.get("child_count", ""))),
                    html.escape(str(row.get("has_hallucination", ""))),
                    html.escape(str(row.get("severity", ""))),
                    html.escape(str(row.get("unsupported_claims", ""))),
                )
            )
        parts.append("</tbody></table>")

    parts.append("<h2>Qualitative Samples</h2>")
    for row in qualitative_rows:
        parts.append(
            "<h3>QA {} [{}] - {}</h3><p><strong>Question:</strong> {}</p>"
            "<p><strong>Best method:</strong> {}</p>"
            "<p><strong>Answer:</strong> {}</p><p><strong>Score:</strong> {}</p>"
            "<p class='small'><strong>Context preview:</strong> {}</p>".format(
                html.escape(str(row["qa_index"])),
                html.escape(row.get("question_type", "")),
                html.escape(row["method"]),
                html.escape(row["question"]),
                html.escape(row.get("best_method", "")),
                html.escape(row["answer"]),
                html.escape(str(row["judge_score"])),
                html.escape(row["context_preview"]),
            )
        )

    parts.append("</body></html>")
    (output_dir / "report.html").write_text("\n".join(parts), encoding="utf-8")


def write_report(
    output_dir,
    args,
    answer_rows,
    retrieval_rows,
    appendix_rows,
    qualitative_rows,
    reporter,
    client,
    summary_repair_rows=None,
):
    ensure_paper_metrics(answer_rows)
    answer_recall_scores = summarize_by_method(answer_rows, "answer_recall")
    answer_recall_by_type = summarize_by_question_type_and_method(
        answer_rows, "answer_recall"
    )
    answer_f1_scores = summarize_by_method(answer_rows, "answer_f1")
    answer_f1_by_type = summarize_by_question_type_and_method(
        answer_rows, "answer_f1"
    )
    answer_scores = summarize_by_method(answer_rows, "judge_score")
    retrieval_hits = summarize_by_method(retrieval_rows, "hit")
    best_counts = best_method_counts(answer_rows)
    best_rows = best_method_rows(answer_rows)
    runtime = reporter.summary()
    methods = answer_methods(args)
    summary_repair_rows = summary_repair_rows or []

    lines = [
        "# RAPTOR Patent Experiment Report",
        "",
        f"- Created: {datetime.now().isoformat(timespec='seconds')}",
        f"- Run label: {args.run_label}",
        f"- Text column: {args.text_column}",
        f"- Sample size per category: {args.sample_size_per_category}",
        f"- Embedding backend: {args.embedding_backend}",
        f"- Embedding model: {args.embedding_model}",
        f"- Retrieval design: {args.retrieval_design}",
        f"- QA mode: {args.qa_mode}",
        f"- QA count: {len({row['qa_index'] for row in answer_rows})}",
        f"- Methods: {', '.join(methods)}",
        f"- DPR backend: {args.dpr_backend}",
        f"- LLM model: {args.llm_model}",
        f"- Reasoning: {args.judge_reasoning_effort}",
        f"- LLM calls: {client.call_count}",
        f"- Actual runtime: {runtime['actual_runtime']}",
        f"- Initial ETA: {runtime['initial_eta']}",
        f"- Initial ETA absolute error: {runtime['initial_eta_error']}",
        "",
        "## Paper Metric Basis",
        "",
        "RAPTOR 논문 메인 성능표는 retrieval recall이 아니라 task answer metric을 사용한다. QASPER는 Answer F1, QuALITY는 Accuracy, NarrativeQA는 ROUGE/BLEU/METEOR를 보고한다. 본 특허 QA는 QASPER처럼 open-ended answer 비교이므로 Answer F1을 메인 지표로 재측정하고, 같은 token-overlap 계산에서 나온 Answer Recall도 함께 표시했다.",
        "",
        "## Paper Main - Answer F1",
        "",
    ]
    for method, value in answer_f1_scores.items():
        lines.append(f"- {method}: {value:.3f}")

    lines.extend(["", "## Answer Recall", ""])
    for method, value in answer_recall_scores.items():
        lines.append(f"- {method}: {value:.3f}")

    lines.extend(["", "## Global vs Local Answer F1", ""])
    for (question_type, method), value in answer_f1_by_type.items():
        lines.append(f"- {question_type} / {method}: {value:.3f}")

    lines.extend(["", "## Global vs Local Answer Recall", ""])
    for (question_type, method), value in answer_recall_by_type.items():
        lines.append(f"- {question_type} / {method}: {value:.3f}")

    lines.extend(["", "## Auxiliary Judge Score", ""])
    for method, value in answer_scores.items():
        lines.append(f"- {method}: {value:.3f}")

    lines.extend(["", "## Paper-style Main Performance", ""])
    for question_type in ("global", "local"):
        rows = [
            row
            for row in quantitative_metrics_by_type(answer_rows)
            if row["question_type"] == question_type
        ]
        if not rows:
            continue
        lines.extend(["", f"### {question_type.title()} QA", ""])
        for row in rows:
            lines.append(
                "- {method}: Answer F1={answer_f1:.3f}, Answer Recall={answer_recall:.3f}, Accuracy={paper_accuracy:.3f}, Avg Judge Score={judge_score:.3f}".format(
                    **row
                )
            )

    lines.extend(["", "## With vs Without RAPTOR Delta", ""])
    delta_rows = raptor_delta_rows(answer_rows)
    if delta_rows:
        for row in delta_rows:
            lines.append(
                "- {label}: answer_f1_delta={answer_f1_delta:+.3f}, answer_recall_delta={answer_recall_delta:+.3f}, accuracy_delta={accuracy_delta:+.3f}, score_delta={score_delta:+.3f} ({count} QA)".format(
                    **row
                )
            )
    else:
        lines.append("- Not available for this retrieval design.")

    lines.extend(["", "## Global vs Local Split Analysis", ""])
    split_rows = query_type_split_rows(answer_rows)
    if split_rows:
        lines.append(
            "Global 5개, Local 5개만 사용한 pilot result이므로 통계적으로 충분한 표본은 아니다. "
            "다만 Dense BGE-M3의 전체 평균 delta가 거의 0인 이유가 Global/Local 상쇄 때문인지 확인하는 데 중요한 진단 표다."
        )
        for row in split_rows:
            lines.append(
                "- {label}: global {global_without:.3f}->{global_with:.3f}, local {local_without:.3f}->{local_with:.3f}, all {all_without:.3f}->{all_with:.3f}. {interpretation}".format(
                    **row
                )
            )
    else:
        lines.append("- Not available for this retrieval design.")

    lines.extend(["", "## Best Method Selection Counts", ""])
    if best_counts:
        for method, count in best_counts.items():
            lines.append(f"- {method}: {count}")
    else:
        lines.append("- No best-method selections recorded.")

    lines.extend(["", "## QA Best Method Summary", ""])
    for row in best_rows:
        lines.append(
            "- QA {qa_index} [{question_type}] best={best_method}; scores={method_scores}; reason={best_reason}".format(
                **row
            )
        )

    lines.extend(["", "## Retrieval Hit Rate", ""])
    for method, value in retrieval_hits.items():
        lines.append(f"- {method}: {value:.3f}")

    lines.extend(["", "## Appendix E Audit", ""])
    if summary_repair_rows:
        before = statistics.mean(
            0.0 if str(row.get("initial_faithful")).lower() == "true" else 1.0
            for row in summary_repair_rows
        )
        after = statistics.mean(
            0.0 if str(row.get("final_faithful")).lower() == "true" else 1.0
            for row in summary_repair_rows
        )
        lines.append(f"- Repair log summaries: {len(summary_repair_rows)}")
        lines.append(f"- Unsupported claim rate before repair: {before:.3f}")
        lines.append(f"- Unsupported claim rate after repair: {after:.3f}")
    if appendix_rows:
        hallucination_rate = statistics.mean(
            1.0 if str(row.get("has_hallucination")).lower() == "true" else 0.0
            for row in appendix_rows
        )
        lines.append(f"- Audited summary nodes: {len(appendix_rows)}")
        lines.append(f"- Hallucination rate: {hallucination_rate:.3f}")
    else:
        lines.append("- Skipped or no summary nodes audited.")

    lines.extend(["", "## BM25 Win Analysis", ""])
    bm25_wins = analyze_bm25_wins(answer_rows)
    if bm25_wins:
        for win in bm25_wins:
            terms = ", ".join(
                "{}(idf={:.2f}, score={:.2f})".format(
                    term.get("term", ""),
                    as_float(term.get("idf")),
                    as_float(term.get("score")),
                )
                for term in win["top_terms"]
            )
            lines.append(
                "- QA {qa_index} {method}: BM25 {bm25_score} vs {best_non_bm25_method} {best_non_bm25_score}; terms: {terms}".format(
                    terms=terms,
                    **win,
                )
            )
    else:
        lines.append("- No BM25 wins over tree retrieval in answer evaluation.")

    lines.extend(["", "## Why BM25 Remains Competitive on Patent Data", ""])
    lines.append(
        "특허 문서는 소설이나 일반 서술형 문서와 달리 핵심 단어가 기술 구성요소의 정확한 식별자처럼 작동한다. "
        "GEMM, DDR, GaN, 부동 게이트, 정규화 회로, PMOS 트랜지스터 같은 표현은 바꿔 쓰기보다 그대로 유지되는 경우가 많다."
    )
    lines.append(
        "- 전문 용어의 희소성: 특정 기술어의 document frequency가 낮아 IDF가 커지고, 질문과 문서가 같은 희귀 용어를 공유하면 관련 특허가 상위로 올라간다."
    )
    lines.append(
        "- 구성요소 명칭의 반복: 특허 요약은 핵심 부품과 동작을 반복적으로 설명해 term frequency가 높아진다."
    )
    lines.append(
        "- 표현의 정밀성: 기술 용어는 문학적 표현처럼 자유롭게 치환되지 않아 exact-match가 dense retrieval보다 직접적인 검색 신호가 되는 경우가 있다."
    )
    if args.retrieval_design == "with_without_raptor":
        lines.append(
            "따라서 본 실험 결과는 RAPTOR가 모든 검색 지표에서 BM25를 압도했다기보다, "
            "BM25는 특허의 precise lexical retrieval에 강하고 with-RAPTOR 전체 node 검색은 최종 QA 답변 생성에 필요한 summary evidence를 보강하는 상보적 관계로 해석하는 것이 적절하다."
        )
    else:
        lines.append(
            "따라서 본 실험 결과는 RAPTOR가 모든 검색 지표에서 BM25를 압도했다기보다, "
            "BM25는 특허의 precise lexical retrieval에 강하고 collapsed-tree RAPTOR는 최종 QA 답변 생성에 강한 상보적 관계로 해석하는 것이 적절하다."
        )

    lines.extend(["", "## Qualitative Samples", ""])
    for row in qualitative_rows:
        lines.extend(
            [
                f"### QA {row['qa_index']} [{row.get('question_type', '')}] - {row['method']}",
                "",
                f"Question: {row['question']}",
                "",
                f"Best method: {row.get('best_method', '')}",
                "",
                f"Answer: {row['answer']}",
                "",
                f"Score: {row['judge_score']}",
                "",
                f"Context preview: {row['context_preview']}",
                "",
            ]
        )

    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    write_html_report(
        output_dir,
        args,
        answer_rows,
        retrieval_rows,
        appendix_rows,
        qualitative_rows,
        reporter,
        client,
        summary_repair_rows,
    )


def write_visualization_artifacts(
    output_dir,
    args,
    tree,
    embedding_model,
    retrievers,
    tokenizer,
    reporter,
):
    reporter.set_stage("writing tree/source overlays", completed=0, total=1)
    from scripts.export_qa_source_map import (
        ancestor_ids,
        expected_node_indices,
        group_answer_rows,
        leaf_index_by_patent_id,
        materialize_bm25_sources,
        materialize_tree_sources,
        parent_map,
        read_csv,
    )
    from scripts.export_tree_visualization import (
        build_tree_payload,
        html_template,
        update_report_link,
    )
    from scripts.inject_qa_overlays_into_report import (
        build_payload as build_overlay_payload,
        inject_section,
        replace_tree_iframe_block,
        section_html,
    )

    qa_items = read_jsonl(output_dir / "synthetic_qa.jsonl")
    answer_rows = group_answer_rows(read_csv(output_dir / "answer_eval.csv"))
    patent_to_leaf = leaf_index_by_patent_id(tree)
    parents = parent_map(tree)

    qa_payload = []
    for qa_index, qa in enumerate(qa_items):
        question = qa["question"]
        expected_ids = [str(value) for value in qa.get("source_patent_ids", [])]
        expected_nodes = expected_node_indices(expected_ids, patent_to_leaf)
        retrievals = {
            result.method: result
            for result in retrieval_results_for_query(
                args,
                question,
                tree,
                embedding_model,
                retrievers,
                tokenizer,
            )
        }
        methods = {}
        for method, result in retrievals.items():
            row = answer_rows.get(qa_index, {}).get(method, {})
            if hasattr(result, "nodes"):
                source_nodes = materialize_tree_sources(result, expected_ids)
            else:
                source_nodes = materialize_bm25_sources(
                    result, tree, patent_to_leaf, expected_ids
                )
            source_indices = [source["node_index"] for source in source_nodes]
            path_nodes = set(source_indices) | set(expected_nodes)
            for node_index in list(path_nodes):
                path_nodes.update(ancestor_ids(node_index, parents))
            methods[method] = {
                "method": method,
                "retrieval_family": retrieval_family(method),
                "answer": row.get("answer", ""),
                "judge_score": row.get("judge_score", ""),
                "judge_supported": row.get("judge_supported", ""),
                "judge_explanation": row.get("judge_explanation", ""),
                "hit": row.get("hit", ""),
                "rank": row.get("rank", ""),
                "mrr": row.get("mrr", ""),
                "latency_seconds": row.get("latency_seconds", ""),
                "source_nodes": source_nodes,
                "source_node_indices": source_indices,
                "path_node_indices": sorted(path_nodes),
                "projection_points": dense_projection_points(
                    method,
                    question,
                    source_nodes,
                    tree,
                    embedding_model,
                ),
            }
        qa_payload.append(
            {
                "qa_index": qa_index,
                "question": question,
                "reference_answer": qa.get("reference_answer", ""),
                "expected_patent_ids": expected_ids,
                "expected_node_indices": expected_nodes,
                "category": qa.get("category", ""),
                "category_name": qa.get("category_name", ""),
                "question_type": qa.get("question_type", ""),
                "methods": methods,
            }
        )
    qa_sources = {
        "meta": {
            "max_context_tokens": args.max_context_tokens,
            "traverse_top_k": args.traverse_top_k,
            "collapsed_top_k": args.collapsed_top_k,
            "bm25_top_k": args.bm25_top_k,
            "dpr_top_k": args.dpr_top_k,
            "dpr_backend": args.dpr_backend,
            "dpr_question_model": args.dpr_question_model,
            "dpr_context_model": args.dpr_context_model,
            "embedding_backend": args.embedding_backend,
            "embedding_model": args.embedding_model,
        },
        "qa_items": qa_payload,
    }
    qa_sources_path = output_dir / "qa_tree_sources.json"
    qa_sources_path.write_text(
        json.dumps(qa_sources, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    tree_payload = build_tree_payload(tree)
    tree_payload["qa_sources"] = qa_sources
    tree_data_path = output_dir / "tree_data.json"
    tree_data_path.write_text(
        json.dumps(tree_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    tree_html_path = output_dir / "tree_visualization.html"
    tree_html_path.write_text(html_template(tree_payload), encoding="utf-8")

    retrieval_html_path = output_dir / "retrieval_visualization.html"
    retrieval_html_path.write_text(
        retrieval_visualization_html(qa_sources),
        encoding="utf-8",
    )

    report_html_path = output_dir / "report.html"
    update_report_link(report_html_path, tree_html_path)
    if report_html_path.exists():
        report = report_html_path.read_text(encoding="utf-8")
        report = replace_tree_iframe_block(report)
        overlay_payload = build_overlay_payload(tree_payload, qa_sources)
        report = inject_section(report, section_html(overlay_payload))
        report = report.replace(
            "</body></html>",
            '<p><a href="retrieval_visualization.html">Open retrieval-specific visualization</a></p>\n</body></html>',
            1,
        )
        report_html_path.write_text(report, encoding="utf-8")
    reporter.advance()


def create_retrievers(args, documents, tree, embedding_model, reporter):
    retrievers = {}
    if args.retrieval_design == "with_without_raptor":
        all_node_documents = build_all_node_bm25_documents(tree)
        reporter.set_stage("building BM25 retrievers", completed=0, total=2)
        retrievers["bm25_without_raptor"] = BM25Retriever(
            documents,
            method="bm25_without_raptor",
        )
        reporter.advance()
        retrievers["bm25_with_raptor"] = BM25Retriever(
            all_node_documents,
            method="bm25_with_raptor",
        )
        reporter.advance()

        reporter.set_stage("building BGE-M3 dense retriever", completed=0, total=1)
        retrievers["dense_bge_m3_without_raptor"] = DenseRetriever(
            documents,
            embedding_model=embedding_model,
            method="dense_bge_m3_without_raptor",
        )
        reporter.advance()

        if args.include_dpr_baseline:
            reporter.set_stage("loading DPR retrievers", completed=0, total=2)
            retrievers["dpr_without_raptor"] = DPRRetriever(
                documents,
                question_model_name=args.dpr_question_model,
                context_model_name=args.dpr_context_model,
                backend=args.dpr_backend,
                method="dpr_without_raptor",
            )
            reporter.advance()
            retrievers["dpr_with_raptor"] = DPRRetriever(
                all_node_documents,
                question_model_name=args.dpr_question_model,
                context_model_name=args.dpr_context_model,
                backend=args.dpr_backend,
                method="dpr_with_raptor",
            )
            reporter.advance()
        return retrievers

    reporter.set_stage("building V2 retrievers", completed=0, total=2)
    retrievers["bm25_leaf"] = BM25Retriever(documents, method="bm25_leaf")
    reporter.advance()
    retrievers["dpr_leaf"] = DPRRetriever(
        documents,
        question_model_name=args.dpr_question_model,
        context_model_name=args.dpr_context_model,
        backend=args.dpr_backend,
        method="dpr_leaf",
    )
    reporter.advance()
    return retrievers


def write_print_reports(output_dir, reporter):
    reporter.set_stage("writing print reports", completed=0, total=2)
    report_html = output_dir / "report.html"
    if report_html.exists():
        from scripts.create_print_report import build_print_report

        rendered = build_print_report(report_html.read_text(encoding="utf-8"))
        (output_dir / "report_print.html").write_text(rendered, encoding="utf-8")
    reporter.advance()

    try:
        from scripts.create_compact_print_report import build_report as build_compact_report

        build_compact_report(output_dir, output_dir / "report_compact_print.html")
    except Exception as exc:
        fallback = (
            "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
            "<title>RAPTOR V3 Compact Print</title></head><body>"
            "<h1>RAPTOR V3 Compact Print</h1>"
            f"<p>Compact print generation failed: {html.escape(str(exc))}</p>"
            "<p>Use report_print.html for A4 output.</p></body></html>"
        )
        (output_dir / "report_compact_print.html").write_text(fallback, encoding="utf-8")
    reporter.advance()


def write_appendix_e_propagation(output_dir, args, reporter):
    if args.skip_llm:
        return
    appendix_path = output_dir / "appendix_e_audit.csv"
    tree_data_path = output_dir / "tree_data.json"
    if not appendix_path.exists() or not tree_data_path.exists():
        return
    try:
        from scripts.audit_appendix_e_propagation import (
            build_records,
            html_section,
            inject_html,
            write_csv as write_propagation_csv,
        )

        propagation_args = type(
            "Args",
            (),
            {
                "appendix_e_audit": appendix_path,
                "tree_data": tree_data_path,
                "base_url": args.llm_base_url,
                "model": args.llm_model,
                "reasoning_effort": args.judge_reasoning_effort,
            },
        )()
        reporter.set_stage("Appendix E propagation audit", completed=0, total=1)
        records = build_records(propagation_args)
        write_propagation_csv(output_dir / "appendix_e_propagation_audit.csv", records)
        report_html = output_dir / "report.html"
        if report_html.exists():
            inject_html(report_html, html_section(records))
        reporter.advance()
    except Exception as exc:
        (output_dir / "appendix_e_propagation_error.txt").write_text(
            str(exc),
            encoding="utf-8",
        )


def main():
    args = parse_args()
    if args.smoke:
        args.sample_size_per_category = min(args.sample_size_per_category, 2)
        args.qa_per_category = min(args.qa_per_category, 1)
        args.qa_global_count = min(args.qa_global_count, 1)
        args.qa_local_count = min(args.qa_local_count, 1)
        args.appendix_e_samples = min(args.appendix_e_samples, 2)
        args.progress_interval_seconds = min(args.progress_interval_seconds, 5)
        args.dpr_backend = "hash"

    output_dir = create_output_dir(args)
    initial_eta_seconds = 600 if args.smoke else (10800 if args.experiment_version == "v3" else 7200)
    reporter = ProgressReporter(
        report_interval_seconds=args.progress_interval_seconds,
        initial_eta_seconds=initial_eta_seconds,
    )
    client = CodexProxyClient(
        base_url=args.llm_base_url,
        model=args.llm_model,
        reasoning_effort=args.judge_reasoning_effort,
    )
    tokenizer = get_tokenizer()

    reporter.start()
    started_at = time.time()
    try:
        if args.skip_llm:
            (output_dir / "codex_proxy_health.json").write_text(
                json.dumps({"skipped": True, "reason": "--skip-llm"}, indent=2),
                encoding="utf-8",
            )
        else:
            reporter.set_stage("checking codex-proxy", completed=0, total=1)
            health = client.health()
            (output_dir / "codex_proxy_health.json").write_text(
                json.dumps(health, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            reporter.advance()

        reuse_dir = Path(args.reuse_run_dir) if args.reuse_run_dir else None
        if reuse_dir:
            reporter.set_stage("loading reused run artifacts", completed=0, total=1)
            sampled_path = reuse_dir / "sampled_patents.jsonl"
            tree_path = reuse_dir / "raptor_tree.pkl"
            documents = read_jsonl(sampled_path)
            sampled_rows = documents_to_rows(documents, text_column=args.text_column)
            with tree_path.open("rb") as handle:
                tree = pickle.load(handle)
            copy_if_different(sampled_path, output_dir / "sampled_patents.jsonl")
            copy_if_different(tree_path, output_dir / "raptor_tree.pkl")
            reporter.advance()
        else:
            reporter.set_stage("sampling patents", completed=0, total=1)
            sampled_rows = sample_patents(
                args.csv_path,
                per_category=args.sample_size_per_category,
                seed=args.seed,
                text_column=args.text_column,
            )
            documents = patent_documents(sampled_rows, text_column=args.text_column)
            write_jsonl(output_dir / "sampled_patents.jsonl", documents)
            reporter.advance()

        reporter.set_stage("loading embedding model", completed=0, total=1)
        embedding_model = create_embedding_model(args)
        reporter.advance()

        qa_model = CodexProxyQAModel(client=client)
        summary_repair_rows = []
        if not reuse_dir:
            if args.skip_llm:
                summarizer = ExtractiveSummarizationModel()
            else:
                base_summarizer = CodexProxySummarizationModel(client=client)
                if args.faithfulness_repair_attempts > 0:
                    summarizer = FaithfulnessRepairSummarizationModel(
                        base_summarizer,
                        client=client,
                        repair_attempts=args.faithfulness_repair_attempts,
                    )
                else:
                    summarizer = base_summarizer
            tree = build_tree(
                args,
                documents,
                embedding_model,
                qa_model,
                summarizer,
                tokenizer,
                reporter,
            )
            with (output_dir / "raptor_tree.pkl").open("wb") as handle:
                pickle.dump(tree, handle)
            summary_repair_rows = getattr(summarizer, "records", [])
            if summary_repair_rows:
                write_jsonl(output_dir / "summary_repair_log.jsonl", summary_repair_rows)

        retrievers = create_retrievers(args, documents, tree, embedding_model, reporter)

        qa_items = generate_synthetic_qa(args, sampled_rows, tree, client, reporter)
        write_jsonl(output_dir / "synthetic_qa.jsonl", qa_items)

        answer_rows, qualitative_rows = run_answer_evaluation(
            args,
            qa_items,
            tree,
            embedding_model,
            retrievers,
            qa_model,
            client,
            tokenizer,
            reporter,
        )
        write_csv(output_dir / "answer_eval.csv", answer_rows)
        write_jsonl(output_dir / "qualitative_samples.jsonl", qualitative_rows)

        retrieval_rows = run_retrieval_metrics(
            args,
            documents,
            tree,
            embedding_model,
            retrievers,
            tokenizer,
            reporter,
        )
        write_csv(output_dir / "retrieval_eval.csv", retrieval_rows)

        appendix_rows = run_appendix_e_audit(args, tree, client, reporter)
        write_csv(output_dir / "appendix_e_audit.csv", appendix_rows)

        reporter.set_stage("writing final report", completed=0, total=1)
        write_report(
            output_dir,
            args,
            answer_rows,
            retrieval_rows,
            appendix_rows,
            qualitative_rows,
            reporter,
            client,
            summary_repair_rows,
        )
        reporter.advance()

        write_visualization_artifacts(
            output_dir,
            args,
            tree,
            embedding_model,
            retrievers,
            tokenizer,
            reporter,
        )
        write_appendix_e_propagation(output_dir, args, reporter)
        write_print_reports(output_dir, reporter)
    finally:
        reporter.stop()

    print(f"Experiment finished in {time.time() - started_at:.1f}s")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
