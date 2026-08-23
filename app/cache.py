import redis
from app.config import settings


REDIS_URL = settings.redis_url

redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True
)
