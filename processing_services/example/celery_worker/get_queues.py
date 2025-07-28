from typing import get_args

from api.schemas import PipelineChoice

if __name__ == "__main__":
    queues = ",".join(get_args(PipelineChoice))
    print(queues)
