from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import aiohttp
import redis.asyncio as redis

from common.config import ROOT_DIR, get_settings
from common.logging import configure_logging
from common.metrics import WorkerAMetrics
from common.schemas import MarketMessage, OrderBookLevel

logger = logging.getLogger("workerA")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"
)


@dataclass(frozen=True, slots=True)
class AssetConfig:
    symbol: str
    asset_type: str


@dataclass(frozen=True, slots=True)
class Instrument:
    symbol: str
    asset_type: str
    instrument_id: str


def load_assets() -> list[AssetConfig]:
    raw = json.loads((ROOT_DIR / "config" / "assets.json").read_text(encoding="utf-8"))
    assets = [AssetConfig(symbol=item["symbol"], asset_type=item["assetType"]) for item in raw]
    if len(assets) < 10:
        raise RuntimeError("WorkerA requires at least 10 configured assets")
    return assets


def _int_or_none(value) -> int | None:
    if value in (None, "", "-"):
        return None
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return None


def normalize_best_limits(rows: list[dict], state: dict[int, OrderBookLevel]) -> tuple[list[OrderBookLevel], str | None]:
    """Apply TSETMC BestLimits rows to a small in-memory order-book state.

    Some TSETMC feeds behave like updates/deltas. Keeping the latest value by level
    prevents a partial response from wiping levels that were not changed.
    """
    exchange_time = None
    for row in rows:
        level = _int_or_none(row.get("number"))
        if level is None or not 1 <= level <= 10:
            continue
        previous = state.get(level, OrderBookLevel(level=level))

        data = previous.model_dump(by_alias=False)

        updates = {
            "bid_price": _int_or_none(row.get("pMeDem")),
            "bid_quantity": _int_or_none(row.get("qTitMeDem")),
            "bid_orders": _int_or_none(row.get("zOrdMeDem")),
            "ask_price": _int_or_none(row.get("pMeOf")),
            "ask_quantity": _int_or_none(row.get("qTitMeOf")),
            "ask_orders": _int_or_none(row.get("zOrdMeOf")),
        }
        for key, value in updates.items():
            if value is not None:
                data[key] = value
        state[level] = OrderBookLevel(**data)
        if row.get("hEven") not in (None, "", 0, "0"):
            exchange_time = str(row["hEven"])
    return [state[key] for key in sorted(state)], exchange_time


class TsetmcClient:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session
        self.settings = get_settings()

    async def _get_json(self, path: str) -> dict:
        url = f"{self.settings.tsetmc_base_url.rstrip('/')}/{path.lstrip('/')}"
        async with self.session.get(
            url,
            proxy=self.settings.tsetmc_proxy_url or None,
            timeout=aiohttp.ClientTimeout(total=self.settings.tsetmc_timeout_seconds),
        ) as response:
            response.raise_for_status()
            return await response.json(content_type=None)

    async def resolve(self, asset: AssetConfig) -> Instrument:
        payload = await self._get_json(f"Instrument/GetInstrumentSearch/{quote(asset.symbol)}")
        candidates = payload.get("instrumentSearch") or []
        if not candidates:
            raise LookupError(f"TSETMC returned no instrument for {asset.symbol!r}")

        exact = [item for item in candidates if str(item.get("lVal18AFC", "")).strip() == asset.symbol]
        pool = exact or candidates
        if asset.asset_type == "etf":
            preferred = [item for item in pool if int(item.get("flow") or 0) == 18]
            if preferred:
                pool = preferred
        else:
            preferred = [item for item in pool if str(item.get("yVal") or "") == "300"]
            if preferred:
                pool = preferred

        item = pool[0]
        instrument_id = str(item.get("insCode") or "")
        if not instrument_id.isdigit():
            raise ValueError(f"Invalid insCode for {asset.symbol!r}: {instrument_id!r}")
        return Instrument(asset.symbol, asset.asset_type, instrument_id)

    async def best_limits(self, instrument: Instrument) -> list[dict]:
        payload = await self._get_json(f"BestLimits/{instrument.instrument_id}")
        rows = payload.get("bestLimits") or []
        if not isinstance(rows, list):
            raise ValueError("Unexpected TSETMC BestLimits response")
        return rows


