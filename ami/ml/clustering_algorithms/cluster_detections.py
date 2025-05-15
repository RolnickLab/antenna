import dataclasses
import logging
import typing

import numpy as np
from django.db.models import Count
from django.utils.timezone import now

from ami.ml.clustering_algorithms.utils import get_clusterer

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job
    from ami.main.models import Classification, Detection, SourceImageCollection
    from ami.ml.models import Algorithm

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


def cluster_detections(
    collection, params: dict, task_logger: logging.Logger = logger, job=None
) -> dict[int, list[ClusterMember]]:
    from ami.jobs.models import JobState
    from ami.main.models import Classification, Detection, TaxaList, Taxon
    from ami.ml.models import Algorithm
    from ami.ml.models.pipeline import create_and_update_occurrences_for_detections

    ood_threshold = params.get("ood_threshold", 1)
    feature_extraction_algorithm = params.get("feature_extraction_algorithm", None)
    algorithm = params.get("clustering_algorithm", "agglomerative")
    task_logger.info(f"Clustering Parameters: {params}")
    job_save(job)
    if feature_extraction_algorithm:
        task_logger.info(f"Feature Extraction Algorithm: {feature_extraction_algorithm}")
        # Check if the feature extraction algorithm is valid
        if not Algorithm.objects.filter(key=feature_extraction_algorithm).exists():
            raise ValueError(f"Invalid feature extraction algorithm key: {feature_extraction_algorithm}")
    else:
        # Fallback to the most used feature extraction algorithm in this collection
        feature_extraction_algorithm = get_most_used_algorithm(collection, task_logger=task_logger)

    detections = Detection.objects.filter(
        classifications__features_2048__isnull=False,
        classifications__algorithm=feature_extraction_algorithm,
        source_image__collections=collection,
        occurrence__determination_ood_score__gt=ood_threshold,
    )

    task_logger.info(f"Found {detections.count()} detections to process for clustering")

    features = []
    valid_detections = []
    valid_classifications = []
    update_job_progress(job, stage_key="feature_collection", status=JobState.STARTED, progress=0.0)
    # Collecting features for detections
    for idx, detection in enumerate(detections):
        classification = detection.classifications.filter(
            features_2048__isnull=False,
            algorithm=feature_extraction_algorithm,
        ).first()
        if classification:
            features.append(classification.features_2048)
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
        raise ValueError("No feature vectors found")

    features_np = np.array(features)
    task_logger.info(f"Feature vectors shape: {features_np.shape}")
    logger.info(f"First feature vector: {features_np[0]}, shape: {features_np[0].shape}")
    update_job_progress(job, stage_key="clustering", status=JobState.STARTED, progress=0.0)
    # Clustering Detections
    ClusteringAlgorithm = get_clusterer(algorithm)
    if not ClusteringAlgorithm:
        raise ValueError(f"Unsupported clustering algorithm: {algorithm}")

    cluster_ids, cluster_scores = ClusteringAlgorithm(params).cluster(features_np)

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
    taxa_list, _created = TaxaList.objects.get_or_create(name=f"Clusters from (Job {job.pk if job else 'unknown'})")
    taxa_list.projects.add(collection.project)
    taxa_to_add = []
    clustering_algorithm, _created = Algorithm.objects.get_or_create(
        name=ClusteringAlgorithm.__name__,
        task_type="clustering",
    )
    logging.info(f"Using clustering algorithm: {clustering_algorithm}")
    # Creating Unknown Taxa
    update_job_progress(job, stage_key="create_unknown_taxa", status=JobState.STARTED, progress=0.0)

    def get_cluster_name(cluster_id: int, taxon: "Taxon | None" = None, job: "Job | None" = None) -> str:
        # if taxon and taxon.rank >= TaxonRank.ORDER:
        #     taxon = None  # don't use in cluster name if "Lepidoptera" or higher

        parts = [
            f"Cluster {cluster_id}",
            f"(Job {job.pk})" if job else "",
            f"{taxon.name}?" if taxon else "",
        ]

        return " ".join(part for part in parts if part)

    for idx, (cluster_id, cluster_members) in enumerate(clusters.items()):
        from ami.main.models import find_common_ancestor_taxon

        predicted_taxa: set[Taxon] = {
            member.classification.taxon for member in cluster_members if member.classification.taxon
        }
        common_taxon = find_common_ancestor_taxon(list(predicted_taxa))
        taxon, _created = Taxon.objects.get_or_create(
            name=get_cluster_name(cluster_id, common_taxon, job=job),
            defaults=dict(
                rank="SPECIES",
                notes=f"Auto-created cluster {cluster_id} for collection {collection.pk}",
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
