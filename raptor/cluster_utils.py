import logging
import math
import random
from abc import ABC, abstractmethod
from typing import List, Optional

try:
    import numpy as np
except ImportError:  # pragma: no cover - depends on local environment
    np = None

try:
    import umap
except ImportError:  # pragma: no cover - depends on local environment
    umap = None

try:
    from sklearn.mixture import GaussianMixture
except ImportError:  # pragma: no cover - depends on local environment
    GaussianMixture = None

# Initialize logging
logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)

from .tree_structures import Node
from .tokenization import get_tokenizer
# Import necessary methods from other modules
from .utils import get_embeddings

# Set a random seed for reproducibility
RANDOM_SEED = 224
random.seed(RANDOM_SEED)


def global_cluster_embeddings(
    embeddings,
    dim: int,
    n_neighbors: Optional[int] = None,
    metric: str = "cosine",
) :
    if np is None or umap is None:
        raise ImportError("numpy and umap-learn are required for RAPTOR_Clustering.")
    if n_neighbors is None:
        n_neighbors = int((len(embeddings) - 1) ** 0.5)
    reduced_embeddings = umap.UMAP(
        n_neighbors=n_neighbors, n_components=dim, metric=metric
    ).fit_transform(embeddings)
    return reduced_embeddings


def local_cluster_embeddings(
    embeddings, dim: int, num_neighbors: int = 10, metric: str = "cosine"
):
    if umap is None:
        raise ImportError("umap-learn is required for RAPTOR_Clustering.")
    reduced_embeddings = umap.UMAP(
        n_neighbors=num_neighbors, n_components=dim, metric=metric
    ).fit_transform(embeddings)
    return reduced_embeddings


def get_optimal_clusters(
    embeddings, max_clusters: int = 50, random_state: int = RANDOM_SEED
) -> int:
    if np is None or GaussianMixture is None:
        raise ImportError("numpy and scikit-learn are required for RAPTOR_Clustering.")
    max_clusters = min(max_clusters, len(embeddings))
    n_clusters = np.arange(1, max_clusters)
    bics = []
    for n in n_clusters:
        gm = GaussianMixture(n_components=n, random_state=random_state)
        gm.fit(embeddings)
        bics.append(gm.bic(embeddings))
    optimal_clusters = n_clusters[np.argmin(bics)]
    return optimal_clusters


def GMM_cluster(embeddings, threshold: float, random_state: int = 0):
    if np is None or GaussianMixture is None:
        raise ImportError("numpy and scikit-learn are required for RAPTOR_Clustering.")
    n_clusters = get_optimal_clusters(embeddings)
    gm = GaussianMixture(n_components=n_clusters, random_state=random_state)
    gm.fit(embeddings)
    probs = gm.predict_proba(embeddings)
    labels = [np.where(prob > threshold)[0] for prob in probs]
    return labels, n_clusters


def perform_clustering(
    embeddings, dim: int, threshold: float, verbose: bool = False
) -> List:
    if np is None:
        raise ImportError("numpy is required for RAPTOR_Clustering.")
    reduced_embeddings_global = global_cluster_embeddings(embeddings, min(dim, len(embeddings) -2))
    global_clusters, n_global_clusters = GMM_cluster(
        reduced_embeddings_global, threshold
    )

    if verbose:
        logging.info(f"Global Clusters: {n_global_clusters}")

    all_local_clusters = [np.array([]) for _ in range(len(embeddings))]
    total_clusters = 0

    for i in range(n_global_clusters):
        global_cluster_embeddings_ = embeddings[
            np.array([i in gc for gc in global_clusters])
        ]
        if verbose:
            logging.info(
                f"Nodes in Global Cluster {i}: {len(global_cluster_embeddings_)}"
            )
        if len(global_cluster_embeddings_) == 0:
            continue
        if len(global_cluster_embeddings_) <= dim + 1:
            local_clusters = [np.array([0]) for _ in global_cluster_embeddings_]
            n_local_clusters = 1
        else:
            reduced_embeddings_local = local_cluster_embeddings(
                global_cluster_embeddings_, dim
            )
            local_clusters, n_local_clusters = GMM_cluster(
                reduced_embeddings_local, threshold
            )

        if verbose:
            logging.info(f"Local Clusters in Global Cluster {i}: {n_local_clusters}")

        for j in range(n_local_clusters):
            local_cluster_embeddings_ = global_cluster_embeddings_[
                np.array([j in lc for lc in local_clusters])
            ]
            indices = np.where(
                (embeddings == local_cluster_embeddings_[:, None]).all(-1)
            )[1]
            for idx in indices:
                all_local_clusters[idx] = np.append(
                    all_local_clusters[idx], j + total_clusters
                )

        total_clusters += n_local_clusters

    if verbose:
        logging.info(f"Total Clusters: {total_clusters}")
    return all_local_clusters


class ClusteringAlgorithm(ABC):
    @abstractmethod
    def perform_clustering(self, embeddings, **kwargs) -> List[List[int]]:
        pass


def _as_float_vector(vector):
    return [float(value) for value in vector]


def _cosine_distance(left, right):
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 1.0
    return 1.0 - dot / (left_norm * right_norm)


