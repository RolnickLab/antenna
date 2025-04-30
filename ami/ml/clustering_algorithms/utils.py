from .agglomerative import AgglomerativeClusterer
from .dbscan import DBSCANClusterer
from .kmeans import KMeansClusterer
from .mean_shift import MeanShiftClusterer


def get_clusterer(clustering_algorithm: str):
    clusterers = {
        "kmeans": KMeansClusterer,
        "agglomerative": AgglomerativeClusterer,
        "mean_shift": MeanShiftClusterer,
        "dbscan": DBSCANClusterer,
    }

    return clusterers.get(clustering_algorithm, None)
