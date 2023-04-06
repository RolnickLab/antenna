from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio.session import AsyncSession
from starlette.responses import Response

from app.deps.db import get_async_session
from app.deps.request_params import parse_react_admin_params
from app.deps.users import current_user
from app.models.occurrence import Occurrence
from app.models.user import User
from app.schemas.occurrence import Occurrence as OccurrenceSchema
from app.schemas.occurrence import OccurrenceCreate, OccurrenceUpdate
from app.schemas.request_params import RequestParams

router = APIRouter(prefix="/occurrences")


@router.get("", response_model=List[OccurrenceSchema])
async def get_occurrences(
    response: Response,
    session: AsyncSession = Depends(get_async_session),
    request_params: RequestParams = Depends(parse_react_admin_params(Occurrence)),
) -> Any:
    total = await session.scalar(
        select(
            func.count(Occurrence.id).filter(
                Occurrence.deployment_id == request_params.deployment_id
            )
        )
    )
    items = (
        (
            await session.execute(
                select(Occurrence)
                .offset(request_params.skip)
                .limit(request_params.limit)
                .order_by(request_params.order_by)
                .filter(Occurrence.deployment_id == request_params.deployment_id)
            )
        )
        .scalars()
        .all()
    )
    response.headers[
        "Content-Range"
    ] = f"{request_params.skip}-{request_params.skip + len(items)}/{total}"
    return items


@router.get("/{item_id}", response_model=OccurrenceSchema)
async def get_occurrence(
    item_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_user),
) -> Any:
    item: Optional[Occurrence] = await session.get(Occurrence, item_id)
    return item


@router.delete("/{item_id}")
async def delete_occurrence(
    item_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_user),
) -> Any:
    item: Optional[Occurrence] = await session.get(Occurrence, item_id)
    await session.delete(item)
    await session.commit()
    return {"success": True}
