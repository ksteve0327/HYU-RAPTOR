#!/usr/bin/env python3
"""Reconstruct per-QA retrieval source nodes for the RAPTOR tree visualization."""

from __future__ import annotations

import argparse
import csv
import json
import pickle
import sys
from pathlib import Path
from typing import Dict, Iterable, List


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from raptor.EmbeddingModels import HashEmbeddingModel, MiniLMKoreanEmbeddingModel
from raptor.bm25 import BM25Retriever
from raptor.dpr import DPRRetriever
from raptor.structured_retrieval import (
    descendant_patent_ids,
    retrieve_collapsed_tree,
    retrieve_traverse_tree,
)
from raptor.tokenization import get_tokenizer


def read_jsonl(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_csv(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def create_embedding_model(name: str, backend: str):
    if backend == "hash":
        return HashEmbeddingModel(dimensions=96)
    return MiniLMKoreanEmbeddingModel(model_name=name)


def leaf_index_by_patent_id(tree) -> Dict[str, int]:
    rows = {}
    for index, node in tree.leaf_nodes.items():
        patent_id = node.metadata.get("patent_id")
        if patent_id:
            rows[str(patent_id)] = index
    return rows


def build_all_node_documents(tree) -> List[Dict]:
    rows = []
    cache = {}
    for node_index, node in sorted(tree.all_nodes.items()):
        rows.append(
            {
                "id": str(node_index),
                "text": node.text,
                "metadata": {
                    "node_index": node_index,
                    "descendant_patent_ids": descendant_patent_ids(tree, node_index, cache),
                },
            }
        )
    return rows


def parent_map(tree) -> Dict[int, List[int]]:
    parents: Dict[int, List[int]] = {}
    for parent_index, node in tree.all_nodes.items():
        for child_index in node.children:
            parents.setdefault(child_index, []).append(parent_index)
    return {key: sorted(value) for key, value in parents.items()}


def ancestor_ids(index: int, parents: Dict[int, List[int]]) -> List[int]:
    result = []
    queue = list(parents.get(index, []))
    seen = set()
    while queue:
        parent = queue.pop(0)
        if parent in seen:
            continue
        seen.add(parent)
        result.append(parent)
        queue.extend(parents.get(parent, []))
    return result


def expected_node_indices(expected_ids: Iterable[str], patent_to_leaf: Dict[str, int]) -> List[int]:
    return [
        patent_to_leaf[patent_id]
        for patent_id in expected_ids
        if patent_id in patent_to_leaf
    ]


def materialize_tree_sources(result, expected_ids: List[str]) -> List[Dict]:
    rows = []
    expected = set(expected_ids)
    for rank, node in enumerate(result.nodes, start=1):
        descendants = list(node.descendant_patent_ids)
        rows.append(
            {
                "rank": rank,
                "node_index": node.node_index,
                "layer": node.layer_number,
                "score": node.score,
                "token_count": node.token_count,
                "descendant_patent_ids": descendants,
                "contains_expected": bool(expected & set(descendants)),
            }
        )
    return rows


def materialize_bm25_sources(result, tree, patent_to_leaf: Dict[str, int], expected_ids: List[str]) -> List[Dict]:
    rows = []
    expected = set(expected_ids)
    cache = {}
    for hit in result.hits:
        if "node_index" in hit.metadata:
            node_index = int(hit.metadata["node_index"])
        else:
            node_index = patent_to_leaf.get(hit.doc_id)
        if node_index is None:
            continue

        descendants = hit.metadata.get("descendant_patent_ids")
        if descendants is None:
            descendants = descendant_patent_ids(tree, node_index, cache)

        layer = 0
        for layer_number, nodes in tree.layer_to_nodes.items():
            if any(node.index == node_index for node in nodes):
                layer = layer_number
                break

        rows.append(
            {
                "rank": hit.rank,
                "node_index": node_index,
                "layer": layer,
                "score": hit.score,
                "token_count": len(str(hit.text).split()),
                "descendant_patent_ids": list(descendants),
                "contains_expected": bool(expected & set(descendants)),
                "bm25_top_terms": hit.contributions,
            }
        )
    return rows


def group_answer_rows(rows: List[Dict]) -> Dict[int, Dict[str, Dict]]:
    grouped: Dict[int, Dict[str, Dict]] = {}
    for row in rows:
        qa_index = int(row["qa_index"])
        grouped.setdefault(qa_index, {})[row["method"]] = row
    return grouped


def build_source_map(args) -> Dict:
    with args.tree_pickle.open("rb") as handle:
        tree = pickle.load(handle)

    qa_items = read_jsonl(args.synthetic_qa)
    answer_rows = group_answer_rows(read_csv(args.answer_eval))
    documents = read_jsonl(args.sampled_documents)
    tokenizer = get_tokenizer()
    embedding_model = create_embedding_model(args.embedding_model, args.embedding_backend)
    bm25_leaf = BM25Retriever(documents, method="bm25_leaf")
    dpr_leaf = DPRRetriever(
        documents,
        question_model_name=args.dpr_question_model,
        context_model_name=args.dpr_context_model,
        backend=args.dpr_backend,
        method="dpr_leaf",
    )
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
        print(f"mapped QA {qa_index + 1}/{len(qa_items)}", flush=True)

    return {
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree-pickle", required=True, type=Path)
    parser.add_argument("--synthetic-qa", required=True, type=Path)
    parser.add_argument("--answer-eval", required=True, type=Path)
    parser.add_argument("--sampled-documents", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument(
        "--embedding-model",
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    parser.add_argument("--embedding-backend", choices=["minilm", "hash"], default="minilm")
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
    parser.add_argument("--dpr-backend", choices=["hf", "hash"], default="hf")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_map = build_source_map(args)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(source_map, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {args.output_json}")


if __name__ == "__main__":
    main()
