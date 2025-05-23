import logging
import os

import numpy as np
from scipy.spatial.distance import pdist, squareform
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_samples

from .base_clusterer import BaseClusterer
from .preprocessing_features import dimension_reduction, standardize

logger = logging.getLogger(__name__)


def get_distance_threshold(features, labels):
    distance_matrix = squareform(pdist(features))
    intra_cluster_distances = []
    inter_cluster_distances = []
    for i in range(len(features)):
        for j in range(i + 1, len(features)):
            if labels[i] == labels[j]:
                intra_cluster_distances.append(distance_matrix[i, j])
            else:
                inter_cluster_distances.append(distance_matrix[i, j])
    # choose the 95th percentile of intra-cluster distances
    threshold = np.percentile(intra_cluster_distances, 95)
    return threshold


class AgglomerativeClusterer(BaseClusterer):
    def __init__(self, config: dict):
        self.config = config
        self.setup_flag = False
        self.data_dict = None
        # Access from dictionary instead of attribute
        self.distance_threshold = config.get("algorithm_kwargs", {}).get("distance_threshold", 0.5)
        self.n_components = config.get("pca", {}).get("n_components", 384)

    def setup(self, data_dict):
        # estimate the distance threshold
        new_data_dict = {}
        # Get output_dir from dictionary
        save_dir = self.config.get("output_dir")

        if not self.setup_flag:
            for data_type in data_dict:
                new_data_dict[data_type] = {}
                features = data_dict[data_type]["feat_list"]
                # Get n_components from dictionary
                features = dimension_reduction(standardize(features), self.config.get("pca", {}).get("n_components"))
                labels = data_dict[data_type]["label_list"]
                new_data_dict[data_type]["feat_list"] = features
                new_data_dict[data_type]["label_list"] = labels

                np.savez(
                    os.path.join(
                        save_dir,
                        f"{data_type}_processed_pca_{self.config.get('pca', {}).get('n_components')}",
                    ),
                    feat_list=features,
                    label_list=labels,
                )

            self.data_dict = new_data_dict
            self.setup_flag = True

            # Auto-calculate threshold if not provided
            if not self.distance_threshold:
                self.distance_threshold = get_distance_threshold(
                    data_dict["val"]["feat_list"], data_dict["val"]["label_list"]
                )

    def cluster(self, features, rel_sizes) -> tuple[np.ndarray, np.ndarray]:
        logger.info(f"distance threshold: {self.distance_threshold}")
        logger.info("features shape: %s", features.shape)
        logger.info(f"self.n_components: {self.n_components}")
        # Get n_components and linkage from dictionary
        if self.n_components <= min(features.shape[0], features.shape[1]):
            features = dimension_reduction(standardize(features), self.n_components)
        else:
            features = standardize(features)
            logger.info(f"Skipping PCA, n_components { self.n_components} is larger than features shape ")

        # Get linkage parameter from config
        rel_sizes = rel_sizes.reshape(-1, 1)
        rel_sizes = standardize(rel_sizes)
        features = np.concatenate([features, rel_sizes], axis=1)
        linkage = self.config.get("algorithm_kwargs", {}).get("linkage", "ward")
        logger.info(f" features shape after PCA: {features.shape}")

        cluster_ids = AgglomerativeClustering(
            n_clusters=None, distance_threshold=self.distance_threshold, linkage=linkage
        ).fit_predict(features)

        try:
            silhouette_scores = silhouette_samples(features, cluster_ids)
            silhouette_scores = np.asarray(silhouette_scores)
            # Scale from -1 to 1 to 0 to 1
            silhouette_scores = (silhouette_scores + 1) / 2
        except ValueError:
            # If silhouette scores cannot be computed, return an array of zeros
            logger.warning(
                f"Returned {len(cluster_ids)} clusters for {len(features)} features. "
                "Cannot compute silhouette scores so setting them to zero."
            )
            silhouette_scores = np.zeros(features.shape[0], dtype=np.float32)

        return cluster_ids, silhouette_scores
