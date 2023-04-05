from typing import Any

from pydantic.main import BaseModel


class RequestParams(BaseModel):
    skip: int
    limit: int
    order_by: Any
    deployment_id: int  # @TODO move this to only the endpoints that need it