class WorkerA:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.assets = load_assets()
        self.redis = redis.Redis.from_url(self.settings.redis_url, decode_responses=True)
        self.book_state: dict[str, dict[int, OrderBookLevel]] = {}
        self._mock_tick = 0
        self.metrics = WorkerAMetrics()

    async def _publish_many(self, messages: list[MarketMessage]) -> None:
        if not messages:
            return
        pipe = self.redis.pipeline(transaction=True)
        for message in messages:
            data = message.model_dump_json(by_alias=True)
            pipe.publish(self.settings.redis_channel, data)
            pipe.xadd(self.settings.redis_stream, {"data": data})
        await pipe.execute()
        self.metrics.published_messages.inc(len(messages))
        self.metrics.last_publish_unixtime.set(time.time())

    async def _resolve_all(self, client: TsetmcClient) -> list[Instrument]:
        delay = 1.0
        while True:
            try:
                instruments = await asyncio.gather(*(client.resolve(asset) for asset in self.assets))
                logger.info("resolved %d TSETMC instruments", len(instruments))
                self.metrics.resolved_instruments.set(len(instruments))
                return list(instruments)
            except (aiohttp.ClientError, asyncio.TimeoutError, LookupError, ValueError) as exc:
                logger.error("instrument resolution failed type=%s error=%r; retrying in %.1fs",type(exc).__name__,exc,delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)

    async def _fetch_message(self, client: TsetmcClient, instrument: Instrument) -> MarketMessage | None:
        try:
            rows = await client.best_limits(instrument)
            levels, exchange_time = normalize_best_limits(
                rows,
                self.book_state.setdefault(instrument.instrument_id, {}),
            )
            if not levels:
                logger.warning("empty order book for %s", instrument.symbol)
                return None
            return MarketMessage(
                instrument_id=instrument.instrument_id,
                symbol=instrument.symbol,
                asset_type=instrument.asset_type,
                observed_at=datetime.now(timezone.utc),
                exchange_time=exchange_time,
                book=levels,
            )
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            self.metrics.fetch_failures.inc()
            logger.warning("TSETMC fetch failed for %s type=%s error=%r",instrument.symbol,type(exc).__name__,exc,)
            return None

    def _mock_messages(self) -> list[MarketMessage]:
        self._mock_tick += 1
        now = datetime.now(timezone.utc)
        messages = []
        for index, asset in enumerate(self.assets, start=1):
            instrument_id = f"9000000000000{index:02d}"
            base = 10_000 + index * 1_000 + self._mock_tick % 100
            rng = random.Random(index * 1_000_000 + self._mock_tick)
            levels = [
                OrderBookLevel(
                    level=level,
                    bid_price=base - level * 10,
                    bid_quantity=rng.randint(100, 10_000),
                    bid_orders=rng.randint(1, 50),
                    ask_price=base + level * 10,
                    ask_quantity=rng.randint(100, 10_000),
                    ask_orders=rng.randint(1, 50),
                )
                for level in range(1, 6)
            ]
            messages.append(
                MarketMessage(
                    source="mock-tsetmc",
                    instrument_id=instrument_id,
                    symbol=asset.symbol,
                    asset_type=asset.asset_type,
                    observed_at=now,
                    exchange_time=now.strftime("%H%M%S"),
                    book=levels,
                )
            )
        return messages

    async def run(self) -> None:
        self.metrics.start()
        logger.info("WorkerA Prometheus metrics listening on :9101")
        interval = self.settings.tsetmc_poll_interval_ms / 1000
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Referer": "https://www.tsetmc.com/",
            "Origin": "https://www.tsetmc.com",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            client = TsetmcClient(session)
            instruments = [] if self.settings.tsetmc_mock else await self._resolve_all(client)
            tick = 0
            while True:
                started = time.monotonic()
                messages = (
                    self._mock_messages()
                    if self.settings.tsetmc_mock
                    else [
                        message
                        for message in await asyncio.gather(
                            *(self._fetch_message(client, instrument) for instrument in instruments)
                        )
                        if message is not None
                    ]
                )
                try:
                    await self._publish_many(messages)
                except redis.RedisError as exc:
                    self.metrics.redis_publish_errors.inc()
                    logger.error("Redis publish batch failed: %s", exc)

                self.metrics.batch_size.set(len(messages))
                self.metrics.cycle_duration_seconds.observe(time.monotonic() - started)
                tick += 1
                if tick % 100 == 0:
                    logger.info("heartbeat tick=%d published=%d", tick, len(messages))
                await asyncio.sleep(max(0.0, interval - (time.monotonic() - started)))


async def main() -> None:
    configure_logging()
    worker = WorkerA()
    try:
        await worker.run()
    finally:
        await worker.redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
