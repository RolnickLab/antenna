import io
import os

import numpy as np
import requests
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Exists, OuterRef, QuerySet
from PIL import Image

from ami.main.models import Detection, Project, SourceImage


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


def load_and_process_image(source_image: SourceImage) -> np.ndarray:
    image_content = fetch_image_content(source_image.public_url())
    image = Image.open(io.BytesIO(image_content))
    return np.array(image)


def crop_detection(image: np.ndarray, bbox: tuple[int, int, int, int]) -> Image.Image:
    x1, y1, x2, y2 = bbox
    cropped_image = image[int(y1) : int(y2), int(x1) : int(x2)]  # noqa: E203
    return Image.fromarray(cropped_image)


def save_cropped_image(
    cropped_image: Image.Image, project: Project, detection: Detection, source_image: SourceImage
) -> str:
    source_basename = os.path.splitext(os.path.basename(source_image.path))[0]
    image_name = f"{source_basename}_detection_{detection.pk}.jpg"
    iso_day = detection.timestamp.date().isoformat() if detection.timestamp else "unknown_date"
    image_path = f"detections/{project.pk}/{iso_day}/{image_name}"

    img_byte_arr = io.BytesIO()
    cropped_image.save(img_byte_arr, format="JPEG")
    img_byte_arr = img_byte_arr.getvalue()

    return default_storage.save(image_path, ContentFile(img_byte_arr))


def process_source_image(source_image: SourceImage) -> list[str]:
    project = source_image.deployment.project
    image_np = load_and_process_image(source_image)
    processed_paths = []

    for detection in source_image.detections.filter(path__isnull=True):
        if detection.bbox:
            cropped_image = crop_detection(image_np, detection.bbox)
            path = save_cropped_image(cropped_image, project, detection, source_image)
            detection.path = path
            detection.save()
            processed_paths.append(path)

    return processed_paths
