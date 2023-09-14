import datetime
import math
from collections import namedtuple
from collections.abc import Generator, Iterable, Sequence
from typing import Optional, Union

import numpy as np
import PIL.Image
import torch
import torch.utils.data
from sqlalchemy import func, orm, select, update
from torch import nn
from torchvision import transforms
from trapdata import constants, logger
from trapdata.common.schemas import BoundingBox, FilePath
from trapdata.db.models.detections import DetectedObject, save_classified_objects
from trapdata.db.models.events import MonitoringSession
from trapdata.db.models.images import TrapImage
from trapdata.db.models.queue import ObjectsWithoutFeaturesQueue, UntrackedObjectsQueue
from trapdata.ml.models.classification import (
    ClassificationIterableDatabaseDataset,
    MothNonMothClassifier,
    QuebecVermontMothSpeciesClassifierMixedResolution,
)
from trapdata.ml.utils import get_device

# from trapdata.db.models.detections import save_untracked_detection
from .base import InferenceBaseClass


def image_diagonal(width: int, height: int) -> int:
    img_diagonal = int(math.ceil(math.sqrt(width**2 + height**2)))
    return img_diagonal


ItemForTrackingCost = namedtuple("ItemForTrackingCost", "image_data bbox source_image_diagonal")


def l1_normalize(v):
    norm = np.sum(np.array(v))
    return v / norm


def l1_normalize_batch(a: np.ndarray) -> np.ndarray:
    # https://stackoverflow.com/a/8904762
    row_sums = a.sum(axis=1)
    normed = a / row_sums[:, np.newaxis]
    return normed


def cosine_similarity(img1_ftrs: torch.Tensor, img2_ftrs: torch.Tensor) -> float:
    """
    Finds cosine similarity between a pair of cropped images.

    Uses the feature embeddings array computed from a CNN model.
    """

    cosine_sim = np.dot(img1_ftrs, img2_ftrs) / (np.linalg.norm(img1_ftrs) * np.linalg.norm(img2_ftrs))
    assert 0 <= cosine_sim <= 1.000000001, "Cosine similarity score out of bounds"

    return cosine_sim


def iou(bb1: BoundingBox, bb2: BoundingBox) -> float:
    """Finds intersection over union for a bounding box pair"""

    assert bb1[0] < bb1[2], "Issue in bounding box 1 x_annotation"
    assert bb1[1] < bb1[3], "Issue in bounding box 1 y_annotation"
    assert bb2[0] < bb2[2], "Issue in bounding box 2 x_annotation"
    assert bb2[1] < bb2[3], "Issue in bounding box 2 y_annotation"

    bb1_area = (bb1[2] - bb1[0] + 1) * (bb1[3] - bb1[1] + 1)
    bb2_area = (bb2[2] - bb2[0] + 1) * (bb2[3] - bb2[1] + 1)

    x_min = max(bb1[0], bb2[0])
    x_max = min(bb1[2], bb2[2])
    width = max(0, x_max - x_min + 1)

    y_min = max(bb1[1], bb2[1])
    y_max = min(bb1[3], bb2[3])
    height = max(0, y_max - y_min + 1)

    intersec_area = width * height
    union_area = bb1_area + bb2_area - intersec_area

    iou = np.around(intersec_area / union_area, 2)
    assert 0 <= iou <= 1, "IoU out of bounds"

    return iou


def box_ratio(bb1: BoundingBox, bb2: BoundingBox) -> float:
    """Finds the ratio of the two bounding boxes"""

    bb1_area = (bb1[2] - bb1[0] + 1) * (bb1[3] - bb1[1] + 1)
    bb2_area = (bb2[2] - bb2[0] + 1) * (bb2[3] - bb2[1] + 1)

    min_area = min(bb1_area, bb2_area)
    max_area = max(bb1_area, bb2_area)

    box_ratio = min_area / max_area
    assert 0 <= box_ratio <= 1, "box ratio out of bounds"

    return box_ratio


def distance_ratio(bb1: BoundingBox, bb2: BoundingBox, img_diag: float) -> float:
    """finds the distance between the two bounding boxes and normalizes
    by the image diagonal length
    """

    centre_x_bb1 = bb1[0] + (bb1[2] - bb1[0]) / 2
    centre_y_bb1 = bb1[1] + (bb1[3] - bb1[1]) / 2

    centre_x_bb2 = bb2[0] + (bb2[2] - bb2[0]) / 2
    centre_y_bb2 = bb2[1] + (bb2[3] - bb2[1]) / 2

    dist = math.sqrt((centre_x_bb2 - centre_x_bb1) ** 2 + (centre_y_bb2 - centre_y_bb1) ** 2)
    max_dist = img_diag

    assert dist <= max_dist, "distance between bounding boxes more than max distance"

    return dist / max_dist


