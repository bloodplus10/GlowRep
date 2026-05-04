from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    BOT_TOKEN: str
    WEBHOOK_HOST: str
    WEBHOOK_PATH: str = "/webhook"
    WEBAPP_URL: str
    ADMIN_IDS: str
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "glowrep_user"
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "glowrep_db"
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "glowrep-photos"
    MINIO_SECURE: bool = False
    WEB_SERVER_HOST: str = "0.0.0.0"
    WEB_SERVER_PORT: int = 8080
    BANNED_WORDS: List[str] = ["badword1", "badword2"]
    NGROK_AUTHTOKEN: str = ""
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
settings = Settings()
