import dataclasses
import logging
import typing

# import cv2
import numpy as np
from django.db.models import Count
from django.utils.timezone import now

from ami.ml.clustering_algorithms.utils import get_clusterer
from ami.ml.utils import get_image

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job
    from ami.main.models import Classification, Detection, SourceImageCollection, Taxon
    from ami.ml.models import Algorithm

import cv2
from transformers import pipeline

logger = logging.getLogger(__name__)


def update_job_progress(job, stage_key, status, progress):
    if job:
        job.progress.update_stage(stage_key, status=status, progress=progress)
        job.save()


def job_save(job):
    if job:
        job.save()


def get_most_used_algorithm(
    collection: "SourceImageCollection", task_logger: logging.Logger | None = None
) -> "Algorithm | None":
    from ami.main.models import Classification
    from ami.ml.models import Algorithm

    task_logger = task_logger or logger

    qs = Classification.objects.filter(
        features_2048__isnull=False,
        detection__source_image__collections=collection,
        algorithm__isnull=False,
        # @TODO if we have a dedicated task type for feature extraction, we can filter by that
        # task_type="feature_extraction",
    ).exclude(
        algorithm__task_type="clustering",
    )

    # Log the number of classifications per algorithm, if debug is enabled
    if task_logger.isEnabledFor(logging.DEBUG):
        algorithm_stats = qs.values("algorithm__pk", "algorithm__name").annotate(count=Count("id")).order_by("-count")
        task_logger.debug(f"Algorithm stats: {algorithm_stats}")

    feature_extraction_algorithm_id = (
        qs.values("algorithm")
        .annotate(count=Count("id"))
        .order_by("-count")
        .values_list("algorithm", flat=True)
        .first()
    )
    if feature_extraction_algorithm_id:
        algorithm = Algorithm.objects.get(pk=feature_extraction_algorithm_id)
        task_logger.info(f"Using feature extraction algorithm: {algorithm.name}")
        return algorithm
    return None


@dataclasses.dataclass
class ClusterMember:
    cluster_id: int
    detection: "Detection"
    classification: "Classification"
    score: float
    features: np.ndarray


def get_cluster_name(cluster_id: int, taxon: "Taxon | None" = None, job: "Job | None" = None) -> str:
    # if taxon and taxon.rank >= TaxonRank.ORDER:
    #     taxon = None  # don't use in cluster name if "Lepidoptera" or higher

    parts = [
        f"Cluster {cluster_id}",
        f"(Job {job.pk})" if job else "",
        f"{taxon.name}?" if taxon else "",
    ]

    return " ".join(part for part in parts if part)


def remove_detection_on_edge(detection):
    bbox = detection.bbox
    img_width, img_height = detection.source_image.width, detection.source_image.height

    # left
    if bbox[0] < 1:
        return True

    # top
    if bbox[1] < 1:
        return True

    # right
    if bbox[2] > img_width - 2:
        return True

    if bbox[3] > img_height - 2:
        return True

    return False


def get_relative_size(detection: "Detection"):
    bbox_width, bbox_height = detection.width(), detection.height()
    img_width, img_height = detection.source_image.width, detection.source_image.height
    detection.source_image.deployment
    assert img_width and img_height
    relative_size = (bbox_width * bbox_height) / (img_width * img_height)
    return relative_size


def compute_sharpness(detection: "Detection", task_logger: logging.Logger | None = None) -> float | None:
    image_url = detection.url()
    task_logger = task_logger or logger
    assert image_url, "Detection must have a valid image URL"
    try:
        image = get_image(image_url)
    except Exception as e:
        task_logger.warning(
            f"Could not compute sharpness. Failed to load data image for detection {detection.pk}: {e}"
        )
        return None
    image_array = np.array(image, dtype=np.float32)

    # Define Laplacian kernel
    kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)

    padded = np.pad(image_array, pad_width=1, mode="reflect")
    laplacian = np.zeros_like(image_array)

    for i in range(image_array.shape[0]):
        for j in range(image_array.shape[1]):
            region = padded[i : i + 3, j : j + 3]
            laplacian[i, j] = np.sum(region * kernel)

    laplacian_std = np.std(laplacian)

    return laplacian_std


def preprocessing_binary_mask(binary_mask):
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    binary_clean = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel)
    binary_clean = cv2.morphologyEx(binary_clean, cv2.MORPH_CLOSE, kernel)

    return binary_clean


def get_connected_component_mask(binary_mask: np.ndarray, min_area_threshold: int =20) -> int:
    binary_mask = (binary_mask > 0).astype(np.int8)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary_mask, connectivity=8)

    min_area = min_area_threshold
    num_components = 0
    for i in range(1, num_labels):  # Skip label 0 (background)
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= min_area:
            num_components += 1

    return num_components

