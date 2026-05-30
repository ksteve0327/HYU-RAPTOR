import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from .tree_structures import Node, Tree
from .utils import (
    distances_from_embeddings,
    get_embeddings,
    get_node_list,
    get_text,
    indices_of_nearest_neighbors_from_distances,
    reverse_mapping,
)


@dataclass
class RetrievedNode:
    node_index: int
    layer_number: int
    score: float
    token_count: int
    text: str
    metadata: Dict
    descendant_patent_ids: List[str]


@dataclass
class RetrievalResult:
    method: str
    query: str
    context: str
    nodes: List[RetrievedNode]
    elapsed_seconds: float


def descendant_patent_ids(tree: Tree, node_index: int, cache=None) -> List[str]:
    if cache is None:
        cache = {}
    if node_index in cache:
        return cache[node_index]

    node = tree.all_nodes[node_index]
    patent_id = node.metadata.get("patent_id")
    if patent_id:
        cache[node_index] = [patent_id]
        return cache[node_index]

    ids = []
    for child_index in sorted(node.children):
        ids.extend(descendant_patent_ids(tree, child_index, cache))

    seen = set()
    deduped = []
    for value in ids:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    cache[node_index] = deduped
    return deduped


def _materialize_nodes(
    tree: Tree,
    nodes: List[Node],
    scores: Dict[int, float],
    tokenizer,
) -> List[RetrievedNode]:
    layer_map = reverse_mapping(tree.layer_to_nodes)
    descendant_cache = {}
    return [
        RetrievedNode(
            node_index=node.index,
            layer_number=layer_map[node.index],
            score=scores.get(node.index, 0.0),
            token_count=len(tokenizer.encode(node.text)),
            text=node.text,
            metadata=node.metadata,
            descendant_patent_ids=descendant_patent_ids(
                tree, node.index, descendant_cache
            ),
        )
        for node in nodes
    ]


def retrieve_collapsed_tree(
    tree: Tree,
    query: str,
    embedding_model,
    context_embedding_model: str,
    tokenizer,
    top_k: int = 20,
    max_tokens: int = 2000,
    method: str = "collapsed_tree",
) -> RetrievalResult:
    started_at = time.time()
    query_embedding = embedding_model.create_embedding(query)
    node_list = get_node_list(tree.all_nodes)
    embeddings = get_embeddings(node_list, context_embedding_model)
    distances = distances_from_embeddings(query_embedding, embeddings)
    indices = indices_of_nearest_neighbors_from_distances(distances)

    selected_nodes = []
    scores = {}
    total_tokens = 0
    for idx in indices:
        node = node_list[idx]
        node_tokens = len(tokenizer.encode(node.text))
        if total_tokens + node_tokens > max_tokens:
            continue
        selected_nodes.append(node)
        scores[node.index] = 1.0 - float(distances[idx])
        total_tokens += node_tokens
        if len(selected_nodes) >= top_k:
            break

    return RetrievalResult(
        method=method,
        query=query,
        context=get_text(selected_nodes),
        nodes=_materialize_nodes(tree, selected_nodes, scores, tokenizer),
        elapsed_seconds=time.time() - started_at,
    )


def retrieve_traverse_tree(
    tree: Tree,
    query: str,
    embedding_model,
    context_embedding_model: str,
    tokenizer,
    top_k: int = 5,
    start_layer: Optional[int] = None,
    num_layers: Optional[int] = None,
    max_tokens: int = 2000,
) -> RetrievalResult:
    started_at = time.time()
    query_embedding = embedding_model.create_embedding(query)
    start_layer = tree.num_layers if start_layer is None else start_layer
    num_layers = start_layer + 1 if num_layers is None else num_layers

    if num_layers > start_layer + 1:
        raise ValueError("num_layers must be less than or equal to start_layer + 1")

    current_nodes = tree.layer_to_nodes[start_layer]
    selected_nodes = []
    selected_ids: Set[int] = set()
    scores = {}
    total_tokens = 0

    for layer_offset in range(num_layers):
        embeddings = get_embeddings(current_nodes, context_embedding_model)
        distances = distances_from_embeddings(query_embedding, embeddings)
        indices = indices_of_nearest_neighbors_from_distances(distances)
        best_indices = list(indices[:top_k])
        nodes_to_follow = [current_nodes[idx] for idx in best_indices]

        for idx, node in zip(best_indices, nodes_to_follow):
            if node.index in selected_ids:
                continue
            scores[node.index] = 1.0 - float(distances[idx])
            node_tokens = len(tokenizer.encode(node.text))
            if total_tokens + node_tokens <= max_tokens:
                selected_nodes.append(node)
                selected_ids.add(node.index)
                total_tokens += node_tokens

        if layer_offset == num_layers - 1:
            break

        child_indices = []
        for node in nodes_to_follow:
            child_indices.extend(sorted(node.children))
        child_indices = list(dict.fromkeys(child_indices))
        current_nodes = [tree.all_nodes[index] for index in child_indices]
        if not current_nodes:
            break

    return RetrievalResult(
        method="traverse_tree",
        query=query,
        context=get_text(selected_nodes),
        nodes=_materialize_nodes(tree, selected_nodes, scores, tokenizer),
        elapsed_seconds=time.time() - started_at,
    )
