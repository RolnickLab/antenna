import logging

import numpy as np
from django.utils.timezone import now

from ami.ml.clustering_algorithms.utils import get_clusterer

logger = logging.getLogger(__name__)


def update_job_progress(job, stage_key, status, progress):
    if job:
        job.progress.update_stage(stage_key, status=status, progress=progress)
        job.save()


def job_save(job):
    if job:
        job.save()


def cluster_detections(collection, params: dict, task_logger: logging.Logger = logger, job=None):
    from ami.jobs.models import JobState
    from ami.main.models import Classification, Detection, TaxaList, Taxon
    from ami.ml.models import Algorithm
    from ami.ml.models.pipeline import create_and_update_occurrences_for_detections

    ood_threshold = params.get("ood_threshold", 1)
    algorithm = params.get("algorithm", "agglomerative")
    task_logger.info(f"Clustering Parameters: {params}")
    job_save(job)
    detections = Detection.objects.filter(
        classifications__features_2048__isnull=False,
        source_image__collections=collection,
        occurrence__determination_ood_score__gte=ood_threshold,
    )

    task_logger.info(f"Found {detections.count()} detections to process for clustering")

    features = []
    valid_detections = []
    update_job_progress(job, stage_key="feature_collection", status=JobState.STARTED, progress=0.0)
    # Collecting features for detections
    for idx, detection in enumerate(detections):
        classification = detection.classifications.filter(features_2048__isnull=False).first()
        if classification:
            features.append(classification.features_2048)
            valid_detections.append(detection)
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

    update_job_progress(job, stage_key="clustering", status=JobState.STARTED, progress=0.0)
    # Clustering Detections
    ClusteringAlgorithm = get_clusterer(algorithm)
    if not ClusteringAlgorithm:
        raise ValueError(f"Unsupported clustering algorithm: {algorithm}")

    cluster_ids = ClusteringAlgorithm(params).cluster(features_np)

    task_logger.info(f"Clustering completed with {len(set(cluster_ids))} clusters")
    clusters = {}
    for idx, (cluster_id, detection) in enumerate(zip(cluster_ids, valid_detections)):
        clusters.setdefault(cluster_id, []).append(detection)
        update_job_progress(
            job,
            stage_key="clustering",
            status=JobState.STARTED,
            progress=(idx + 1) / len(valid_detections),
        )
    update_job_progress(job, stage_key="clustering", status=JobState.SUCCESS, progress=1.0)
    taxa_list = TaxaList.objects.create(name=f"Clusters from (Job {job.pk if job else 'unknown'})")
    taxa_list.projects.add(collection.project)
    taxa_to_add = []
    clustering_algorithm, _created = Algorithm.objects.get_or_create(
        name=str(ClusteringAlgorithm),
        task_type="clustering",
    )
    logging.info(f"Using clustering algorithm: {clustering_algorithm}")
    # Creating Unknown Taxa
    update_job_progress(job, stage_key="create_unknown_taxa", status=JobState.STARTED, progress=0.0)
    for idx, (cluster_id, cluster_detections) in enumerate(clusters.items()):
        taxon, _created = Taxon.objects.get_or_create(
            name=f"Cluster {cluster_id} (Collection {collection.pk}) (Job {job.pk if job else 'unknown'})",
            rank="SPECIES",
            notes=f"Auto-created cluster {cluster_id} for collection  {collection.pk}",
            unknown_species=True,
        )
        taxon.projects.add(collection.project)
        taxa_to_add.append(taxon)

        for idx, detection in enumerate(cluster_detections):
            # Create a new Classification linking the detection to the new taxon

            Classification.objects.create(
                detection=detection,
                taxon=taxon,
                algorithm=clustering_algorithm,
                score=1.0,
                timestamp=now(),
                logits=None,
                features_2048=None,
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
