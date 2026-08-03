import json
from redis.asyncio import Redis
from .config import settings

QUEUE_NAME = "incoming_messages"
_redis: Redis | None = None


async def redis_client() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def enqueue(payload: dict) -> None:
    client = await redis_client()
    await client.lpush(QUEUE_NAME, json.dumps(payload))

