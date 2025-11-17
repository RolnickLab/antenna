from typing import get_args

from api.schemas import PipelineChoice

if __name__ == "__main__":
    pipeline_names = get_args(PipelineChoice)
    queue_names = [f"ml-pipeline-{name}" for name in pipeline_names]
    queues = ",".join(queue_names)
    print(queues)
