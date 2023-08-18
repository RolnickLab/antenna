from ami.main.models import Deployment, S3StorageSource
from config import celery_app

one_day = 60 * 60 * 24
two_days = 60 * 60 * 24 * 2
one_hour = 60 * 60


@celery_app.task(soft_time_limit=two_days, time_limit=two_days + one_hour)
def import_source_images(deployment_id: int) -> int:
    deployment = Deployment.objects.get(id=deployment_id)
    return deployment.import_captures()


@celery_app.task(soft_time_limit=two_days, time_limit=two_days + one_hour)
def calculate_storage_size(storage_source_id: int) -> int:
    storage = S3StorageSource.objects.get(id=storage_source_id)
    return storage.calculate_size()