def segment_by_threshold(depth_map: np.ndarray, min_area_threshold: int) -> int:
    depth_normalized = cv2.normalize(depth_map, None, 0, 255, cv2.NORM_MINMAX)
    depth_uint8 = depth_normalized.astype(np.uint8)

    num_components = []

    threshold_list = [120, 180, 200]

    for i, intensity_threshold in enumerate(threshold_list):
        _, binary_mask = cv2.threshold(depth_uint8, thresh=intensity_threshold, maxval=255, type=cv2.THRESH_BINARY)
        binary_clean = preprocessing_binary_mask(binary_mask)
        num_comp = get_connected_component_mask(binary_clean, min_area_threshold=min_area_threshold)
        num_components.append(num_comp)

    return np.array(num_components).max()

def count_objects_in_bbox(detection: "Detection", pipe, task_logger: logging.Logger | None = None) -> int | None:
    image_url = detection.url()
    task_logger = task_logger or logger
    assert image_url, "Detection must have a valid image URL"
    try:
        image = get_image(image_url)
    except Exception as e:
        task_logger.warning(
            f"Could not count objects in this detection. Failed to load data image for detection {detection.pk}: {e}"
        )
        return None

    depth = pipe(image)["depth"]
    depth_map = np.asarray(depth)
    min_area_threshold = 10
    num_components = segment_by_threshold(depth_map, min_area_threshold)

    return num_components



