import os
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


BASE_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
if not BASE_DATABASE_URL:
    raise RuntimeError("Set TEST_DATABASE_URL or DATABASE_URL for pytest (see example.env)")

if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = BASE_DATABASE_URL

TEST_API_KEY = os.getenv("TEST_API_KEY", "pytest-local-api-key")


class FakePipeline:
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.commands = []

    def incr(self, key):
        self.commands.append(("incr", key))
        val = self.redis_client.incrby(key, 1)
        return self

    def incrby(self, key, amount):
        self.commands.append(("incrby", key, amount))
        self.redis_client.incrby(key, amount)
        return self

    def expire(self, key, ttl):
        self.commands.append(("expire", key, ttl))
        self.redis_client.calls.append(("expire", key, ttl))
        return self

    def execute(self):
        self.redis_client.pipeline_execute_count += 1
        results = []
        for cmd in self.commands:
            if cmd[0] == "incr":
                results.append(self.redis_client.values.get(cmd[1], 0))
            elif cmd[0] == "expire":
                results.append(True)
            elif cmd[0] == "incrby":
                results.append(self.redis_client.values.get(cmd[1], 0))
        return results


class FakeRedis:
    def __init__(self, *, fail_on_rate=False):
        self.fail_on_rate = fail_on_rate
        self.calls = []
        self.values = {}
        self.pipeline_created_count = 0
        self.pipeline_execute_count = 0

    def incr(self, key):
        return self.incrby(key, 1)

    def incrby(self, key, amount):
        self.calls.append(("incrby", key, amount))
        if self.fail_on_rate and key.startswith("rate:"):
            raise ConnectionError("redis down")
        self.values[key] = int(self.values.get(key, 0)) + amount
        return self.values[key]

    def expire(self, key, ttl):
        self.calls.append(("expire", key, ttl))
        return True

    def get(self, key):
        self.calls.append(("get", key))
        return self.values.get(key)

    def ping(self):
        self.calls.append(("ping",))
        if self.fail_on_rate:
            raise ConnectionError("redis down")
        return True

    def pipeline(self):
        self.pipeline_created_count += 1
        return FakePipeline(self)


@pytest.fixture
def isolated_app(monkeypatch):
    monkeypatch.setenv("INITIAL_API_KEY", TEST_API_KEY)
    import app.cards as cards
    import app.database as app_database
    import app.main as app_main
    import app.redis_client as redis_client_module
    import app.wallet as wallet
    from fastapi.testclient import TestClient

    schema = f"pytest_{uuid.uuid4().hex[:8]}"
    admin_engine = create_engine(BASE_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))

    test_engine = create_engine(
        BASE_DATABASE_URL,
        connect_args={"options": f"-csearch_path={schema}"},
        pool_size=5,
        max_overflow=10,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    monkeypatch.setattr(app_database, "engine", test_engine)
    monkeypatch.setattr(app_database, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(cards, "engine", test_engine)
    monkeypatch.setattr(cards, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(wallet, "engine", test_engine)
    monkeypatch.setattr(app_main, "engine", test_engine)
    monkeypatch.setattr(app_main, "SessionLocal", TestingSessionLocal)

    monkeypatch.setattr(redis_client_module, "_redis_circuit_open_until", 0.0)
    redis_client_module.reset_request_redis_state()
    cards._rate_data.clear()

    app_database.init_db()

    client = TestClient(app_main.app)
    try:
        yield SimpleNamespace(
            client=client,
            schema=schema,
            engine=test_engine,
            session_local=TestingSessionLocal,
            cards=cards,
            app_main=app_main,
            redis_module=redis_client_module,
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )
    finally:
        client.close()
        test_engine.dispose()
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def fake_redis(monkeypatch, isolated_app):
    def _apply(fake):
        monkeypatch.setattr(isolated_app.redis_module, "redis_client", fake)
        monkeypatch.setattr(isolated_app.cards, "redis_client", fake)
        monkeypatch.setattr(isolated_app.app_main, "redis_client", fake)
        monkeypatch.setattr(isolated_app.redis_module, "_redis_circuit_open_until", 0.0)
        isolated_app.redis_module.reset_request_redis_state()
        isolated_app.cards._rate_data.clear()
        return fake

    return _apply


@pytest.fixture
def seeded_wallet_and_cards(isolated_app):
    def _seed(*, category, phone, codes, amount=20):
        import_response = isolated_app.client.post(
            "/cards/import",
            headers=isolated_app.headers,
            json={"codes": list(codes), "category": category, "price": 1},
        )
        assert import_response.status_code == 200

        deposit_response = isolated_app.client.post(
            "/wallet/deposit",
            headers=isolated_app.headers,
            json={"phone": phone, "amount": amount, "reference_id": f"{phone}-deposit"},
        )
        assert deposit_response.status_code == 200

    return _seed

