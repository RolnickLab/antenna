from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio.session import AsyncSession
from starlette.responses import Response

from app.deps.db import get_async_session
from app.deps.request_params import parse_react_admin_params
from app.deps.users import current_user
from app.models.deployment import Deployment
from app.models.user import User
from app.schemas.deployment import Deployment as DeploymentSchema
from app.schemas.deployment import DeploymentCreate, DeploymentUpdate
from app.schemas.request_params import RequestParams

router = APIRouter(prefix="/deployments")


@router.get("", response_model=List[DeploymentSchema])
async def get_deployments(
    response: Response,
    session: AsyncSession = Depends(get_async_session),
    request_params: RequestParams = Depends(parse_react_admin_params(Deployment)),
) -> Any:
    total = await session.scalar(
        select(func.count(Deployment.id))
    )
    deployments = (
        (
            await session.execute(
                select(Deployment)
                .offset(request_params.skip)
                .limit(request_params.limit)
                .order_by(request_params.order_by)
            )
        )
        .scalars()
        .all()
    )
    response.headers[
        "Content-Range"
    ] = f"{request_params.skip}-{request_params.skip + len(deployments)}/{total}"
    return deployments


@router.post("", response_model=DeploymentSchema, status_code=201)
async def create_deployment(
    deployment_in: DeploymentCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_user),
) -> Any:
    deployment = Deployment(**deployment_in.dict())
    session.add(deployment)
    await session.commit()
    return deployment


@router.put("/{deployment_id}", response_model=DeploymentSchema)
async def update_deployment(
    deployment_id: int,
    deployment_in: DeploymentUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_user),
) -> Any:
    deployment: Optional[Deployment] = await session.get(Deployment, deployment_id)
    update_data = deployment_in.dict(exclude_unset=True)
    session.add(deployment)
    await session.commit()
    return deployment


@router.get("/{deployment_id}", response_model=DeploymentSchema)
async def get_deployment(
    deployment_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_user),
) -> Any:
    deployment: Optional[Deployment] = await session.get(Deployment, deployment_id)
    return deployment


@router.delete("/{deployment_id}")
async def delete_deployment(
    deployment_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_user),
) -> Any:
    deployment: Optional[Deployment] = await session.get(Deployment, deployment_id)
    await session.delete(deployment)
    await session.commit()
    return {"success": True}
