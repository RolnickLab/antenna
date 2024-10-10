import datetime
import math
import random

from .schemas import BoundingBox, Classification, Detection, SourceImage


def make_random_bbox(source_image_width: int, source_image_height: int):
    # Make a random box.
    # Ensure that the box is within the image bounds and the bottom right corner is greater than the top left corner.
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


def make_fake_detections(source_image: SourceImage, num_detections: int = 10):
    source_image.open(raise_exception=True)
    assert source_image.width is not None and source_image.height is not None
    bboxes = generate_adaptive_grid_bounding_boxes(source_image.width, source_image.height, num_detections)
    timestamp = datetime.datetime.now()

    return [
        Detection(
            source_image_id=source_image.id,
            bbox=bbox,
            timestamp=timestamp,
            algorithm="Random Detector",
            classifications=[
                Classification(
                    classification="moth",
                    labels=["moth"],
                    scores=[random.random()],
                    timestamp=timestamp,
                    algorithm="Always Moth Classifier",
                )
            ],
        )
        for bbox in bboxes
    ]


class DummyPipeline:
    source_images: list[SourceImage]

    def __init__(self, source_images: list[SourceImage]):
        self.source_images = source_images

    def run(self) -> list[Detection]:
        results = [make_fake_detections(source_image) for source_image in self.source_images]
        # Flatten the list of lists
        return [item for sublist in results for item in sublist]
