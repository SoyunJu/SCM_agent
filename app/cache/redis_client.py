import json
import redis as redis_lib
from loguru import logger
from app.config import settings

_client: redis_lib.Redis | None = None


def get_redis() -> redis_lib.Redis:
    global _client
    if _client is None:
        _client = redis_lib.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=0,
            decode_responses=True,
            socket_connect_timeout=3,
        )
        _client.ping()
        logger.info(f"Redis 연결 성공: {settings.redis_host}:{settings.redis_port}")
    return _client


def cache_get(key: str):
    try:
        val = get_redis().get(key)
        if val:
            return json.loads(val)
    except Exception as e:
        logger.debug(f"Redis GET 실패 ({key}): {e}")
    return None


def cache_set(key: str, value, ttl: int = 300) -> None:
    try:
        get_redis().setex(key, ttl, json.dumps(value, ensure_ascii=False, default=str))
    except Exception as e:
        logger.debug(f"Redis SET 실패 ({key}): {e}")


def cache_delete(key: str) -> None:
    try:
        get_redis().delete(key)
    except Exception as e:
        logger.debug(f"Redis DELETE 실패 ({key}): {e}")
