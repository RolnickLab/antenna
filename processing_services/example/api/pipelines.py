import datetime
import math
import random

from . import algorithms
from .schemas import (
    AlgorithmConfigResponse,
    AlgorithmReference,
    BoundingBox,
    ClassificationResponse,
    DetectionResponse,
    PipelineConfigResponse,
    SourceImage,
)


def make_random_bbox(source_image_width: int, source_image_height: int):
    # Make a random box.
    # Ensure that the box is within the image bounds and the bottom right corner is greater than the
    # top left corner.
    x1 = random.randint(0, source_image_width)
    x2 = random.randint(0, source_image_width)
    y1 = random.randint(0, source_image_height)
    y2 = random.randint(0, source_image_height)

    return BoundingBox(
        x1=min(x1, x2),
        y1=min(y1, y2),
        x2=max(x1, x2),
        y2=max(y1, y2),
    )


def generate_adaptive_grid_bounding_boxes(image_width: int, image_height: int, num_boxes: int) -> list[BoundingBox]:
    # Estimate grid size based on num_boxes
    grid_size: int = math.ceil(math.sqrt(num_boxes))

    cell_width: float = image_width / grid_size
    cell_height: float = image_height / grid_size

    boxes: list[BoundingBox] = []

    for _ in range(num_boxes):
        # Select a random cell
        row: int = random.randint(0, grid_size - 1)
        col: int = random.randint(0, grid_size - 1)

        # Calculate the cell's boundaries
        cell_x1: float = col * cell_width
        cell_y1: float = row * cell_height

        # Generate a random box within the cell
        # Ensure the box is between 50% and 100% of the cell size
        box_width: float = random.uniform(cell_width * 0.5, cell_width)
        box_height: float = random.uniform(cell_height * 0.5, cell_height)

        x1: float = cell_x1 + random.uniform(0, cell_width - box_width)
        y1: float = cell_y1 + random.uniform(0, cell_height - box_height)
        x2: float = x1 + box_width
        y2: float = y1 + box_height

        boxes.append(BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2))

    return boxes


def make_random_prediction(
    algorithm: AlgorithmConfigResponse,
    terminal: bool = True,
    max_labels: int = 2,
) -> ClassificationResponse:
    assert algorithm.category_map is not None
    category_labels = algorithm.category_map.labels
    logits = [random.random() for _ in category_labels]
    softmax = [math.exp(logit) / sum([math.exp(logit) for logit in logits]) for logit in logits]
    top_class = category_labels[softmax.index(max(softmax))]
    return ClassificationResponse(
        classification=top_class,
        labels=category_labels if len(category_labels) <= max_labels else None,
        scores=softmax,
        logits=logits,
        timestamp=datetime.datetime.now(),
        algorithm=AlgorithmReference(name=algorithm.name, key=algorithm.key),
        terminal=terminal,
    )


def make_random_detections(source_image: SourceImage, num_detections: int = 10):
    source_image.open(raise_exception=True)
    assert source_image.width is not None and source_image.height is not None
    bboxes = generate_adaptive_grid_bounding_boxes(source_image.width, source_image.height, num_detections)
    timestamp = datetime.datetime.now()

    return [
        DetectionResponse(
            source_image_id=source_image.id,
            bbox=bbox,
            timestamp=timestamp,
            algorithm=AlgorithmReference(
                name=algorithms.RANDOM_DETECTOR.name,
                key=algorithms.RANDOM_DETECTOR.key,
            ),
            classifications=[
                make_random_prediction(
                    algorithm=algorithms.RANDOM_BINARY_CLASSIFIER,
                    terminal=False,
                ),
                make_random_prediction(
                    algorithm=algorithms.RANDOM_SPECIES_CLASSIFIER,
                    terminal=True,
                ),
            ],
        )
        for bbox in bboxes
    ]


def make_constant_detections(source_image: SourceImage, num_detections: int = 10):
    source_image.open(raise_exception=True)
    assert source_image.width is not None and source_image.height is not None

    # Define a fixed bounding box size and position relative to image size
    box_width, box_height = source_image.width // 4, source_image.height // 4
    start_x, start_y = source_image.width // 8, source_image.height // 8
    bboxes = [BoundingBox(x1=start_x, y1=start_y, x2=start_x + box_width, y2=start_y + box_height)]
    timestamp = datetime.datetime.now()

    assert algorithms.CONSTANT_CLASSIFIER.category_map is not None
    labels = algorithms.CONSTANT_CLASSIFIER.category_map.labels

    return [
        DetectionResponse(
            source_image_id=source_image.id,
            bbox=bbox,
            timestamp=timestamp,
            algorithm=AlgorithmReference(name=algorithms.CONSTANT_DETECTOR.name, key=algorithms.CONSTANT_DETECTOR.key),
            classifications=[
                ClassificationResponse(
                    classification=labels[0],
                    labels=labels,
                    scores=[0.9],  # Constant score for each detection
                    timestamp=timestamp,
                    algorithm=AlgorithmReference(
                        name=algorithms.CONSTANT_CLASSIFIER.name, key=algorithms.CONSTANT_CLASSIFIER.key
                    ),
                )
            ],
        )
        for bbox in bboxes
    ]


class Pipeline:
    source_images: list[SourceImage]

    def __init__(self, source_images: list[SourceImage]):
        self.source_images = source_images

    def run(self) -> list[DetectionResponse]:
        raise NotImplementedError("Subclasses must implement the run method")

    config = PipelineConfigResponse(
        name="Base Pipeline",
        slug="base",
        description="A base class for all pipelines.",
        version=1,
        algorithms=[],
    )


class RandomPipeline(Pipeline):
    """
    A pipeline that returns detections in random positions within the image bounds with random classifications.
    """

    def run(self) -> list[DetectionResponse]:
        results = [make_random_detections(source_image) for source_image in self.source_images]
        # Flatten the list of lists
        return [item for sublist in results for item in sublist]

    config = PipelineConfigResponse(
        name="Random Pipeline",
        slug="random",
        description=(
            "A pipeline that returns detections in random positions within the image bounds "
            "with random classifications."
        ),
        version=1,
        algorithms=[
            algorithms.RANDOM_DETECTOR,
            algorithms.RANDOM_BINARY_CLASSIFIER,
            algorithms.RANDOM_SPECIES_CLASSIFIER,
        ],
    )


class ConstantPipeline(Pipeline):
    """
    A pipeline that always returns a detection in the same position with a fixed classification.
    """

    def run(self) -> list[DetectionResponse]:
        results = [make_constant_detections(source_image) for source_image in self.source_images]
        # Flatten the list of lists
        return [item for sublist in results for item in sublist]

    config = PipelineConfigResponse(
        name="Constant Pipeline",
        slug="constant",
        description="A pipeline that always returns a detection in the same position with a fixed classification.",
        version=1,
        algorithms=[
            algorithms.CONSTANT_DETECTOR,
            algorithms.CONSTANT_CLASSIFIER,
        ],
    )
