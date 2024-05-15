import redis
from config.settings import app_settings


def create_redis():
    return redis.ConnectionPool(
        host=app_settings.REDIS_ADDRESS,
        port=app_settings.REDIS_PORT,
        db=app_settings.REDIS_DB,
    )


pool = create_redis()


def get_redis():
    return redis.Redis(connection_pool=pool)