def total_cost(
    img1_features: Iterable[float],
    img2_features: Iterable[float],
    bb1: BoundingBox,
    bb2: BoundingBox,
    image_diagonal: float,
    w_cnn: float = 1,
    w_iou: float = 1,
    w_box: float = 1,
    w_dis: float = 1,
) -> float:
    """returns the final cost"""

    cnn_cost = 1 - cosine_similarity(img1_features, img2_features)
    iou_cost = 1 - iou(bb1, bb2)
    box_ratio_cost = 1 - box_ratio(bb1, bb2)
    dist_ratio_cost = distance_ratio(bb1, bb2, image_diagonal)

    total_cost = w_cnn * cnn_cost + w_iou * iou_cost + w_box * box_ratio_cost + w_dis * dist_ratio_cost

    return total_cost


class TrackingCostOriginal:
    def __init__(
        self,
        image1: PIL.Image.Image,
        image2: PIL.Image.Image,
        bb1: tuple[int, int, int, int],
        bb2: tuple[int, int, int, int],
        source_image_diagonal: float,
        cnn_source_model,
        cost_weights: tuple[int, int, int, int] = (1, 1, 1, 1),
        cost_threshold=1,
        img_resize=224,
        device=None,
    ):
        """
        Finds tracking cost for a pair of bounding box using cnn features, distance, iou and box ratio
        Author        : Aditya Jain
        Date created  : June 23, 2022

        Args:
        image1       : first moth image
        image2       : second moth image
        bb1          : [x1, y1, x2, y2] The origin is top-left corner; x1<x2; y1<y2; integer values in the list
        bb2          : [x1, y1, x2, y2] The origin is top-left corner; x1<x2; y1<y2; integer values in the list
        weights      : weights assigned to various cost metrics
        model        : trained moth model
        img_diagonal : diagonal length of the image in pixels

        """

        self.image1 = image1
        self.image2 = image2
        self.img_resize = img_resize
        self.device = device or get_device()
        self.total_cost = 0
        self.bb1 = bb1
        self.bb2 = bb2
        self.img_diag = source_image_diagonal
        self.w_cnn = cost_weights[0]
        self.w_iou = cost_weights[1]
        self.w_box = cost_weights[2]
        self.w_dis = cost_weights[3]
        self.model = self._load_model(cnn_source_model)

    def _load_model(self, cnn_source_model):
        # Get the last feature layer of the model
        model = nn.Sequential(*list(cnn_source_model.children())[:-3])

        return model

    def _transform_image(self, image):
        """Transforms the cropped moth images for model prediction"""

        transformer = transforms.Compose(
            [
                transforms.Resize((self.img_resize, self.img_resize)),
                transforms.ToTensor(),
            ]
        )
        image = transformer(image)

        # RGBA image; extra alpha channel
        if image.shape[0] > 3:
            image = image[0:3, :, :]

        # grayscale image; converted to 3 channels r=g=b
        if image.shape[0] == 1:
            to_pil = transforms.ToPILImage()
            to_rgb = transforms.Grayscale(num_output_channels=3)
            to_tensor = transforms.ToTensor()
            image = to_tensor(to_rgb(to_pil(image)))

        return image

    def _l1_normalize(self, v):
        norm = np.sum(np.array(v))
        return v / norm

    def _cosine_similarity(self):
        """Finds cosine similarity for a bounding box pair images"""

        img2_moth = self._transform_image(self.image2)
        img2_moth = torch.unsqueeze(img2_moth, 0).to(self.device)

        img1_moth = self._transform_image(self.image1)
        img1_moth = torch.unsqueeze(img1_moth, 0).to(self.device)

        # getting model features for each image
        with torch.no_grad():
            img2_ftrs = self.model(img2_moth)
            img2_ftrs = img2_ftrs.view(-1, img2_ftrs.size(0)).cpu()
            img2_ftrs = img2_ftrs.reshape((img2_ftrs.shape[0],))
            img2_ftrs = self._l1_normalize(img2_ftrs)

            img1_ftrs = self.model(img1_moth)
            img1_ftrs = img1_ftrs.view(-1, img1_ftrs.size(0)).cpu()
            img1_ftrs = img1_ftrs.reshape((img1_ftrs.shape[0],))
            img1_ftrs = self._l1_normalize(img1_ftrs)

        cosine_sim = np.dot(img1_ftrs, img2_ftrs) / (np.linalg.norm(img1_ftrs) * np.linalg.norm(img2_ftrs))
        assert 0 <= cosine_sim <= 1, "cosine similarity score out of bounds"

        return cosine_sim

    def _iou(self):
        """Finds intersection over union for a bounding box pair"""

        assert self.bb1[0] < self.bb1[2], "Issue in bounding box 1 x_annotation"
        assert self.bb1[1] < self.bb1[3], "Issue in bounding box 1 y_annotation"
        assert self.bb2[0] < self.bb2[2], "Issue in bounding box 2 x_annotation"
        assert self.bb2[1] < self.bb2[3], "Issue in bounding box 2 y_annotation"

        bb1_area = (self.bb1[2] - self.bb1[0] + 1) * (self.bb1[3] - self.bb1[1] + 1)
        bb2_area = (self.bb2[2] - self.bb2[0] + 1) * (self.bb2[3] - self.bb2[1] + 1)

        x_min = max(self.bb1[0], self.bb2[0])
        x_max = min(self.bb1[2], self.bb2[2])
        width = max(0, x_max - x_min + 1)

        y_min = max(self.bb1[1], self.bb2[1])
        y_max = min(self.bb1[3], self.bb2[3])
        height = max(0, y_max - y_min + 1)

        intersec_area = width * height
        union_area = bb1_area + bb2_area - intersec_area

        iou = np.around(intersec_area / union_area, 2)
        assert 0 <= iou <= 1, "IoU out of bounds"

        return iou

    def _box_ratio(self):
        """Finds the ratio of the two bounding boxes"""

        bb1_area = (self.bb1[2] - self.bb1[0] + 1) * (self.bb1[3] - self.bb1[1] + 1)
        bb2_area = (self.bb2[2] - self.bb2[0] + 1) * (self.bb2[3] - self.bb2[1] + 1)

        min_area = min(bb1_area, bb2_area)
        max_area = max(bb1_area, bb2_area)

        box_ratio = min_area / max_area
        assert 0 <= box_ratio <= 1, "box ratio out of bounds"

        return box_ratio

    def _distance_ratio(self):
        """finds the distance between the two bounding boxes and normalizes
        by the image diagonal length
        """

        centre_x_bb1 = self.bb1[0] + (self.bb1[2] - self.bb1[0]) / 2
        centre_y_bb1 = self.bb1[1] + (self.bb1[3] - self.bb1[1]) / 2

        centre_x_bb2 = self.bb2[0] + (self.bb2[2] - self.bb2[0]) / 2
        centre_y_bb2 = self.bb2[1] + (self.bb2[3] - self.bb2[1]) / 2

        dist = math.sqrt((centre_x_bb2 - centre_x_bb1) ** 2 + (centre_y_bb2 - centre_y_bb1) ** 2)
        max_dist = self.img_diag

        assert dist <= max_dist, "distance between bounding boxes more than max distance"

        return dist / max_dist

    def final_cost(self):
        """returns the final cost"""

        cnn_cost = 1 - self._cosine_similarity()
        iou_cost = 1 - self._iou()
        box_ratio_cost = 1 - self._box_ratio()
        dist_ratio_cost = self._distance_ratio()

        self.total_cost = (
            self.w_cnn * cnn_cost + self.w_iou * iou_cost + self.w_box * box_ratio_cost + self.w_dis * dist_ratio_cost
        )

        return self.total_cost


