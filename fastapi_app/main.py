from __future__ import annotations

import base64
import hmac
import json
import mimetypes
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from common.config import get_settings
from common.db import get_engine
from common.schemas import MarketRecord, OrderBookLevel

settings = get_settings()
app = FastAPI(
    title="DadeKavan-PD-X API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect",
)


async def require_api_key(api_key: str | None = Header(default=None, alias=settings.api_key_header)) -> None:
    if api_key is None or not hmac.compare_digest(api_key, settings.api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class UserProfileResponse(CamelModel):
    userId: int
    username: str
    firstName: str
    lastName: str
    email: str
    userLevel: str | None
    isActive: bool
    isStaff: bool


class UserPhotoResponse(CamelModel):
    userId: int
    contentType: str
    photoBase64: str


def _market_record(row) -> MarketRecord:
    book = row["book"]
    if isinstance(book, (str, bytes, bytearray)):
        book = json.loads(book)
    return MarketRecord(
        id=row["id"],
        redis_message_id=row["redisMessageId"],
        instrument_id=row["instrumentId"],
        symbol=row["symbol"],
        asset_type=row["assetType"],
        observed_at=row["observedAt"],
        exchange_time=row["exchangeTime"],
        best_bid_price=row["bestBidPrice"],
        best_bid_quantity=row["bestBidQuantity"],
        best_ask_price=row["bestAskPrice"],
        best_ask_quantity=row["bestAskQuantity"],
        book=[OrderBookLevel.model_validate(item) for item in book],
    )


@app.get("/api/health", dependencies=[Depends(require_api_key)])
async def health() -> dict:
    async with get_engine().connect() as connection:
        await connection.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get(
    "/api/users/get/profile/{userid}",
    response_model=UserProfileResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_user_profile(userid: int) -> UserProfileResponse:
    query = text(
        """
        SELECT u.id AS userId, u.username, u.first_name AS firstName,
               u.last_name AS lastName, u.email, p.userLevel,
               u.is_active AS isActive, u.is_staff AS isStaff
        FROM auth_user AS u
        LEFT JOIN userProfile AS p ON p.userId = u.id
        WHERE u.id = :userid
        """
    )
    async with get_engine().connect() as connection:
        row = (await connection.execute(query, {"userid": userid})).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfileResponse(**row)


@app.get(
    "/api/users/get/photo/{userid}",
    response_model=UserPhotoResponse,
    dependencies=[Depends(require_api_key)],
)
async def get_user_photo(userid: int) -> UserPhotoResponse:
    query = text("SELECT photo FROM userProfile WHERE userId = :userid")
    async with get_engine().connect() as connection:
        photo = (await connection.execute(query, {"userid": userid})).scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="User photo not found")

    root = settings.media_path.resolve()
    path = (root / str(photo)).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="User photo file not found")
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return UserPhotoResponse(userId=userid, contentType=content_type, photoBase64=encoded)


MARKET_SELECT = """
SELECT id, redisMessageId, instrumentId, symbol, assetType, observedAt,
       exchangeTime, bestBidPrice, bestBidQuantity, bestAskPrice,
       bestAskQuantity, book
FROM RTDS
WHERE instrumentId = :instrument_id
"""


@app.get(
    "/api/RTDS/get/current/{id}",
    response_model=MarketRecord,
    dependencies=[Depends(require_api_key)],
)
async def get_current_market_data(id: str) -> MarketRecord:
    query = text(MARKET_SELECT + " ORDER BY observedAt DESC, id DESC LIMIT 1")
    async with get_engine().connect() as connection:
        row = (await connection.execute(query, {"instrument_id": id})).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Instrument data not found")
    return _market_record(row)


@app.get(
    "/api/RTDS/get/historical/{id}",
    response_model=list[MarketRecord],
    dependencies=[Depends(require_api_key)],
)
async def get_historical_market_data(
    id: str,
    limit: int | None = Query(default=None, ge=1, le=100_000),
) -> list[MarketRecord]:
    suffix = " ORDER BY observedAt DESC, id DESC"
    params: dict[str, object] = {"instrument_id": id}
    if limit is not None:
        suffix += " LIMIT :limit"
        params["limit"] = limit
    async with get_engine().connect() as connection:
        rows = (await connection.execute(text(MARKET_SELECT + suffix), params)).mappings().all()
    return [_market_record(row) for row in rows]
