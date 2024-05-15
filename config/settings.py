from typing import Any, Annotated

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_core import MultiHostUrl
from pydantic import MySQLDsn, computed_field, AnyUrl, BeforeValidator


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    API_PREFIX: str
    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    DB_SCHEME: str
    DB_ADDRESS: str
    DB_PORT: int = 3306
    DB_USER: str
    DB_PASSWORD: str
    DB_DB_NAME: str

    @computed_field  # type: ignore[misc]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> MySQLDsn:
        return MultiHostUrl.build(
            scheme=self.DB_SCHEME,
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_ADDRESS,
            port=self.DB_PORT,
            path=self.DB_DB_NAME,
        )

    REDIS_ADDRESS: str
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_KEY: str


app_settings = Settings()
