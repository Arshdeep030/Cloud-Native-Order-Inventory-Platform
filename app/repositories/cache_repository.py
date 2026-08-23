import json

from app.cache import redis_client


class CacheRepository:

    def get(self, key: str):

        value = redis_client.get(key)

        if value is None:
            return None

        return json.loads(value)

    def set(
        self,
        key: str,
        value,
        expiration: int = 300
    ):

        redis_client.set(
            key,
            json.dumps(value),
            ex=expiration
        )

    def delete(self, key: str):

        redis_client.delete(key)


cache_repository = CacheRepository()