class UntrackedObjectsIterableDatabaseDataset(torch.utils.data.IterableDataset):
    def __init__(
        self,
        queue: UntrackedObjectsQueue,
        image_transforms: transforms.Compose,
        batch_size: int = 4,
    ):
        super().__init__()
        self.queue = queue
        self.image_transforms = image_transforms
        self.batch_size = batch_size

    def __len__(self):
        count = self.queue.queue_count()
        return count

    def __iter__(
        self,
    ) -> Generator[
        tuple[
            torch.Tensor,
            # tuple[
            #     tuple[
            #         torch.Tensor, torch.Tensor, tuple[int]
            #     ],  # Can we make this types? help me out here!
            #     tuple[
            #         torch.Tensor,
            #         torch.Tensor,
            #     ],
            # ],
        ],
        None,
        None,
    ]:
        while len(self):
            worker_info = torch.utils.data.get_worker_info()
            logger.info(f"Using worker: {worker_info}")

            # This should probably be one item, and then all of the objects from the previous frame
            records = self.queue.pull_n_from_queue(self.batch_size)

            # Prepare data for TrackingCost calculator exactly, return in tensor

            if records:
                item_ids = torch.utils.data.default_collate([record.id for record, _ in records])

                image_pairs = []
                for record, comparisons in records:
                    for comparison in comparisons:
                        image_pairs.append(
                            (
                                self.data_for_tracking(record),
                                self.data_for_tracking(comparison),
                            )
                        )

                yield (
                    item_ids,
                    # batch_image_data,
                    # batch_comparison_image_data,
                    # batch_metadata,
                    # batch_comparison_metadata,
                )

    def transform(self, cropped_image) -> torch.Tensor:
        return self.image_transforms(cropped_image)

    def data_for_tracking(self, record: DetectedObject) -> tuple[torch.Tensor, tuple, int]:
        image_data = self.transform(record.cropped_image_data())
        bbox = tuple(record.bbox)
        diagonal = image_diagonal(record.source_image_width, record.source_image_height)
        return image_data, bbox, diagonal

    def collate_pairs():
        pass


