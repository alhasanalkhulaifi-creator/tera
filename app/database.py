import os

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be set in the environment (see example.env)")

engine = create_engine(
    DATABASE_URL,
    pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "50")),
    pool_pre_ping=True,
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "1800")),
    connect_args={"application_name": os.getenv("DB_APP_NAME", "tera_api")},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    # create tables from models then ensure desired columns exist
    from app import models  # noqa: F401 (import for table registration)
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    if 'sessions' in inspector.get_table_names():
        col_names = [c['name'] for c in inspector.get_columns('sessions')]
        with engine.begin() as conn:
            if 'profile' not in col_names:
                conn.execute(text("ALTER TABLE sessions ADD COLUMN profile VARCHAR(100)"))
            if 'from_time' not in col_names:
                conn.execute(text("ALTER TABLE sessions ADD COLUMN from_time VARCHAR(100)"))
            if 'created_at' not in col_names:
                conn.execute(text("ALTER TABLE sessions ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT now()"))
            # ensure unique index for deduplication (card + ip + mac + from_time)
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS sessions_unique_idx ON sessions (card, ip, mac, from_time)"))
    # ensure cards table has unique index on code
    if 'cards' in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS cards_code_idx ON cards (code)"))
            col_names = [c['name'] for c in inspector.get_columns('cards')]
            if 'user_id' not in col_names:
                conn.execute(text("ALTER TABLE cards ADD COLUMN user_id INTEGER"))
        # FK add must be its own transaction: failure poisons the txn in PostgreSQL even if caught in Python
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE cards ADD CONSTRAINT cards_user_id_fkey "
                        "FOREIGN KEY (user_id) REFERENCES users (id)"
                    )
                )
        except Exception:
            pass
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS cards_available_category_id_idx "
                    "ON cards (category, id) WHERE status = 'available'"
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS cards_status_idx ON cards (status)"))
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS cards_status_category_id_idx "
                    "ON cards (status, category, id) INCLUDE (code, price)"
                )
            )

    # ensure users table has unique index on phone
    if 'users' in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS users_phone_idx ON users (phone)"))

    # ensure transactions table has audit fields
    if 'transactions' in inspector.get_table_names():
        col_names = [c['name'] for c in inspector.get_columns('transactions')]
        with engine.begin() as conn:
            if 'balance_before' not in col_names:
                conn.execute(text("ALTER TABLE transactions ADD COLUMN balance_before BIGINT DEFAULT 0"))
            if 'balance_after' not in col_names:
                conn.execute(text("ALTER TABLE transactions ADD COLUMN balance_after BIGINT DEFAULT 0"))
            if 'reference_id' not in col_names:
                conn.execute(text("ALTER TABLE transactions ADD COLUMN reference_id VARCHAR(100)"))
            # ensure unique index on reference_id for idempotency
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS transactions_reference_idx ON transactions (reference_id)"))
            if 'status' not in col_names:
                conn.execute(text("ALTER TABLE transactions ADD COLUMN status VARCHAR(20) DEFAULT 'success'"))
            # Assign unique refs to orphan transactions (NULL/empty) without colliding with order references
            conn.execute(
                text(
                    "UPDATE transactions SET reference_id = ('unlinked-tx-' || id::text) "
                    "WHERE reference_id IS NULL OR trim(reference_id) = ''"
                )
            )

    # ensure orders table has unique index if needed
    if 'orders' in inspector.get_table_names():
        with engine.begin() as conn:
            col_names = [c['name'] for c in inspector.get_columns('orders')]
            # ensure columns exist (they're defined in the model, but just in case)
            if not col_names:  # table is empty or corrupted
                pass  # metadata.create_all should have created it
            # add reference_id for idempotent orders
            if 'reference_id' not in col_names:
                conn.execute(text("ALTER TABLE orders ADD COLUMN reference_id VARCHAR(100)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS orders_reference_idx ON orders (reference_id)"))
            # backfill NULL/empty reference_id (legacy rows) so joins and uniqueness checks are meaningful
            conn.execute(
                text(
                    "UPDATE orders SET reference_id = ('legacy-order-' || id::text) "
                    "WHERE reference_id IS NULL OR trim(reference_id) = ''"
                )
            )
    # ensure api_keys table exists and seed a default key if none
    if 'api_keys' in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS api_keys_key_idx ON api_keys (key)"))
            existing = conn.execute(text("SELECT id FROM api_keys LIMIT 1")).fetchone()
            if not existing:
                initial_key = os.getenv("INITIAL_API_KEY")
                if initial_key:
                    conn.execute(
                        text(
                            "INSERT INTO api_keys (key, name, revoked, created_at) "
                            "VALUES (:key, 'default', false, now())"
                        ),
                        {"key": initial_key},
                    )