def _mean_vector(vectors):
    if not vectors:
        return []
    dimensions = len(vectors[0])
    return [
        sum(vector[dimension] for vector in vectors) / len(vectors)
        for dimension in range(dimensions)
    ]


def _kmeans_labels(embeddings, k, random_state=RANDOM_SEED, max_iter=50):
    if k <= 1:
        return [0 for _ in embeddings]

    rng = random.Random(random_state)
    first_index = rng.randrange(len(embeddings))
    centroids = [embeddings[first_index]]

    while len(centroids) < k:
        scored = [
            (
                min(_cosine_distance(embedding, centroid) for centroid in centroids),
                index,
            )
            for index, embedding in enumerate(embeddings)
        ]
        scored.sort(reverse=True)
        centroids.append(embeddings[scored[0][1]])

    labels = [0 for _ in embeddings]
    for _ in range(max_iter):
        changed = False
        for index, embedding in enumerate(embeddings):
            best_label = min(
                range(k),
                key=lambda label: _cosine_distance(embedding, centroids[label]),
            )
            if labels[index] != best_label:
                labels[index] = best_label
                changed = True

        if not changed:
            break

        for label in range(k):
            members = [
                embedding
                for embedding, member_label in zip(embeddings, labels)
                if member_label == label
            ]
            if members:
                centroids[label] = _mean_vector(members)

    return labels


class HardKMeansClustering(ClusteringAlgorithm):
    @staticmethod
    def perform_clustering(
        nodes: List[Node],
        embedding_model_name: str,
        max_length_in_cluster: int = 3500,
        tokenizer=None,
        target_cluster_size: int = 7,
        random_state: int = RANDOM_SEED,
        max_iter: int = 50,
        **kwargs,
    ) -> List[List[Node]]:
        if not nodes:
            return []

        if tokenizer is None:
            tokenizer = get_tokenizer()

        if target_cluster_size < 1:
            raise ValueError("target_cluster_size must be at least 1")

        if len(nodes) <= target_cluster_size:
            return [nodes]

        embeddings = [
            _as_float_vector(node.embeddings[embedding_model_name]) for node in nodes
        ]
        cluster_count = max(1, math.ceil(len(nodes) / target_cluster_size))
        labels = _kmeans_labels(
            embeddings,
            cluster_count,
            random_state=random_state,
            max_iter=max_iter,
        )

        clusters = [[] for _ in range(cluster_count)]
        for node, label in zip(nodes, labels):
            clusters[label].append(node)

        result = []
        for cluster in clusters:
            if not cluster:
                continue
            token_count = sum(len(tokenizer.encode(node.text)) for node in cluster)
            if token_count > max_length_in_cluster and len(cluster) > 1:
                result.extend(
                    HardKMeansClustering.perform_clustering(
                        cluster,
                        embedding_model_name,
                        max_length_in_cluster=max_length_in_cluster,
                        tokenizer=tokenizer,
                        target_cluster_size=max(1, target_cluster_size // 2),
                        random_state=random_state,
                        max_iter=max_iter,
                    )
                )
            else:
                result.append(cluster)

        return result


class RAPTOR_Clustering(ClusteringAlgorithm):
    def perform_clustering(
        nodes: List[Node],
        embedding_model_name: str,
        max_length_in_cluster: int = 3500,
        tokenizer=None,
        reduction_dimension: int = 10,
        threshold: float = 0.1,
        verbose: bool = False,
    ) -> List[List[Node]]:
        if np is None:
            raise ImportError(
                "numpy, umap-learn, and scikit-learn are required for RAPTOR_Clustering. Use HardKMeansClustering for the patent experiment."
            )
        if tokenizer is None:
            tokenizer = get_tokenizer()
        # Get the embeddings from the nodes
        embeddings = np.array([node.embeddings[embedding_model_name] for node in nodes])

        # Perform the clustering
        clusters = perform_clustering(
            embeddings, dim=reduction_dimension, threshold=threshold
        )

        # Initialize an empty list to store the clusters of nodes
        node_clusters = []

        # Iterate over each unique label in the clusters
        for label in np.unique(np.concatenate(clusters)):
            # Get the indices of the nodes that belong to this cluster
            indices = [i for i, cluster in enumerate(clusters) if label in cluster]

            # Add the corresponding nodes to the node_clusters list
            cluster_nodes = [nodes[i] for i in indices]

            # Base case: if the cluster only has one node, do not attempt to recluster it
            if len(cluster_nodes) == 1:
                node_clusters.append(cluster_nodes)
                continue

            # Calculate the total length of the text in the nodes
            total_length = sum(
                [len(tokenizer.encode(node.text)) for node in cluster_nodes]
            )

            # If the total length exceeds the maximum allowed length, recluster this cluster
            if total_length > max_length_in_cluster:
                if verbose:
                    logging.info(
                        f"reclustering cluster with {len(cluster_nodes)} nodes"
                    )
                node_clusters.extend(
                    RAPTOR_Clustering.perform_clustering(
                        cluster_nodes, embedding_model_name, max_length_in_cluster
                    )
                )
            else:
                node_clusters.append(cluster_nodes)

        return node_clusters
