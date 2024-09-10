from django.core.management.base import BaseCommand
from tqdm import tqdm

from ami.main.models import SourceImage
from ami.ml.media import create_detection_crops_from_source_image, get_source_images_with_missing_detections


class Command(BaseCommand):
    help = "Create crops for detections with missing paths"

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, help="Project ID to process")
        parser.add_argument("--batch-size", type=int, default=100, help="Batch size for processing")

    def handle(self, *args, **options):
        project_id = options["project"]
        batch_size = options["batch_size"]

        queryset = SourceImage.objects.all()
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        total_images = get_source_images_with_missing_detections(queryset).count()
        self.stdout.write(f"Found {total_images} source images with missing detection crops")

        processed_images = 0
        processed_detections = 0
        errors: list[tuple[SourceImage, str]] = []

        with tqdm(total=total_images, desc="Processing images", unit="img") as pbar:
            while True:
                # Exclude images that have known errors
                queryset = queryset.exclude(id__in=[source_image.pk for source_image, _ in errors])
                batch = get_source_images_with_missing_detections(queryset, batch_size)
                if not batch:
                    break

                for source_image in batch:
                    try:
                        processed_paths = create_detection_crops_from_source_image(source_image)
                        processed_detections += len(processed_paths)
                        processed_images += 1
                    except Exception as e:
                        error_message = (
                            f"Error processing image {source_image} from project '{source_image.project}': {str(e)}"
                        )
                        self.stderr.write(error_message)
                        errors.append((source_image, error_message))
                    finally:
                        pbar.update(1)

                self.stdout.write(
                    f"Processed {processed_images}/{total_images} images, {processed_detections} detections"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed {processed_images} images and {processed_detections} detections"
            )
        )

        if errors:
            self.stdout.write(self.style.WARNING(f"Encountered {len(errors)} errors:"))
            for source_image, error_message in errors:
                self.stdout.write(f"  - {error_message}")
