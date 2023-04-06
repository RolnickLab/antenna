from datetime import datetime

from pydantic import BaseModel, Field
from pydantic.types import PositiveInt


class DeploymentBase(BaseModel):
    name: str

class DeploymentCreate(DeploymentBase):
    pass

class DeploymentUpdate(DeploymentBase):
    pass

class Deployment(DeploymentBase):
    id: PositiveInt
    created: datetime
    updated: datetime

    class Config:
        orm_mode = True
