from datetime import datetime

from sqlalchemy import BigInteger, Index, JSON, String, func
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from common.db import Base


class RTDS(Base):
    __tablename__ = "RTDS"
    __table_args__ = (
        Index("ixRTDSInstrumentObserved", "instrumentId", "observedAt"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    redis_message_id: Mapped[str] = mapped_column(
        "redisMessageId", String(32), unique=True, nullable=False
    )
    instrument_id: Mapped[str] = mapped_column("instrumentId", String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_type: Mapped[str] = mapped_column("assetType", String(32), nullable=False)
    observed_at: Mapped[datetime] = mapped_column("observedAt", DATETIME(fsp=6), nullable=False)
    exchange_time: Mapped[str | None] = mapped_column("exchangeTime", String(16))
    best_bid_price: Mapped[int | None] = mapped_column("bestBidPrice", BigInteger)
    best_bid_quantity: Mapped[int | None] = mapped_column("bestBidQuantity", BigInteger)
    best_ask_price: Mapped[int | None] = mapped_column("bestAskPrice", BigInteger)
    best_ask_quantity: Mapped[int | None] = mapped_column("bestAskQuantity", BigInteger)
    book: Mapped[list[dict]] = mapped_column("book", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DATETIME(fsp=6), nullable=False, server_default=func.now(6)
    )
