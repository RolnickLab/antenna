import logging

from ami import ml

logger = logging.getLogger(__name__)


def start_pipeline(
    settings: Settings,
    single: bool = False,
):
    logger.info(f"Local user data path: {settings.user_data_path}")

    ObjectDetector = ml.models.object_detectors[settings.localization_model.value]
    object_detector = ObjectDetector(
        db_path=settings.database_url,
        image_base_path=image_base_path,
        user_data_path=settings.user_data_path,
        batch_size=settings.localization_batch_size,
        num_workers=settings.num_workers,
        single=single,
    )
    if object_detector.queue.queue_count() > 0:
        object_detector.run()
        logger.info("Localization complete")

    BinaryClassifier = ml.models.binary_classifiers[settings.binary_classification_model.value]
    binary_classifier = BinaryClassifier(
        db_path=settings.database_url,
        image_base_path=image_base_path,
        user_data_path=settings.user_data_path,
        batch_size=settings.classification_batch_size,
        num_workers=settings.num_workers,
        single=single,
    )
    if binary_classifier.queue.queue_count() > 0:
        binary_classifier.run()
        logger.info("Binary classification complete")

    SpeciesClassifier = ml.models.species_classifiers[settings.species_classification_model.value]
    species_classifier = SpeciesClassifier(
        db_path=settings.database_url,
        image_base_path=image_base_path,
        user_data_path=settings.user_data_path,
        batch_size=settings.classification_batch_size,
        num_workers=settings.num_workers,
        single=single,
    )
    if species_classifier.queue.queue_count() > 0:
        species_classifier.run()
        logger.info("Species classification complete")

    FeatureExtractor = ml.models.feature_extractors[settings.feature_extractor.value]
    feature_extractor = FeatureExtractor(
        db_path=settings.database_url,
        image_base_path=image_base_path,
        user_data_path=settings.user_data_path,
        batch_size=settings.classification_batch_size,
        num_workers=settings.num_workers,
        single=single,
    )
    feature_extractor.queue.add_unprocessed()
    if feature_extractor.queue.queue_count() > 0:
        feature_extractor.run()
        logger.info("Feature extraction complete")

    # @TODO this should only generate tracks with cnn_features for all detections
    # in a monitoring session. Consider creating or updating a QueueManager
    # instead of the code below.
    # @TODO standardize and clean up this method for find all tracks
    Session = get_session_class(settings.database_url)
    logger.info("Looking for events that need tracking")
    with Session() as session:
        events = ml.models.tracking.get_events_that_need_tracks(
            base_directory=image_base_path,
            session=session,
        )
        for event in events:
            logger.info(f"Calculating tracks in event {event}")
            ml.models.tracking.find_all_tracks(monitoring_session=event, session=session)

        # Debug extra unprocessed objects:
        # from trapdata.ml.models.tracking import UntrackedObjectsQueue
        # queue = UntrackedObjectsQueue(db_path=db_path, base_directory=image_base_path)
        # queue.add_unprocessed()
        # for obj, previous_objects in queue.pull_n_from_queue(100):
        #     print(len(previous_objects), obj)
