from fastapi import Depends
from typing import Annotated
from sqlmodel import Session
from redis import Redis

from config.db import get_db
from config.redis_config import get_redis

DbSessionDeps = Annotated[Session, Depends(get_db)]
RedisSessionDeps = Annotated[Redis, Depends(get_redis)]
