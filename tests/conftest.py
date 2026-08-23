import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app

from app.models import Product, Order, OrderItem, User, IdempotencyKey


TEST_DATABASE_URL = (
    "postgresql+psycopg://"
    "order_user:order_password"
    "@localhost:5432/order_test_db"
)


test_engine = create_engine(TEST_DATABASE_URL)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)


@pytest.fixture(scope="session", autouse=True)
def setup_database():

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    yield

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():

    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()


from app.cache import redis_client
from app.messaging.rabbitmq import get_connection


@pytest.fixture(autouse=True)
def clear_cache_and_queues():
    try:
        redis_client.flushdb()
    except Exception:
        pass
    queues_to_purge = [
        "order-created",
        "inventory-results",
        "inventory-reserved",
        "inventory-rejected",
        "payment-inventory-queue",
        "inventory-payment-failed-queue",
    ]
    try:
        conn = get_connection()
        ch = conn.channel()
        for q in queues_to_purge:
            ch.queue_declare(queue=q, durable=True)
            ch.queue_purge(queue=q)
        conn.close()
    except Exception:
        pass
    yield
    try:
        redis_client.flushdb()
    except Exception:
        pass
    try:
        conn = get_connection()
        ch = conn.channel()
        for q in queues_to_purge:
            ch.queue_declare(queue=q, durable=True)
            ch.queue_purge(queue=q)
        conn.close()
    except Exception:
        pass


@pytest.fixture
def client(db_session):

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
