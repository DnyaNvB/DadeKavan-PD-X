from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class OrderBookLevel(ApiModel):
    level: int = Field(ge=1, le=10)
    bid_price: int | None = Field(default=None, ge=0)
    bid_quantity: int | None = Field(default=None, ge=0)
    bid_orders: int | None = Field(default=None, ge=0)
    ask_price: int | None = Field(default=None, ge=0)
    ask_quantity: int | None = Field(default=None, ge=0)
    ask_orders: int | None = Field(default=None, ge=0)


class MarketMessage(ApiModel):
    schema_version: int = 1
    source: str = "TSETMC"
    instrument_id: str
    symbol: str
    asset_type: str
    observed_at: datetime
    exchange_time: str | None = None
    book: list[OrderBookLevel]


class MarketRecord(ApiModel):
    id: int
    redis_message_id: str
    instrument_id: str
    symbol: str
    asset_type: str
    observed_at: datetime
    exchange_time: str | None = None
    best_bid_price: int | None = None
    best_bid_quantity: int | None = None
    best_ask_price: int | None = None
    best_ask_quantity: int | None = None
    book: list[OrderBookLevel]
