#!/usr/bin/env python3
import argparse
import html
import json
import pickle
import shutil
import statistics
import sys
import time
from collections import defaultdict
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


ANSWER_METHODS = ("traverse_tree", "collapsed_tree", "bm25_leaf", "dpr_leaf")


class ExtractiveSummarizationModel(BaseSummarizationModel):
    def summarize(self, context, max_tokens=500):
        return " ".join(context.split()[: max(20, max_tokens)])


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run RAPTOR patent retrieval experiments on patent_rawdata.csv."
    )
    parser.add_argument("--csv-path", default=str(REPO_ROOT / "patent_rawdata.csv"))
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--run-label", default="v2")
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
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    parser.add_argument(
        "--embedding-backend",
        choices=["minilm", "hash"],
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
    parser.add_argument("--progress-interval-seconds", type=int, default=60)
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Use a tiny category sample and short progress interval.",
    )
    return parser.parse_args()


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
        "context": result.context,
    }


def bm25_retrieval_row(result, expected_patent_ids=None):
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
        "retrieved_layers": "",
        "latency_seconds": result.elapsed_seconds,
        "hit": int(rank is not None) if expected_ids else "",
        "rank": rank or "",
        "mrr": (1 / rank) if rank else 0,
        "bm25_top_terms": json.dumps(
            result.hits[0].contributions if result.hits else [],
            ensure_ascii=False,
        ),
        "context": result.context,
    }


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
    for node_index, node in sorted(tree.all_nodes.items()):
        documents.append(
            {
                "id": str(node_index),
                "text": node.text,
                "metadata": {
                    "node_index": node_index,
                    "descendant_patent_ids": descendant_patent_ids(tree, node_index, cache),
                },
            }
        )
    return documents


def run_answer_evaluation(
    args,
    qa_items,
    tree,
    embedding_model,
    bm25_leaf,
    dpr_leaf,
    qa_model,
    client,
    tokenizer,
    reporter,
):
    rows = []
    qualitative_rows = []
    total = len(qa_items) * (len(ANSWER_METHODS) + 1)
    reporter.set_stage("answer evaluation", completed=0, total=total)
    for qa_index, qa in enumerate(qa_items):
        question = qa["question"]
        reference_answer = qa.get("reference_answer", "")
        expected_ids = [str(value) for value in qa.get("source_patent_ids", [])]

        retrieval_results = [
            retrieve_traverse_tree(
                tree,
                question,
                embedding_model,
                "EMB",
                tokenizer,
                top_k=args.traverse_top_k,
                max_tokens=args.max_context_tokens,
            ),
            retrieve_collapsed_tree(
                tree,
                question,
                embedding_model,
                "EMB",
                tokenizer,
                top_k=args.collapsed_top_k,
                max_tokens=args.max_context_tokens,
            ),
            bm25_leaf.search(
                question,
                top_k=args.bm25_top_k,
                max_context_tokens=args.max_context_tokens,
                tokenizer=tokenizer,
            ),
            dpr_leaf.search(
                question,
                top_k=args.dpr_top_k,
                max_context_tokens=args.max_context_tokens,
                tokenizer=tokenizer,
            ),
        ]

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
    bm25_leaf,
    dpr_leaf,
    tokenizer,
    reporter,
):
    rows = []
    total = len(documents) * len(ANSWER_METHODS)
    reporter.set_stage("retrieval metrics", completed=0, total=total)
    for document in documents:
        metadata = document["metadata"]
        query = metadata.get("query_title") or metadata.get("query_ai_summary") or document["text"]
        expected_id = document["id"]
        results = [
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
            bm25_leaf.search(
                query,
                top_k=args.bm25_top_k,
                max_context_tokens=args.max_context_tokens,
                tokenizer=tokenizer,
            ),
            dpr_leaf.search(
                query,
                top_k=args.dpr_top_k,
                max_context_tokens=args.max_context_tokens,
                tokenizer=tokenizer,
            ),
        ]
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
    summary_nodes = [
        node for node in tree.all_nodes.values() if node.metadata.get("node_type") == "summary"
    ]
    summary_nodes = summary_nodes[: args.appendix_e_samples]
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
            f"Child text:\n{child_text[:5000]}\n\nParent summary:\n{node.text}"
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
):
    answer_scores = summarize_by_method(answer_rows, "judge_score")
    answer_scores_by_type = summarize_by_question_type_and_method(
        answer_rows, "judge_score"
    )
    retrieval_hits = summarize_by_method(retrieval_rows, "hit")
    retrieval_mrr = summarize_by_method(retrieval_rows, "mrr")
    runtime = reporter.summary()
    bm25_wins = analyze_bm25_wins(answer_rows)
    best_counts = best_method_counts(answer_rows)
    best_rows = best_method_rows(answer_rows)
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
        "QA mode": args.qa_mode,
        "QA count": str(len({row["qa_index"] for row in answer_rows})),
        "Methods": ", ".join(ANSWER_METHODS),
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

    parts.append(render_metric_table("Answer Scores", answer_scores))
    parts.append(render_question_type_metric_table("Global vs Local Answer Scores", answer_scores_by_type))
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
    parts.append(render_metric_table("Retrieval MRR", retrieval_mrr))

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

    parts.append("<h2>Appendix E Hallucination Audit</h2>")
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