class FeatureExtractor(InferenceBaseClass):
    name = "Default Feature Extractor"
    stage = 4
    type = "feature_extractor"
    input_size = 300

    def get_queue(self):
        return ObjectsWithoutFeaturesQueue(self.db_path, self.image_base_path)

    def get_dataset(self):
        dataset = ClassificationIterableDatabaseDataset(
            queue=self.queue,
            image_transforms=self.get_transforms(),
            batch_size=self.batch_size,
        )
        return dataset

    def get_model(self):
        model = super().get_model()
        # Get the last feature layer of the ResNet50 model
        model = nn.Sequential(*list(model.children())[:-1])
        # # Get the last feature layer of the EfficientNet model
        # model = nn.Sequential(*list(model.children())[:-3])
        return model

    def post_process_batch(self, output) -> np.ndarray:
        # output = output.view(-1, output.size(0)).cpu()
        # output = output.reshape((output.shape[0],))
        batch_size = output.shape[0]
        num_features = np.product(output.shape[1:])

        output = output.reshape(batch_size, num_features)
        output = output.cpu().numpy()
        output = l1_normalize_batch(output)
        # logger.debug(f"Post-processing features: {output[0]}")
        return output

    def save_results(self, object_ids, batch_output):
        # Here we are saving the moth/non-moth labels
        data = [
            {
                "cnn_features": features.tolist(),
                # Clear any existing sequence assignment:
                "sequence_id": None,
                "sequence_frame": None,
                "sequence_previous_id": None,
                "sequence_previous_cost": None,
            }
            for features in batch_output
        ]
        save_classified_objects(self.db_path, object_ids, data)


class QuebecVermontFeatureExtractor(FeatureExtractor, QuebecVermontMothSpeciesClassifierMixedResolution):
    name = "Features from Quebec/Vermont species model"


class UKDenmarkFeatureExtractor(FeatureExtractor, QuebecVermontMothSpeciesClassifierMixedResolution):
    name = "Features from UK/Denmark species model"


class MothNonMothFeatureExtractor(FeatureExtractor, MothNonMothClassifier):
    name = "Features from general Moth/Non-Moth model"


def clear_sequences(monitoring_session: MonitoringSession, session: orm.Session):
    logger.info(f"Clearing existing sequences for {monitoring_session.day}")
    stmt = (
        update(DetectedObject)
        .where(DetectedObject.monitoring_session_id == monitoring_session.id)
        .values(
            {
                "sequence_id": None,
                "sequence_frame": None,
                "sequence_previous_id": None,
                "sequence_previous_cost": None,
            }
        )
    )
    session.execute(stmt)
    session.flush()
    session.commit()


def make_sequence_id(date: datetime.date, obj_id: int):
    sequence_id = f"{date.strftime('%Y%m%d')}-SEQ-{obj_id}"
    return sequence_id


