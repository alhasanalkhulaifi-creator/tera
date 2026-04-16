import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.schemas import CardBuyIn

from .conftest import FakeRedis


def _as_json(response):
    if isinstance(response, JSONResponse):
        return response.status_code, json.loads(response.body.decode())
    return 200, response


def test_redis_on_uses_redis_rate_limiter(isolated_app, fake_redis, seeded_wallet_and_cards, caplog):
    fake = fake_redis(FakeRedis())
    seeded_wallet_and_cards(
        category="redis-on-cat",
        phone="redis-on-user",
        codes=["redis-on-card-1", "redis-on-card-2"],
    )

    response = isolated_app.client.post(
        "/cards/buy",
        headers=isolated_app.headers,
        json={
            "category": "redis-on-cat",
            "user_phone": "redis-on-user",
            "order_reference": "redis-on-order-1",
        },
    )

    assert response.status_code == 200
    assert any(call[0] == "incrby" and str(call[1]).startswith("rate:redis-on-user:") for call in fake.calls)
    assert any(call[0] == "expire" and call[1].startswith("rate:redis-on-user:") for call in fake.calls)


def test_redis_off_fallback_is_fast(isolated_app, fake_redis, seeded_wallet_and_cards, caplog):
    fake = fake_redis(FakeRedis(fail_on_rate=True))
    seeded_wallet_and_cards(
        category="redis-off-cat",
        phone="redis-off-user",
        codes=["redis-off-card-1", "redis-off-card-2"],
    )
    fake.pipeline_created_count = 0
    fake.pipeline_execute_count = 0

    started_at = time.perf_counter()
    response = isolated_app.client.post(
        "/cards/buy",
        headers=isolated_app.headers,
        json={
            "category": "redis-off-cat",
            "user_phone": "redis-off-user",
            "order_reference": "redis-off-order-1",
        },
    )
    elapsed = time.perf_counter() - started_at

    assert response.status_code == 200
    assert elapsed < 0.5
    assert any("Redis failed -> fallback in-memory" in record.message for record in caplog.records)
    # Rate limit uses a pipeline; incr fails before execute when Redis is down for rate keys
    assert fake.pipeline_created_count == 1


def test_circuit_breaker_skips_redis_after_first_failure(isolated_app, fake_redis, seeded_wallet_and_cards):
    fake = fake_redis(FakeRedis(fail_on_rate=True))
    seeded_wallet_and_cards(
        category="redis-cb-cat",
        phone="redis-cb-user",
        codes=["redis-cb-card-1", "redis-cb-card-2", "redis-cb-card-3"],
    )

    first = isolated_app.client.post(
        "/cards/buy",
        headers=isolated_app.headers,
        json={
            "category": "redis-cb-cat",
            "user_phone": "redis-cb-user",
            "order_reference": "redis-cb-order-1",
        },
    )
    first_incr_calls = len([call for call in fake.calls if call[0] == "incrby" and call[1].startswith("rate:")])

    started_at = time.perf_counter()
    second = isolated_app.client.post(
        "/cards/buy",
        headers=isolated_app.headers,
        json={
            "category": "redis-cb-cat",
            "user_phone": "redis-cb-user",
            "order_reference": "redis-cb-order-2",
        },
    )
    second_elapsed = time.perf_counter() - started_at
    second_incr_calls = len([call for call in fake.calls if call[0] == "incrby" and call[1].startswith("rate:")])

    assert first.status_code == 200
    assert second.status_code == 200
    assert isolated_app.redis_module.redis_circuit_remaining() > 0
    assert first_incr_calls == 1
    assert second_incr_calls == 1
    assert second_elapsed < 0.5


def test_no_duplicate_charge_under_concurrency(isolated_app, monkeypatch, seeded_wallet_and_cards):
    monkeypatch.setattr(isolated_app.redis_module, "redis_client", None)
    monkeypatch.setattr(isolated_app.cards, "redis_client", None)
    monkeypatch.setattr(isolated_app.app_main, "redis_client", None)
    isolated_app.cards._rate_data.clear()

    seeded_wallet_and_cards(
        category="redis-concurrency-cat",
        phone="redis-concurrency-user",
        codes=["redis-concurrency-card-1"],
        amount=10,
    )

    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        payload = CardBuyIn(
            category="redis-concurrency-cat",
            user_phone="redis-concurrency-user",
            order_reference="redis-concurrency-order-1",
        )
        return _as_json(isolated_app.cards.buy_card(payload))

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: worker(), range(8)))

    status_codes = [status for status, _ in results]
    assert any(status == 200 for status in status_codes)

    with isolated_app.engine.connect() as conn:
        balance = conn.execute(
            text("SELECT balance FROM users WHERE phone = :phone"),
            {"phone": "redis-concurrency-user"},
        ).scalar_one()
        purchase_count = conn.execute(
            text(
                "SELECT COUNT(*) FROM transactions "
                "WHERE reference_id = :ref AND type = 'purchase' AND status = 'success'"
            ),
            {"ref": "redis-concurrency-order-1"},
        ).scalar_one()
        order_count = conn.execute(
            text("SELECT COUNT(*) FROM orders WHERE reference_id = :ref"),
            {"ref": "redis-concurrency-order-1"},
        ).scalar_one()
        sold_cards = conn.execute(
            text("SELECT COUNT(*) FROM cards WHERE category = :category AND status = 'sold'"),
            {"category": "redis-concurrency-cat"},
        ).scalar_one()

    assert balance == 9
    assert purchase_count == 1
    assert order_count == 1
    assert sold_cards == 1