def write_report(output_dir, args, answer_rows, retrieval_rows, appendix_rows, qualitative_rows, reporter, client):
    answer_scores = summarize_by_method(answer_rows, "judge_score")
    answer_scores_by_type = summarize_by_question_type_and_method(
        answer_rows, "judge_score"
    )
    retrieval_hits = summarize_by_method(retrieval_rows, "hit")
    retrieval_mrr = summarize_by_method(retrieval_rows, "mrr")
    best_counts = best_method_counts(answer_rows)
    best_rows = best_method_rows(answer_rows)
    runtime = reporter.summary()

    lines = [
        "# RAPTOR Patent Experiment Report",
        "",
        f"- Created: {datetime.now().isoformat(timespec='seconds')}",
        f"- Run label: {args.run_label}",
        f"- Text column: {args.text_column}",
        f"- Sample size per category: {args.sample_size_per_category}",
        f"- Embedding backend: {args.embedding_backend}",
        f"- QA mode: {args.qa_mode}",
        f"- QA count: {len({row['qa_index'] for row in answer_rows})}",
        f"- Methods: {', '.join(ANSWER_METHODS)}",
        f"- DPR backend: {args.dpr_backend}",
        f"- LLM model: {args.llm_model}",
        f"- Reasoning: {args.judge_reasoning_effort}",
        f"- LLM calls: {client.call_count}",
        f"- Actual runtime: {runtime['actual_runtime']}",
        f"- Initial ETA: {runtime['initial_eta']}",
        f"- Initial ETA absolute error: {runtime['initial_eta_error']}",
        "",
        "## Answer Scores",
        "",
    ]
    for method, value in answer_scores.items():
        lines.append(f"- {method}: {value:.3f}")

    lines.extend(["", "## Global vs Local Answer Scores", ""])
    for (question_type, method), value in answer_scores_by_type.items():
        lines.append(f"- {question_type} / {method}: {value:.3f}")

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

    lines.extend(["", "## Retrieval MRR", ""])
    for method, value in retrieval_mrr.items():
        lines.append(f"- {method}: {value:.3f}")

    lines.extend(["", "## Appendix E Audit", ""])
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
    )


def write_visualization_artifacts(
    output_dir,
    args,
    tree,
    embedding_model,
    bm25_leaf,
    dpr_leaf,
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
            "traverse_tree": retrieve_traverse_tree(
                tree,
                question,
                embedding_model,
                "EMB",
                tokenizer,
                top_k=args.traverse_top_k,
                max_tokens=args.max_context_tokens,
            ),
            "collapsed_tree": retrieve_collapsed_tree(
                tree,
                question,
                embedding_model,
                "EMB",
                tokenizer,
                top_k=args.collapsed_top_k,
                max_tokens=args.max_context_tokens,
            ),
            "bm25_leaf": bm25_leaf.search(
                question,
                top_k=args.bm25_top_k,
                max_context_tokens=args.max_context_tokens,
                tokenizer=tokenizer,
            ),
            "dpr_leaf": dpr_leaf.search(
                question,
                top_k=args.dpr_top_k,
                max_context_tokens=args.max_context_tokens,
                tokenizer=tokenizer,
            ),
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

    report_html_path = output_dir / "report.html"
    update_report_link(report_html_path, tree_html_path)
    if report_html_path.exists():
        report = report_html_path.read_text(encoding="utf-8")
        report = replace_tree_iframe_block(report)
        overlay_payload = build_overlay_payload(tree_payload, qa_sources)
        report = inject_section(report, section_html(overlay_payload))
        report_html_path.write_text(report, encoding="utf-8")
    reporter.advance()


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
    initial_eta_seconds = 600 if args.smoke else 7200
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
        if not reuse_dir:
            summarizer = (
                ExtractiveSummarizationModel()
                if args.skip_llm
                else CodexProxySummarizationModel(client=client)
            )
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

        bm25_leaf = BM25Retriever(documents, method="bm25_leaf")
        reporter.set_stage("loading DPR retriever", completed=0, total=1)
        dpr_leaf = DPRRetriever(
            documents,
            question_model_name=args.dpr_question_model,
            context_model_name=args.dpr_context_model,
            backend=args.dpr_backend,
            method="dpr_leaf",
        )
        reporter.advance()

        qa_items = generate_synthetic_qa(args, sampled_rows, tree, client, reporter)
        write_jsonl(output_dir / "synthetic_qa.jsonl", qa_items)

        answer_rows, qualitative_rows = run_answer_evaluation(
            args,
            qa_items,
            tree,
            embedding_model,
            bm25_leaf,
            dpr_leaf,
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
            bm25_leaf,
            dpr_leaf,
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
        )
        reporter.advance()

        write_visualization_artifacts(
            output_dir,
            args,
            tree,
            embedding_model,
            bm25_leaf,
            dpr_leaf,
            tokenizer,
            reporter,
        )
    finally:
        reporter.stop()

    print(f"Experiment finished in {time.time() - started_at:.1f}s")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
