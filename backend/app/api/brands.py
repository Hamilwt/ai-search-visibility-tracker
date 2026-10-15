from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import BrandOut
from app.db import get_session
from app.models.brand import Brand

router = APIRouter(tags=["brands"])


@router.get("/brands", response_model=list[BrandOut])
async def list_brands(session: AsyncSession = Depends(get_session)) -> list[BrandOut]:
    brands = await session.scalars(select(Brand).order_by(Brand.name))
    return [BrandOut.model_validate(brand) for brand in brands]
