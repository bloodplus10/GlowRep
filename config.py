from typing import List, Any
from pydantic_settings import BaseSettings
from pydantic import field_validator

class Settings(BaseSettings):
    # Telegram / Webhook / WebApp
    BOT_TOKEN: str
    WEBHOOK_HOST: str
    WEBHOOK_PATH: str = "/webhook"
    WEBAPP_URL: str

    # Admins
    ADMIN_IDS: List[int] = []

    # Postgres
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "glowrep_user"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "glowrep_db"

    # Redis
    REDIS_HOST: str =
