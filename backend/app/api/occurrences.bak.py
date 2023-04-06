import random
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio.session import AsyncSession
from starlette.responses import Response

from app.deps.db import get_async_session
from app.deps.request_params import parse_react_admin_params
from app.deps.users import current_user

# from app.models.occurrence import Occurrence
from app.models.user import User
from app.schemas.occurrence import test_data
from app.schemas.occurrence import Occurrence
from app.schemas.request_params import RequestParams

router = APIRouter(prefix="/occurrences")


@router.get("", response_model=List[Occurrence])
async def get_occurrences(
    response: Response,
    session: AsyncSession = Depends(get_async_session),
    request_params: RequestParams = Depends(parse_react_admin_params(Occurrence)),
) -> Any:
    occurrences = test_data[
        request_params.skip : request_params.skip + request_params.limit
    ]
    total = len(occurrences)
    response.headers[
        "Content-Range"
    ] = f"{request_params.skip}-{request_params.skip + len(occurrences)}/{total}"
    return occurrences


@router.get("/{occurrence_id}", response_model=Occurrence)
async def get_occurrence(
    occurrence_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_user),
) -> Any:
    occurrence: Optional[Occurrence] = await session.get(Occurrence, occurrence_id)
    if not occurrence or occurrence.user_id != user.id:
        raise HTTPException(404)
    return occurrence