def new_sequence(
    obj_current: DetectedObject,
    obj_previous: DetectedObject,
    session: orm.Session,
):
    """
    Create a new sequence ID and assign it to the current & previous detections.
    """
    # obj_current.sequence_id = uuid.uuid4() # @TODO ensure this is unique, or
    sequence_id = make_sequence_id(obj_previous.monitoring_session.day, obj_previous.id)
    obj_previous.sequence_id = sequence_id
    obj_previous.sequence_frame = 0

    obj_current.sequence_id = sequence_id
    obj_current.sequence_frame = 1

    logger.info(f"Created new sequence beginning with obj {obj_previous.id}: {sequence_id}")

    session.add(obj_current)
    session.add(obj_previous)

    return sequence_id


def assign_solo_sequence(
    obj_current: DetectedObject,
    session: orm.Session,
):
    """
    Create a new sequence ID and assign it to the current & previous detections.
    """
    # obj_current.sequence_id = uuid.uuid4() # @TODO ensure this is unique, or
    sequence_id = make_sequence_id(obj_current.monitoring_session.day, obj_current.id)

    obj_current.sequence_id = sequence_id
    obj_current.sequence_frame = 0

    logger.debug(f"Created new single-frame sequence for obj {obj_current.id}: {sequence_id}")

    session.add(obj_current)

    return sequence_id


def assign_solo_sequences(detected_objects: Sequence[DetectedObject], session: orm.Session, commit=True):
    # Check list of objects and assign a solo-sequence if they are missing one.
    for obj in detected_objects:
        if not obj.sequence_id:
            assign_solo_sequence(obj, session=session)

    if commit:
        session.commit()


def assign_sequence(
    obj_current: DetectedObject,
    obj_previous: DetectedObject,
    final_cost: float,
    session: orm.Session,
    commit: bool = True,
):
    """
    Assign a pair of objects to the same sequence.

    Will create a new sequence if necessary. Saves their similarity and order to the database.
    """
    obj_current.sequence_previous_cost = final_cost
    obj_current.sequence_previous_id = obj_previous.id
    if obj_previous.sequence_id:
        obj_current.sequence_id = obj_previous.sequence_id
        obj_current.sequence_frame = obj_previous.sequence_frame + 1
    else:
        new_sequence(obj_current, obj_previous, session=session)

    session.add(obj_current)
    session.add(obj_previous)
    if commit:
        session.flush()
        session.commit()
    return obj_current.sequence_id, obj_current.sequence_frame


def compare_objects(
    image_current: TrapImage,
    session: orm.Session,
    image_previous: TrapImage | None = None,
    skip_existing: bool = False,
    commit: bool = True,
):
    """
    Calculate the similarity (tracking cost) between all objects detected in a pair of images.

    Will assign objects to a sequence if the similarity exceeds the TRACKING_COST_THRESHOLD.
    """
    if not image_previous:
        image_previous = image_current.previous_image(session)

    logger.debug(f"Calculating tracking costs for objects in image {image_current.id}")
    objects_current = (
        session.execute(
            select(DetectedObject)
            .filter(DetectedObject.image == image_current)
            .where(DetectedObject.binary_label == constants.POSITIVE_BINARY_LABEL)
        )
        .unique()
        .scalars()
        .all()
    )

    if image_previous:
        objects_previous = (
            session.execute(
                select(DetectedObject)
                .filter(DetectedObject.image == image_previous)
                .where(DetectedObject.binary_label == constants.POSITIVE_BINARY_LABEL)
            )
            .unique()
            .scalars()
            .all()
        )
    else:
        logger.debug("No previous frame found for image, assigning all current objects a solo-sequence")
        objects_previous = list()

    logger.debug(f"Objects in current frame: {len(objects_current)}, objects in previous: {len(objects_previous)}")

    img_shape = PIL.Image.open(image_current.absolute_path).size

    for obj_current in objects_current:
        if not obj_current.cnn_features:
            logger.warn(f"Object is missing CNN features, can't determine track for object {obj_current.id}")
            break

        if skip_existing and obj_current.sequence_id:
            logger.debug(
                f"Skipping obj {obj_current.id}, already assigned to sequence {obj_current.sequence_id} as frame {obj_current.sequence_frame}"
            )
            continue

        logger.debug(f"Comparing obj {obj_current.id} to all objects in previous frame")
        costs = []
        for obj_previous in objects_previous:
            if not obj_previous.cnn_features:
                logger.warn(
                    f"An object in the previous frame is missing features, can't determine track for object {obj_current.id}"
                )
                break

            final_cost = total_cost(
                obj_current.cnn_features,
                obj_previous.cnn_features,
                bb1=tuple(obj_current.bbox),
                bb2=tuple(obj_previous.bbox),
                image_diagonal=image_diagonal(img_shape[0], img_shape[1]),
            )
            # cost = TrackingCostOriginal(
            #     obj_current.cropped_image_data(),
            #     obj_previous.cropped_image_data(),
            #     tuple(obj_current.bbox),
            #     tuple(obj_previous.bbox),
            #     source_image_diagonal=image_diagonal(img_shape[0], img_shape[1]),
            #     cnn_source_model=cnn_model,
            #     device=device,
            # )
            # final_cost = cost.final_cost()
            logger.debug(f"\tScore for obj {obj_current.id} vs. {obj_previous.id}: {final_cost}")
            costs.append((final_cost, obj_previous))

        costs.sort(key=lambda cost: cost[0])
        if costs:
            lowest_cost, best_match = costs[0]

            if lowest_cost <= constants.TRACKING_COST_THRESHOLD:
                sequence_id, frame_num = assign_sequence(
                    obj_current=obj_current,
                    obj_previous=best_match,
                    final_cost=lowest_cost,
                    session=session,
                    commit=False,
                )
                logger.debug(
                    f"Assigned {obj_current.id} to sequence {sequence_id} as frame #{frame_num}. Tracking cost: {round(lowest_cost, 2)}"
                )

    # Assign a sequence ID for any objects that still don't have one
    assign_solo_sequences(objects_current, session=session, commit=False)

    if commit:
        session.flush()
        session.commit()


