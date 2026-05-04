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
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Minio
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "glowrep-photos"
    MINIO_SECURE: bool = False

    # Web server
    WEB_SERVER_HOST: str = "0.0.0.0"
    WEB_SERVER_PORT: int = 8080

    # Other
    BANNED_WORDS: List[str] = ["badword1", "badword2"]
    NGROK_AUTHTOKEN: str = ""

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Any) -> List[int]:
        """
        Принимаем ADMIN_IDS в любом виде:
        - 5218040142            (int)
        - "5218040142"          (str)
        - "[5218040142]"        (str)
        - [5218040142, ...]     (list)
        """
        if v is None or v == "":
            return []

        if isinstance(v, int):
            return [v]

        if isinstance(v, list):
            return [int(x) for x in v]

        if isinstance(v, str):
            s = v.strip()
            if s.startswith("[") and s.endswith("]"):
                inner = s[1:-1].strip()
                if not inner:
                    return []
                return [int(x.strip()) for x in inner.split(",") if x.strip()]
            # "5218040142" или "5218040142,123"
            if "," in s:
                return [int(x.strip()) for x in s.split(",") if x.strip()]
            return [int(s)]

        # если вдруг прилетело что-то странное
        return []

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
