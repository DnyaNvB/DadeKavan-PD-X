from __future__ import annotations

import asyncio
import logging
from datetime import timezone

import redis.asyncio as redis
from redis.exceptions import ResponseError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from common.config import get_settings
from common.db import Base, get_engine, get_session_factory
from common.logging import configure_logging
from common.models import RTDS
from common.schemas import MarketMessage

logger = logging.getLogger("workerB")


class WorkerB:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.redis = redis.Redis.from_url(self.settings.redis_url, decode_responses=True)
        self.sessions = get_session_factory()

    async def initialize(self) -> None:
        async with get_engine().begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        try:
            await self.redis.xgroup_create(
                self.settings.redis_stream,
                self.settings.redis_consumer_group,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def _persist(self, redis_id: str, raw: str) -> bool:
        try:
            message = MarketMessage.model_validate_json(raw)
            observed = message.observed_at
            if observed.tzinfo is not None:
                observed = observed.astimezone(timezone.utc).replace(tzinfo=None)
            top = message.book[0] if message.book else None

            async with self.sessions() as session:
                async with session.begin():
                    existing = await session.scalar(
                        select(RTDS.id).where(RTDS.redis_message_id == redis_id)
                    )
                    if existing is None:
                        session.add(
                            RTDS(
                                redis_message_id=redis_id,
                                instrument_id=message.instrument_id,
                                symbol=message.symbol,
                                asset_type=message.asset_type,
                                observed_at=observed,
                                exchange_time=message.exchange_time,
                                best_bid_price=top.bid_price if top else None,
                                best_bid_quantity=top.bid_quantity if top else None,
                                best_ask_price=top.ask_price if top else None,
                                best_ask_quantity=top.ask_quantity if top else None,
                                book=[level.model_dump(by_alias=True) for level in message.book],
                            )
                        )
            return True
        except (SQLAlchemyError, ValueError) as exc:
            logger.exception("failed to store Redis message %s: %s", redis_id, exc)
            return False

    async def _consume(self, start_id: str) -> tuple[int, int]:
        response = await self.redis.xreadgroup(
            groupname=self.settings.redis_consumer_group,
            consumername=self.settings.redis_consumer_name,
            streams={self.settings.redis_stream: start_id},
            count=self.settings.worker_b_batch_size,
            block=self.settings.worker_b_block_ms if start_id == ">" else 1,
        )
        stored = 0
        failed = 0
        for _, entries in response:
            for redis_id, fields in entries:
                raw = fields.get("data")
                if raw is None:
                    logger.error("stream message %s has no data field; leaving unacked", redis_id)
                    failed += 1
                    continue
                if await self._persist(redis_id, raw):
                    await self.redis.xack(
                        self.settings.redis_stream,
                        self.settings.redis_consumer_group,
                        redis_id,
                    )
                    stored += 1
                else:
                    failed += 1
        return stored, failed

    async def run(self) -> None:
        await self.initialize()
        logger.info("WorkerB initialized; pending messages are retried before new messages")
        total = 0
        while True:
            try:
                pending_stored, pending_failed = await self._consume("0")
                total += pending_stored
                if pending_failed:
                    await asyncio.sleep(1)
                    continue

                new_stored, new_failed = await self._consume(">")
                total += new_stored
                if new_failed:
                    await asyncio.sleep(1)
                if total and total % 1000 == 0:
                    logger.info("stored %d messages", total)
            except (redis.RedisError, SQLAlchemyError) as exc:
                logger.exception("WorkerB loop error: %s", exc)
                await asyncio.sleep(1)


async def main() -> None:
    configure_logging()
    worker = WorkerB()
    try:
        await worker.run()
    finally:
        await worker.redis.aclose()
        await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(main())
