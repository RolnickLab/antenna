from fastapi import APIRouter

from app.api import deployments, occurrences, items, users, utils

api_router = APIRouter()

api_router.include_router(utils.router, tags=["utils"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(items.router, tags=["items"])
api_router.include_router(occurrences.router, tags=["occurrences"])
api_router.include_router(deployments.router, tags=["deployments"])
