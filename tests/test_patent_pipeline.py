import csv
import tempfile
import unittest
from pathlib import Path

from raptor.EmbeddingModels import HashEmbeddingModel
from raptor.SummarizationModels import BaseSummarizationModel
from raptor.bm25 import BM25Retriever
from raptor.cluster_tree_builder import ClusterTreeConfig, ClusterTreeBuilder
from raptor.cluster_utils import HardKMeansClustering
from raptor.dense import DenseRetriever
from raptor.dpr import DPRRetriever
from raptor.experiment_utils import patent_documents, sample_patents
from raptor.structured_retrieval import retrieve_collapsed_tree, retrieve_traverse_tree
from raptor.tokenization import get_tokenizer
from scripts.run_patent_raptor_experiment import (
    answer_methods,
    build_all_node_bm25_documents,
    fallback_global_local_qa,
    retrieval_results_for_query,
)


class FakeSummarizer(BaseSummarizationModel):
    def summarize(self, context, max_tokens=150):
        return " ".join(context.split()[:40])


class PatentPipelineTests(unittest.TestCase):
    def test_sample_patents_per_category(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "patents.csv"
            fieldnames = [
                "patent_id",
                "중분류",
                "중분류명",
                "요약",
                "발명의 명칭",
                "AI요약(목적+솔루션)",
            ]
            with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for category in ["AA", "AB"]:
                    for index in range(3):
                        writer.writerow(
                            {
                                "patent_id": f"{category}-{index}",
                                "중분류": category,
                                "중분류명": category,
                                "요약": f"{category} summary {index}",
                                "발명의 명칭": f"{category} title {index}",
                                "AI요약(목적+솔루션)": f"{category} ai {index}",
                            }
                        )

            rows = sample_patents(csv_path, per_category=2, seed=42)
            counts = {}
            for row in rows:
                counts[row["중분류"]] = counts.get(row["중분류"], 0) + 1
            self.assertEqual(counts, {"AA": 2, "AB": 2})

    def test_hard_clustering_assigns_once(self):
        nodes = []
        embedding_model = HashEmbeddingModel(dimensions=16)
        for index in range(12):
            text = f"cluster text {index}"
            node = type("Node", (), {})()
            node.text = text
            node.embeddings = {"EMB": embedding_model.create_embedding(text)}
            nodes.append(node)

        clusters = HardKMeansClustering.perform_clustering(
            nodes, "EMB", target_cluster_size=4
        )
        assigned = [id(node) for cluster in clusters for node in cluster]
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertEqual(len(assigned), len(nodes))

    def test_structured_retrieval_and_bm25(self):
        tokenizer = get_tokenizer()
        embedding_model = HashEmbeddingModel(dimensions=32)
        documents = patent_documents(
            [
                {
                    "patent_id": "P1",
                    "중분류": "AA",
                    "중분류명": "AA",
                    "요약": "뉴럴 프로세서가 행렬 연산을 가속한다",
                    "발명의 명칭": "뉴럴 프로세서",
                    "AI요약(목적+솔루션)": "행렬 연산 가속",
                },
                {
                    "patent_id": "P2",
                    "중분류": "AA",
                    "중분류명": "AA",
                    "요약": "패키징 공정에서 열 방출 구조를 개선한다",
                    "발명의 명칭": "반도체 패키징",
                    "AI요약(목적+솔루션)": "열 방출 개선",
                },
                {
                    "patent_id": "P3",
                    "중분류": "AA",
                    "중분류명": "AA",
                    "요약": "데이터 플랫폼이 모델 배포 이력을 관리한다",
                    "발명의 명칭": "모델 배포 플랫폼",
                    "AI요약(목적+솔루션)": "배포 이력 관리",
                },
            ],
            text_column="요약",
        )
        config = ClusterTreeConfig(
            tokenizer=tokenizer,
            num_layers=2,
            summarization_model=FakeSummarizer(),
            embedding_models={"EMB": embedding_model},
            cluster_embedding_model="EMB",
            clustering_algorithm=HardKMeansClustering,
            clustering_params={"target_cluster_size": 2},
        )
        tree = ClusterTreeBuilder(config).build_from_documents(
            documents, use_multithreading=False
        )

        collapsed = retrieve_collapsed_tree(
            tree, "행렬 연산", embedding_model, "EMB", tokenizer, top_k=2
        )
        traverse = retrieve_traverse_tree(
            tree, "행렬 연산", embedding_model, "EMB", tokenizer, top_k=1
        )
        self.assertTrue(collapsed.nodes)
        self.assertTrue(traverse.nodes)

        bm25 = BM25Retriever(documents)
        result = bm25.search("행렬 연산", top_k=2)
        self.assertEqual(result.hits[0].doc_id, "P1")
        self.assertTrue(result.hits[0].contributions)

        dpr = DPRRetriever(documents, backend="hash")
        dpr_result = dpr.search("행렬 연산", top_k=2, tokenizer=tokenizer)
        self.assertEqual(dpr_result.method, "dpr_leaf")
        self.assertTrue(dpr_result.hits)
        self.assertLessEqual(len(dpr_result.hits), 2)

        args = type(
            "Args",
            (),
            {
                "retrieval_design": "with_without_raptor",
                "include_dpr_baseline": False,
                "bm25_top_k": 2,
                "dense_top_k": 2,
                "dpr_top_k": 2,
                "traverse_top_k": 1,
                "collapsed_top_k": 2,
                "max_context_tokens": 2000,
            },
        )()
        all_node_docs = build_all_node_bm25_documents(tree)
        retrievers = {
            "bm25_without_raptor": BM25Retriever(
                documents, method="bm25_without_raptor"
            ),
            "bm25_with_raptor": BM25Retriever(
                all_node_docs, method="bm25_with_raptor"
            ),
            "dense_bge_m3_without_raptor": DenseRetriever(
                documents,
                embedding_model=embedding_model,
                method="dense_bge_m3_without_raptor",
            ),
        }
        v3_results = retrieval_results_for_query(
            args, "행렬 연산", tree, embedding_model, retrievers, tokenizer
        )
        self.assertEqual(
            [result.method for result in v3_results],
            list(answer_methods(args)),
        )
        with_layers = [
            hit.metadata.get("layer")
            for hit in v3_results[1].hits
            if "layer" in hit.metadata
        ]
        self.assertTrue(with_layers)

    def test_global_local_fallback_qa_counts(self):
        rows = []
        for category in ["AA", "AB"]:
            for index in range(4):
                rows.append(
                    {
                        "patent_id": f"{category}-{index}",
                        "중분류": category,
                        "중분류명": category,
                        "요약": f"{category} summary {index}",
                        "발명의 명칭": f"{category} title {index}",
                    }
                )
        args = type(
            "Args",
            (),
            {
                "qa_global_count": 5,
                "qa_local_count": 5,
                "text_column": "요약",
            },
        )()
        qa_items = fallback_global_local_qa(rows, args)
        self.assertEqual(len(qa_items), 10)
        self.assertEqual(
            sum(1 for item in qa_items if item["question_type"] == "global"), 5
        )
        self.assertEqual(
            sum(1 for item in qa_items if item["question_type"] == "local"), 5
        )
        self.assertTrue(
            all(len(item["source_patent_ids"]) >= 2 for item in qa_items[:5])
        )
        self.assertTrue(
            all(len(item["source_patent_ids"]) == 1 for item in qa_items[5:])
        )


if __name__ == "__main__":
    unittest.main()
