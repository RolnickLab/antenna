from typing import get_args

from api.processing import process_pipeline_request as process
from api.schemas import PipelineChoice, PipelineRequest, PipelineResultsResponse
from celery import Celery
from kombu import Exchange, Queue, binding

celery_app = Celery(
    "example_worker",
    broker="amqp://user:password@rabbitmq:5672//",
    backend="redis://redis:6379/0",
)

PIPELINES: list[PipelineChoice] = list(get_args(PipelineChoice))
PIPELINE_EXCHANGE = Exchange("pipeline", type="direct")

celery_app.conf.task_queues = [
    Queue(
        name=pipeline,
        exchange=PIPELINE_EXCHANGE,
        routing_key=pipeline,
        bindings=[binding(PIPELINE_EXCHANGE, routing_key=pipeline)],
    )
    for pipeline in PIPELINES
]

celery_app.conf.update(task_default_exchange="pipeline", task_default_exchange_type="direct")


@celery_app.task(name="process_pipeline_request", soft_time_limit=60 * 4, time_limit=60 * 5)
def process_pipeline_request(pipeline_request: dict) -> dict:
    print(f"Running pipeline on: {pipeline_request}")
    request_data = PipelineRequest(**pipeline_request)
    resp: PipelineResultsResponse = process(request_data)
    return resp.dict()


# Don't really need this? unless we auto-discover tasks if apps use `@celery_app.task` and define __init__.py
celery_app.autodiscover_tasks()