def cluster_detections(
    collection, params: dict, task_logger: logging.Logger = logger, filter_by_critera=True, job=None
) -> dict[int, list[ClusterMember]]:
    from ami.jobs.models import JobState
    from ami.main.models import Classification, Detection, TaxaList, Taxon
    from ami.ml.models import Algorithm
    from ami.ml.models.pipeline import create_and_update_occurrences_for_detections

    sharpness_threshold = params.get("sharpness_threshold", 8)
    relative_size_threshold = params.get("relative_size_threshold", 0.0015)

    ood_threshold = params.get("ood_threshold", 1)
    feature_extraction_algorithm = params.get("feature_extraction_algorithm", None)
    algorithm = params.get("clustering_algorithm", "agglomerative")
    task_logger.info(f"Clustering Parameters: {params}")
    job_save(job)
    if feature_extraction_algorithm:
        # Check if the feature extraction algorithm is valid
        if not Algorithm.objects.filter(key=feature_extraction_algorithm).exists():
            raise ValueError(f"Invalid feature extraction algorithm key: {feature_extraction_algorithm}")
    else:
        # Fallback to the most used feature extraction algorithm in this collection
        feature_extraction_algorithm = get_most_used_algorithm(collection, task_logger=task_logger)
    task_logger.info(f"Feature Extraction Algorithm: {feature_extraction_algorithm}")
    if not feature_extraction_algorithm:
        raise ValueError("No feature extraction algorithm found for detections in collection.")

    detections = Detection.objects.filter(
        classifications__features_2048__isnull=False,
        classifications__algorithm=feature_extraction_algorithm,
        source_image__collections=collection,
        occurrence__determination_ood_score__gt=ood_threshold,
    )

    task_logger.info(f"Found {detections.count()} detections to process for clustering")

    features = []
    sizes = []
    valid_detections = []
    valid_classifications = []
    update_job_progress(job, stage_key="feature_collection", status=JobState.STARTED, progress=0.0)

    # Collecting features for detections

    depth_pipe = pipeline(task="depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf")

    for idx, detection in enumerate(detections):
        classification = detection.classifications.filter(
            features_2048__isnull=False,
            algorithm=feature_extraction_algorithm,
        ).first()

        if classification:
            relative_size = get_relative_size(detection)

            if filter_by_critera:
                if remove_detection_on_edge(detection):  # remove crops that are on the edge
                    task_logger.info(f"Removing detection {detection.pk} on edge")
                    continue

                if relative_size < relative_size_threshold:  # remove small crops
                    task_logger.info(f"Removing detection {detection.pk} with relative size {relative_size}")
                    continue

                sharpness = compute_sharpness(detection)  # remove blurry images
                if sharpness is not None and sharpness < sharpness_threshold:
                    task_logger.info(f"Removing detection {detection.pk} with sharpness {sharpness}")
                    continue


                num_objects = count_objects_in_bbox(detection, depth_pipe)

                if num_objects is not None and num_objects > 1: # remove bbox with multi objects
                    continue

            features.append(classification.features_2048)
            sizes.append(relative_size)
            valid_detections.append(detection)
            valid_classifications.append(classification)
        update_job_progress(
            job,
            stage_key="feature_collection",
            status=JobState.STARTED,
            progress=(idx + 1) / detections.count(),
        )
    update_job_progress(job, stage_key="feature_collection", status=JobState.SUCCESS, progress=1.0)
    logger.info(f"Clustering {len(features)} features from {len(valid_detections)} detections")

    if not features:
        raise ValueError(
            "No feature vectors found. All detections were filtered out based on the criteria, "
            "or they are missing features."
        )

    features_np = np.array(features)
    size_np = np.array(sizes)
    task_logger.info(f"Feature vectors shape: {features_np.shape}")
    logger.info(f"First feature vector: {features_np[0]}, shape: {features_np[0].shape}")
    update_job_progress(job, stage_key="clustering", status=JobState.STARTED, progress=0.0)
    # Clustering Detections
    ClusteringAlgorithm = get_clusterer(algorithm)
    if not ClusteringAlgorithm:
        raise ValueError(f"Unsupported clustering algorithm: {algorithm}")

    cluster_ids, cluster_scores = ClusteringAlgorithm(params).cluster(features_np, size_np)  # TODO: change this

    task_logger.info(f"Clustering completed with {len(set(cluster_ids))} clusters")
    clusters: dict[int, list[ClusterMember]] = {}
    for idx, (cluster_id, score, member_features, detection, classification) in enumerate(
        zip(cluster_ids, cluster_scores, features, valid_detections, valid_classifications)
    ):
        cluster_member = ClusterMember(
            cluster_id=cluster_id,
            detection=detection,
            classification=classification,
            score=score,
            features=member_features,
        )
        clusters.setdefault(cluster_id, []).append(cluster_member)
        update_job_progress(
            job,
            stage_key="clustering",
            status=JobState.STARTED,
            progress=(idx + 1) / len(valid_detections),
        )
    update_job_progress(job, stage_key="clustering", status=JobState.SUCCESS, progress=1.0)
    taxa_list, _created = TaxaList.objects.get_or_create(name=f"Clusters (Job {job.pk if job else 'unknown'})")
    taxa_list.projects.add(collection.project)
    taxa_to_add = []
    clustering_algorithm, _created = Algorithm.objects.get_or_create(
        name=ClusteringAlgorithm.__name__,
        task_type="clustering",
    )
    logging.info(f"Using clustering algorithm: {clustering_algorithm}")
    # Creating Unknown Taxa
    update_job_progress(job, stage_key="create_unknown_taxa", status=JobState.STARTED, progress=0.0)

    for idx, (cluster_id, cluster_members) in enumerate(clusters.items()):
        from ami.main.models import find_common_ancestor_taxon

        predicted_taxa: set[Taxon] = {
            member.classification.taxon for member in cluster_members if member.classification.taxon
        }
        common_taxon = find_common_ancestor_taxon(list(predicted_taxa))
        taxon, _created = Taxon.objects.get_or_create(
            name=get_cluster_name(cluster_id=cluster_id, job=job),
            defaults=dict(
                rank="SPECIES",
                notes=(
                    f"Auto-created taxon representing cluster {cluster_id}, "
                    "created by {job.pk if job else 'an unknown process'} "
                    f"from {len(cluster_members)} detections in collection {collection.pk}."
                    "Feature vector was from "
                    f"{feature_extraction_algorithm.name if feature_extraction_algorithm else 'unknown algorithm'}."
                    f" Common ancestor: {common_taxon.name if common_taxon else 'None'}"
                ),
                unknown_species=True,
                parent=common_taxon or None,
            ),
        )
        taxon.projects.add(collection.project)
        taxa_to_add.append(taxon)

        for idx, cluster_member in enumerate(cluster_members):
            # Create a new Classification linking the detection to the new taxon

            Classification.objects.create(
                detection=cluster_member.detection,
                taxon=taxon,
                algorithm=clustering_algorithm,
                score=cluster_member.score,
                timestamp=now(),
                logits=None,
                # @TODO it would be nice to copy features here, but right now it confuses the queries
                # when selecting detections & classifications for clustering
                scores=None,
                terminal=True,
                category_map=None,
            )
        update_job_progress(
            job,
            stage_key="create_unknown_taxa",
            status=JobState.STARTED,
            progress=(idx + 1) / len(clusters),
        )
    taxa_list.taxa.add(*taxa_to_add)
    task_logger.info(f"Created {len(clusters)} clusters and updated {len(valid_detections)} detections")
    update_job_progress(job, stage_key="create_unknown_taxa", status=JobState.SUCCESS, progress=1.0)

    # Updating Occurrences
    create_and_update_occurrences_for_detections(detections=valid_detections, logger=task_logger)
    job_save(job)
    return clusters
