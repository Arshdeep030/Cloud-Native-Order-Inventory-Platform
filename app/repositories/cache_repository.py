import json
import logging

from app.cache import redis_client

logger = logging.getLogger("cloud-order-platform.cache")


class CacheRepository:

    def get(self, key: str):
        try:
            value = redis_client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            logger.warning(f"Redis cache get failed for key {key}: {e}")
            return None

    def set(
        self,
        key: str,
        value,
        expiration: int = 300
    ):
        try:
            redis_client.set(
                key,
                json.dumps(value),
                ex=expiration
            )
        except Exception as e:
            logger.warning(f"Redis cache set failed for key {key}: {e}")

    def delete(self, key: str):
        try:
            redis_client.delete(key)
        except Exception as e:
            logger.warning(f"Redis cache delete failed for key {key}: {e}")


cache_repository = CacheRepository()
