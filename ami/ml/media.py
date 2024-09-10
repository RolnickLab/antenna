import io
import logging
import os

import numpy as np
import requests
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Exists, OuterRef, QuerySet
from PIL import Image

from ami.main.models import Detection, SourceImage

logger = logging.getLogger(__name__)


def get_source_images_with_missing_detections(
    queryset: QuerySet[SourceImage] | None = None, batch_size: int = 100
) -> QuerySet[SourceImage]:
    if queryset is None:
        queryset = SourceImage.objects.all()

    return queryset.filter(
        Exists(Detection.objects.filter(source_image=OuterRef("pk"), path__isnull=True))
    ).prefetch_related("detections", "deployment__project")[:batch_size]


def fetch_image_content(url: str) -> bytes:
    response = requests.get(url)
    response.raise_for_status()
    return response.content


def load_source_image(source_image: SourceImage) -> np.ndarray:
    url = source_image.public_url(raise_errors=True)
    assert url
    image_content = fetch_image_content(url)
    image = Image.open(io.BytesIO(image_content))
    return np.array(image)


def crop_detection(image: np.ndarray, bbox: tuple[int, int, int, int]) -> Image.Image:
    x1, y1, x2, y2 = bbox
    # Check the bounding box is within the image and has a non-zero area
    if x1 < 0 or y1 < 0 or x2 > image.shape[1] or y2 > image.shape[0]:
        logger.warning(
            f"Bounding box is outside the image. Image shape: {image.shape} Bounding box: {bbox}. "
            "Clamping to image bounds."
        )
        # Set max and min values for x and y
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(image.shape[1], x2)
        y2 = min(image.shape[0], y2)
    if x1 >= x2 or y1 >= y2:
        raise ValueError(f"Bounding box has zero area. Bounding box: {bbox} Width: {x2 - x1} Height: {y2 - y1}")
    cropped_image = image[int(y1) : int(y2), int(x1) : int(x2)]  # noqa: E203
    img = Image.fromarray(cropped_image)
    if not img.getbbox():
        raise ValueError("Cropped image is empty")
    return img


def save_crop(cropped_image: Image.Image, detection: Detection, source_image: SourceImage) -> str:
    source_basename = os.path.splitext(os.path.basename(source_image.path))[0]
    image_name = f"{source_basename}_detection_{detection.pk}.jpg"
    iso_day = detection.timestamp.date().isoformat() if detection.timestamp else "unknown_date"
    assert source_image.project, "Source image must belong to a project"
    image_path = f"detections/{source_image.project.pk}/{iso_day}/{image_name}"

    img_byte_arr = io.BytesIO()
    cropped_image.save(img_byte_arr, format="JPEG")
    img_byte_arr = img_byte_arr.getvalue()

    return default_storage.save(image_path, ContentFile(img_byte_arr))


def create_detection_crops_from_source_image(source_image: SourceImage) -> list[str]:
    image_np = load_source_image(source_image)
    processed_paths = []

    for detection in source_image.detections.filter(path__isnull=True):
        if detection.bbox:
            cropped_image = crop_detection(image_np, detection.bbox)
            path = save_crop(cropped_image, detection, source_image)
            detection.path = path
            detection.save()
            processed_paths.append(path)

    return processed_paths
