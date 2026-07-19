from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import GeneratedTab
from app.db.session import get_db
from app.schemas.tabs import GeneratedTabResponse, GeneratedTabSummaryResponse

router = APIRouter()


@router.get("", response_model=list[GeneratedTabSummaryResponse])
def list_generated_tabs(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    db: Session = Depends(get_db),
) -> list[GeneratedTab]:
    try:
        return list(
            db.scalars(
                select(GeneratedTab).order_by(GeneratedTab.created_at.desc()).limit(limit)
            )
        )
    except SQLAlchemyError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is unavailable") from error


@router.get("/{tab_id}", response_model=GeneratedTabResponse)
def get_generated_tab(tab_id: str, db: Session = Depends(get_db)) -> GeneratedTab:
    try:
        tab = db.get(GeneratedTab, tab_id)
    except SQLAlchemyError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is unavailable") from error

    if tab is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated tab was not found")

    return tab

