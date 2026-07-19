from fastapi import APIRouter
from pydantic import BaseModel

from app.core.settings import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    environment: str


@router.get("", response_model=HealthResponse)
def get_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", environment=settings.app_env)
