from pydantic_settings import BaseSettings
from pydantic import Field, AnyUrl


class Settings(BaseSettings):
    bot_token: str = Field(..., env="BOT_TOKEN")
    server_base_url: AnyUrl = Field(..., env="SERVER_BASE_URL")
    db_path: str = Field("/data/db.sqlite", env="DB_PATH")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()