def get_events_that_need_tracks(base_directory: FilePath, session: orm.Session) -> Sequence[MonitoringSession]:
    stmt = (
        select(MonitoringSession)
        .join(DetectedObject.monitoring_session)
        .where((DetectedObject.sequence_id.is_(None)) & (MonitoringSession.base_directory == str(base_directory)))
    )
    results = session.execute(stmt).unique().scalars().all()
    return results


def find_all_tracks(
    monitoring_session: MonitoringSession,
    session: orm.Session,
):
    """
    Retrieve all images for an Event / Monitoring Session and find all sequential objects.
    """
    clear_sequences(monitoring_session, session)

    logger.info(f"Calculating tracks for {monitoring_session.day}")

    # The queue is less applicable to tracks, since we are calculating tracks for all objects
    # in the session, but for now... @TODO queue by monitoring session rather than object.
    session.execute(
        update(DetectedObject)
        .where(
            (DetectedObject.monitoring_session == monitoring_session)
            & (DetectedObject.in_queue.is_(True))
            & (DetectedObject.cnn_features.is_not(None))
        )
        .values({"in_queue": False})
    )
    session.commit()

    images = (
        session.execute(
            select(TrapImage).filter(TrapImage.monitoring_session == monitoring_session).order_by(TrapImage.timestamp)
        )
        .unique()
        .scalars()
        .all()
    )
    for i, image in enumerate(images):
        n_current = i
        n_previous = max(n_current - 1, 0)
        image_current = images[n_current]
        image_previous = images[n_previous]
        if image_current == image_previous:
            image_previous = None

        compare_objects(
            image_current=image_current,
            image_previous=image_previous,
            session=session,
            commit=False,
        )
    logger.info("Saving tracks to database")
    session.flush()
    session.commit()


def summarize_tracks(
    session: orm.Session,
    event: MonitoringSession | None = None,
) -> dict[str | None, list[dict]]:
    query_args = {}
    if event:
        query_args = {"monitoring_session": event}

    tracks = session.execute(
        select(
            DetectedObject.monitoring_session_id,
            DetectedObject.sequence_id,
            func.count(DetectedObject.id),
        )
        .where(DetectedObject.sequence_id.is_not(None))
        .group_by(DetectedObject.monitoring_session_id, DetectedObject.sequence_id)
        .filter_by(**query_args)
    ).all()

    sequences = {}
    for ms, sequence_id, count in tracks:
        track_objects = (
            session.execute(
                select(DetectedObject)
                .where(DetectedObject.sequence_id == sequence_id)
                .order_by(DetectedObject.sequence_frame)
            )
            .unique()
            .scalars()
            .all()
        )
        sequences[sequence_id] = [
            dict(
                event=obj.monitoring_session.day,
                sequence=sequence_id,
                frame=obj.sequence_frame,
                image=obj.image_id,
                id=obj.id,
                path=obj.path,
                binary_label=obj.binary_label,
                specific_label=obj.specific_label,
                specific_label_score=obj.specific_label_score,
                cost=obj.sequence_previous_cost,
            )
            for obj in track_objects
        ]

    return sequences
