from datetime import datetime, timezone

from common.schemas import MarketMessage, OrderBookLevel


def test_market_message_serializes_camel_case():
    message = MarketMessage(
        instrument_id="1",
        symbol="TEST",
        asset_type="stock",
        observed_at=datetime.now(timezone.utc),
        book=[OrderBookLevel(level=1, bid_price=10, ask_price=11)],
    )
    payload = message.model_dump(by_alias=True)
    assert payload["instrumentId"] == "1"
    assert payload["assetType"] == "stock"
    assert payload["book"][0]["bidPrice"] == 10
